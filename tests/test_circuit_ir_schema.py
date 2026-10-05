"""M1C shape/typed loading only; no graph, electrical rules or external services."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

import circuit_ir as ir
from circuit_ir import schema
from test_circuit_ir_serialization import minimal_document, populated_document


ROOT = Path(__file__).resolve().parents[1]


def at(data, path):
    for part in path:
        data = data[part]
    return data


class SchemaTests(unittest.TestCase):
    def reject(self, data, field=None, keyword=None):
        result = ir.document_from_dict(data)
        self.assertIsNone(result.document)
        self.assertTrue(result.issues)
        self.assertTrue(all(issue.blocking and issue.code == "SCHEMA_INVALID"
                            for issue in result.issues))
        if field is not None:
            self.assertTrue(any(issue.field == field for issue in result.issues), result.issues)
        if keyword is not None:
            self.assertTrue(any(issue.message.startswith(keyword + ":")
                                for issue in result.issues), result.issues)
        return result

    def test_static_resource_matches_authoritative_schema_and_meta_schema(self):
        resource = json.loads((ROOT / "circuit_ir/circuit-json.schema.json").read_text(encoding="utf-8"))
        contract = (ROOT / "docs/v0.2/circuit-json-schema.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)\n```", contract, re.S)
        self.assertEqual(resource, json.loads(blocks[0]))
        self.assertEqual(resource["$schema"], "https://json-schema.org/draft/2020-12/schema")
        Draft202012Validator.check_schema(resource)

    def test_parent_authored_divider_loads(self):
        contract = (ROOT / "docs/v0.2/circuit-json-schema.md").read_text(encoding="utf-8")
        text = re.findall(r"```json\n(.*?)\n```", contract, re.S)[1]
        result = ir.load_document(text)
        self.assertEqual(result.issues, ())
        self.assertEqual(ir.document_to_dict(result.document), ir.decode_json(text))

    def test_minimal_and_populated_serializer_outputs_validate(self):
        for document in (minimal_document(), populated_document()):
            with self.subTest(document=document.metadata.origin):
                self.assertEqual(ir.validate_schema(ir.document_to_dict(document)), ())

    def test_authored_golden_loads_without_changes(self):
        text = (ROOT / "tests/fixtures/circuit_ir/serialization_draft.json").read_text(encoding="utf-8")
        result = ir.load_document(text)
        self.assertEqual(result.issues, ())
        self.assertEqual(result.document, minimal_document())

    def test_missing_version(self):
        data = ir.document_to_dict(minimal_document())
        del data["schema_version"]
        self.reject(data, "/schema_version", "required")

    def test_wrong_future_and_malformed_versions(self):
        for version in ("0.2", "0.2-draft2", "0.3", "", None, 2, True, ["0.2-draft1"]):
            with self.subTest(version=version):
                data = ir.document_to_dict(minimal_document())
                data["schema_version"] = version
                self.reject(data, "/schema_version", "const")

    def test_unknown_top_level_field_and_pointer_escaping(self):
        data = ir.document_to_dict(minimal_document())
        data["extra~/field"] = "DO_NOT_ECHO_THIS_VALUE"
        result = self.reject(data, "/extra~0~1field", "additionalProperties")
        self.assertNotIn("DO_NOT_ECHO_THIS_VALUE", result.issues[0].message)

    def test_unknown_nested_fields_are_not_dropped(self):
        paths = (("metadata",), ("source_image_reference",), ("components", 0),
                 ("components", 0, "parameters"), ("components", 1, "value"),
                 ("components", 2, "source"), ("components", 2, "source", "ac"),
                 ("components", 2, "source", "waveform"), ("pins", 0), ("nets", 0),
                 ("connections", 0), ("labels", 0), ("visual",),
                 ("visual", "entities", 0), ("confidence",), ("ambiguities", 0),
                 ("ambiguities", 0, "candidates", 0), ("validation_state",),
                 ("validation_state", "findings", 0))
        for path in paths:
            with self.subTest(path=path):
                data = ir.document_to_dict(populated_document())
                at(data, path)["extra"] = True
                self.reject(data, "/" + "/".join(map(str, path)) + "/extra", "additionalProperties")

    def test_unknown_wire_enums(self):
        paths = (("metadata", "origin"), ("components", 0, "type"), ("pins", 0, "role"),
                 ("confidence", "basis"), ("components", 1, "value", "grammar"),
                 ("components", 1, "value", "unit"),
                 ("components", 2, "source", "waveform", "kind"),
                 ("visual", "entities", 0, "kind"), ("visual", "entities", 0, "orientation"),
                 ("ambiguities", 0, "kind"), ("ambiguities", 0, "state"),
                 ("validation_state", "status"), ("validation_state", "findings", 0, "severity"))
        for path in paths:
            with self.subTest(path=path):
                data = ir.document_to_dict(populated_document())
                at(data, path[:-1])[path[-1]] = "future_enum"
                self.reject(data, "/" + "/".join(map(str, path)), "enum")

    def test_wrong_primitive_types_without_coercion(self):
        cases = ((('metadata', 'revision'), "0"), (('metadata', 'revision'), True),
                 (('metadata', 'revision'), 0.0), (('nets', 0, 'is_ground'), 1),
                 (('confidence', 'calibrated'), "false"), (('confidence', 'score'), True),
                 (('components', 0, 'pin_ids'), "R1.a"), (('pins', 0, 'id'), 123),
                 (('source_image_reference', 'width_px'), 640.0))
        for path, value in cases:
            with self.subTest(path=path, value=value):
                data = ir.document_to_dict(populated_document())
                at(data, path[:-1])[path[-1]] = value
                self.reject(data, "/" + "/".join(map(str, path)), "type")

    def test_missing_required_nested_fields(self):
        paths = (("metadata", "origin"), ("components", 0, "parameters"),
                 ("components", 2, "source", "waveform"), ("pins", 0, "role"),
                 ("visual", "entities", 0, "method"), ("confidence", "basis"),
                 ("ambiguities", 0, "state"), ("validation_state", "findings"))
        for path in paths:
            with self.subTest(path=path):
                data = ir.document_to_dict(populated_document())
                del at(data, path[:-1])[path[-1]]
                self.reject(data, "/" + "/".join(map(str, path)), "required")

    def test_required_nullable_fields_cannot_be_omitted(self):
        paths = (("source_image_reference",), ("components", 0, "model_ref"),
                 ("components", 0, "source"), ("pins", 0, "visual_ref"),
                 ("confidence", "score"), ("validation_state", "validated_revision"))
        for path in paths:
            with self.subTest(path=path):
                data = ir.document_to_dict(minimal_document())
                self.assertIsNone(at(data, path))
                del at(data, path[:-1])[path[-1]]
                self.reject(data, "/" + "/".join(map(str, path)), "required")

    def test_null_nonnullable_fields_rejected(self):
        for path in (("metadata",), ("components",), ("confidence",),
                     ("pins", 0, "role"), ("visual", "entities")):
            with self.subTest(path=path):
                data = ir.document_to_dict(minimal_document())
                at(data, path[:-1])[path[-1]] = None
                self.reject(data, "/" + "/".join(map(str, path)))

    def test_array_where_object_expected(self):
        data = ir.document_to_dict(minimal_document())
        data["metadata"] = []
        self.reject(data, "/metadata", "type")

    def test_malformed_confidence(self):
        for score in (-0.01, 1.01, "0.5", [], {}):
            with self.subTest(score=score):
                data = ir.document_to_dict(minimal_document())
                data["confidence"]["score"] = score
                self.reject(data, "/confidence/score")

    def test_malformed_geometry_has_actionable_nested_path(self):
        for field, values in (("bbox", ([0, 1, 2], [0, 1, 2, 3, 4], [-1, 0, 1, 2], [True, 0, 1, 2])),
                              ("position", ([1], [1, 2, 3], [0, -1]))):
            for value in values:
                with self.subTest(field=field, value=value):
                    data = ir.document_to_dict(populated_document())
                    data["visual"]["entities"][0][field] = value
                    result = self.reject(data)
                    self.assertTrue(any(issue.field.startswith("/visual/entities/0/" + field)
                                        for issue in result.issues))
                    self.assertFalse(any(issue.message.startswith("oneOf:") for issue in result.issues))

    def test_malformed_source_image_hash(self):
        for value in ("a" * 63, "A" * 64, "z" * 64, 123):
            with self.subTest(value=value):
                data = ir.document_to_dict(populated_document())
                data["source_image_reference"]["sha256"] = value
                self.reject(data, "/source_image_reference/sha256")

    def test_nonfinite_and_non_json_native_input(self):
        for value in (float("nan"), float("inf"), float("-inf"), Decimal("0.5"), object()):
            with self.subTest(type=type(value)):
                data = ir.document_to_dict(minimal_document())
                data["confidence"]["score"] = value
                self.reject(data, "/confidence/score", "type")
        data = ir.document_to_dict(minimal_document())
        data["components"] = tuple(data["components"])
        self.reject(data, "/components", "type")
        data = ir.document_to_dict(minimal_document())
        data["metadata"][1] = "not_a_string_key"
        self.reject(data, "/metadata", "type")

    def test_quantity_si_is_decimal_string_or_null(self):
        for value in (2000, 2.0, "NaN", "Inf", "1k", "", "1/2"):
            with self.subTest(value=value):
                data = ir.document_to_dict(minimal_document())
                data["components"][0]["value"]["si_value"] = value
                self.reject(data, "/components/0/value/si_value")

    def test_bad_shape_never_reaches_constructors(self):
        data = ir.document_to_dict(minimal_document())
        data["metadata"]["revision"] = "0"
        with patch.object(schema, "_document", side_effect=AssertionError("construction")):
            self.reject(data)

    def test_local_constructor_format_failure_returns_no_partial_document(self):
        # Parent JSON Schema '$' permits a final newline; model fullmatch does not.
        # Preserve the authoritative schema and reject at the typed boundary.
        data = ir.document_to_dict(minimal_document())
        data["metadata"]["circuit_id"] += "\n"
        self.reject(data, "", "construction")

    def test_diagnostics_are_deterministic_and_concise(self):
        data = ir.document_to_dict(minimal_document())
        data["confidence"]["score"] = 2
        del data["metadata"]["revision"]
        data["extra"] = "private_value_marker"
        first = self.reject(data)
        reordered = dict(reversed(list(data.items())))
        self.assertEqual(first, ir.document_from_dict(reordered))
        self.assertEqual([issue.issue_id for issue in first.issues],
                         [f"issue_{i:04d}" for i in range(1, len(first.issues) + 1)])
        for issue in first.issues:
            self.assertLess(len(issue.message), 150)
            self.assertNotIn("private_value_marker", issue.message)

    def test_resource_count_limits(self):
        for path, maximum in ((("components",), 256), (("pins",), 1024),
                              (("nets",), 1024), (("connections",), 1024),
                              (("visual", "entities"), 4096)):
            with self.subTest(path=path):
                data = ir.document_to_dict(populated_document())
                item = at(data, path)[0]
                at(data, path[:-1])[path[-1]] = [item] * maximum
                self.assertEqual(ir.validate_schema(data), ())
                at(data, path).append(item)
                self.reject(data, "/" + "/".join(path), "resourceLimit")

    def test_depth_size_and_cyclic_input_are_bounded(self):
        nested = None
        for _ in range(40):
            nested = [nested]
        data = ir.document_to_dict(minimal_document())
        data["extra"] = nested
        self.reject(data, keyword="resourceLimit")
        data["extra"] = data
        self.reject(data, keyword="resourceLimit")
        result = ir.load_document(" " * (1024 * 1024 + 1))
        self.assertIsNone(result.document)
        self.assertTrue(result.issues[0].message.startswith("resourceLimit:"))
        self.assertEqual(ir.load_document(" " * (1024 * 1024)).issues[0].message,
                         "parse: Invalid strict JSON text.")

    def test_strict_parse_failures_return_issues(self):
        for text in ("{", '{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}',
                     '{"x":NaN}', '{"x":1e999}', "[" * 3000 + "]" * 3000):
            with self.subTest(text=text[:30]):
                result = ir.load_document(text)
                self.assertIsNone(result.document)
                self.assertEqual(result.issues[0].code, "SCHEMA_INVALID")
                self.assertTrue(result.issues[0].message.startswith("parse:"))

    def test_root_and_api_input_types_are_explicit(self):
        for text in ("null", "true", "[]", '"text"', "0"):
            self.assertIsNone(ir.load_document(text).document)
        for value in (None, [], "{}", 0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.document_from_dict(value)
        for value in (None, {}, b"{}", 0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.load_document(value)

    def test_primitive_decode_stays_distinct_from_typed_loading(self):
        text = '{"schema_version":"future","unknown":1,"role":"new_role"}'
        self.assertEqual(ir.decode_json(text), json.loads(text))
        self.assertIsNone(ir.load_document(text).document)

    def test_resource_is_cwd_independent_cached_and_offline(self):
        schema._validator.cache_clear()
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch("socket.create_connection", side_effect=AssertionError("network")):
                    self.assertEqual(ir.load_document(ir.dump_document(minimal_document())).issues, ())
                with patch.object(schema, "files", side_effect=AssertionError("resource reload")):
                    self.assertEqual(ir.load_document(ir.dump_document(populated_document())).issues, ())
            finally:
                # Windows cannot delete the process's current working directory.
                os.chdir(previous)

    def test_missing_dependency_is_clear_setup_failure(self):
        import builtins
        original = builtins.__import__

        def missing(name, *args, **kwargs):
            if name == "jsonschema":
                raise ModuleNotFoundError("simulated missing validator")
            return original(name, *args, **kwargs)

        schema._validator.cache_clear()
        try:
            with patch("builtins.__import__", side_effect=missing):
                with self.assertRaisesRegex(RuntimeError, "requirements-circuit-ir.txt"):
                    ir.load_document("{}")
        finally:
            schema._validator.cache_clear()


class TypedLoadingTests(unittest.TestCase):
    def loaded(self, document):
        result = ir.document_from_dict(ir.document_to_dict(document))
        self.assertEqual(result.issues, ())
        self.assertIsInstance(result.document, ir.CircuitDocument)
        return result.document

    def test_minimal_and_populated_dict_round_trip(self):
        for document in (minimal_document(), populated_document()):
            with self.subTest(origin=document.metadata.origin):
                self.assertEqual(self.loaded(document), document)

    def test_full_json_load_dump_load_round_trip(self):
        document = populated_document()
        result = ir.load_document(ir.dump_document(document))
        self.assertEqual(result.issues, ())
        self.assertEqual(result.document, document)
        self.assertEqual(ir.dump_document(result.document), ir.dump_document(document))
        self.assertEqual(ir.load_document(ir.dump_document(result.document)), result)

    def test_enum_restoration_for_every_wire_family(self):
        document = populated_document()
        cases = ((ir.ComponentType, "components", 0, "type"),
                 (ir.PinRole, "pins", 0, "role"), (ir.Origin, "metadata", "origin"),
                 (ir.WireValidationStatus, "validation_state", "status"),
                 (ir.IssueSeverity, "validation_state", "findings", 0, "severity"),
                 (ir.ConfidenceBasis, "confidence", "basis"),
                 (ir.ValueGrammar, "components", 1, "value", "grammar"),
                 (ir.WaveformKind, "components", 2, "source", "waveform", "kind"),
                 (ir.VisualKind, "visual", "entities", 0, "kind"),
                 (ir.Orientation, "visual", "entities", 0, "orientation"),
                 (ir.AmbiguityKind, "ambiguities", 0, "kind"),
                 (ir.AmbiguityStatus, "ambiguities", 0, "state"))
        for enum, *path in cases:
            for member in enum:
                with self.subTest(enum=enum, member=member):
                    data = ir.document_to_dict(document)
                    at(data, path[:-1])[path[-1]] = member.value
                    result = ir.document_from_dict(data)
                    self.assertEqual(result.issues, ())
                    record = result.document
                    for part in path:
                        record = record[part] if type(part) is int else getattr(record, part)
                    self.assertIs(record, member)

    def test_tuple_collections_and_nested_typed_geometry(self):
        document = self.loaded(populated_document())
        for collection in (document.components, document.pins, document.nets, document.connections,
                           document.labels, document.ambiguities, document.warnings,
                           document.visual.entities, document.components[0].pin_ids,
                           document.components[0].parameters, document.visual.entities[0].points,
                           document.ambiguities[0].candidates, document.validation_state.findings):
            self.assertIs(type(collection), tuple)
        self.assertIsInstance(document.visual.entities[0].bbox, ir.BoundingBox)
        self.assertIsInstance(document.visual.entities[0].position, ir.PixelPoint)
        self.assertIsInstance(document.visual.entities[0].points[0], ir.PixelPoint)
        self.assertIsInstance(document.components[2].source, ir.SourceConfiguration)
        self.assertIsInstance(document.components[2].source.ac, ir.ACConfiguration)
        self.assertIsInstance(document.source_image_reference, ir.SourceImageReference)

    def test_quantity_precision_literal_and_parameter_map_equality(self):
        document = populated_document()
        data = ir.document_to_dict(document)
        data["components"][0]["parameters"] = dict(reversed(list(data["components"][0]["parameters"].items())))
        loaded = ir.document_from_dict(data).document
        self.assertEqual(loaded, document)
        self.assertEqual(loaded.components[2].source.dc.literal, " 0.1 ")
        self.assertEqual(loaded.components[2].source.dc.si_value,
                         "0.100000000000000000000000000000000001")
        self.assertIs(type(loaded.components[2].source.dc.si_value), str)
        self.assertEqual(ir.dump_document(loaded), ir.dump_document(document))

    def test_nullable_and_unresolved_records_round_trip(self):
        document = populated_document()
        visual = replace(document.visual.entities[0], bbox=None, position=None, text=None)
        ambiguity = replace(document.ambiguities[0], state=ir.AmbiguityStatus.UNRESOLVED,
                            selected_candidate_id=None, resolution_note=None)
        component = replace(document.components[1], value=ir.Quantity(None, None, "ohm", ir.ValueGrammar.UNRESOLVED))
        source = replace(document.components[2].source, dc=None, ac=None)
        changed = replace(document, components=(component, replace(document.components[2], source=source)),
                          ambiguities=(ambiguity,), visual=replace(document.visual, entities=(visual,)),
                          labels=(replace(document.labels[0], net_id=None, visual_ref=None),))
        self.assertEqual(self.loaded(changed), changed)

    def test_imported_snapshots_and_canonical_connections_remain_archival(self):
        document = self.loaded(populated_document())
        self.assertEqual(document.validation_state, populated_document().validation_state)
        data = ir.document_to_dict(document)
        self.assertEqual(set(data["nets"][0]), {"id", "is_ground"})
        self.assertNotIn("net_id", data["pins"][0])
        self.assertNotIn("technical_state", data)
        self.assertNotIn("approved", data)
        self.assertEqual(data["validation_state"]["status"], "reviewed")

    def test_array_order_and_input_preservation_on_success_and_failure(self):
        data = ir.document_to_dict(populated_document())
        data["components"].reverse()
        data["visual"]["entities"][0]["points"].reverse()
        before = deepcopy(data)
        result = ir.document_from_dict(data)
        self.assertEqual(result.issues, ())
        self.assertEqual(ir.document_to_dict(result.document), before)
        self.assertEqual(data, before)
        data["components"].clear()
        self.assertEqual(len(result.document.components), 3)
        before["extra"] = True
        failed_before = deepcopy(before)
        self.assertIsNone(ir.document_from_dict(before).document)
        self.assertEqual(before, failed_before)
        with self.assertRaises(FrozenInstanceError):
            result.document.metadata.revision = 8


if __name__ == "__main__":
    unittest.main()
