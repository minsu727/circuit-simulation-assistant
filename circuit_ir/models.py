"""Immutable 0.2-draft1 records; construction does not validate a circuit."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Literal


SCHEMA_VERSION = "0.2-draft1"
Unit = Literal["ohm", "F", "H", "V", "A", "Hz", "s", "deg", "m"]


class ComponentType(str, Enum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"
    VOLTAGE_SOURCE = "voltage_source"
    CURRENT_SOURCE = "current_source"
    NMOS = "nmos"
    PMOS = "pmos"
    UNKNOWN = "unknown"


class PinRole(str, Enum):
    A = "a"
    B = "b"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    DRAIN = "drain"
    GATE = "gate"
    SOURCE = "source"
    BULK = "bulk"
    UNKNOWN = "unknown"


class IssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    AMBIGUOUS = "AMBIGUOUS"
    CONFIRMED = "CONFIRMED"


class WireValidationStatus(str, Enum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"
    REVIEWED = "reviewed"


class TechnicalState(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    INVALID = "INVALID"
    AMBIGUOUS = "AMBIGUOUS"
    VALID = "VALID"


class NetRole(str, Enum):
    GROUND = "GROUND"
    NORMAL = "NORMAL"


class WaveformKind(str, Enum):
    NONE = "none"
    SINE = "sine"
    PULSE = "pulse"


class ValueGrammar(str, Enum):
    SPICE = "spice"
    SI = "si"
    MANUAL = "manual"
    UNRESOLVED = "unresolved"


class ConfidenceBasis(str, Enum):
    PROVIDER_SCORE = "provider_score"
    HEURISTIC = "heuristic"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class Origin(str, Enum):
    IMAGE = "image"
    MANUAL = "manual"


class VisualKind(str, Enum):
    SYMBOL = "symbol"
    PIN = "pin"
    WIRE = "wire"
    JUNCTION = "junction"
    GROUND = "ground"
    LABEL = "label"
    TEXT = "text"
    UNKNOWN = "unknown"


class Orientation(str, Enum):
    R0 = "r0"
    R90 = "r90"
    R180 = "r180"
    R270 = "r270"
    R0_MIRROR = "r0_mirror"
    R90_MIRROR = "r90_mirror"
    R180_MIRROR = "r180_mirror"
    R270_MIRROR = "r270_mirror"
    UNKNOWN = "unknown"


class AmbiguityKind(str, Enum):
    SYMBOL_TYPE = "symbol_type"
    VALUE = "value"
    CROSSING = "crossing"
    WIRE_GAP = "wire_gap"
    LABEL_ATTACHMENT = "label_attachment"
    PIN_MAPPING = "pin_mapping"
    BODY_CONNECTION = "body_connection"


class AmbiguityStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


def _string(value: object, name: str, *, minimum: int = 0,
            maximum: int | None = None) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if len(value) < minimum or (maximum is not None and len(value) > maximum):
        raise ValueError(f"{name} has an invalid length")


def _id(value: object, name: str) -> None:
    _string(value, name, minimum=1, maximum=64)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value) is None:
        raise ValueError(f"{name} must be an opaque Circuit IR ID")


def _optional_id(value: object, name: str) -> None:
    if value is not None:
        _id(value, name)


def _instance(value: object, cls: type, name: str) -> None:
    if not isinstance(value, cls):
        raise TypeError(f"{name} must be {cls.__name__}")


def _optional_instance(value: object, cls: type, name: str) -> None:
    if value is not None:
        _instance(value, cls, name)


def _integer(value: object, name: str, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer, not bool")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _number(value: object, name: str) -> None:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be an int or float, not bool")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _tuple(value: object, cls: type, name: str) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an immutable tuple")
    for item in value:
        _instance(item, cls, name)


def _ids(value: object, name: str) -> None:
    _tuple(value, str, name)
    for item in value:
        _id(item, name)


def _parameters(value: object) -> tuple[tuple[str, Quantity], ...]:
    """Keep JSON object entries immutable and independent of key insertion order."""
    _tuple(value, tuple, "parameters")
    keys = []
    for pair in value:
        if len(pair) != 2:
            raise ValueError("parameters must contain (key, quantity) pairs")
        key, quantity = pair
        _string(key, "parameter key")
        _instance(quantity, Quantity, "parameter value")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError("parameter keys must be unique")
    return tuple(sorted(value, key=lambda pair: pair[0]))


@dataclass(frozen=True, slots=True)
class Confidence:
    score: int | float | None
    basis: ConfidenceBasis
    calibrated: bool

    def __post_init__(self) -> None:
        if self.score is not None:
            _number(self.score, "score")
            if self.score > 1:
                raise ValueError("score must be in [0, 1]")
        _instance(self.basis, ConfidenceBasis, "basis")
        _instance(self.calibrated, bool, "calibrated")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: int | float
    y: int | float
    width: int | float
    height: int | float

    def __post_init__(self) -> None:
        for name in ("x", "y", "width", "height"):
            _number(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class PixelPoint:
    x: int | float
    y: int | float

    def __post_init__(self) -> None:
        _number(self.x, "x")
        _number(self.y, "y")


@dataclass(frozen=True, slots=True)
class Metadata:
    circuit_id: str
    revision: int
    origin: Origin
    catalog_version: str

    def __post_init__(self) -> None:
        _id(self.circuit_id, "circuit_id")
        _integer(self.revision, "revision")
        _instance(self.origin, Origin, "origin")
        _string(self.catalog_version, "catalog_version", minimum=1, maximum=64)


@dataclass(frozen=True, slots=True)
class SourceImageReference:
    asset_id: str
    sha256: str
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        _id(self.asset_id, "asset_id")
        _string(self.sha256, "sha256")
        if re.fullmatch(r"[a-f0-9]{64}", self.sha256) is None:
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        _integer(self.width_px, "width_px", 1)
        _integer(self.height_px, "height_px", 1)


@dataclass(frozen=True, slots=True)
class Quantity:
    literal: str | None
    si_value: str | None
    unit: Unit
    grammar: ValueGrammar

    def __post_init__(self) -> None:
        for name in ("literal", "si_value"):
            value = getattr(self, name)
            if value is not None:
                _string(value, name, maximum=128)
        _string(self.unit, "unit")
        if self.unit not in ("ohm", "F", "H", "V", "A", "Hz", "s", "deg", "m"):
            raise ValueError("unit is not supported by 0.2-draft1")
        _instance(self.grammar, ValueGrammar, "grammar")


@dataclass(frozen=True, slots=True)
class ACConfiguration:
    magnitude: Quantity
    phase: Quantity

    def __post_init__(self) -> None:
        _instance(self.magnitude, Quantity, "magnitude")
        _instance(self.phase, Quantity, "phase")


@dataclass(frozen=True, slots=True)
class Waveform:
    kind: WaveformKind
    parameters: tuple[tuple[str, Quantity], ...]

    def __post_init__(self) -> None:
        _instance(self.kind, WaveformKind, "kind")
        object.__setattr__(self, "parameters", _parameters(self.parameters))


@dataclass(frozen=True, slots=True)
class SourceConfiguration:
    dc: Quantity | None
    ac: ACConfiguration | None
    waveform: Waveform

    def __post_init__(self) -> None:
        _optional_instance(self.dc, Quantity, "dc")
        _optional_instance(self.ac, ACConfiguration, "ac")
        _instance(self.waveform, Waveform, "waveform")


@dataclass(frozen=True, slots=True)
class Component:
    id: str
    type: ComponentType
    pin_ids: tuple[str, ...]
    value: Quantity | None
    model_ref: str | None
    parameters: tuple[tuple[str, Quantity], ...]
    source: SourceConfiguration | None
    visual_ref: str | None

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _instance(self.type, ComponentType, "type")
        _ids(self.pin_ids, "pin_ids")
        _optional_instance(self.value, Quantity, "value")
        _optional_id(self.model_ref, "model_ref")
        object.__setattr__(self, "parameters", _parameters(self.parameters))
        _optional_instance(self.source, SourceConfiguration, "source")
        _optional_id(self.visual_ref, "visual_ref")


@dataclass(frozen=True, slots=True)
class Pin:
    id: str
    component_id: str
    role: PinRole
    visual_ref: str | None

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _id(self.component_id, "component_id")
        _instance(self.role, PinRole, "role")
        _optional_id(self.visual_ref, "visual_ref")


@dataclass(frozen=True, slots=True)
class Net:
    id: str
    is_ground: bool

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _instance(self.is_ground, bool, "is_ground")

    @property
    def role(self) -> NetRole:
        return NetRole.GROUND if self.is_ground else NetRole.NORMAL


@dataclass(frozen=True, slots=True)
class Connection:
    pin_id: str
    net_id: str
    visual_refs: tuple[str, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        _id(self.pin_id, "pin_id")
        _id(self.net_id, "net_id")
        _ids(self.visual_refs, "visual_refs")
        _instance(self.confidence, Confidence, "confidence")


@dataclass(frozen=True, slots=True)
class Label:
    id: str
    text: str
    scope: Literal["flat"]
    net_id: str | None
    visual_ref: str | None

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _string(self.text, "text", minimum=1, maximum=64)
        _string(self.scope, "scope")
        if self.scope != "flat":
            raise ValueError("scope must be flat")
        _optional_id(self.net_id, "net_id")
        _optional_id(self.visual_ref, "visual_ref")


@dataclass(frozen=True, slots=True)
class VisualEntity:
    id: str
    kind: VisualKind
    bbox: BoundingBox | None
    position: PixelPoint | None
    orientation: Orientation
    points: tuple[PixelPoint, ...]
    text: str | None
    method: str
    confidence: Confidence

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _instance(self.kind, VisualKind, "kind")
        _optional_instance(self.bbox, BoundingBox, "bbox")
        _optional_instance(self.position, PixelPoint, "position")
        _instance(self.orientation, Orientation, "orientation")
        _tuple(self.points, PixelPoint, "points")
        if self.text is not None:
            _string(self.text, "text", maximum=256)
        _string(self.method, "method", minimum=1, maximum=64)
        _instance(self.confidence, Confidence, "confidence")


@dataclass(frozen=True, slots=True)
class VisualProvenance:
    coordinate_space: Literal["original_pixels"]
    entities: tuple[VisualEntity, ...]

    def __post_init__(self) -> None:
        _string(self.coordinate_space, "coordinate_space")
        if self.coordinate_space != "original_pixels":
            raise ValueError("coordinate_space must be original_pixels")
        _tuple(self.entities, VisualEntity, "entities")


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    description: str

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _string(self.description, "description", minimum=1, maximum=256)


@dataclass(frozen=True, slots=True)
class Ambiguity:
    id: str
    kind: AmbiguityKind
    target_refs: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    state: AmbiguityStatus
    selected_candidate_id: str | None
    resolution_note: str | None

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _instance(self.kind, AmbiguityKind, "kind")
        _ids(self.target_refs, "target_refs")
        _tuple(self.candidates, Candidate, "candidates")
        _instance(self.state, AmbiguityStatus, "state")
        _optional_id(self.selected_candidate_id, "selected_candidate_id")
        if self.resolution_note is not None:
            _string(self.resolution_note, "resolution_note", maximum=256)


@dataclass(frozen=True, slots=True)
class ImportedFinding:
    """An archival finding is data, not a fresh validation result."""

    id: str
    code: str
    severity: IssueSeverity
    target_refs: tuple[str, ...]
    message: str
    visual_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _id(self.id, "id")
        _id(self.code, "code")
        _instance(self.severity, IssueSeverity, "severity")
        _ids(self.target_refs, "target_refs")
        _string(self.message, "message", minimum=1, maximum=512)
        _ids(self.visual_refs, "visual_refs")


@dataclass(frozen=True, slots=True)
class ImportedValidationState:
    """A reviewed snapshot never supplies human approval or execution permission."""

    status: WireValidationStatus
    validated_revision: int | None
    ruleset_version: str | None
    findings: tuple[ImportedFinding, ...]

    def __post_init__(self) -> None:
        _instance(self.status, WireValidationStatus, "status")
        if self.validated_revision is not None:
            _integer(self.validated_revision, "validated_revision")
        if self.ruleset_version is not None:
            _string(self.ruleset_version, "ruleset_version")
        _tuple(self.findings, ImportedFinding, "findings")


@dataclass(frozen=True, slots=True)
class CircuitDocument:
    """Ordered source records; no graph, inferred defaults or approval state.

    Equality includes array order and provenance; parameter object keys have
    canonical order. Future electrical equivalence is a separate projection.
    Edits use dataclasses.replace.
    """

    schema_version: Literal["0.2-draft1"]
    metadata: Metadata
    source_image_reference: SourceImageReference | None
    components: tuple[Component, ...]
    pins: tuple[Pin, ...]
    nets: tuple[Net, ...]
    connections: tuple[Connection, ...]
    labels: tuple[Label, ...]
    visual: VisualProvenance
    confidence: Confidence
    ambiguities: tuple[Ambiguity, ...]
    warnings: tuple[str, ...]
    validation_state: ImportedValidationState

    def __post_init__(self) -> None:
        _string(self.schema_version, "schema_version")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported Circuit IR schema_version")
        _instance(self.metadata, Metadata, "metadata")
        _optional_instance(self.source_image_reference, SourceImageReference,
                           "source_image_reference")
        for name, cls in (("components", Component), ("pins", Pin), ("nets", Net),
                          ("connections", Connection), ("labels", Label),
                          ("ambiguities", Ambiguity)):
            _tuple(getattr(self, name), cls, name)
        _instance(self.visual, VisualProvenance, "visual")
        _instance(self.confidence, Confidence, "confidence")
        _ids(self.warnings, "warnings")
        _instance(self.validation_state, ImportedValidationState, "validation_state")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Runtime diagnosis record only; no validation pipeline or approval behavior."""

    issue_id: str
    severity: IssueSeverity
    code: str
    message: str
    target_refs: tuple[str, ...]
    entity_type: str | None
    entity_id: str | None
    field: str | None
    suggested_action: str | None
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        _id(self.issue_id, "issue_id")
        _instance(self.severity, IssueSeverity, "severity")
        _id(self.code, "code")
        _string(self.message, "message", minimum=1, maximum=512)
        _ids(self.target_refs, "target_refs")
        _optional_id(self.entity_id, "entity_id")
        for name in ("entity_type", "field", "suggested_action"):
            value = getattr(self, name)
            if value is not None:
                _string(value, name)
        _ids(self.provenance, "provenance")

    @property
    def blocking(self) -> bool:
        return self.severity in (IssueSeverity.ERROR, IssueSeverity.AMBIGUOUS)


@dataclass(frozen=True, slots=True)
class ValueParseResult:
    quantity: Quantity | None
    issues: tuple[ValidationIssue, ...]

    def __post_init__(self) -> None:
        _optional_instance(self.quantity, Quantity, "quantity")
        _tuple(self.issues, ValidationIssue, "issues")
