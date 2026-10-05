"""Deterministic m1-local-v1 validation of explicit Circuit IR records.

VALID is local contract consistency, not human approval, model resolution,
simulator readiness, a proven operating point or good analog design. Required
stage completion is checked independently of severity. Catalog/assets/calibration
and full export readiness remain explicitly scoped out, never CONFIRMED.
The only resource read is the existing lazy, bundled M1C schema; no asset/model,
user filesystem, environment, simulator or external service is consulted.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from . import models as m
from .graph import build_graph, _issue, _report, _with_provenance
from .value_parser import parse_quantity


_STRUCTURAL_STAGES = ("schema", "ids", "references", "incidence", "pins", "ground", "labels")
_LATER_STAGES = ("component_value_source", "graph_dc", "ambiguity_confidence_provenance")
_REQUIRED_STAGES = _STRUCTURAL_STAGES + _LATER_STAGES
_DEFERRED = ("model_catalog_resolution", "image_asset_resolution",
             "inference_calibration", "full_export_readiness", "human_approval")


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
            skipped.append((f"component[{identity}].pins", "type_unknown"))
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
                    # The device stage emits the specific body issue once.
                    continue
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


def _quantity(value, unit, component_id, field, *, code="VALUE_INVALID",
              sign=None, missing=m.IssueSeverity.ERROR, pending=False):
    """Return exact bounded SI data and one root finding, never a repaired value."""
    def failure(severity, message, issue_code=code):
        return None, [_finding(issue_code, severity, (component_id,), "component",
                               component_id, field, message)]
    if value is None:
        return failure(m.IssueSeverity.AMBIGUOUS if pending else missing,
                       "Required scalar quantity is missing.")
    if value.unit != unit and (value.grammar is m.ValueGrammar.UNRESOLVED or value.si_value is None):
        # An unresolved number cannot soften a known dimension contradiction.
        return failure(m.IssueSeverity.ERROR, f"Quantity must have unit {unit}.")
    if value.grammar is m.ValueGrammar.UNRESOLVED:
        return failure(m.IssueSeverity.AMBIGUOUS, "Scalar interpretation is unresolved.")
    # Parse selected literal grammar before sign/range checks. Preserve the M1B
    # root code instead of reporting both syntax and positivity for one field.
    parsed = None
    if value.literal is not None:
        parsed = parse_quantity(value.literal, value.unit, value.grammar)
        if parsed.issues:
            return failure(m.IssueSeverity.ERROR, parsed.issues[0].message, "VALUE_INVALID")
    if value.si_value is None:
        return failure(m.IssueSeverity.AMBIGUOUS if pending else missing,
                       "Required normalized SI scalar is missing.")
    normalized = parse_quantity(value.si_value, value.unit, m.ValueGrammar.SI)
    if normalized.issues:
        return failure(m.IssueSeverity.ERROR, normalized.issues[0].message, "VALUE_INVALID")
    number = Fraction(Decimal(normalized.quantity.si_value))
    if parsed is not None and number != Fraction(Decimal(parsed.quantity.si_value)):
        return failure(m.IssueSeverity.ERROR, "Literal and normalized SI scalar disagree.", "VALUE_INVALID")
    if value.unit != unit:
        return failure(m.IssueSeverity.ERROR, f"Quantity must have unit {unit}.")
    if sign == "positive" and number <= 0:
        return failure(m.IssueSeverity.ERROR, "Quantity must be strictly positive.")
    if sign == "nonnegative" and number < 0:
        return failure(m.IssueSeverity.ERROR, "Quantity must be nonnegative.")
    return number, []


def _pending(document, kind, targets):
    return any(item.state is m.AmbiguityStatus.UNRESOLVED and item.kind is kind
               and set(item.target_refs).intersection(targets) for item in document.ambiguities)


def _role_nets(graph, identity):
    # Disposable lookup from explicit roles/connections; not a second canonical state.
    return {graph.pin_by_id[pin].role: graph.net_for_pin(pin)
            for pin in graph.pins_for_component(identity)}


def _source(component, pending_value):
    issues, numbers = [], {}
    identity, source = component.id, component.source
    if source is None:
        return [_finding("SOURCE_INVALID", m.IssueSeverity.AMBIGUOUS, (identity,),
                         "component", identity, "source", "Source configuration is missing.")], numbers
    unit = "V" if component.type is m.ComponentType.VOLTAGE_SOURCE else "A"
    def check(value, expected_unit, field, sign=None, missing=m.IssueSeverity.ERROR):
        number, findings = _quantity(value, expected_unit, identity, field, code="SOURCE_INVALID",
                                     sign=sign, missing=missing, pending=pending_value)
        issues.extend(findings)
        if number is not None:
            numbers[field] = number
        return number
    check(source.dc, unit, "source.dc", missing=m.IssueSeverity.AMBIGUOUS)
    if source.ac is not None:
        check(source.ac.magnitude, unit, "source.ac.magnitude", "nonnegative")
        check(source.ac.phase, "deg", "source.ac.phase")
    waveform = source.waveform
    # SINE names follow the authored model examples. PULSE has no previously
    # fixed key spellings; use explicit level1/level2 and the documented timing
    # names. No aliases or raw LTspice expressions are silently accepted.
    specs = {
        m.WaveformKind.NONE: {},
        m.WaveformKind.SINE: {"offset": (unit, None), "amplitude": (unit, None),
                              "frequency": ("Hz", "positive")},
        m.WaveformKind.PULSE: {"level1": (unit, None), "level2": (unit, None),
                               "delay": ("s", "nonnegative"), "rise": ("s", "positive"),
                               "fall": ("s", "positive"), "width": ("s", "positive"),
                               "period": ("s", "positive")},
    }[waveform.kind]
    parameters = dict(waveform.parameters)
    if set(parameters) != set(specs):
        issues.append(_finding("SOURCE_INVALID", m.IssueSeverity.ERROR, (identity,), "component",
                               identity, "source.waveform.parameters",
                               "Waveform parameters must match its exact typed key set."))
    else:
        for name, (expected_unit, sign) in sorted(specs.items()):
            check(parameters[name], expected_unit, f"source.waveform.{name}", sign)
        if waveform.kind is m.WaveformKind.PULSE:
            fields = tuple(f"source.waveform.{name}" for name in ("rise", "width", "fall", "period"))
            if all(field in numbers for field in fields):
                if sum(numbers[field] for field in fields[:3]) > numbers[fields[3]]:
                    issues.append(_finding("SOURCE_INVALID", m.IssueSeverity.ERROR, (identity,),
                                           "component", identity, "source.waveform.timing",
                                           "Pulse rise + width + fall exceeds its period."))
    return issues, numbers


def _devices(document, graph, pin_issues):
    issues, skipped, eligible, source_numbers = [], [], set(), {}
    blocked = {identity for issue in pin_issues if issue.blocking
               for identity in issue.target_refs if identity in graph.component_by_id}
    passive_units = {m.ComponentType.RESISTOR: "ohm", m.ComponentType.CAPACITOR: "F",
                     m.ComponentType.INDUCTOR: "H"}
    for identity, component in graph.component_by_id.items():
        local = []
        if component.type is m.ComponentType.UNKNOWN:
            pending = _pending(document, m.AmbiguityKind.SYMBOL_TYPE, (identity,))
            local.append(_finding("UNSUPPORTED_FEATURE", m.IssueSeverity.AMBIGUOUS if pending
                                  else m.IssueSeverity.ERROR, (identity,), "component", identity,
                                  "type", "Device type is outside the supported local profile."))
        elif identity in blocked:
            skipped.append((f"component[{identity}].component_value_source", "pin_prerequisite_failed"))
            continue
        else:
            mos = component.type in (m.ComponentType.NMOS, m.ComponentType.PMOS)
            source = component.type in (m.ComponentType.VOLTAGE_SOURCE, m.ComponentType.CURRENT_SOURCE)
            role_nets = _role_nets(graph, identity)
            pending = _pending(document, m.AmbiguityKind.VALUE, (identity,))
            if not source and component.source is not None:
                local.append(_finding("SOURCE_INVALID", m.IssueSeverity.ERROR, (identity,), "component",
                                      identity, "source", "Non-source device cannot have source settings."))
            if not mos and (component.model_ref is not None or component.parameters):
                local.append(_finding("MODEL_INVALID", m.IssueSeverity.ERROR, (identity,), "component",
                                      identity, "model_ref_parameters", "Model/sizing fields require a MOS device."))
            if component.type in passive_units:
                _, findings = _quantity(component.value, passive_units[component.type], identity,
                                        "value", sign="positive", pending=pending)
                local.extend(findings)
            elif component.value is not None:
                local.append(_finding("VALUE_INVALID", m.IssueSeverity.ERROR, (identity,), "component",
                                      identity, "value", "Device uses typed source/sizing fields, not a passive value."))
            if source:
                p, n = role_nets[m.PinRole.POSITIVE], role_nets[m.PinRole.NEGATIVE]
                if p == n:
                    local.append(_finding("SOURCE_SAME_NET", m.IssueSeverity.ERROR, (identity, p),
                                          "component", identity, "connections",
                                          "Both source terminals connect to the same net."))
                findings, numbers = _source(component, pending)
                local.extend(findings)
                source_numbers[identity] = numbers
            if mos:
                if role_nets[m.PinRole.BULK] is None:
                    bulk = next(pin for pin in graph.pins_for_component(identity)
                                if graph.pin_by_id[pin].role is m.PinRole.BULK)
                    local.append(_finding("MOS_BODY_UNRESOLVED", m.IssueSeverity.AMBIGUOUS,
                                          (identity, bulk), "pin", bulk, "connection",
                                          "MOS bulk has no explicit net; no body tie is inferred."))
                if component.model_ref is None:
                    local.append(_finding("MODEL_INVALID", m.IssueSeverity.AMBIGUOUS, (identity,),
                                          "component", identity, "model_ref", "MOS model reference is not selected."))
                else:
                    local.append(_finding("CHECK_DEFERRED", m.IssueSeverity.WARNING, (identity,),
                                          "component", identity, "model_ref",
                                          "Model catalog existence/polarity/body convention is not resolved."))
                for name in ("width", "length"):
                    _, findings = _quantity(dict(component.parameters).get(name), "m", identity,
                                            f"parameters.{name}", sign="positive", pending=pending)
                    local.extend(findings)
        if not any(issue.blocking for issue in local):
            eligible.add(identity)
        issues.extend(local)
    return issues, skipped, eligible, source_numbers


def _reachable(adjacency, starts):
    seen, queue = set(starts), deque(sorted(starts))
    while queue:
        for neighbor in sorted(adjacency.get(queue.popleft(), ())):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def _constraint_cycle(parent, first, second, closing):
    ancestors, path = {}, set()
    node = first
    while True:
        ancestors[node] = set(path)
        if parent[node] is None:
            break
        node, identity = parent[node]
        path.add(identity)
    node, other = second, set()
    while node not in ancestors:
        node, identity = parent[node]
        other.add(identity)
    return tuple(sorted(ancestors[node] | other | {closing}))


def _constraints(graph, identities, source_numbers):
    """Exact DC potential traversal; ownership is never a conductive branch."""
    adjacency, sources = defaultdict(list), defaultdict(list)
    for identity in sorted(identities):
        component = graph.component_by_id[identity]
        nets = _role_nets(graph, identity)
        if component.type is m.ComponentType.VOLTAGE_SOURCE:
            p, n, voltage = nets[m.PinRole.POSITIVE], nets[m.PinRole.NEGATIVE], source_numbers[identity]["source.dc"]
            sources[tuple(sorted((p, n)))].append(identity)
        elif component.type is m.ComponentType.INDUCTOR:
            p, n, voltage = nets[m.PinRole.A], nets[m.PinRole.B], Fraction(0)
            if p == n:
                continue  # PASSIVE_BYPASSED is the root for this zero self-edge.
        else:
            continue
        adjacency[n].append((p, voltage, identity))
        adjacency[p].append((n, -voltage, identity))
    issues, potential, parent, seen_edges, deferred = [], {}, {}, set(), set()
    for start in sorted(adjacency):
        if start in potential:
            continue
        potential[start], parent[start], queue = Fraction(0), None, deque((start,))
        while queue:
            node = queue.popleft()
            for neighbor, difference, identity in sorted(adjacency[node], key=lambda row: (row[2], row[0])):
                if identity in seen_edges:
                    continue
                seen_edges.add(identity)
                expected = potential[node] + difference
                if neighbor not in potential:
                    potential[neighbor], parent[neighbor] = expected, (node, identity)
                    queue.append(neighbor)
                else:
                    targets = _constraint_cycle(parent, node, neighbor, identity)
                    severity = m.IssueSeverity.WARNING if potential[neighbor] == expected else m.IssueSeverity.ERROR
                    issues.append(_finding("SOURCE_CONSTRAINT_CONFLICT", severity, targets,
                                          "component_group", None, "dc_constraints",
                                          "Ideal DC constraint is redundant." if severity is m.IssueSeverity.WARNING
                                          else "Ideal DC constraints have inconsistent exact potential sums."))
                    dynamic_cycle = any(graph.component_by_id[item].type is m.ComponentType.VOLTAGE_SOURCE
                        and (graph.component_by_id[item].source.ac is not None or
                             graph.component_by_id[item].source.waveform.kind is not m.WaveformKind.NONE)
                        for item in targets)
                    direct_parallel = len(targets) == 2 and all(
                        graph.component_by_id[item].type is m.ComponentType.VOLTAGE_SOURCE for item in targets)
                    if severity is m.IssueSeverity.WARNING and dynamic_cycle and not direct_parallel:
                        deferred.add("dynamic_source_constraint_proof")
                        issues.append(_finding("CHECK_DEFERRED", m.IssueSeverity.WARNING, targets,
                                              "component_group", None, "dynamic_source_constraints",
                                              "General waveform/AC loop proof is outside exact local DC constraints."))
    for identities in sources.values():
        # Direct comparison only. No waveform solver or opposite-polarity AC
        # equivalence proof; uncertain dynamic cases remain explicitly deferred.
        for index, first in enumerate(identities):
            for second in identities[index + 1:]:
                a, b = graph.component_by_id[first], graph.component_by_id[second]
                na, nb = source_numbers[first], source_numbers[second]
                ra, rb = _role_nets(graph, first), _role_nets(graph, second)
                same_polarity = ra[m.PinRole.POSITIVE] == rb[m.PinRole.POSITIVE]
                dc_b = nb["source.dc"] if same_polarity else -nb["source.dc"]
                if na["source.dc"] != dc_b:
                    continue  # DC root already diagnosed above.
                dynamic = a.source.ac is not None or b.source.ac is not None or (
                    a.source.waveform.kind is not m.WaveformKind.NONE or b.source.waveform.kind is not m.WaveformKind.NONE)
                if not dynamic:
                    continue
                unknown, conflict = not same_polarity, False
                if same_polarity:
                    if a.source.ac is not None and b.source.ac is not None:
                        ma, mb = na["source.ac.magnitude"], nb["source.ac.magnitude"]
                        conflict = ma != mb or (ma != 0 and na["source.ac.phase"] % 360 != nb["source.ac.phase"] % 360)
                    elif (a.source.ac is None) != (b.source.ac is None):
                        unknown = True
                    ka, kb = a.source.waveform.kind, b.source.waveform.kind
                    if ka != kb:
                        unknown = True
                    elif ka is not m.WaveformKind.NONE:
                        names = ("offset", "amplitude", "frequency") if ka is m.WaveformKind.SINE else (
                            "level1", "level2", "delay", "rise", "fall", "width", "period")
                        va = tuple(na[f"source.waveform.{name}"] for name in names)
                        vb = tuple(nb[f"source.waveform.{name}"] for name in names)
                        if ka is m.WaveformKind.SINE and va[1] == vb[1] == 0:
                            conflict |= va[0] != vb[0]
                        elif ka is m.WaveformKind.PULSE and va[0] == va[1] and vb[0] == vb[1]:
                            conflict |= va[0] != vb[0]
                        else:
                            conflict |= va != vb
                if conflict:
                    issues.append(_finding("SOURCE_CONSTRAINT_CONFLICT", m.IssueSeverity.ERROR,
                                          (first, second), "component_group", None, "parallel_source_settings",
                                          "Parallel sources have conflicting directly comparable typed settings."))
                elif unknown:
                    deferred.add("dynamic_source_constraint_proof")
                    issues.append(_finding("CHECK_DEFERRED", m.IssueSeverity.WARNING, (first, second),
                                          "component_group", None, "parallel_source_settings",
                                          "General dynamic source equivalence is outside the local DC proof."))
    return issues, deferred


def _graph_rules(graph, eligible, source_numbers, ground_ok):
    issues, skipped = [], []
    for identity in sorted(eligible):
        component = graph.component_by_id[identity]
        if component.type in (m.ComponentType.RESISTOR, m.ComponentType.CAPACITOR, m.ComponentType.INDUCTOR):
            nets = _role_nets(graph, identity)
            if nets[m.PinRole.A] == nets[m.PinRole.B]:
                issues.append(_finding("PASSIVE_BYPASSED", m.IssueSeverity.WARNING,
                                       (identity, nets[m.PinRole.A]), "component", identity,
                                       "connections", "Both passive terminals share one net."))
    constraint_issues, deferred = _constraints(graph, eligible, source_numbers)
    issues.extend(constraint_issues)
    if not ground_ok:
        return issues, [("graph_dc", "blocked_by_ground_missing")], deferred
    ground = next(identity for identity, net in graph.net_by_id.items() if net.is_ground)
    for group in graph.connected_components():
        devices = {identity for kind, identity in group if kind == "component"}
        nets = {identity for kind, identity in group if kind == "net"}
        if not devices:
            continue  # No invented unused/single-pin-net rejection.
        if not devices.issubset(eligible):
            skipped.append((f"region[{min(devices)}].graph_dc", "invalid_component_prerequisite"))
            continue
        if ground not in nets:
            issues.append(_finding("ISOLATED_SUBNETWORK", m.IssueSeverity.ERROR,
                                   tuple(identity for kind, identity in group), "component_group", None,
                                   "reference", "Incidence island has no accepted ground reference."))
            continue  # No derived floating findings for the same island.
        linear, conditional = defaultdict(set), defaultdict(set)
        for identity in sorted(devices):
            component, roles = graph.component_by_id[identity], _role_nets(graph, identity)
            if component.type in (m.ComponentType.RESISTOR, m.ComponentType.INDUCTOR):
                branches = ((roles[m.PinRole.A], roles[m.PinRole.B]),)
            elif component.type is m.ComponentType.VOLTAGE_SOURCE:
                branches = ((roles[m.PinRole.POSITIVE], roles[m.PinRole.NEGATIVE]),)
            else:
                branches = ()
            for a, b in branches:
                linear[a].add(b)
                linear[b].add(a)
            if component.type in (m.ComponentType.NMOS, m.ComponentType.PMOS):
                body_nets = {roles[role] for role in (m.PinRole.DRAIN, m.PinRole.SOURCE, m.PinRole.BULK)}
                for net in body_nets:
                    conditional[net].update(body_nets - {net})
        proven = _reachable(linear, (ground,))
        possible = defaultdict(set, {net: set(neighbors) for net, neighbors in linear.items()})
        for net, neighbors in conditional.items():
            possible[net].update(neighbors)
        uncertain = _reachable(possible, proven)
        for net in sorted(nets - proven):
            code, severity = (("DC_REFERENCE_UNPROVEN", m.IssueSeverity.WARNING) if net in uncertain
                              else ("FLOATING_DC_NODE", m.IssueSeverity.ERROR))
            issues.append(_finding(code, severity, (net,), "net", net, "dc_reference",
                                   "DC reference depends on an unsolved nonlinear path." if net in uncertain
                                   else "No supported linear or conditional DC-reference path exists."))
            if net in uncertain:
                deferred.add("nonlinear_dc_reference")
    return issues, skipped, deferred


def _resolution_valid(item):
    return item.state is m.AmbiguityStatus.RESOLVED and (
        item.selected_candidate_id is not None or bool(item.resolution_note and item.resolution_note.strip()))


def _record_rules(document, graph, prior):
    issues, skipped = [], []
    # Specific field diagnostics consume their matching declared ambiguities;
    # unrelated errors on the same device cannot erase an independent choice.
    roots = {
        m.AmbiguityKind.SYMBOL_TYPE: {"UNSUPPORTED_FEATURE"},
        m.AmbiguityKind.VALUE: {"VALUE_INVALID", "SOURCE_INVALID"},
        m.AmbiguityKind.PIN_MAPPING: {"PIN_ROLES_INVALID"},
        m.AmbiguityKind.BODY_CONNECTION: {"MOS_BODY_UNRESOLVED", "PIN_ROLES_INVALID"},
        m.AmbiguityKind.LABEL_ATTACHMENT: {"LABEL_UNRESOLVED", "LABEL_CONFLICT"},
    }
    for item in sorted(document.ambiguities, key=lambda record: record.id):
        if item.state is m.AmbiguityStatus.RESOLVED:
            if not _resolution_valid(item):
                issues.append(_finding("BROKEN_REFERENCE", m.IssueSeverity.ERROR, (item.id, *item.target_refs),
                                       "ambiguity", item.id, "resolution",
                                       "Resolved choice needs a selected candidate or nonempty manual resolution."))
            elif item.kind is m.AmbiguityKind.WIRE_GAP:
                issues.append(_finding("DANGLING_WIRE", m.IssueSeverity.WARNING, (item.id, *item.target_refs),
                                       "ambiguity", item.id, "state",
                                       "Declared wire-gap disposition is resolved; retained evidence requires review."))
            continue
        if any(issue.code in roots.get(item.kind, ()) and set(issue.target_refs).intersection(item.target_refs)
               for issue in prior):
            continue
        code = {m.AmbiguityKind.CROSSING: "CROSSING_UNRESOLVED",
                m.AmbiguityKind.WIRE_GAP: "DANGLING_WIRE"}.get(item.kind, "AMBIGUITY_UNRESOLVED")
        issues.append(_finding(code, m.IssueSeverity.AMBIGUOUS, (item.id, *item.target_refs),
                               "ambiguity", item.id, "state", "Explicit circuit interpretation remains unresolved."))
    resolved = [item for item in document.ambiguities if _resolution_valid(item)]
    def reviewed(targets, kinds):
        return any(item.kind in kinds and set(item.target_refs).intersection(targets) for item in resolved)
    connection_kinds = {m.AmbiguityKind.PIN_MAPPING, m.AmbiguityKind.BODY_CONNECTION,
                        m.AmbiguityKind.CROSSING, m.AmbiguityKind.WIRE_GAP}
    blocked = prior + issues
    for row in sorted(document.connections, key=lambda row: row.pin_id):
        owner = graph.pin_by_id[row.pin_id].component_id
        targets = (row.pin_id, owner, *row.visual_refs)
        kinds = connection_kinds if graph.pin_by_id[row.pin_id].role is m.PinRole.BULK else (
            connection_kinds - {m.AmbiguityKind.BODY_CONNECTION})
        if row.confidence.basis is not m.ConfidenceBasis.MANUAL and not reviewed(targets, kinds):
            connection_roots = {"PIN_ROLES_INVALID", "PIN_NET_INVALID", "MOS_BODY_UNRESOLVED",
                                "SOURCE_SAME_NET", "CROSSING_UNRESOLVED", "DANGLING_WIRE"}
            matching_choice = any(item.state is m.AmbiguityStatus.UNRESOLVED and item.kind in kinds
                                  and set(item.target_refs).intersection(targets) for item in document.ambiguities)
            if not matching_choice and not any(issue.blocking and issue.code in connection_roots
                    and set(issue.target_refs).intersection(targets) for issue in blocked):
                issues.append(_finding("CONFIDENCE_REVIEW_REQUIRED", m.IssueSeverity.AMBIGUOUS,
                                       (row.pin_id, row.net_id), "pin", row.pin_id, "connection.confidence",
                                       "Declared inferred connectivity lacks an explicit item resolution; score is not approval."))
    evidence_targets = defaultdict(set)
    for records in (document.components, document.pins, document.labels):
        for record in records:
            if record.visual_ref is not None:
                evidence_targets[record.visual_ref].add(record.id)
    for row in document.connections:
        for identity in row.visual_refs:
            evidence_targets[identity].add(row.pin_id)
    for visual in document.visual.entities:
        targets = evidence_targets[visual.id] | {visual.id}
        if evidence_targets[visual.id] and visual.confidence.basis is not m.ConfidenceBasis.MANUAL:
            if not reviewed(targets, set(m.AmbiguityKind)) and not any(
                    issue.blocking and set(issue.target_refs).intersection(targets) for issue in blocked + issues):
                issues.append(_finding("CONFIDENCE_REVIEW_REQUIRED", m.IssueSeverity.AMBIGUOUS,
                                       tuple(targets), "visual", visual.id, "confidence",
                                       "Declared critical visual inference lacks an explicit item resolution."))
    image = document.source_image_reference
    if document.metadata.origin is m.Origin.IMAGE and image is None:
        issues.append(_finding("IMAGE_PROVENANCE_INVALID", m.IssueSeverity.ERROR, (), "document", None,
                               "source_image_reference", "Image-origin document lacks its source/hash/dimensions reference."))
        skipped.append(("visual.bounds", "source_image_reference_missing"))
    if image is not None:
        for visual in sorted(document.visual.entities, key=lambda record: record.id):
            points = visual.points + (() if visual.position is None else (visual.position,))
            bad = any(point.x >= image.width_px or point.y >= image.height_px for point in points)
            if visual.bbox is not None:
                box = visual.bbox
                bad |= (Fraction(str(box.x)) + Fraction(str(box.width)) > image.width_px
                        or Fraction(str(box.y)) + Fraction(str(box.height)) > image.height_px)
            if bad:
                issues.append(_finding("IMAGE_PROVENANCE_INVALID", m.IssueSeverity.ERROR, (visual.id,),
                                       "visual", visual.id, "geometry", "Original-pixel geometry exceeds declared image bounds."))
    return issues, skipped


def _result(document, issues, completed, skipped, deferred=_DEFERRED):
    issues = _report(issues)
    if any(issue.severity is m.IssueSeverity.ERROR for issue in issues):
        state = m.TechnicalState.INVALID
    elif any(issue.severity is m.IssueSeverity.AMBIGUOUS for issue in issues):
        state = m.TechnicalState.AMBIGUOUS
    else:
        required = set(_REQUIRED_STAGES)
        incomplete = (not required.issubset(completed)
                      or any(stage in required for stage, reason in skipped)
                      or bool(required.intersection(deferred)))
        state = m.TechnicalState.UNVALIDATED if incomplete else m.TechnicalState.VALID
    return m.ValidationResult("m1-local-v1", "m1-local-v1", document.metadata.revision,
                              state, issues, tuple(completed) + ("result",),
                              tuple(sorted(set(skipped))), tuple(sorted(set(deferred))))


def validate_document(document: m.CircuitDocument) -> m.ValidationResult:
    """Fresh immutable local report, with no human approval/execution authority.

    Stage names expose schema/IDs/references/incidence reuse, then the pin and
    ground/label substeps, then device/source/value, DC and explicit evidence
    stages. Unsafe dependent checks are skipped with reasons; no status mutation.
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
    completed = list(_STRUCTURAL_STAGES)
    ground_issues = _ground(graph)
    issues.extend(ground_issues)
    issues.extend(_labels(document, graph))
    findings, device_skips, eligible, source_numbers = _devices(document, graph, issues)
    issues.extend(findings)
    skipped.extend(device_skips)
    completed.append("component_value_source")
    findings, graph_skips, deferred = _graph_rules(graph, eligible, source_numbers, not ground_issues)
    issues.extend(findings)
    skipped.extend(graph_skips)
    if not ground_issues:
        completed.append("graph_dc")
    findings, record_skips = _record_rules(document, graph, issues)
    issues.extend(findings)
    skipped.extend(record_skips)
    completed.append("ambiguity_confidence_provenance")
    return _result(document, _with_provenance(issues, document), completed, skipped, (*_DEFERRED, *deferred))
