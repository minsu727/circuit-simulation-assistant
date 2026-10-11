"""Pure reviewed-image projection into the existing M1 wire contract."""
from dataclasses import dataclass, replace
from circuit_ir import models as ir
from circuit_ir.serialization import dump_document
from circuit_ir.schema import load_document
from circuit_ir.validation import validate_document
from circuit_ir.approval import document_digest, validation_digest
from .intake import canonical_json, content_digest
from .models import Diagnostic, diagnostic
from .review import validate_review
from .review_models import PROMOTION_VERSION
from .review_serialization import decode_archive


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    version: str
    source_identity_sha256: str
    observation_sha256: str
    topology_sha256: str
    review_sha256: str
    revision_sha256: str
    confirmation_sha256: str
    document_sha256: str
    validation_sha256: str
    component_map: tuple[tuple[str, str], ...]
    pin_map: tuple[tuple[str, str], ...]
    net_map: tuple[tuple[str, str], ...]
    label_map: tuple[tuple[str, str], ...]
    digest: str


@dataclass(frozen=True, slots=True)
class PromotionResult:
    document: ir.CircuitDocument | None
    validation: ir.ValidationResult | None
    record: PromotionRecord | None
    diagnostics: tuple[Diagnostic, ...]


def promotion_to_dict(record, include_digest=True):
    data = dict(version=record.version, source_identity_sha256=record.source_identity_sha256,
                observation_sha256=record.observation_sha256, topology_sha256=record.topology_sha256,
                review_sha256=record.review_sha256, revision_sha256=record.revision_sha256,
                confirmation_sha256=record.confirmation_sha256, document_sha256=record.document_sha256,
                validation_sha256=record.validation_sha256,
                component_map=[list(p) for p in record.component_map],
                pin_map=[list(p) for p in record.pin_map], net_map=[list(p) for p in record.net_map],
                label_map=[list(p) for p in record.label_map])
    if include_digest:
        data['digest'] = record.digest
    return data


def dump_promotion(record):
    return canonical_json(promotion_to_dict(record)) + '\n'


def _id(prefix, source):
    # M3 identifiers exceed M1's 64-character bound. Explicit sidecar maps
    # preserve full source identifiers; no connectivity goes into M1 metadata.
    return prefix + content_digest(source)[:64-len(prefix)]


def _blocked(code, field='promotion'):
    return PromotionResult(None, None, None, (diagnostic(code, field),))


def promote_review(session, *, hypothesis, observations, image):
    """Require live exact confirmation; return fresh M1 state, including INVALID.

    All image/observation/topology integrity is rechecked by validate_review.
    This function neither creates confirmation nor grants admission/approval.
    """
    diagnostics = validate_review(session, hypothesis, observations, image)
    if diagnostics:
        return PromotionResult(None, None, None, diagnostics)
    if session.confirmation is None:
        return _blocked('PROMOTION_CONFIRMATION_REQUIRED')
    if session.current.issues:
        return _blocked('PROMOTION_REVIEW_INCOMPLETE')
    try:
        snapshot = session.current.snapshot
        components = dict((c.id, c.reference) for c in snapshot.components)
        pins = dict((p.id, _id('pin_', [p.component_id, p.id])) for p in snapshot.pins)
        memberships = dict(snapshot.memberships)
        groups = sorted(set(memberships.values()) - {None})
        nets = dict((n, _id('net_', n)) for n in groups)
        labels = dict((l, _id('label_', l)) for l, _ in snapshot.labels if memberships[l] is not None)
        for mapping in (components, pins, nets, labels):
            if len(set(mapping.values())) != len(mapping):
                return _blocked('PROMOTION_ID_COLLISION')
        confidence = ir.Confidence(None, ir.ConfidenceBasis.MANUAL, False)
        doc = ir.CircuitDocument(
            ir.SCHEMA_VERSION,
            ir.Metadata(_id('image_', [session.source_identity_sha256, session.observation_sha256,
                                      session.topology_sha256]), session.current.number,
                        ir.Origin.IMAGE, observations.provider.catalog_version),
            ir.SourceImageReference(_id('asset_', image.identity.identity_sha256),
                                    image.identity.source_sha256, image.identity.width, image.identity.height),
            tuple(sorted((ir.Component(components[c.id], c.component_type,
                  tuple(sorted(pins[p.id] for p in snapshot.pins if p.component_id == c.id)),
                  c.value, c.model_ref, c.parameters, c.source, None) for c in snapshot.components), key=lambda c:c.id)),
            tuple(sorted((ir.Pin(pins[p.id], components[p.component_id], p.role, None)
                          for p in snapshot.pins), key=lambda p:p.id)),
            tuple(sorted((ir.Net(nets[n], any(memberships[g] == n for g in snapshot.ground_ids))
                          for n in groups), key=lambda n:n.id)),
            tuple(sorted((ir.Connection(pins[p.id], nets[memberships[p.id]], (), confidence)
                          for p in snapshot.pins), key=lambda c:c.pin_id)),
            tuple(sorted((ir.Label(labels[l], text, 'flat', nets[memberships[l]], None)
                          for l, text in snapshot.labels if l in labels), key=lambda l:l.id)),
            ir.VisualProvenance('original_pixels', ()), confidence, (), (),
            ir.ImportedValidationState(ir.WireValidationStatus.DRAFT, None, None, ()))
        loaded = load_document(dump_document(doc))
        if loaded.document != doc:
            return _blocked('PROMOTION_SCHEMA_INVALID')
        report = validate_document(doc)
        record = PromotionRecord(PROMOTION_VERSION, session.source_identity_sha256,
            session.observation_sha256, session.topology_sha256, session.digest, session.current.digest,
            session.confirmation.digest, document_digest(doc), validation_digest(report),
            tuple(sorted(components.items())), tuple(sorted(pins.items())), tuple(sorted(nets.items())),
            tuple(sorted(labels.items())), '')
        record = replace(record, digest=content_digest(promotion_to_dict(record, False)))
        return PromotionResult(doc, report, record, ())
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _blocked('PROMOTION_INPUT_INVALID')


def verify_promotion(result, session, *, hypothesis, observations, image):
    current = promote_review(session, hypothesis=hypothesis, observations=observations, image=image)
    if current.diagnostics:
        return current.diagnostics
    if type(result) is not PromotionResult or result != current:
        return (diagnostic('PROMOTION_STALE', 'promotion'),)
    return ()


def load_promotion(payload, session, *, hypothesis, observations, image):
    """Check an archival sidecar against a newly verified current promotion."""
    current = promote_review(session, hypothesis=hypothesis, observations=observations, image=image)
    if current.diagnostics:
        return current
    try:
        if canonical_json(decode_archive(payload)) != canonical_json(promotion_to_dict(current.record)):
            return _blocked('PROMOTION_ARCHIVE_INVALID')
        return current
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return _blocked('PROMOTION_ARCHIVE_INVALID')
