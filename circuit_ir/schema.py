"""Bundled 0.2-draft1 shape validation and explicit typed reconstruction.

Loading does not check references, electrical rules or literal/SI consistency.
Imported findings remain archival data and grant no validity or approval.
The schema/validator are loaded lazily, without network access or CWD assumptions.
Future packaged v0.2 integration must include circuit-json.schema.json as data;
this isolated increment does not change the existing v0.1 packaging.
"""
from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import json
import math

from . import models as m
from .serialization import decode_json


_MAX_TEXT_BYTES = 1024 * 1024
_MAX_DEPTH = 32


def _no_remote(uri: str):
    raise RuntimeError("Circuit IR schema cannot retrieve external resources")


@lru_cache(maxsize=1)
def _validator():
    # A missing direct dependency is a setup error, not invalid circuit input.
    try:
        from jsonschema import Draft202012Validator, validators
        from referencing import Registry
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Circuit IR loading requires requirements-circuit-ir.txt; "
            "install it or requirements-test.txt"
        ) from error

    schema = json.loads(files("circuit_ir").joinpath(
        "circuit-json.schema.json").read_text(encoding="utf-8"))

    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value and not value["$ref"].startswith("#/"):
                raise RuntimeError("Circuit IR schema must use internal references only")
            for item in value.values():
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)

    check_refs(schema)
    Draft202012Validator.check_schema(schema)
    # JSON Schema accepts 1.0 as an integer. The existing Python IR contract
    # requires an actual int and forbids coercion, so enforce that at the gate.
    checker = Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int)
    strict_validator = validators.extend(Draft202012Validator, type_checker=checker)
    # Kept private and reused read-only; callers never receive the schema dict.
    return strict_validator(schema, registry=Registry(retrieve=_no_remote))


def _pointer(path) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1")
                   for part in path)


def _issue(index: int, path: str, keyword: str, message: str) -> m.ValidationIssue:
    return m.ValidationIssue(
        f"issue_{index:04d}", m.IssueSeverity.ERROR, "SCHEMA_INVALID",
        f"{keyword}: {message}", (), None, None, path, None, ())


def _input_guard(data):
    """Only JSON-native finite primitives and the planned local loader bounds."""
    if type(data) is dict:
        for name, maximum in (("components", 256), ("pins", 1024),
                              ("nets", 1024), ("connections", 1024)):
            value = data.get(name)
            if type(value) is list and len(value) > maximum:
                return (("/" + name, "resourceLimit", f"At most {maximum} items allowed."),)
        visual = data.get("visual")
        if type(visual) is dict:
            entities = visual.get("entities")
            if type(entities) is list and len(entities) > 4096:
                return (("/visual/entities", "resourceLimit", "At most 4096 items allowed."),)

    def walk(value, path, depth):
        # Root is depth 0. Cyclic Python containers also fail this bounded walk.
        if depth > _MAX_DEPTH:
            return (path, "resourceLimit", "Nesting depth exceeds 32.")
        if type(value) not in (dict, list, str, int, float, bool, type(None)):
            return (path, "type", "Expected a JSON-native primitive/container.")
        if type(value) is float and not math.isfinite(value):
            return (path, "type", "Numeric values must be finite.")
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                return (path, "type", "Object keys must be strings.")
            items = sorted(value.items())
        elif type(value) is list:
            items = enumerate(value)
        else:
            return None
        for key, item in items:
            problem = walk(item, path + _pointer((key,)), depth + 1)
            if problem is not None:
                return problem
        return None

    problem = walk(data, "", 0)
    return (problem,) if problem is not None else ()


def _diagnostics(error):
    # All current oneOfs are nullable unions. Discard the irrelevant null
    # branch and report the actual nested constraint, not a verbose branch tree.
    if error.validator == "oneOf" and error.context and error.instance is not None:
        for child in error.context:
            if child.schema == {"type": "null"}:
                continue
            yield from _diagnostics(child)
        return
    path = _pointer(error.absolute_path)
    keyword = error.validator
    if keyword == "required":
        for key in error.validator_value:
            if key not in error.instance:
                yield (path + _pointer((key,)), keyword, "Required field is missing.")
    elif keyword == "additionalProperties":
        for key in sorted(set(error.instance) - set(error.schema.get("properties", {}))):
            yield (path + _pointer((key,)), keyword, "Unknown field is not permitted.")
    else:
        messages = {
            "type": "Expected " + str(error.validator_value) + ".",
            "const": "Value does not match the supported constant.",
            "enum": "Unsupported enum value.",
            "minimum": "Value is below the allowed minimum.",
            "maximum": "Value exceeds the allowed maximum.",
            "minItems": "Array has too few items.",
            "maxItems": "Array has too many items.",
            "uniqueItems": "Array items must be unique.",
            "minLength": "String is too short.",
            "maxLength": "String is too long.",
            "pattern": "String does not match the required format.",
        }
        yield (path, keyword, messages.get(keyword, "Schema constraint failed."))


def validate_schema(data: object) -> tuple[m.ValidationIssue, ...]:
    """Validate primitives only; success says nothing about electrical validity.

    Diagnostics use SCHEMA_INVALID, an RFC 6901 pointer in field (empty at root)
    and the failed keyword in message. No input values/validator trees are dumped.
    """
    validator = _validator()
    problems = _input_guard(data)
    if not problems:
        problems = sorted(set(problem for error in validator.iter_errors(data)
                              for problem in _diagnostics(error)))
    return tuple(_issue(index, *problem) for index, problem in enumerate(problems, 1))


