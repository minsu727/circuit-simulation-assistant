"""Disposable, unapproved M3D topology views; never authoritative Circuit IR."""
from dataclasses import dataclass
from enum import Enum
from . import models as m

TOPOLOGY_VERSION = "m3-topology-1"


class TopologyState(str, Enum):
    RESOLVED = "RESOLVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class TopologyLimits:
    max_claims: int = 8192
    max_ambiguities: int = 64
    max_alternatives: int = 8
    max_hypotheses: int = 64
    max_pair_checks: int = 100_000
    max_evidence_refs: int = 65_536
    ambiguity_depth: int = 1
    near_distance_px: float = 2.0

    def __post_init__(self):
        import math
        for value in (self.max_claims,self.max_ambiguities,self.max_alternatives,self.max_hypotheses,self.max_pair_checks,self.max_evidence_refs):
            if type(value) is not int or value <= 0: raise ValueError("Positive integer budgets required.")
        if type(self.ambiguity_depth) is not int or self.ambiguity_depth != 1:
            raise ValueError("Only flat local ambiguities are supported.")
        if type(self.near_distance_px) not in (int,float) or not math.isfinite(self.near_distance_px) or not 0 <= self.near_distance_px <= 12:
            raise ValueError("Review distance must be finite and within 0–12 original pixels.")


@dataclass(frozen=True, slots=True)
class CandidateComponent:
    observation_id: str
    payload: m.SymbolCandidate | m.UnknownCandidate
    text_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateTerminal:
    observation_id: str
    component_observation_id: str
    role: m.PinRole
    role_alternatives: tuple[m.PinRole, ...]


@dataclass(frozen=True, slots=True)
class CandidateNet:
    id: str
    wire_observation_ids: tuple[str, ...]
    ground_observation_ids: tuple[str, ...]
    label_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TopologyClaim:
    id: str
    kind: str
    subjects: tuple[str, ...]
    evidence: tuple[str, ...]
    decision: str
    net_id: str | None = None
    role: m.PinRole | None = None


@dataclass(frozen=True, slots=True)
class TopologyOption:
    id: str
    meaning: str
    subjects: tuple[str, ...]
    evidence: tuple[str, ...]
    source_alternative_id: str | None = None


@dataclass(frozen=True, slots=True)
class TopologyAmbiguity:
    id: str
    kind: str
    subjects: tuple[str, ...]
    evidence: tuple[str, ...]
    options: tuple[TopologyOption, ...]


@dataclass(frozen=True, slots=True)
class TopologyIssue:
    code: str
    scope: str
    observation_ids: tuple[str, ...]
    requires_review: bool
    missing: bool


@dataclass(frozen=True, slots=True)
class TopologyHypothesis:
    version: str
    source_identity_sha256: str
    source_sha256: str
    observation_response_sha256: str
    extraction_id: str
    limits: TopologyLimits
    topology_state: TopologyState
    conversion_state: TopologyState
    candidate_state: str
    review_required: bool
    admission_state: str
    hypothesis_count: int
    components: tuple[CandidateComponent, ...]
    terminals: tuple[CandidateTerminal, ...]
    nets: tuple[CandidateNet, ...]
    claims: tuple[TopologyClaim, ...]
    ambiguities: tuple[TopologyAmbiguity, ...]
    issues: tuple[TopologyIssue, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class TopologyResult:
    hypothesis: TopologyHypothesis | None
    diagnostics: tuple[m.Diagnostic, ...]
