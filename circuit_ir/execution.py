"""Pure M2 adapter contracts/composition, outside CircuitDocument/IR state.

No files, runner, simulator, metrics or implicit approvals. Existing ASC builders
are reused under a bounded exact Decimal context; their admission restrictions
(including the DC resolvable-step guard) remain intact. Source/trace names come
only from verified IR maps. M2F still owns actual text/simulator compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from enum import Enum
from fractions import Fraction
import hashlib
import json
import re

from .approval import ApprovalEnvelope, ApprovalError, approval_digest, verify_representation_approval
from .models import ComponentType, ValueGrammar
from .model_profiles import _si_token
from .value_parser import parse_quantity


_ADAPTER = "m2-netlist-adapter-v1"
_APPROVAL = "m2-execution-approval-v1"
_CONDITION = "m2-analysis-condition-v1"


class ACSweep(str, Enum):
    DECADE = "dec"
    OCTAVE = "oct"
    LINEAR = "lin"


def _scalar(value, field, sign=None):
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an exact SI decimal string")
    parsed = parse_quantity(value, "V", ValueGrammar.SI)  # syntax carrier; condition owns its dimensions
    if parsed.quantity is None:
        raise ValueError(f"{field} requires a bounded finite SI scalar")
    number = Decimal(parsed.quantity.si_value)
    if (sign == "positive" and number <= 0) or (sign == "nonnegative" and number < 0):
        raise ValueError(f"{field} has an invalid sign")
    return _si_token(number)


def _id(value, field):
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an IR identifier")
    if len(value) > 64 or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value) is None:
        raise ValueError(f"{field} must be a bounded IR identifier")


def _hash(value, field):
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError(f"{field} must be lowercase SHA-256")


def _digest(projection):
    return hashlib.sha256(json.dumps(projection, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ACCondition:
    sweep: ACSweep
    points: int
    start_frequency: str
    stop_frequency: str

    def __post_init__(self):
        if not isinstance(self.sweep, ACSweep):
            raise TypeError("sweep must be ACSweep")
        if type(self.points) is not int:
            raise TypeError("points must be a native integer")
        if self.points < (2 if self.sweep is ACSweep.LINEAR else 1):
            raise ValueError("points is outside the supported positive range")
        start = _scalar(self.start_frequency, "start_frequency", "positive")
        stop = _scalar(self.stop_frequency, "stop_frequency", "positive")
        if Decimal(start) >= Decimal(stop):
            raise ValueError("AC requires start < stop")


@dataclass(frozen=True, slots=True)
class TransientCondition:
    stop_time: str
    start_saving_time: str | None = None
    maximum_timestep: str | None = None

    def __post_init__(self):
        stop = Decimal(_scalar(self.stop_time, "stop_time", "positive"))
        if self.start_saving_time is not None:
            start = Decimal(_scalar(self.start_saving_time, "start_saving_time", "nonnegative"))
            if start >= stop:
                raise ValueError("Start saving must precede stop time")
        if self.maximum_timestep is not None:
            maximum = Decimal(_scalar(self.maximum_timestep, "maximum_timestep", "positive"))
            if maximum > stop:
                raise ValueError("Maximum timestep must not exceed stop time")


@dataclass(frozen=True, slots=True)
class DCCondition:
    sweep_source: str
    start_value: str
    stop_value: str
    step_value: str

    def __post_init__(self):
        _id(self.sweep_source, "sweep_source")
        start = Decimal(_scalar(self.start_value, "start_value"))
        stop = Decimal(_scalar(self.stop_value, "stop_value"))
        step = Decimal(_scalar(self.step_value, "step_value", "positive"))
        if start >= stop or Fraction(step) > Fraction(stop) - Fraction(start):
            raise ValueError("DC requires ascending range and step no larger than range")


def _condition_projection(condition):
    if type(condition) is ACCondition:
        return {"contract": _CONDITION, "analysis_type": "AC", "sweep": condition.sweep.value,
                "points": condition.points, "start_frequency": _scalar(condition.start_frequency, "start_frequency"),
                "stop_frequency": _scalar(condition.stop_frequency, "stop_frequency")}
    if type(condition) is TransientCondition:
        start = None if condition.start_saving_time is None else _scalar(condition.start_saving_time, "start_saving_time")
        # Saving from zero is the default: equivalent reviewed choices compose
        # one canonical syntax, without an unnecessary positional placeholder.
        if start == "0":
            start = None
        return {"contract": _CONDITION, "analysis_type": "TRAN", "stop_time": _scalar(condition.stop_time, "stop_time"),
                "start_saving_time": start,
                "maximum_timestep": None if condition.maximum_timestep is None else _scalar(condition.maximum_timestep, "maximum_timestep")}
    if type(condition) is DCCondition:
        return {"contract": _CONDITION, "analysis_type": "DC", "sweep_source": condition.sweep_source,
                "start_value": _scalar(condition.start_value, "start_value"),
                "stop_value": _scalar(condition.stop_value, "stop_value"), "step_value": _scalar(condition.step_value, "step_value")}
    raise TypeError("condition must be a supported typed AC/Transient/DC condition")


def condition_digest(condition) -> str:
    """Exact numeric equivalence; default zero saving start canonicalizes to null."""
    return _digest(_condition_projection(condition))


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    condition: ACCondition | TransientCondition | DCCondition
    target_net: str | None = None
    reference_net: str | None = None
    comparison_net: str | None = None
    requested_point: str | None = None
    measurements: tuple[str, ...] = ()

    def __post_init__(self):
        kind = _condition_projection(self.condition)["analysis_type"]
        for field in ("target_net", "reference_net", "comparison_net"):
            if getattr(self, field) is not None:
                _id(getattr(self, field), field)
        if self.requested_point is not None:
            if kind != "DC":
                raise ValueError("Requested point is only supported for DC")
            point = Decimal(_scalar(self.requested_point, "requested_point"))
            if not Decimal(self.condition.start_value) <= point <= Decimal(self.condition.stop_value):
                raise ValueError("Requested point is outside the DC sweep")
        allowed = {"AC": {"Gain", "-3 dB Bandwidth"}, "TRAN": {"Voltage Gain", "Output Swing", "Rise Time", "Fall Time", "Overshoot", "Settling Time"},
                   "DC": {"Minimum", "Maximum", "Value at Sweep Point", "Difference", "Absolute Difference", "Matching Error"}}[kind]
        if type(self.measurements) is not tuple or any(not isinstance(v, str) for v in self.measurements):
            raise TypeError("measurements must be an immutable tuple of names")
        if len(set(self.measurements)) != len(self.measurements) or not set(self.measurements) <= allowed:
            raise ValueError("Measurements must be unique supported names for this analysis")


def _request_digest(request, mapping_sha256):
    if not isinstance(request, AnalysisRequest):
        raise TypeError("request must be AnalysisRequest")
    return _digest({"contract": "m2-analysis-request-v1", "condition": _condition_projection(request.condition),
                    "target_net": request.target_net, "reference_net": request.reference_net,
                    "comparison_net": request.comparison_net,
                    "requested_point": None if request.requested_point is None else _scalar(request.requested_point, "requested_point"),
                    "measurements": sorted(request.measurements), "mapping_sha256": mapping_sha256})


def _request_view(document, export_result, request):
    """Resolve exact IR IDs only; never labels, uploaded names or RAW guesses."""
    _request_digest(request, export_result.provenance.mapping_sha256)
    nets, elements = dict(export_result.net_map), dict(export_result.element_map)
    traces = []
    for field in ("target_net", "reference_net", "comparison_net"):
        identity = getattr(request, field)
        if identity is not None:
            if identity not in nets:
                raise ApprovalError("REQUEST_TARGET_UNKNOWN", field, "Requested IR net does not exist.")
            traces.append((field, identity, "V(" + nets[identity] + ")"))
    condition = request.condition
    source = None
    if type(condition) is DCCondition:
        component = next((c for c in document.components if c.id == condition.sweep_source), None)
        if component is None or component.type not in (ComponentType.VOLTAGE_SOURCE, ComponentType.CURRENT_SOURCE):
            raise ApprovalError("DC_SOURCE_UNSUPPORTED", "sweep_source", "Select an exact independent source IR ID.")
        source = elements[component.id]
        prefix = "V" if component.type is ComponentType.VOLTAGE_SOURCE else "I"
        if re.fullmatch(prefix + r"_[0-9]{4,}", source) is None:
            raise ApprovalError("DC_SOURCE_UNSUPPORTED", "element_map", "Mapped source token is not generated safely.")
    # Up to 128 digits and ±300 exponent are admitted by M1. A local precision
    # of 1024 covers exact scaling/subtraction in existing builders, independent
    # of caller context. No typed value or digest ever uses a float.
    from ac_analysis import build_ac_directive
    from transient_analysis import build_transient_directive
    from dc_analysis import build_dc_directive
    with localcontext(Context(prec=1024)):
        values = _condition_projection(condition)
        if type(condition) is ACCondition:
            sweep = {ACSweep.DECADE: "Decade", ACSweep.OCTAVE: "Octave", ACSweep.LINEAR: "Linear"}[condition.sweep]
            directive = build_ac_directive(sweep, condition.points, values["start_frequency"], values["stop_frequency"])
        elif type(condition) is TransientCondition:
            directive = build_transient_directive(values["stop_time"], values["start_saving_time"] or "", values["maximum_timestep"] or "")
        else:
            directive = build_dc_directive(source, values["start_value"], values["stop_value"], values["step_value"])
    _check_directive(directive, condition, source, values)
    return directive, tuple(traces), None if source is None else (condition.sweep_source, source)


def _check_directive(directive, condition, source, values):
    """Check fixed token shape and exact numeric equality after builder reuse."""
    if not isinstance(directive, str) or not directive.isascii():
        raise ValueError("Directive must be controlled ASCII text")
    tokens = directive.split(" ")
    if any(not token or any(c.isspace() for c in token) for token in tokens):
        raise ValueError("Directive must use single spaces and no control characters")
    if type(condition) is ACCondition:
        prefix = [".ac", condition.sweep.value, str(condition.points)]
        expected = [values["start_frequency"], values["stop_frequency"]]
    elif type(condition) is DCCondition:
        prefix = [".dc", source]
        expected = [values["start_value"], values["stop_value"], values["step_value"]]
    else:
        prefix = [".tran"]
        if values["start_saving_time"] is None and values["maximum_timestep"] is None:
            expected = [values["stop_time"]]
        else:
            expected = ["0", values["stop_time"], values["start_saving_time"] or "0"]
            if values["maximum_timestep"] is not None:
                expected.append(values["maximum_timestep"])
    if tokens[:len(prefix)] != prefix or len(tokens) != len(prefix) + len(expected):
        raise ValueError("Directive differs from the approved token structure")
    for token, value in zip(tokens[len(prefix):], expected):
        parsed = parse_quantity(token, "V", ValueGrammar.SPICE)
        if parsed.quantity is None or Decimal(parsed.quantity.si_value) != Decimal(value):
            raise ValueError("Directive token is unbounded or differs from the exact approved value")


@dataclass(frozen=True, slots=True)
class ExecutionApproval:
    """Adapter-owned condition approval; not an IR ApprovalScope/technical state."""
    contract_version: str
    adapter_contract: str
    approved: bool
    representation_approval_sha256: str
    base_netlist_sha256: str
    request_sha256: str

    def __post_init__(self):
        _id(self.contract_version, "contract_version")
        _id(self.adapter_contract, "adapter_contract")
        if type(self.approved) is not bool:
            raise TypeError("approved must be a native bool")
        for field in ("representation_approval_sha256", "base_netlist_sha256", "request_sha256"):
            _hash(getattr(self, field), field)


def execution_approval_digest(approval: ExecutionApproval) -> str:
    if not isinstance(approval, ExecutionApproval):
        raise TypeError("approval must be ExecutionApproval")
    return _digest({"contract_version": approval.contract_version, "adapter_contract": approval.adapter_contract,
                    "approved": approval.approved, "representation_approval_sha256": approval.representation_approval_sha256,
                    "base_netlist_sha256": approval.base_netlist_sha256, "request_sha256": approval.request_sha256})


def make_execution_approval(document, export_result, circuit_approval, representation_approval, request, *,
                              approved: bool, model_context: tuple[str, str]) -> ExecutionApproval:
    if type(approved) is not bool:
        raise TypeError("approved must be a native bool")
    verify_representation_approval(document, export_result, circuit_approval, representation_approval, model_context=model_context)
    _request_view(document, export_result, request)
    if not approved:
        raise ApprovalError("APPROVAL_NOT_GRANTED", "approved", "Explicit condition approval is required.")
    return ExecutionApproval(_APPROVAL, _ADAPTER, approved, approval_digest(representation_approval),
                             export_result.provenance.base_netlist_sha256,
                             _request_digest(request, export_result.provenance.mapping_sha256))


def verify_execution_approval(document, export_result, circuit_approval, representation_approval, request,
                                execution_approval, *, model_context: tuple[str, str]) -> None:
    if not isinstance(execution_approval, ExecutionApproval):
        raise TypeError("execution_approval must be ExecutionApproval")
    if execution_approval.contract_version != _APPROVAL or execution_approval.adapter_contract != _ADAPTER:
        raise ApprovalError("EXECUTION_VERSION_UNSUPPORTED", "contract_version", "Unsupported execution contract.")
    if not execution_approval.approved:
        raise ApprovalError("APPROVAL_NOT_GRANTED", "approved", "Conditions were not approved.")
    verify_representation_approval(document, export_result, circuit_approval, representation_approval, model_context=model_context)
    _request_view(document, export_result, request)
    for field, expected in (("representation_approval_sha256", approval_digest(representation_approval)),
                            ("base_netlist_sha256", export_result.provenance.base_netlist_sha256),
                            ("request_sha256", _request_digest(request, export_result.provenance.mapping_sha256))):
        if getattr(execution_approval, field) != expected:
            raise ApprovalError("EXECUTION_BINDING_MISMATCH", field, "Execution approval is stale.")


@dataclass(frozen=True, slots=True)
class ExecutionIssue:
    code: str
    field: str | None
    message: str

    def __post_init__(self):
        _id(self.code, "code")
        if self.field is not None and not isinstance(self.field, str):
            raise TypeError("field must be a string or None")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("message must be a nonempty string")


@dataclass(frozen=True, slots=True)
class ExecutionProvenance:
    adapter_contract: str
    exporter_contract: str
    model_registry_version: str
    model_registry_sha256: str
    document_sha256: str
    electrical_sha256: str
    validation_sha256: str
    circuit_approval_sha256: str
    mapping_sha256: str
    base_netlist_sha256: str
    representation_approval_sha256: str
    request_sha256: str
    execution_approval_sha256: str
    execution_netlist_sha256: str

    def __post_init__(self):
        for field in ("adapter_contract", "exporter_contract", "model_registry_version"):
            _id(getattr(self, field), field)
        for field in ("model_registry_sha256", "document_sha256", "electrical_sha256", "validation_sha256",
                      "circuit_approval_sha256", "mapping_sha256", "base_netlist_sha256",
                      "representation_approval_sha256", "request_sha256", "execution_approval_sha256", "execution_netlist_sha256"):
            _hash(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class ExecutionArtifact:
    spice_text: str
    directive: str
    trace_map: tuple[tuple[str, str, str], ...]
    sweep_source_map: tuple[str, str] | None
    provenance: ExecutionProvenance

    def __post_init__(self):
        if not isinstance(self.spice_text, str) or not isinstance(self.directive, str):
            raise TypeError("Artifact text/directive must be strings")
        if not isinstance(self.provenance, ExecutionProvenance):
            raise TypeError("provenance must be ExecutionProvenance")
        if type(self.trace_map) is not tuple or any(type(row) is not tuple or len(row) != 3
                or any(not isinstance(v, str) for v in row) for row in self.trace_map):
            raise TypeError("trace_map must be immutable role/IR ID/trace triples")
        if self.sweep_source_map is not None and (type(self.sweep_source_map) is not tuple
                or len(self.sweep_source_map) != 2 or any(not isinstance(v, str) for v in self.sweep_source_map)):
            raise TypeError("sweep_source_map must be an immutable pair or None")

    @property
    def netlist_bytes(self):
        return self.spice_text.encode("utf-8")


@dataclass(frozen=True, slots=True)
class CompositionResult:
    artifact: ExecutionArtifact | None
    issues: tuple[ExecutionIssue, ...]

    def __post_init__(self):
        if self.artifact is not None and not isinstance(self.artifact, ExecutionArtifact):
            raise TypeError("artifact must be ExecutionArtifact or None")
        if type(self.issues) is not tuple or any(not isinstance(i, ExecutionIssue) for i in self.issues):
            raise TypeError("issues must be an immutable issue tuple")
        if (self.artifact is None) != bool(self.issues):
            raise ValueError("Composition is complete success or blocked without artifact")


def compose_execution_netlist(document, export_result, circuit_approval, representation_approval, request,
                                execution_approval, *, model_context: tuple[str, str]) -> CompositionResult:
    """Fail closed with no artifact; no file I/O and no implicit review action."""
    try:
        verify_execution_approval(document, export_result, circuit_approval, representation_approval, request,
                                    execution_approval, model_context=model_context)
        directive, traces, source_map = _request_view(document, export_result, request)
        text = export_result.spice_text
        # Checked byte editor: exact regenerated base only, not general replacement.
        lines = text.splitlines()
        if (not text.isascii() or "\r" in text or not text.endswith(".end\n")
                or lines.count(".end") != 1 or any(line.startswith(".") and not line.startswith(".model ")
                    and line != ".end" for line in lines)):
            raise ApprovalError("BASE_TERMINATION_INVALID", "spice_text", "Base termination/directives violate the contract.")
        if "\n" in directive or "\r" in directive or not directive.startswith((".ac ", ".tran ", ".dc ")):
            raise ApprovalError("DIRECTIVE_INVALID", "condition", "Builder returned unsupported directive syntax.")
        execution_text = text[:-len(".end\n")] + directive + "\n.end\n"
        base = export_result.provenance
        provenance = ExecutionProvenance(_ADAPTER, base.exporter_contract, base.model_registry_version, base.model_registry_sha256,
            base.document_sha256, base.electrical_sha256, base.validation_sha256, approval_digest(circuit_approval),
            base.mapping_sha256, base.base_netlist_sha256, approval_digest(representation_approval),
            _request_digest(request, base.mapping_sha256), execution_approval_digest(execution_approval),
            hashlib.sha256(execution_text.encode("utf-8")).hexdigest())
        return CompositionResult(ExecutionArtifact(execution_text, directive, traces, source_map, provenance), ())
    except ApprovalError as error:
        return CompositionResult(None, (ExecutionIssue(error.code, error.field, str(error)),))
    except (TypeError, ValueError) as error:
        return CompositionResult(None, (ExecutionIssue("EXECUTION_INPUT_INVALID", None, str(error)),))