def _quantity(data):
    if data is None:
        return None
    return m.Quantity(data["literal"], data["si_value"], data["unit"],
                      m.ValueGrammar(data["grammar"]))


def _parameters(data):
    return tuple((key, _quantity(value)) for key, value in data.items())


def _confidence(data):
    return m.Confidence(data["score"], m.ConfidenceBasis(data["basis"]), data["calibrated"])


def _source(data):
    if data is None:
        return None
    ac = data["ac"]
    waveform = data["waveform"]
    return m.SourceConfiguration(
        _quantity(data["dc"]),
        None if ac is None else m.ACConfiguration(
            _quantity(ac["magnitude"]), _quantity(ac["phase"])),
        m.Waveform(m.WaveformKind(waveform["kind"]), _parameters(waveform["parameters"])))


def _component(data):
    return m.Component(data["id"], m.ComponentType(data["type"]), tuple(data["pin_ids"]),
                       _quantity(data["value"]), data["model_ref"],
                       _parameters(data["parameters"]), _source(data["source"]), data["visual_ref"])


def _visual(data):
    bbox, position = data["bbox"], data["position"]
    return m.VisualEntity(
        data["id"], m.VisualKind(data["kind"]),
        None if bbox is None else m.BoundingBox(bbox[0], bbox[1], bbox[2], bbox[3]),
        None if position is None else m.PixelPoint(position[0], position[1]),
        m.Orientation(data["orientation"]),
        tuple(m.PixelPoint(point[0], point[1]) for point in data["points"]),
        data["text"], data["method"], _confidence(data["confidence"]))


def _ambiguity(data):
    return m.Ambiguity(
        data["id"], m.AmbiguityKind(data["kind"]), tuple(data["target_refs"]),
        tuple(m.Candidate(item["id"], item["description"]) for item in data["candidates"]),
        m.AmbiguityStatus(data["state"]), data["selected_candidate_id"], data["resolution_note"])


def _document(data):
    metadata, image, visual, state = (data["metadata"], data["source_image_reference"],
                                      data["visual"], data["validation_state"])
    return m.CircuitDocument(
        data["schema_version"],
        m.Metadata(metadata["circuit_id"], metadata["revision"],
                   m.Origin(metadata["origin"]), metadata["catalog_version"]),
        None if image is None else m.SourceImageReference(
            image["asset_id"], image["sha256"], image["width_px"], image["height_px"]),
        tuple(_component(item) for item in data["components"]),
        tuple(m.Pin(item["id"], item["component_id"], m.PinRole(item["role"]),
                    item["visual_ref"]) for item in data["pins"]),
        tuple(m.Net(item["id"], item["is_ground"]) for item in data["nets"]),
        tuple(m.Connection(item["pin_id"], item["net_id"], tuple(item["visual_refs"]),
                           _confidence(item["confidence"])) for item in data["connections"]),
        tuple(m.Label(item["id"], item["text"], item["scope"], item["net_id"],
                      item["visual_ref"]) for item in data["labels"]),
        m.VisualProvenance(visual["coordinate_space"],
                           tuple(_visual(item) for item in visual["entities"])),
        _confidence(data["confidence"]), tuple(_ambiguity(item) for item in data["ambiguities"]),
        tuple(data["warnings"]),
        m.ImportedValidationState(
            m.WireValidationStatus(state["status"]), state["validated_revision"],
            state["ruleset_version"],
            tuple(m.ImportedFinding(item["id"], item["code"], m.IssueSeverity(item["severity"]),
                                    tuple(item["target_refs"]), item["message"],
                                    tuple(item["visual_refs"])) for item in state["findings"])))


def document_from_dict(data: dict) -> m.LoadResult:
    """Load an explicit primitive dict, with no defaults, inference or coercion.

    Non-dict API arguments raise TypeError; invalid dict contents return issues.
    Setup/resource errors propagate, and no partial document is ever returned.
    """
    if type(data) is not dict:
        raise TypeError("data must be a JSON primitive dict")
    issues = validate_schema(data)
    if issues:
        return m.LoadResult(None, issues)
    try:
        document = _document(data)
    except (TypeError, ValueError) as error:
        # Local constructors are slightly stricter than regex '$' semantics
        # (e.g. a trailing newline in an ID). Do not let that leak a partial load.
        return m.LoadResult(None, (_issue(1, "", "construction", str(error)),))
    return m.LoadResult(document, ())


def load_document(text: str) -> m.LoadResult:
    """Strict JSON text -> LoadResult; primitive decode_json remains separate."""
    if type(text) is not str:
        raise TypeError("text must be a JSON string")
    # Check setup even for malformed input rather than hiding missing validation.
    _validator()
    try:
        if len(text) > _MAX_TEXT_BYTES or len(text.encode("utf-8")) > _MAX_TEXT_BYTES:
            return m.LoadResult(None, (_issue(1, "", "resourceLimit", "JSON text exceeds 1 MiB."),))
        data = decode_json(text)
    except ValueError:
        return m.LoadResult(None, (_issue(1, "", "parse", "Invalid strict JSON text."),))
    if type(data) is not dict:
        return m.LoadResult(None, (_issue(1, "", "type", "Document root must be an object."),))
    return document_from_dict(data)
