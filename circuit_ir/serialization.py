"""Explicit source-record projection and strict primitive JSON decoding.

Typed loading and schema validation belong to M1C. decode_json returns primitive
data only; neither decoding nor dumping establishes validity or approval.
"""
from __future__ import annotations

import json
import math

from . import models as m


def _confidence(value: m.Confidence) -> dict:
    return {"score": value.score, "basis": value.basis.value,
            "calibrated": value.calibrated}


def _quantity(value: m.Quantity | None) -> dict | None:
    if value is None:
        return None
    return {"literal": value.literal, "si_value": value.si_value,
            "unit": value.unit, "grammar": value.grammar.value}


def _ac(value: m.ACConfiguration | None) -> dict | None:
    if value is None:
        return None
    return {"magnitude": _quantity(value.magnitude), "phase": _quantity(value.phase)}


def _parameters(values: tuple[tuple[str, m.Quantity], ...]) -> dict:
    return {key: _quantity(value) for key, value in values}


def _source(value: m.SourceConfiguration | None) -> dict | None:
    if value is None:
        return None
    return {"dc": _quantity(value.dc), "ac": _ac(value.ac),
            "waveform": {"kind": value.waveform.kind.value,
                         "parameters": _parameters(value.waveform.parameters)}}


def _component(value: m.Component) -> dict:
    return {"id": value.id, "type": value.type.value, "pin_ids": list(value.pin_ids),
            "value": _quantity(value.value), "model_ref": value.model_ref,
            "parameters": _parameters(value.parameters), "source": _source(value.source),
            "visual_ref": value.visual_ref}


def _pin(value: m.Pin) -> dict:
    return {"id": value.id, "component_id": value.component_id,
            "role": value.role.value, "visual_ref": value.visual_ref}


def _connection(value: m.Connection) -> dict:
    return {"pin_id": value.pin_id, "net_id": value.net_id,
            "visual_refs": list(value.visual_refs), "confidence": _confidence(value.confidence)}


def _label(value: m.Label) -> dict:
    return {"id": value.id, "text": value.text, "scope": value.scope,
            "net_id": value.net_id, "visual_ref": value.visual_ref}


def _point(value: m.PixelPoint | None) -> list | None:
    return None if value is None else [value.x, value.y]


def _bbox(value: m.BoundingBox | None) -> list | None:
    return None if value is None else [value.x, value.y, value.width, value.height]


def _visual_entity(value: m.VisualEntity) -> dict:
    return {"id": value.id, "kind": value.kind.value, "bbox": _bbox(value.bbox),
            "position": _point(value.position), "orientation": value.orientation.value,
            "points": [_point(point) for point in value.points], "text": value.text,
            "method": value.method, "confidence": _confidence(value.confidence)}


def _ambiguity(value: m.Ambiguity) -> dict:
    return {"id": value.id, "kind": value.kind.value, "target_refs": list(value.target_refs),
            "candidates": [{"id": candidate.id, "description": candidate.description}
                           for candidate in value.candidates], "state": value.state.value,
            "selected_candidate_id": value.selected_candidate_id,
            "resolution_note": value.resolution_note}


def _finding(value: m.ImportedFinding) -> dict:
    return {"id": value.id, "code": value.code, "severity": value.severity.value,
            "target_refs": list(value.target_refs), "message": value.message,
            "visual_refs": list(value.visual_refs)}


def _image(value: m.SourceImageReference | None) -> dict | None:
    if value is None:
        return None
    return {"asset_id": value.asset_id, "sha256": value.sha256,
            "width_px": value.width_px, "height_px": value.height_px}


def document_to_dict(document: m.CircuitDocument) -> dict:
    """Return independent wire containers, including every required nullable key."""
    if not isinstance(document, m.CircuitDocument):
        raise TypeError("document must be a CircuitDocument")
    metadata = document.metadata
    state = document.validation_state
    return {
        "schema_version": document.schema_version,
        "metadata": {"circuit_id": metadata.circuit_id, "revision": metadata.revision,
                     "origin": metadata.origin.value, "catalog_version": metadata.catalog_version},
        "source_image_reference": _image(document.source_image_reference),
        "components": [_component(value) for value in document.components],
        "pins": [_pin(value) for value in document.pins],
        "nets": [{"id": value.id, "is_ground": value.is_ground} for value in document.nets],
        "connections": [_connection(value) for value in document.connections],
        "labels": [_label(value) for value in document.labels],
        "visual": {"coordinate_space": document.visual.coordinate_space,
                   "entities": [_visual_entity(value) for value in document.visual.entities]},
        "confidence": _confidence(document.confidence),
        "ambiguities": [_ambiguity(value) for value in document.ambiguities],
        "warnings": list(document.warnings),
        "validation_state": {"status": state.status.value,
                             "validated_revision": state.validated_revision,
                             "ruleset_version": state.ruleset_version,
                             "findings": [_finding(value) for value in state.findings]},
    }


def dump_document(document: m.CircuitDocument) -> str:
    """Sorted object keys, original array order, ASCII escapes, two-space indent + LF.

    This is reproducible archival JSON, not a canonical electrical hash format.
    No values, imported reports or approvals are recomputed.
    """
    return json.dumps(document_to_dict(document), sort_keys=True, ensure_ascii=True,
                      allow_nan=False, indent=2) + "\n"


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def _constant(text: str) -> None:
    raise ValueError("non-standard JSON numeric constant")


def decode_json(text: str) -> object:
    """Decode primitives only; preserve unknown fields for M1C shape validation.

    Reject duplicate keys and non-finite numbers. Decimal quantity strings stay
    strings; JSON numeric coordinates/scores retain normal Python int/float types.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a JSON string")
    try:
        return json.loads(text, object_pairs_hook=_object, parse_float=_float,
                          parse_constant=_constant)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds decoder capacity") from error
