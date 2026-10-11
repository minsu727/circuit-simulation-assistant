"""Immutable M3E sidecar data. No imported flag is execution authority."""
from dataclasses import dataclass
from enum import Enum
from circuit_ir import models as ir
from .models import Diagnostic
from .topology_models import TopologyHypothesis

REVIEW_VERSION = 'm3-review-1'
PROMOTION_VERSION = 'm3-promotion-1'
ADMISSION_VERSION = 'm3-image-admission-1'


class ReviewDecision(str, Enum):
    CONFIRM = 'CONFIRM'


@dataclass(frozen=True, slots=True)
class SetComponentType:
    component_id: str
    component_type: ir.ComponentType


@dataclass(frozen=True, slots=True)
class SetReference:
    component_id: str
    reference: str


@dataclass(frozen=True, slots=True)
class SetValue:
    component_id: str
    value: ir.Quantity


@dataclass(frozen=True, slots=True)
class SetSource:
    component_id: str
    source: ir.SourceConfiguration


@dataclass(frozen=True, slots=True)
class SetMOSModel:
    component_id: str
    profile_id: str
    width: ir.Quantity
    length: ir.Quantity


@dataclass(frozen=True, slots=True)
class SetTerminalRole:
    pin_id: str
    role: ir.PinRole


@dataclass(frozen=True, slots=True)
class SetTerminalOwner:
    pin_id: str
    component_id: str


@dataclass(frozen=True, slots=True)
class AddTerminal:
    component_id: str
    key: str
    role: ir.PinRole


@dataclass(frozen=True, slots=True)
class ConnectPin:
    pin_id: str
    net_id: str | None


@dataclass(frozen=True, slots=True)
class ChooseTopology:
    ambiguity_id: str
    option_id: str


@dataclass(frozen=True, slots=True)
class ConfirmContact:
    observation_id: str
    connected: bool


@dataclass(frozen=True, slots=True)
class MergeNets:
    net_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SplitNet:
    net_id: str
    partitions: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class SetLabel:
    observation_id: str
    text: str
    net_id: str | None


@dataclass(frozen=True, slots=True)
class LabelEquivalence:
    observation_ids: tuple[str, ...]
    equivalent: bool


@dataclass(frozen=True, slots=True)
class SetGround:
    observation_id: str
    net_id: str | None


@dataclass(frozen=True, slots=True)
class MarkUnsupported:
    component_id: str


@dataclass(frozen=True, slots=True)
class RetainIssue:
    issue_id: str


Correction = (SetComponentType | SetReference | SetValue | SetSource | SetMOSModel |
              SetTerminalRole | SetTerminalOwner | AddTerminal | ConnectPin |
              ChooseTopology | ConfirmContact | MergeNets | SplitNet | SetLabel |
              LabelEquivalence | SetGround | MarkUnsupported | RetainIssue)


@dataclass(frozen=True, slots=True)
class ReviewedComponent:
    id: str
    component_type: ir.ComponentType | None
    reference: str | None
    value: ir.Quantity | None
    source: ir.SourceConfiguration | None
    model_ref: str | None
    parameters: tuple[tuple[str, ir.Quantity], ...]
    unsupported: bool


@dataclass(frozen=True, slots=True)
class ReviewedPin:
    id: str
    component_id: str
    role: ir.PinRole


@dataclass(frozen=True, slots=True)
class ReviewIssue:
    id: str
    code: str
    targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    components: tuple[ReviewedComponent, ...]
    pins: tuple[ReviewedPin, ...]
    memberships: tuple[tuple[str, str | None], ...]
    labels: tuple[tuple[str, str], ...]
    ground_ids: tuple[str, ...]
    resolutions: tuple[tuple[str, str], ...]
    corrected_entities: tuple[str, ...]
    retained_issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewRevision:
    number: int
    parent_digest: str | None
    snapshot: ReviewSnapshot
    issues: tuple[ReviewIssue, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    base_digest: str
    operations: tuple[Correction, ...]
    revision_digest: str


@dataclass(frozen=True, slots=True)
class ReviewConfirmation:
    version: str
    source_identity_sha256: str
    observation_sha256: str
    topology_sha256: str
    revision_sha256: str
    decision: ReviewDecision
    reviewed_claim_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class ReviewSession:
    version: str
    source_identity_sha256: str
    observation_sha256: str
    topology_sha256: str
    initial_topology: TopologyHypothesis
    events: tuple[ReviewEvent, ...]
    current: ReviewRevision
    confirmation: ReviewConfirmation | None
    digest: str


@dataclass(frozen=True, slots=True)
class ReviewResult:
    session: ReviewSession | None
    diagnostics: tuple[Diagnostic, ...]
