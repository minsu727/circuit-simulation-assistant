"""M2B reviewed-snapshot bindings, not export eligibility or authentication.

Creation and verification recompute M1 validation for the exact input. No cached
report, imported reviewed flag or digest supplied by a caller grants authority.
The trusted caller must obtain the explicit decision/acknowledgements from review.
Exporter preflight stays separate; representation workflows remain deferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re

from .graph import build_graph
from .models import CircuitDocument, IssueSeverity, TechnicalState, ValidationResult, ValueGrammar
from .serialization import document_to_dict, dump_document
from .validation import validate_document
from .value_parser import parse_quantity
from .model_profiles import repository_model_profiles


_CONTRACT = "m2-approval-v1"
_EXPORTER = "m2-spice-v1"
_VALIDATOR = "m1-local-v1"
# Public M1 stage names required by the M2 contract, not validator implementation.
_REQUIRED_STAGES = frozenset((
    "schema", "ids", "references", "incidence", "pins", "ground", "labels",
    "component_value_source", "graph_dc", "ambiguity_confidence_provenance",
))


class ApprovalScope(str, Enum):
    CIRCUIT_EXPORT = "CIRCUIT_EXPORT"
    REPRESENTATION = "REPRESENTATION"


class ApprovalError(ValueError):
    """Fail-fast approval diagnostic; separate from M1 ValidationIssue."""

    def __init__(self, code: str, field: str, message: str):
        self.code = code
        self.field = field
        super().__init__(message)


def _identifier(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if len(value) > 64 or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value) is None:
        raise ValueError(f"{field} must be a bounded identifier")


def _sha256(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")


def _warning_ids(value: tuple[str, ...]) -> None:
    if type(value) is not tuple:
        raise TypeError("acknowledged_warning_ids must be an immutable tuple")
    for item in value:
        _identifier(item, "acknowledged_warning_ids")
    if value != tuple(sorted(set(value))):
        raise ValueError("acknowledged_warning_ids must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ApprovalEnvelope:
    """Local shape checks only; construction alone does not verify approval.

    Future versions are representable but rejected by the current consuming API.
    REPRESENTATION fields reserve the documented shape, not its future workflow.
    """

    contract_version: str
    scope: ApprovalScope
    approved: bool
    document_id: str
    document_revision: int
    document_sha256: str
    electrical_sha256: str
    validation_profile: str
    validation_ruleset: str
    validation_sha256: str
    exporter_contract: str
    model_registry_version: str
    model_registry_sha256: str
    acknowledged_warning_ids: tuple[str, ...]
    parent_approval_sha256: str | None
    base_netlist_sha256: str | None
    mapping_sha256: str | None

    def __post_init__(self) -> None:
        for field, value in (
            ("contract_version", self.contract_version), ("document_id", self.document_id),
            ("validation_profile", self.validation_profile),
            ("validation_ruleset", self.validation_ruleset),
            ("exporter_contract", self.exporter_contract),
            ("model_registry_version", self.model_registry_version),
        ):
            _identifier(value, field)
        if not isinstance(self.scope, ApprovalScope):
            raise TypeError("scope must be ApprovalScope")
        if type(self.approved) is not bool:
            raise TypeError("approved must be a native bool")
        if type(self.document_revision) is not int:
            raise TypeError("document_revision must be an integer, not bool")
        if self.document_revision < 0:
            raise ValueError("document_revision must be nonnegative")
        for field, value in (
            ("document_sha256", self.document_sha256),
            ("electrical_sha256", self.electrical_sha256),
            ("validation_sha256", self.validation_sha256),
            ("model_registry_sha256", self.model_registry_sha256),
        ):
            _sha256(value, field)
        _warning_ids(self.acknowledged_warning_ids)
        for field, value in (
            ("parent_approval_sha256", self.parent_approval_sha256),
            ("base_netlist_sha256", self.base_netlist_sha256),
            ("mapping_sha256", self.mapping_sha256),
        ):
            if self.scope is ApprovalScope.CIRCUIT_EXPORT:
                if value is not None:
                    raise ValueError(f"{field} must be null for CIRCUIT_EXPORT")
            else:
                _sha256(value, field)


def _digest(projection: dict) -> str:
    # Derived projections have no trailing LF; full snapshots use dump_document.
    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def document_digest(document: CircuitDocument) -> str:
    """SHA-256 of existing M1 archival UTF-8 bytes, including the final LF."""
    return hashlib.sha256(dump_document(document).encode("utf-8")).hexdigest()


def _quantity(value: dict | None) -> dict | None:
    if value is None:
        return None
    number = value["si_value"]
    if number is not None:
        parsed = parse_quantity(number, value["unit"], ValueGrammar.SI)
        if parsed.quantity is None:
            raise ApprovalError("ELECTRICAL_VALUE_INVALID", "si_value",
                                "Electrical projection requires a finite SI scalar.")
        number = parsed.quantity.si_value
    return {"si_value": number, "unit": value["unit"]}


def _parameters(values: dict) -> dict:
    return {key: _quantity(values[key]) for key in sorted(values)}


def _source(value: dict | None) -> dict | None:
    if value is None:
        return None
    ac = value["ac"]
    return {
        "dc": _quantity(value["dc"]),
        "ac": None if ac is None else {
            "magnitude": _quantity(ac["magnitude"]), "phase": _quantity(ac["phase"])},
        "waveform": {"kind": value["waveform"]["kind"],
                     "parameters": _parameters(value["waveform"]["parameters"])},
    }


def electrical_digest(document: CircuitDocument) -> str:
    """Normalized M2 electrical projection; never a sole approval authority.

    Graph prerequisites reject invalid IDs/references/incidence, not electrical
    validity. Explicit unresolved/null quantities remain null; nothing is inferred.
    """
    if build_graph(document).graph is None:
        raise ApprovalError("DOCUMENT_STRUCTURE_INVALID", "connections",
                            "Electrical projection requires a checked complete graph result.")
    data = document_to_dict(document)
    return _digest({
        "digest_profile": "m2-electrical-digest-v1",
        "schema_version": data["schema_version"],
        "metadata": {"catalog_version": data["metadata"]["catalog_version"]},
        "components": [{
            "id": row["id"], "type": row["type"], "pin_ids": sorted(row["pin_ids"]),
            "value": _quantity(row["value"]), "model_ref": row["model_ref"],
            "parameters": _parameters(row["parameters"]), "source": _source(row["source"]),
        } for row in sorted(data["components"], key=lambda row: row["id"])],
        "pins": [{"id": row["id"], "component_id": row["component_id"], "role": row["role"]}
                 for row in sorted(data["pins"], key=lambda row: row["id"])],
        "nets": [{"id": row["id"], "is_ground": row["is_ground"]}
                 for row in sorted(data["nets"], key=lambda row: row["id"])],
        "connections": [{"pin_id": row["pin_id"], "net_id": row["net_id"]}
                        for row in sorted(data["connections"],
                                          key=lambda row: (row["pin_id"], row["net_id"]))],
        "labels": [{
            "id": row["id"], "scope": row["scope"], "net_id": row["net_id"],
            # Match M1's ASCII-only identity; Unicode casefold would change it.
            "text": "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char
                            for char in row["text"].strip()),
        } for row in sorted(data["labels"], key=lambda row: row["id"])],
    })


def validation_digest(result: ValidationResult) -> str:
    """Hash stable report fields in M1 issue/stage order; prose is excluded.

    This hashes a supplied report but makes no claim that the report is fresh.
    """
    if not isinstance(result, ValidationResult):
        raise TypeError("result must be ValidationResult")
    return _digest({
        "digest_profile": "m2-validation-digest-v1",
        "profile": result.profile, "ruleset_version": result.ruleset_version,
        "document_revision": result.document_revision,
        "technical_state": result.technical_state.value,
        "completed_stages": list(result.completed_stages),
        "skipped_stages": [list(pair) for pair in sorted(result.skipped_stages)],
        "deferred_checks": list(result.deferred_checks),
        "issues": [{
            "issue_id": issue.issue_id, "severity": issue.severity.value, "code": issue.code,
            "target_refs": list(issue.target_refs), "entity_type": issue.entity_type,
            "entity_id": issue.entity_id, "field": issue.field,
            "provenance": list(issue.provenance),
        } for issue in result.issues],
    })


def approval_digest(approval: ApprovalEnvelope) -> str:
    """Hash all explicit envelope fields; no self-reference or timestamp."""
    if not isinstance(approval, ApprovalEnvelope):
        raise TypeError("approval must be ApprovalEnvelope")
    return _digest({
        "contract_version": approval.contract_version, "scope": approval.scope.value,
        "approved": approval.approved, "document_id": approval.document_id,
        "document_revision": approval.document_revision,
        "document_sha256": approval.document_sha256,
        "electrical_sha256": approval.electrical_sha256,
        "validation_profile": approval.validation_profile,
        "validation_ruleset": approval.validation_ruleset,
        "validation_sha256": approval.validation_sha256,
        "exporter_contract": approval.exporter_contract,
        "model_registry_version": approval.model_registry_version,
        "model_registry_sha256": approval.model_registry_sha256,
        "acknowledged_warning_ids": list(approval.acknowledged_warning_ids),
        "parent_approval_sha256": approval.parent_approval_sha256,
        "base_netlist_sha256": approval.base_netlist_sha256,
        "mapping_sha256": approval.mapping_sha256,
    })


def _context(exporter_contract: str, model_registry_version: str,
             model_registry_sha256: str) -> None:
    _identifier(exporter_contract, "exporter_contract")
    _identifier(model_registry_version, "model_registry_version")
    _sha256(model_registry_sha256, "model_registry_sha256")
    if exporter_contract != _EXPORTER:
        raise ApprovalError("EXPORTER_CONTRACT_UNSUPPORTED", "exporter_contract",
                            "Unsupported exporter contract.")
    try:
        repository_model_profiles((model_registry_version, model_registry_sha256))
    except (ValueError, TypeError) as error:
        raise ApprovalError("MODEL_CONTEXT_UNSUPPORTED", "model_registry_sha256",
                            "An exact sealed repository model context is required.") from error


def _fresh_report(document: CircuitDocument) -> ValidationResult:
    if not isinstance(document, CircuitDocument):
        raise TypeError("document must be CircuitDocument")
    result = validate_document(document)
    if not isinstance(result, ValidationResult):
        raise TypeError("validator must return ValidationResult")
    if result.profile != _VALIDATOR:
        raise ApprovalError("VALIDATION_PROFILE_UNSUPPORTED", "profile", "Unsupported validation profile.")
    if result.ruleset_version != _VALIDATOR:
        raise ApprovalError("VALIDATION_RULESET_UNSUPPORTED", "ruleset_version", "Unsupported validation ruleset.")
    if result.document_revision != document.metadata.revision:
        raise ApprovalError("VALIDATION_REVISION_MISMATCH", "document_revision", "Validation revision does not match.")
    if result.technical_state is not TechnicalState.VALID or result.blocking_issue_count:
        raise ApprovalError("DOCUMENT_NOT_VALID", "technical_state", "A complete fresh VALID report is required.")
    if (not _REQUIRED_STAGES.issubset(result.completed_stages)
            or any(stage in _REQUIRED_STAGES for stage, _ in result.skipped_stages)
            or _REQUIRED_STAGES.intersection(result.deferred_checks)):
        raise ApprovalError("VALIDATION_INCOMPLETE", "completed_stages", "Required local validation is incomplete.")
    return result


def _warnings(result: ValidationResult) -> tuple[str, ...]:
    return tuple(sorted({issue.issue_id for issue in result.issues
                         if issue.severity is IssueSeverity.WARNING}))


def make_circuit_approval(
    document: CircuitDocument, *, approved: bool, acknowledged_warning_ids: tuple[str, ...],
    exporter_contract: str, model_registry_version: str, model_registry_sha256: str,
) -> ApprovalEnvelope:
    """Bind a trusted explicit review decision to fresh M1 validation.

    All decision/context arguments are mandatory. There is no supplied cached
    report or digest argument. Warning acknowledgement records review only; M2C
    preflight may still refuse export. No simulation/representation is authorized.
    """
    if type(approved) is not bool:
        raise TypeError("approved must be a native bool")
    _warning_ids(acknowledged_warning_ids)
    _context(exporter_contract, model_registry_version, model_registry_sha256)
    result = _fresh_report(document)
    if not approved:
        raise ApprovalError("APPROVAL_NOT_GRANTED", "approved", "An explicit approved decision is required.")
    if acknowledged_warning_ids != _warnings(result):
        raise ApprovalError("WARNING_ACKNOWLEDGEMENT_MISMATCH", "acknowledged_warning_ids",
                            "Acknowledge exactly the current fresh warning IDs.")
    return ApprovalEnvelope(
        _CONTRACT, ApprovalScope.CIRCUIT_EXPORT, approved,
        document.metadata.circuit_id, document.metadata.revision,
        document_digest(document), electrical_digest(document),
        result.profile, result.ruleset_version, validation_digest(result),
        exporter_contract, model_registry_version, model_registry_sha256,
        acknowledged_warning_ids, None, None, None,
    )


def verify_circuit_approval(
    document: CircuitDocument, approval: ApprovalEnvelope, *, exporter_contract: str,
    model_registry_version: str, model_registry_sha256: str,
) -> None:
    """Return None on exact match or raise fail-fast ApprovalError(code, field).

    Recompute validation/digests without refreshing or mutating the envelope.
    Matching proves review binding only, not identity or exporter eligibility.
    """
    if not isinstance(document, CircuitDocument):
        raise TypeError("document must be CircuitDocument")
    if not isinstance(approval, ApprovalEnvelope):
        raise TypeError("approval must be ApprovalEnvelope")
    if approval.contract_version != _CONTRACT:
        raise ApprovalError("APPROVAL_VERSION_UNSUPPORTED", "contract_version", "Unsupported approval version.")
    if approval.scope is not ApprovalScope.CIRCUIT_EXPORT:
        raise ApprovalError("APPROVAL_SCOPE_INVALID", "scope", "Circuit approval scope is required.")
    if not approval.approved:
        raise ApprovalError("APPROVAL_NOT_GRANTED", "approved", "Approval was not granted.")
    _context(exporter_contract, model_registry_version, model_registry_sha256)
    result = _fresh_report(document)
    # Explicit ordered comparisons keep the first failure deterministic.
    for field, actual, expected, code in (
        ("document_id", approval.document_id, document.metadata.circuit_id, "DOCUMENT_ID_MISMATCH"),
        ("document_revision", approval.document_revision, document.metadata.revision, "DOCUMENT_REVISION_MISMATCH"),
        ("document_sha256", approval.document_sha256, document_digest(document), "DOCUMENT_DIGEST_MISMATCH"),
        ("electrical_sha256", approval.electrical_sha256, electrical_digest(document), "ELECTRICAL_DIGEST_MISMATCH"),
        ("validation_profile", approval.validation_profile, result.profile, "VALIDATION_PROFILE_MISMATCH"),
        ("validation_ruleset", approval.validation_ruleset, result.ruleset_version, "VALIDATION_RULESET_MISMATCH"),
        ("validation_sha256", approval.validation_sha256, validation_digest(result), "VALIDATION_DIGEST_MISMATCH"),
        ("exporter_contract", approval.exporter_contract, exporter_contract, "EXPORTER_CONTRACT_MISMATCH"),
        ("model_registry_version", approval.model_registry_version, model_registry_version, "MODEL_CONTEXT_MISMATCH"),
        ("model_registry_sha256", approval.model_registry_sha256, model_registry_sha256, "MODEL_CONTEXT_MISMATCH"),
        ("acknowledged_warning_ids", approval.acknowledged_warning_ids, _warnings(result), "WARNING_ACKNOWLEDGEMENT_MISMATCH"),
    ):
        if actual != expected:
            raise ApprovalError(code, field, f"Current binding does not match {field}.")
