"""Image-origin eligibility, separate from all three mandatory M2 approvals."""
from dataclasses import dataclass, replace
from circuit_ir import models as ir
from circuit_ir.approval import _fresh_report
from .intake import canonical_json, content_digest, ImageArtifact
from .models import Diagnostic, ObservationSet, diagnostic
from .topology_models import TopologyHypothesis
from .review_models import ADMISSION_VERSION, PROMOTION_VERSION, REVIEW_VERSION, ReviewSession
from .review_serialization import decode_archive
from .promotion import PromotionResult, verify_promotion


@dataclass(frozen=True, slots=True)
class ImageOriginAdmission:
    version: str
    review_version: str
    promotion_version: str
    source_identity_sha256: str
    observation_sha256: str
    topology_sha256: str
    review_sha256: str
    revision_sha256: str
    confirmation_sha256: str
    promotion_sha256: str
    document_sha256: str
    validation_sha256: str
    validation_profile: str
    validation_ruleset: str
    digest: str


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    admission: ImageOriginAdmission | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class ImageAdmissionContext:
    image: ImageArtifact
    observations: ObservationSet
    hypothesis: TopologyHypothesis
    review: ReviewSession
    promotion: PromotionResult
    admission: ImageOriginAdmission


def admission_to_dict(a, include_digest=True):
    data = dict(version=a.version, review_version=a.review_version, promotion_version=a.promotion_version,
        source_identity_sha256=a.source_identity_sha256, observation_sha256=a.observation_sha256,
        topology_sha256=a.topology_sha256, review_sha256=a.review_sha256,
        revision_sha256=a.revision_sha256, confirmation_sha256=a.confirmation_sha256,
        promotion_sha256=a.promotion_sha256, document_sha256=a.document_sha256,
        validation_sha256=a.validation_sha256, validation_profile=a.validation_profile,
        validation_ruleset=a.validation_ruleset)
    if include_digest:
        data['digest'] = a.digest
    return data


def dump_admission(a):
    return canonical_json(admission_to_dict(a)) + '\n'


def issue_image_admission(promotion, review, *, hypothesis, observations, image):
    """Recheck the entire exact chain. Never create a review/M2 approval."""
    diagnostics = verify_promotion(promotion, review, hypothesis=hypothesis, observations=observations, image=image)
    if diagnostics:
        return AdmissionResult(None, diagnostics)
    try:
        report = _fresh_report(promotion.document)
        if report != promotion.validation or promotion.document.metadata.origin is not ir.Origin.IMAGE:
            return AdmissionResult(None, (diagnostic('ADMISSION_VALIDATION_STALE', 'validation'),))
        p = promotion.record
        a = ImageOriginAdmission(ADMISSION_VERSION, REVIEW_VERSION, PROMOTION_VERSION,
            p.source_identity_sha256, p.observation_sha256, p.topology_sha256, p.review_sha256,
            p.revision_sha256, p.confirmation_sha256, p.digest, p.document_sha256,
            p.validation_sha256, report.profile, report.ruleset_version, '')
        a = replace(a, digest=content_digest(admission_to_dict(a, False)))
        return AdmissionResult(a, ())
    except (TypeError, ValueError, KeyError, AttributeError):
        return AdmissionResult(None, (diagnostic('ADMISSION_DOCUMENT_NOT_VALID', 'validation'),))


def verify_image_admission(document, context, *, validation=None):
    """Return diagnostics; supplied digests/flags alone are never authority."""
    if type(context) is not ImageAdmissionContext:
        return (diagnostic('IMAGE_ADMISSION_REQUIRED', 'image_admission'),)
    if type(context.promotion) is not PromotionResult:
        return (diagnostic('ADMISSION_INPUT_INVALID', 'promotion'),)
    if document != context.promotion.document:
        return (diagnostic('ADMISSION_DOCUMENT_STALE', 'document'),)
    if validation is not None and validation != context.promotion.validation:
        return (diagnostic('ADMISSION_VALIDATION_STALE', 'validation'),)
    current = issue_image_admission(context.promotion, context.review,
        hypothesis=context.hypothesis, observations=context.observations, image=context.image)
    if current.diagnostics:
        return current.diagnostics
    if type(context.admission) is not ImageOriginAdmission or current.admission != context.admission:
        return (diagnostic('IMAGE_ADMISSION_STALE', 'image_admission'),)
    return ()


def load_admission(payload, context):
    """An archive is data: require a current independently confirmed context."""
    if type(context) is not ImageAdmissionContext:
        return AdmissionResult(None, (diagnostic('IMAGE_ADMISSION_REQUIRED', 'image_admission'),))
    diagnostics = verify_image_admission(context.promotion.document, context)
    if diagnostics:
        return AdmissionResult(None, diagnostics)
    try:
        if canonical_json(decode_archive(payload)) != canonical_json(admission_to_dict(context.admission)):
            raise ValueError('Archive differs from current verified bindings')
        return AdmissionResult(context.admission, ())
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return AdmissionResult(None, (diagnostic('ADMISSION_ARCHIVE_INVALID', 'archive'),))
