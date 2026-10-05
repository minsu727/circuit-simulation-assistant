"""M1D checked incidence views, not electrical validation or human approval.

Prerequisites are checked in order: existing M1C shape, unique definition IDs,
references/ownership, then repeated incidence. A failed stage returns no graph
and suppresses dependent stages while collecting independent errors in that stage.
Missing incidence, empty nets/devices, role completeness, ground, label semantics,
DC conduction and ambiguity resolution policy await M1E/F. No edges are inferred.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from . import models as m
from .schema import validate_schema
from .serialization import document_to_dict


NodeKey = tuple[str, str]


def _read_only(values):
    return MappingProxyType(dict(sorted(values.items())))


@dataclass(frozen=True, slots=True)
class CircuitGraph:
    """Read-only derived indexes and typed undirected incidence adjacency.

    Node keys are (component|pin|net, ID). Ownership is not DC conduction.
    Connection records remain canonical; all indexes/edges are disposable views.
    Lookup methods return sorted ID tuples, and unknown IDs raise KeyError.
    A known pin without a Connection returns None from net_for_pin.
    """

    component_by_id: Mapping[str, m.Component]
    pin_by_id: Mapping[str, m.Pin]
    net_by_id: Mapping[str, m.Net]
    connection_by_pin: Mapping[str, m.Connection]
    adjacency: Mapping[NodeKey, tuple[NodeKey, ...]]

    def __post_init__(self) -> None:
        # Copy before exposing proxies, so no retained caller dictionary can edit
        # these views. Records are frozen; nested adjacency is immutable too.
        object.__setattr__(self, "component_by_id", _read_only(self.component_by_id))
        object.__setattr__(self, "pin_by_id", _read_only(self.pin_by_id))
        object.__setattr__(self, "net_by_id", _read_only(self.net_by_id))
        object.__setattr__(self, "connection_by_pin", _read_only(self.connection_by_pin))
        object.__setattr__(self, "adjacency", _read_only(
            {node: tuple(sorted(neighbors)) for node, neighbors in self.adjacency.items()}))

    def pins_for_component(self, component_id: str) -> tuple[str, ...]:
        return tuple(node[1] for node in self.adjacency[("component", component_id)])

    def net_for_pin(self, pin_id: str) -> str | None:
        self.pin_by_id[pin_id]
        connection = self.connection_by_pin.get(pin_id)
        return None if connection is None else connection.net_id

    def pins_for_net(self, net_id: str) -> tuple[str, ...]:
        return tuple(node[1] for node in self.adjacency[("net", net_id)])

    def connected_components(self) -> tuple[tuple[NodeKey, ...], ...]:
        """Deterministic BFS incidence groups; no ground/DC/island judgment."""
        visited, groups = set(), []
        for start in self.adjacency:
            if start in visited:
                continue
            queue, members = deque((start,)), []
            visited.add(start)
            while queue:
                node = queue.popleft()
                members.append(node)
                for neighbor in self.adjacency[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            groups.append(tuple(sorted(members)))
        return tuple(groups)


@dataclass(frozen=True, slots=True)
class GraphBuildResult:
    """Fresh prerequisite issues only; graph availability grants no validity."""

    graph: CircuitGraph | None
    issues: tuple[m.ValidationIssue, ...]

    def __post_init__(self) -> None:
        if self.graph is not None and not isinstance(self.graph, CircuitGraph):
            raise TypeError("graph must be CircuitGraph or None")
        if type(self.issues) is not tuple or any(
                not isinstance(issue, m.ValidationIssue) for issue in self.issues):
            raise TypeError("issues must be a tuple of ValidationIssue")


def _issue(code, targets, entity_type, entity_id, field, message):
    # References are opaque IDs, including the unresolved spelling in a broken
    # reference diagnosis. Target membership does not imply successful resolution.
    # Qualify a known entity's field so symmetric bad references do not collapse
    # under the documented (code, severity, targets, semantic_field) dedup key.
    if entity_id is not None:
        field = f"{entity_type}[{entity_id}].{field}"
    return m.ValidationIssue("issue_pending", m.IssueSeverity.ERROR, code, message,
                             tuple(sorted(set(targets))), entity_type, entity_id,
                             field, None, ())


def _report(issues):
    """Documented deduplication and severity/code/target/field ordering."""
    rank = {m.IssueSeverity.ERROR: 0, m.IssueSeverity.AMBIGUOUS: 1,
            m.IssueSeverity.WARNING: 2, m.IssueSeverity.CONFIRMED: 3}
    ordered = sorted(issues, key=lambda issue: (
        rank[issue.severity], issue.code, issue.target_refs, issue.field or "",
        issue.entity_type or "", issue.entity_id or "", issue.message))
    seen, result = set(), []
    for issue in ordered:
        key = (issue.code, issue.severity, issue.target_refs, issue.field)
        if key not in seen:
            seen.add(key)
            result.append(replace(issue, issue_id=f"issue_{len(result) + 1:04d}"))
    return tuple(result)


def _definitions(document):
    return (("component", document.components), ("pin", document.pins),
            ("net", document.nets), ("label", document.labels),
            ("visual", document.visual.entities), ("ambiguity", document.ambiguities),
            ("finding", document.validation_state.findings))


def _with_provenance(issues, document):
    """Attach only explicitly associated, existing visual IDs after the ID gate."""
    visuals = {item.id for item in document.visual.entities}
    evidence = defaultdict(set)
    for identity in visuals:
        evidence[identity].add(identity)
    for records in (document.components, document.pins, document.labels):
        for record in records:
            if record.visual_ref in visuals:
                evidence[record.id].add(record.visual_ref)
    for finding in document.validation_state.findings:
        evidence[finding.id].update(visuals.intersection(finding.visual_refs))
    pins = {pin.id for pin in document.pins}
    for connection in document.connections:
        if connection.pin_id in pins:
            evidence[connection.pin_id].update(visuals.intersection(connection.visual_refs))
    return [replace(issue, provenance=tuple(sorted({visual
            for target in issue.target_refs for visual in evidence.get(target, ())})))
            for issue in issues]


def _duplicate_issues(document):
    counts = defaultdict(int)
    for kind, records in _definitions(document):
        for record in records:
            counts[record.id] += 1
    issues = [_issue("DUPLICATE_ID", (identity,), "document", None, "id",
                     "Definition ID occurs more than once in the global namespace.")
              for identity, count in counts.items() if count > 1]
    # Only component identities have the planned case-insensitive collision rule.
    names = defaultdict(set)
    for component in document.components:
        names[component.id.lower()].add(component.id)
    for group in names.values():
        if len(group) > 1:
            issues.append(_issue("DUPLICATE_ID", group, "component", min(group), "id",
                                 "Component IDs collide when compared without case."))
    # Candidates are local to one ambiguity, not global circuit definitions.
    for ambiguity in document.ambiguities:
        local = defaultdict(int)
        for candidate in ambiguity.candidates:
            local[candidate.id] += 1
        for identity, count in local.items():
            if count > 1:
                issues.append(_issue("DUPLICATE_ID", (ambiguity.id, identity),
                                     "ambiguity", ambiguity.id, "candidates",
                                     "Candidate ID occurs more than once in this ambiguity."))
    return issues


def _reference_issues(document, components, pins, nets):
    definitions = {record.id for kind, records in _definitions(document) for record in records}
    visuals = {item.id for item in document.visual.entities}
    findings = {item.id: item for item in document.validation_state.findings}
    issues = []

    def check(reference, namespace, kind, identity, field):
        if reference is not None and reference not in namespace:
            targets = (reference,) if identity is None else (identity, reference)
            issues.append(_issue("BROKEN_REFERENCE", targets, kind, identity, field,
                                 f"Reference '{reference}' does not resolve in the required namespace."))

    declared_owners = defaultdict(set)
    for component in document.components:
        check(component.visual_ref, visuals, "component", component.id, "visual_ref")
        for pin_id in component.pin_ids:
            check(pin_id, pins, "component", component.id, "pin_ids")
            declared_owners[pin_id].add(component.id)
    for pin in document.pins:
        check(pin.visual_ref, visuals, "pin", pin.id, "visual_ref")
        check(pin.component_id, components, "pin", pin.id, "component_id")
        if pin.component_id in components and declared_owners[pin.id] != {pin.component_id}:
            issues.append(_issue("BROKEN_REFERENCE",
                                 (pin.id, pin.component_id, *declared_owners[pin.id]),
                                 "pin", pin.id, "ownership",
                                 "Pin owner and component pin_ids do not agree."))
    for connection in document.connections:
        # Connections have no definition ID. Diagnose via their explicit endpoints.
        selector = f"connections[{connection.pin_id}->{connection.net_id}]"
        for reference, namespace, field in ((connection.pin_id, pins, "pin_id"),
                                            (connection.net_id, nets, "net_id")):
            if reference not in namespace:
                issues.append(_issue("BROKEN_REFERENCE", (connection.pin_id, connection.net_id),
                                     "connection", None, f"{selector}.{field}",
                                     f"Connection {field} '{reference}' is not defined."))
        for visual_ref in connection.visual_refs:
            if visual_ref not in visuals:
                issues.append(_issue("BROKEN_REFERENCE",
                                     (connection.pin_id, connection.net_id, visual_ref),
                                     "connection", None, f"{selector}.visual_refs",
                                     f"Connection visual ref '{visual_ref}' is not defined."))
    for label in document.labels:
        check(label.net_id, nets, "label", label.id, "net_id")
        check(label.visual_ref, visuals, "label", label.id, "visual_ref")
    for ambiguity in document.ambiguities:
        for target in ambiguity.target_refs:
            check(target, definitions, "ambiguity", ambiguity.id, "target_refs")
        # A selected candidate must resolve locally, even if a same-named
        # candidate/definition exists elsewhere. Resolution policy awaits M1F.
        check(ambiguity.selected_candidate_id, {item.id for item in ambiguity.candidates},
              "ambiguity", ambiguity.id, "selected_candidate_id")
    for finding in document.validation_state.findings:
        for target in finding.target_refs:
            check(target, definitions, "finding", finding.id, "target_refs")
        for visual_ref in finding.visual_refs:
            check(visual_ref, visuals, "finding", finding.id, "visual_refs")
    for warning_id in document.warnings:
        check(warning_id, findings, "document", None, "warnings")
        if warning_id in findings and findings[warning_id].severity != m.IssueSeverity.WARNING:
            issues.append(_issue("BROKEN_REFERENCE", (warning_id,), "document", None, "warnings",
                                 "Warning ID must refer to an imported WARNING finding."))
    return issues


def _incidence_issues(document):
    rows = defaultdict(list)
    for connection in document.connections:
        rows[connection.pin_id].append(connection.net_id)
    issues = []
    for pin_id, net_ids in rows.items():
        if len(net_ids) > 1:
            distinct = set(net_ids)
            message = ("Pin is assigned to multiple distinct nets." if len(distinct) > 1
                       else "Pin occurs in duplicate connection rows.")
            issues.append(_issue("PIN_NET_INVALID", (pin_id, *distinct), "pin", pin_id,
                                 "connections", message))
    return issues


def build_graph(document: m.CircuitDocument) -> GraphBuildResult:
    """Check structural prerequisites and build derived component-pin-net views.

    Non-document input raises TypeError. Schema/ID/reference/incidence failures
    return issues and graph=None. Unconnected draft pins are preserved with None
    incidence; no net, ground or component-specific pin count is manufactured.
    Imported statuses/revisions/findings do not override fresh checks.
    Normal indexing/checks are O(N); deterministic sorting adds O(N log N).
    """
    if not isinstance(document, m.CircuitDocument):
        raise TypeError("document must be CircuitDocument")
    issues = validate_schema(document_to_dict(document))
    if issues:
        return GraphBuildResult(None, _report(issues))
    issues = _duplicate_issues(document)
    if issues:
        return GraphBuildResult(None, _report(issues))
    # Comprehensions cannot overwrite duplicates: the global namespace gate passed.
    components = {item.id: item for item in document.components}
    pins = {item.id: item for item in document.pins}
    nets = {item.id: item for item in document.nets}
    issues = _reference_issues(document, components, pins, nets)
    if issues:
        return GraphBuildResult(None, _report(_with_provenance(issues, document)))
    issues = _incidence_issues(document)
    if issues:
        return GraphBuildResult(None, _report(_with_provenance(issues, document)))
    adjacency = {("component", identity): [] for identity in components}
    adjacency.update({("pin", identity): [] for identity in pins})
    adjacency.update({("net", identity): [] for identity in nets})

    def edge(first, second):
        adjacency[first].append(second)
        adjacency[second].append(first)

    for pin in document.pins:
        edge(("component", pin.component_id), ("pin", pin.id))
    for connection in document.connections:
        edge(("pin", connection.pin_id), ("net", connection.net_id))
    return GraphBuildResult(CircuitGraph(
        components, pins, nets, {item.pin_id: item for item in document.connections},
        adjacency), ())
