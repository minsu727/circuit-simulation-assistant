"""M3 observation sidecar records. No electrical graph or human approval."""
from dataclasses import dataclass, field
from enum import Enum
from circuit_ir.models import ComponentType, PinRole

INTAKE_VERSION = "m3-intake-1"
OBSERVATION_VERSION = "m3-observations-1"


class ObservationKind(str, Enum):
    SYMBOL = "symbol"
    TEXT = "text"
    LABEL = "label"
    SUPPLY_LABEL = "supply_label"
    PIN = "pin"
    WIRE = "wire_segment"
    JUNCTION = "junction"
    CROSSING = "crossing"
    GROUND = "ground"
    UNKNOWN = "unknown_symbol"
    CONTACT = "contact_candidate"


class Classification(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
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


class UncertaintyState(str, Enum):
    PROVISIONAL = "provisional"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"
    UNREADABLE = "unreadable"


class Reason(str, Enum):
    SYMBOL_UNCLEAR = "symbol_unclear"
    CROSSING_UNCLEAR = "crossing_unclear"
    CONTACT_UNCLEAR = "contact_unclear"
    LABEL_EQUIVALENCE = "possible_label_equivalence"
    POLARITY_UNCLEAR = "polarity_unclear"
    MOS_ROLE_UNCLEAR = "mos_role_unclear"
    BULK_MISSING = "bulk_missing"
    GROUND_UNCLEAR = "ground_unclear"
    VALUE_MISSING = "value_missing"
    TEXT_UNREADABLE = "text_unreadable"
    NOTATION_UNSUPPORTED = "notation_unsupported"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    INCOMPLETE_WIRE = "incomplete_wire"


class Notation(str, Enum):
    PRINTED = "printed_engineering"
    SPICE = "spice"
    SI = "si"
    UNRESOLVED = "unresolved"


class TextPurpose(str, Enum):
    GENERIC = "generic"
    REFERENCE = "reference"
    VALUE = "value"
    SOURCE_DC = "source_dc"
    SOURCE_AC = "source_ac"
    SOURCE_WAVEFORM = "source_waveform"
    DEVICE_WIDTH = "device_width"
    DEVICE_LENGTH = "device_length"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class Geometry:
    bbox: Box | None
    points: tuple[Point, ...]
    orientation: Orientation


@dataclass(frozen=True, slots=True)
class ValueCandidate:
    raw_scalar: str = field(repr=False)
    raw_unit: str | None = field(repr=False)
    notation: Notation
    unit: str | None
    si_value: str | None


@dataclass(frozen=True, slots=True)
class SymbolCandidate:
    classification: Classification
    component_type: ComponentType | None
    observed_name: str | None = field(repr=False)
    reference_text: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class TextCandidate:
    raw_text: str = field(repr=False)
    purpose: TextPurpose
    component_ref: str | None
    value: ValueCandidate | None


@dataclass(frozen=True, slots=True)
class LabelCandidate:
    raw_text: str = field(repr=False)
    attachment_ref: str | None


@dataclass(frozen=True, slots=True)
class PinCandidate:
    component_ref: str
    role: PinRole


@dataclass(frozen=True, slots=True)
class WireCandidate:
    pass


@dataclass(frozen=True, slots=True)
class JunctionCandidate:
    wire_refs: tuple[str, ...]
    interpretation: str


@dataclass(frozen=True, slots=True)
class GroundCandidate:
    style: str


@dataclass(frozen=True, slots=True)
class UnknownCandidate:
    observed_name: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class ContactCandidate:
    refs: tuple[str, str]
    interpretation: str


Payload = (SymbolCandidate | TextCandidate | LabelCandidate | PinCandidate |
           WireCandidate | JunctionCandidate | GroundCandidate | UnknownCandidate | ContactCandidate)


@dataclass(frozen=True, slots=True)
class Confidence:
    score: float | None
    basis: str
    calibrated: bool


@dataclass(frozen=True, slots=True)
class Alternative:
    id: str
    payload: Payload


@dataclass(frozen=True, slots=True)
class Uncertainty:
    state: UncertaintyState
    reasons: tuple[Reason, ...]
    related_refs: tuple[str, ...]
    alternatives: tuple[Alternative, ...]


@dataclass(frozen=True, slots=True)
class Observation:
    id: str
    provider_id: str = field(repr=False)
    kind: ObservationKind
    source_sha256: str
    geometry: Geometry | None
    payload: Payload
    confidence: Confidence
    uncertainty: Uncertainty


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    provider_id: str
    provider_version: str | None
    model_id: str | None
    model_version: str | None
    adapter_version: str
    catalog_version: str
    prompt_version: str | None
    mode: str


@dataclass(frozen=True, slots=True)
class ObservationSet:
    version: str
    source_identity_sha256: str
    source_sha256: str
    normalized_sha256: str
    transform_sha256: str
    provider: ProviderInfo
    coverage: str
    extraction_key: str
    response_sha256: str
    extraction_id: str
    observations: tuple[Observation, ...]


@dataclass(frozen=True, slots=True)
class ObservationResult:
    observation_set: ObservationSet | None
    diagnostics: tuple[Diagnostic, ...]


def diagnostic(code, field):
    """Bounded, data-free diagnostics; never stringify an untrusted exception."""
    return Diagnostic(code, field, "Input does not satisfy the " + code + " contract.")
