"""Pure m2-spice-v1 passive/source/MOS preview; no execution permission or I/O.

M1 technical validity, M2 representability, circuit approval and later artifact /
execution approval are separate gates. Connections alone supply terminal nets.
M1's existing lazy bundled-schema loading remains the sole inherited I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from . import models as m
from .approval import (
    ApprovalEnvelope, ApprovalError, approval_digest, document_digest,
    electrical_digest, validation_digest, verify_circuit_approval,
)
from .graph import build_graph
from .validation import validate_document
from .value_parser import parse_quantity
from .model_profiles import _si_token, _profile_projection, repository_model_profiles


_CONTRACT = "m2-spice-v1"
_MOS = frozenset((m.ComponentType.NMOS, m.ComponentType.PMOS))
_PASSIVES = {m.ComponentType.RESISTOR: ("R", "ohm"),
             m.ComponentType.CAPACITOR: ("C", "F"), m.ComponentType.INDUCTOR: ("L", "H")}
_SOURCES = {m.ComponentType.VOLTAGE_SOURCE: ("V", "V"),
            m.ComponentType.CURRENT_SOURCE: ("I", "A")}
_REQUIRED_STAGES = frozenset(("schema", "ids", "references", "incidence", "pins", "ground",
                            "labels", "component_value_source", "graph_dc",
                            "ambiguity_confidence_provenance"))
_MANUAL_DEFERRALS = frozenset(("model_catalog_resolution", "image_asset_resolution",
                             "inference_calibration", "human_approval", "full_export_readiness"))


class ExportStatus(str, Enum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"


def _string(value, field, *, nonempty=True):
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")


def _id(value, field):
    _string(value, field)
    if len(value) > 64 or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value) is None:
        raise ValueError(f"{field} must be a bounded Circuit IR identifier")


def _hash(value, field):
    _string(value, field)
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError(f"{field} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ExportIssue:
    code: str
    severity: m.IssueSeverity
    target_refs: tuple[str, ...]
    field: str | None
    message: str

    def __post_init__(self):
        _id(self.code, "code")
        if not isinstance(self.severity, m.IssueSeverity):
            raise TypeError("severity must be IssueSeverity")
        if self.severity not in (m.IssueSeverity.ERROR, m.IssueSeverity.WARNING):
            raise ValueError("export issues use ERROR or WARNING only")
        if type(self.target_refs) is not tuple:
            raise TypeError("target_refs must be an immutable tuple")
        for identity in self.target_refs:
            _id(identity, "target_refs")
        if self.field is not None:
            _string(self.field, "field", nonempty=False)
        _string(self.message, "message")

    @property
    def blocking(self):
        return self.severity is m.IssueSeverity.ERROR


@dataclass(frozen=True, slots=True)
class ExportProvenance:
    document_id: str
    document_revision: int
    document_sha256: str
    electrical_sha256: str
    validation_sha256: str
    circuit_approval_sha256: str
    validation_profile: str
    validation_ruleset: str
    exporter_contract: str
    model_registry_version: str
    model_registry_sha256: str
    base_netlist_sha256: str
    mapping_sha256: str

    def __post_init__(self):
        for field, value in (("document_id", self.document_id),
                             ("validation_profile", self.validation_profile),
                             ("validation_ruleset", self.validation_ruleset),
                             ("exporter_contract", self.exporter_contract),
                             ("model_registry_version", self.model_registry_version)):
            _id(value, field)
        if type(self.document_revision) is not int:
            raise TypeError("document_revision must be an integer, not bool")
        if self.document_revision < 0:
            raise ValueError("document_revision must be nonnegative")
        for field, value in (("document_sha256", self.document_sha256),
                             ("electrical_sha256", self.electrical_sha256),
                             ("validation_sha256", self.validation_sha256),
                             ("circuit_approval_sha256", self.circuit_approval_sha256),
                             ("model_registry_sha256", self.model_registry_sha256),
                             ("base_netlist_sha256", self.base_netlist_sha256),
                             ("mapping_sha256", self.mapping_sha256)):
            _hash(value, field)


def _map_shape(value, field):
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an immutable tuple")
    ids, names = [], []
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            raise TypeError(f"{field} requires immutable ID/name pairs")
        identity, name = pair
        _id(identity, field)
        _string(name, field)
        if re.fullmatch(r"[A-Za-z0-9_]+", name) is None:
            raise ValueError(f"{field} requires generated safe names")
        ids.append(identity)
        names.append(name.lower())
    if ids != sorted(ids) or len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise ValueError(f"{field} must be sorted and collision-free")


@dataclass(frozen=True, slots=True)
class ExportResult:
    status: ExportStatus
    spice_text: str | None
    issues: tuple[ExportIssue, ...]
    provenance: ExportProvenance | None
    element_map: tuple[tuple[str, str], ...]
    net_map: tuple[tuple[str, str], ...]
    model_map: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if not isinstance(self.status, ExportStatus):
            raise TypeError("status must be ExportStatus")
        if type(self.issues) is not tuple or any(not isinstance(i, ExportIssue) for i in self.issues):
            raise TypeError("issues must be a tuple of ExportIssue")
        for field, value in (("element_map", self.element_map), ("net_map", self.net_map),
                             ("model_map", self.model_map)):
            _map_shape(value, field)
        if self.status is ExportStatus.BLOCKED:
            if (self.spice_text is not None or self.provenance is not None
                    or self.element_map or self.net_map or self.model_map):
                raise ValueError("BLOCKED must contain no text, provenance or generated maps")
            if not any(i.blocking for i in self.issues):
                raise ValueError("BLOCKED requires a blocking issue")
        else:
            _string(self.spice_text, "spice_text")
            if not isinstance(self.provenance, ExportProvenance):
                raise TypeError("SUCCESS requires ExportProvenance")
            if any(i.blocking for i in self.issues):
                raise ValueError("SUCCESS cannot contain blocking issues")


def _issue(code, targets=(), field=None, message="Export prerequisite failed.",
           severity=m.IssueSeverity.ERROR):
    return ExportIssue(code, severity, tuple(sorted(set(targets))), field, message)


def _ordered(issues):
    # Deduplicate by stable contract fields, never prose or set iteration order.
    unique = {}
    for issue in issues:
        key = (0 if issue.blocking else 1, issue.code, issue.target_refs, issue.field or "")
        unique.setdefault(key, issue)
    return tuple(unique[key] for key in sorted(unique))


class _Refusal(Exception):
    def __init__(self, issue):
        self.issue = issue


def _refuse(code, identity, field, message):
    raise _Refusal(_issue(code, (identity,), field, message))


def _number(value, unit, identity, field, sign=None):
    """Exact M2 SI token: fixed for adjusted exponent [-3,6], scientific otherwise.

    Decimal construction/as_tuple are context-independent. No float, normalize,
    arithmetic rounding, engineering suffix or original literal is emitted.
    """
    if (value is None or value.unit != unit or value.si_value is None
            or value.grammar is m.ValueGrammar.UNRESOLVED):
        _refuse("EXPORT_VALUE_INVALID", identity, field, "Required resolved quantity/unit is unavailable.")
    parsed = parse_quantity(value.si_value, unit, m.ValueGrammar.SI)
    if parsed.quantity is None:
        _refuse("EXPORT_VALUE_INVALID", identity, field, "SI scalar is not finite or bounded.")
    decimal = Decimal(parsed.quantity.si_value)
    if (sign == "positive" and decimal <= 0) or (sign == "nonnegative" and decimal < 0):
        _refuse("EXPORT_VALUE_INVALID", identity, field, "Quantity violates the required sign.")
    try:
        return _si_token(decimal)
    except ValueError as error:
        _refuse("EXPORT_VALUE_INVALID", identity, field, str(error))


def _mos_profile(component, profiles):
    # Logical IDs equal sealed profile IDs: no alias/default/fuzzy substitution.
    profile = next((p for p in profiles if p.profile_id == component.model_ref), None)
    if profile is None:
        _refuse("EXPORT_MODEL_UNRESOLVED", component.id, "model_ref", "No exact trusted model profile.")
    if profile.component_type is not component.type:
        _refuse("EXPORT_MODEL_INCOMPATIBLE", component.id, "model_ref", "Trusted profile polarity mismatch.")
    if set(dict(component.parameters)) != {"width", "length"}:
        _refuse("EXPORT_UNSUPPORTED_FEATURE", component.id, "parameters", "MOS requires only width and length.")
    if component.value is not None or component.source is not None:
        _refuse("EXPORT_UNSUPPORTED_FEATURE", component.id, "value", "MOS cannot carry passive/source settings.")
    for key in ("width", "length"):
        _number(dict(component.parameters)[key], "m", component.id, "parameters." + key, "positive")
    return profile


def _model_line(profile, token):
    values = _profile_projection(profile)
    polarity = "NMOS" if profile.component_type is m.ComponentType.NMOS else "PMOS"
    # Fixed keys/template only; IDs and literal model text never enter this row.
    fields = (("VTO", "vto"), ("KP", "kp"), ("LAMBDA", "lambda_"),
              ("GAMMA", "gamma"), ("PHI", "phi"), ("CGSO", "cgso"), ("CGDO", "cgdo"))
    parameters = " ".join(name + "=" + values[key] for name, key in fields)
    return ".model " + token + " " + polarity + " (LEVEL=1 " + parameters + ")"


def _source(component, *, render=True):
    """Check source fields; form a controlled row suffix only after approval."""
    identity, source = component.id, component.source
    unit = _SOURCES[component.type][1]
    if source is None:
        _refuse("EXPORT_UNSUPPORTED_SOURCE", identity, "source", "Typed source settings are required.")
    dc = _number(source.dc, unit, identity, "source.dc")
    parameters = dict(source.waveform.parameters)
    kind = source.waveform.kind
    order = {m.WaveformKind.NONE: (), m.WaveformKind.SINE: ("offset", "amplitude", "frequency"),
             m.WaveformKind.PULSE: ("level1", "level2", "delay", "rise", "fall", "width", "period")}
    if kind not in order or set(parameters) != set(order[kind]):
        _refuse("EXPORT_UNSUPPORTED_SOURCE", identity, "source.waveform", "Unsupported waveform key set.")
    values = []
    if kind is not m.WaveformKind.NONE:
        values = []
        for key in order[kind]:
            if key in ("frequency",):
                dimension, sign = "Hz", "positive"
            elif key in ("delay", "rise", "fall", "width", "period"):
                dimension, sign = "s", "nonnegative" if key == "delay" else "positive"
            else:
                dimension, sign = unit, None
            values.append(_number(parameters[key], dimension, identity, "source.waveform." + key, sign))
        if Decimal(dc) != Decimal(values[0]):
            _refuse("EXPORT_UNSUPPORTED_SOURCE", identity, "source.dc",
                    "DC must equal SINE offset or PULSE level1 under m2-spice-v1.")
        # M1's exact rational timing check already proved rise+width+fall<=period.
    if source.ac is not None:
        magnitude = _number(source.ac.magnitude, unit, identity, "source.ac.magnitude", "nonnegative")
        phase = _number(source.ac.phase, "deg", identity, "source.ac.phase")
    if not render:
        return None
    if kind is m.WaveformKind.NONE:
        text = "DC " + dc
    elif kind is m.WaveformKind.SINE:
        text = "SINE(" + " ".join((*values, "0", "0", "0")) + ")"
    else:
        text = "PULSE(" + " ".join(values) + ")"
    if source.ac is not None:
        text += " AC " + magnitude + " " + phase
    return text


def _terminals(component, graph):
    expected = ((m.PinRole.DRAIN, m.PinRole.GATE, m.PinRole.SOURCE, m.PinRole.BULK)
                if component.type in _MOS else (m.PinRole.A, m.PinRole.B) if component.type in _PASSIVES
                else (m.PinRole.POSITIVE, m.PinRole.NEGATIVE))
    assignments = {}
    for pin_id in graph.pins_for_component(component.id):
        role = graph.pin_by_id[pin_id].role
        if role in assignments:
            _refuse("EXPORT_PREREQUISITE_UNRESOLVED", component.id, "pins", "Repeated terminal role.")
        assignments[role] = graph.net_for_pin(pin_id)
    if set(assignments) != set(expected) or any(assignments[role] is None for role in expected):
        _refuse("EXPORT_PREREQUISITE_UNRESOLVED", component.id, "connections", "Explicit terminal nets are required.")
    return tuple(assignments[role] for role in expected)


def _preflight(document, model_context):
    if not isinstance(document, m.CircuitDocument):
        raise TypeError("document must be CircuitDocument")
    if (type(model_context) is not tuple or len(model_context) != 2
            or any(not isinstance(value, str) for value in model_context)):
        raise TypeError("model_context must be an immutable (version, sha256) string pair")
    report = validate_document(document)
    if not isinstance(report, m.ValidationResult):
        raise TypeError("validator must return ValidationResult")
    incomplete = (not _REQUIRED_STAGES.issubset(report.completed_stages)
                  or any(stage in _REQUIRED_STAGES for stage, _ in report.skipped_stages)
                  or bool(_REQUIRED_STAGES.intersection(report.deferred_checks)))
    if (report.technical_state is not m.TechnicalState.VALID or report.blocking_issue_count or incomplete
            or report.document_revision != document.metadata.revision
            or report.profile != "m1-local-v1" or report.ruleset_version != "m1-local-v1"):
        return (_issue("EXPORT_DOCUMENT_NOT_VALID", field="validation",
                       message="Fresh complete VALID@m1-local-v1 validation is required."),), report, None
    graph = build_graph(document).graph
    if graph is None:
        return (_issue("EXPORT_DOCUMENT_NOT_VALID", field="connections",
                       message="Checked graph is unavailable."),), report, None
    if document.metadata.origin is not m.Origin.MANUAL or document.source_image_reference is not None:
        return (_issue("EXPORT_UNSUPPORTED_FEATURE", field="metadata.origin",
                       message="Initial exporter admits manual input without an image reference only."),), report, graph
    try:
        profiles = repository_model_profiles(model_context)
    except (ValueError, TypeError):
        return (_issue("EXPORT_MODEL_INCOMPATIBLE", field="model_context",
                       message="Exact sealed repository model context is required."),), report, graph
    issues = []
    supplied_models = set()
    for component in sorted(document.components, key=lambda c: c.id):
        if component.type not in _PASSIVES and component.type not in _SOURCES and component.type not in _MOS:
            issues.append(_issue("EXPORT_UNSUPPORTED_COMPONENT", (component.id,), "type",
                                 "Only R/C/L/V/I/NMOS/PMOS are supported."))
            continue
        try:
            _terminals(component, graph)
            if component.type in _MOS:
                _mos_profile(component, profiles)
                supplied_models.add(component.id)
                continue
            if component.parameters or component.model_ref is not None:
                _refuse("EXPORT_UNSUPPORTED_FEATURE", component.id, "parameters",
                        "Arbitrary instance parameters/model references are unsupported.")
            if component.type in _PASSIVES:
                _number(component.value, _PASSIVES[component.type][1], component.id, "value", "positive")
            else:
                _source(component, render=False)
        except _Refusal as failure:
            issues.append(failure.issue)
    if issues:
        return _ordered(issues), report, graph
    # Unknown/blocked warning and deferral names cannot be waived by approval.
    for issue in report.issues:
        if issue.severity is m.IssueSeverity.WARNING:
            resolved_stub = (issue.code == "DANGLING_WIRE" and any(
                item.id in issue.target_refs and item.kind is m.AmbiguityKind.WIRE_GAP
                and item.state is m.AmbiguityStatus.RESOLVED
                for item in document.ambiguities))
            supplied_model = (issue.code == "CHECK_DEFERRED"
                              and issue.field == f"component[{issue.entity_id}].model_ref"
                              and issue.entity_type == "component"
                              and issue.entity_id in supplied_models
                              and issue.target_refs == (issue.entity_id,))
            if issue.code == "LABEL_ALIAS" or resolved_stub or supplied_model:
                issues.append(_issue(issue.code, issue.target_refs, issue.field, issue.message, m.IssueSeverity.WARNING))
            else:
                issues.append(_issue("EXPORT_PREREQUISITE_UNRESOLVED", issue.target_refs, issue.field,
                                     "Blocked or unknown M1 warning: " + issue.code))
    for name in report.deferred_checks:
        if name not in _MANUAL_DEFERRALS:
            issues.append(_issue("EXPORT_PREREQUISITE_UNRESOLVED", field="deferred_checks",
                                 message="Blocked or unknown deferred check: " + name))
    return _ordered(issues), report, graph


def check_export_eligibility(document: m.CircuitDocument, *, model_context: tuple[str, str]) -> tuple[ExportIssue, ...]:
    """Fresh diagnostic-only preflight; no text, approval or execution authority."""
    return _preflight(document, model_context)[0]


def _allocate(ids, prefix):
    # Four is a minimum width, so 10000 remains 10000 (never wraps/truncates).
    return tuple((identity, f"{prefix}_{index:04d}") for index, identity in enumerate(sorted(ids), 1))


def _mappings(document):
    grounds = [net.id for net in document.nets if net.is_ground]
    if len(grounds) != 1:
        raise _Refusal(_issue("EXPORT_PREREQUISITE_UNRESOLVED", field="nets", message="Exactly one explicit ground is required."))
    net_map = tuple(sorted(((grounds[0], "0"), *_allocate(
        [net.id for net in document.nets if not net.is_ground], "n"))))
    element_map = []
    for kind, (prefix, _) in (*_PASSIVES.items(), *_SOURCES.items()):
        element_map.extend(_allocate([c.id for c in document.components if c.type is kind], prefix))
    element_map.extend(_allocate([c.id for c in document.components if c.type in _MOS], "M"))
    element_map = tuple(sorted(element_map))
    _map_shape(net_map, "net_map")
    _map_shape(element_map, "element_map")
    return element_map, net_map


def _mapping_digest(element_map, net_map, model_map):
    projection = {"mapping_profile": "m2-mapping-v1", "element_map": [list(pair) for pair in element_map],
                  "net_map": [list(pair) for pair in net_map], "model_map": [list(pair) for pair in model_map]}
    return hashlib.sha256(json.dumps(projection, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _blocked(issues):
    return ExportResult(ExportStatus.BLOCKED, None, _ordered(issues), None, (), (), ())


def export_document(document: m.CircuitDocument, circuit_approval: ApprovalEnvelope | None,
                    *, model_context: tuple[str, str]) -> ExportResult:
    """Return complete deterministic base text or BLOCKED with no partial artifact.

    No cached validation argument, directive, path or approval boolean is accepted.
    SUCCESS is a preview that still needs separate representation/condition review.
    """
    if circuit_approval is not None and not isinstance(circuit_approval, ApprovalEnvelope):
        raise TypeError("circuit_approval must be ApprovalEnvelope or None")
    issues, report, graph = _preflight(document, model_context)
    if any(issue.blocking for issue in issues):
        return _blocked(issues)
    if circuit_approval is None or not circuit_approval.approved:
        return _blocked((*issues, _issue("EXPORT_APPROVAL_MISSING", field="circuit_approval",
                                        message="An approved circuit envelope is required.")))
    try:
        verify_circuit_approval(document, circuit_approval, exporter_contract=_CONTRACT,
                                model_registry_version=model_context[0], model_registry_sha256=model_context[1])
    except ApprovalError as failure:
        return _blocked((*issues, _issue("EXPORT_APPROVAL_STALE", field=failure.field,
                                        message="Circuit approval verification failed: " + failure.code)))
    # The preflight report used in provenance must also match the reviewed report,
    # even if a validator boundary produces different evidence on repeated calls.
    if validation_digest(report) != circuit_approval.validation_sha256:
        return _blocked((*issues, _issue("EXPORT_APPROVAL_STALE", field="validation_sha256",
                                        message="Preflight validation differs from the reviewed report.")))
    source_hash, electrical_hash = document_digest(document), electrical_digest(document)
    try:
        element_map, net_map = _mappings(document)
        elements, nets = dict(element_map), dict(net_map)
        profiles = repository_model_profiles(model_context)
        used = {c.model_ref for c in document.components if c.type in _MOS}
        model_map = _allocate(used, "mdl")
        _map_shape(model_map, "model_map")
        models = dict(model_map)
        lines = ["Circuit Simulation Assistant restricted circuit", "* exporter m2-spice-v1",
                 "* source_sha256 " + source_hash, "* electrical_sha256 " + electrical_hash]
        for profile in sorted(profiles, key=lambda p: p.profile_id):
            if profile.profile_id in used:
                lines.append(_model_line(profile, models[profile.profile_id]))
        for component in sorted(document.components, key=lambda c: c.id):
            if component.type in _MOS:
                terminals = _terminals(component, graph)
                params = dict(component.parameters)
                width = _number(params["width"], "m", component.id, "parameters.width", "positive")
                length = _number(params["length"], "m", component.id, "parameters.length", "positive")
                lines.append(" ".join((elements[component.id], *(nets[n] for n in terminals),
                                       models[component.model_ref], "W=" + width, "L=" + length)))
                continue
            a, b = _terminals(component, graph)
            suffix = (_number(component.value, _PASSIVES[component.type][1], component.id, "value", "positive")
                      if component.type in _PASSIVES else _source(component))
            if component.type is m.ComponentType.INDUCTOR:
                suffix += " Rser=0"
            lines.append(" ".join((elements[component.id], nets[a], nets[b], suffix)))
        text = "\n".join((*lines, ".end")) + "\n"
    except _Refusal as failure:
        return _blocked((*issues, failure.issue))
    provenance = ExportProvenance(
        document.metadata.circuit_id, document.metadata.revision, source_hash, electrical_hash,
        validation_digest(report), approval_digest(circuit_approval), report.profile, report.ruleset_version,
        _CONTRACT, model_context[0], model_context[1], hashlib.sha256(text.encode("utf-8")).hexdigest(),
        _mapping_digest(element_map, net_map, model_map),
    )
    return ExportResult(ExportStatus.SUCCESS, text, issues, provenance, element_map, net_map, model_map)
