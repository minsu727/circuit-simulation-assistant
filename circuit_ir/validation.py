"""M1E intermediate deterministic structural report, not the full M1 validator.

Follow prompt-breakdown.md: source/value/device/DC/ambiguity/confidence/provenance
rules belong to M1F. Structural checks run now, with explicit skipped reasons.
ERROR -> INVALID; otherwise known AMBIGUOUS -> AMBIGUOUS; otherwise UNVALIDATED
until the unimplemented M1F stages exist. This is not successful final validation
and never returns VALID, changes an imported snapshot or grants human approval.
The only resource read is the existing lazy, bundled M1C schema; no asset/model,
user filesystem, environment, simulator or external service is consulted.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from . import models as m
from .graph import build_graph, _issue, _report, _with_provenance


_STRUCTURAL_STAGES = ("schema", "ids", "references", "incidence", "pins", "ground", "labels")
_LATER_STAGES = ("component_value_source", "graph_dc", "ambiguity_confidence_provenance")
_DEFERRED = ("m1f_component_value_source", "m1f_graph_dc",
             "m1f_ambiguity_confidence_provenance", "model_catalog_resolution",
             "image_asset_resolution", "full_export_readiness", "human_approval")


def _finding(code, severity, targets, kind, identity, field, message):
    # Reuse M1D's semantic selectors/issue record rather than a parallel diagnosis.
    return replace(_issue(code, targets, kind, identity, field, message), severity=severity)


def _expected_roles(component_type):
    passive = (m.PinRole.A, m.PinRole.B)
    source = (m.PinRole.POSITIVE, m.PinRole.NEGATIVE)
    mos = (m.PinRole.DRAIN, m.PinRole.GATE, m.PinRole.SOURCE, m.PinRole.BULK)
    return {
        m.ComponentType.RESISTOR: passive, m.ComponentType.CAPACITOR: passive,
        m.ComponentType.INDUCTOR: passive, m.ComponentType.VOLTAGE_SOURCE: source,
        m.ComponentType.CURRENT_SOURCE: source, m.ComponentType.NMOS: mos,
        m.ComponentType.PMOS: mos,
    }.get(component_type)


def _pins(graph):
    issues, skipped = [], []
    if not graph.component_by_id:
        issues.append(_finding("ORPHAN_DEVICE", m.IssueSeverity.ERROR, (), "document", None,
                               "components", "Document contains no devices."))
    for identity, component in graph.component_by_id.items():
        expected = _expected_roles(component.type)
        if expected is None:
            skipped.append((f"component[{identity}].pins", "type_unknown_deferred_to_m1f"))
            continue
        pin_ids = graph.pins_for_component(identity)
        if not pin_ids:
            issues.append(_finding("ORPHAN_DEVICE", m.IssueSeverity.ERROR, (identity,),
                                   "component", identity, "pins", "Device has no owned pins."))
            skipped.append((f"component[{identity}].pin_roles", "orphan_device"))
            continue
        roles = tuple(graph.pin_by_id[pin].role for pin in pin_ids)
        known = tuple(role for role in roles if role is not m.PinRole.UNKNOWN)
        contradiction = (len(roles) != len(expected) or len(known) != len(set(known))
                         or not set(known).issubset(expected))
        if contradiction or m.PinRole.UNKNOWN in roles:
            severity = m.IssueSeverity.ERROR if contradiction else m.IssueSeverity.AMBIGUOUS
            issues.append(_finding("PIN_ROLES_INVALID", severity, (identity, *pin_ids),
                                   "component", identity, "pin_roles",
                                   "Pin roles/count contradict the device contract." if contradiction
                                   else "Pin role mapping is unresolved."))
            skipped.append((f"component[{identity}].missing_incidence", "pin_roles_invalid"))
        connected = tuple(pin for pin in pin_ids if graph.net_for_pin(pin) is not None)
        if not connected:
            issues.append(_finding("ORPHAN_DEVICE", m.IssueSeverity.ERROR, (identity,),
                                   "component", identity, "connections",
                                   "Device has no connected terminals."))
            continue
        if contradiction or m.PinRole.UNKNOWN in roles:
            continue
        for pin in pin_ids:
            if graph.net_for_pin(pin) is None:
                if (component.type in (m.ComponentType.NMOS, m.ComponentType.PMOS)
                        and graph.pin_by_id[pin].role is m.PinRole.BULK):
                    # M1F will emit MOS_BODY_UNRESOLVED, not a duplicate generic
                    # PIN_NET_INVALID for that same missing bulk incidence.
                    skipped.append((f"pin[{pin}].incidence", "mos_bulk_deferred_to_m1f"))
                else:
                    issues.append(_finding("PIN_NET_INVALID", m.IssueSeverity.AMBIGUOUS,
                                           (identity, pin), "pin", pin, "connection",
                                           "Pin has no explicit net connection."))
    return issues, skipped


def _ground(graph):
    ground_ids = tuple(identity for identity, net in graph.net_by_id.items() if net.is_ground)
    if len(ground_ids) == 1:
        return []
    return [_finding("GROUND_MISSING", m.IssueSeverity.ERROR, ground_ids, "document", None,
                     "is_ground", "Exactly one explicit ground net is required.")]


def _label_identity(text):
    # ASCII case folding only; original spelling and non-ASCII identity survive.
    return "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char for char in text.strip())


def _labels(document, graph):
    issues, by_name = [], defaultdict(list)
    for label in document.labels:
        name = _label_identity(label.text)
        if not name:
            issues.append(_finding("LABEL_CONFLICT", m.IssueSeverity.ERROR, (label.id,),
                                   "label", label.id, "text", "Label text contains only whitespace."))
        if label.net_id is None:
            issues.append(_finding("LABEL_UNRESOLVED", m.IssueSeverity.AMBIGUOUS, (label.id,),
                                   "label", label.id, "net_id", "Label has no confirmed net attachment."))
            continue
        if not name:
            continue
        # Only node 0 is explicitly reserved by the committed contract. Do not
        # invent GND/VSS aliases or create ground from any text/visual position.
        if name == "0" and not graph.net_by_id[label.net_id].is_ground:
            issues.append(_finding("LABEL_CONFLICT", m.IssueSeverity.ERROR,
                                   (label.id, label.net_id), "label", label.id, "text",
                                   "Reserved ground label 0 is attached to a non-ground net."))
            continue
        by_name[name].append(label)
    by_net = defaultdict(list)
    for name, labels in sorted(by_name.items()):
        net_ids = {label.net_id for label in labels}
        if len(net_ids) > 1:
            issues.append(_finding("LABEL_CONFLICT", m.IssueSeverity.ERROR,
                                   tuple(label.id for label in labels) + tuple(net_ids),
                                   "label_group", None, "text",
                                   "Same normalized label is attached to separate nets."))
            continue  # Conflicting attachments cannot establish harmless aliases.
        by_net[labels[0].net_id].append((name, tuple(label.id for label in labels)))
    for net_id, entries in sorted(by_net.items()):
        if len(entries) > 1:
            targets = (net_id,) + tuple(identity for name, ids in entries for identity in ids)
            issues.append(_finding("LABEL_ALIAS", m.IssueSeverity.WARNING, targets, "net", net_id,
                                   "labels", "Different labels share one net; alias review is required."))
    return issues


def _result(document, issues, completed, skipped):
    issues = _report(issues)
    if any(issue.severity is m.IssueSeverity.ERROR for issue in issues):
        state = m.TechnicalState.INVALID
    elif any(issue.severity is m.IssueSeverity.AMBIGUOUS for issue in issues):
        state = m.TechnicalState.AMBIGUOUS
    else:
        # The structural subset is checked, but planned M1F stages are not.
        state = m.TechnicalState.UNVALIDATED
    return m.ValidationResult("m1-local-v1", "m1-local-v1", document.metadata.revision,
                              state, issues, tuple(completed) + ("result",),
                              tuple(sorted(set(skipped))), _DEFERRED)


def validate_document(document: m.CircuitDocument) -> m.ValidationResult:
    """Fresh immutable M1E report; success of this subset is not full M1 VALID.

    Stage names expose schema/IDs/references/incidence reuse, then the pin and
    ground/label substeps of the committed pipeline. Later stages are explicitly
    skipped with reasons. No source/status mutation or inferred connectivity.
    Wrong API input raises TypeError, as in build_graph.
    """
    graph_result = build_graph(document)
    if graph_result.graph is None:
        code = graph_result.issues[0].code
        index = {"SCHEMA_INVALID": 0, "DUPLICATE_ID": 1,
                 "BROKEN_REFERENCE": 2, "PIN_NET_INVALID": 3}[code]
        completed = _STRUCTURAL_STAGES[:index + 1]
        skipped = tuple((stage, f"blocked_by_{code.lower()}")
                        for stage in _STRUCTURAL_STAGES[index + 1:] + _LATER_STAGES)
        return _result(document, graph_result.issues, completed, skipped)
    graph = graph_result.graph
    issues, skipped = _pins(graph)
    ground_issues = _ground(graph)
    issues.extend(ground_issues)
    issues.extend(_labels(document, graph))
    skipped.extend((stage, "blocked_by_ground_missing" if stage == "graph_dc" and ground_issues
                    else "not_implemented_m1f") for stage in _LATER_STAGES)
    return _result(document, _with_provenance(issues, document), _STRUCTURAL_STAGES, skipped)
