"""M1B wire projection/primitive decode; typed loading is deliberately M1C."""
from dataclasses import replace
from enum import Enum
import json
from pathlib import Path
import unittest

import circuit_ir as ir
from circuit_ir.serialization import decode_json, document_to_dict, dump_document


def minimal_document():
    confidence = ir.Confidence(None, ir.ConfidenceBasis.MANUAL, False)
    resistor = ir.Component("R1", ir.ComponentType.RESISTOR, ("R1.a", "R1.b"),
                            ir.Quantity("2k", "2000", "ohm", ir.ValueGrammar.SPICE),
                            None, (), None, None)
    return ir.CircuitDocument(
        ir.SCHEMA_VERSION, ir.Metadata("serialization_demo", 0, ir.Origin.MANUAL,
                                       "phase_a_draft1"), None, (resistor,),
        (ir.Pin("R1.a", "R1", ir.PinRole.A, None),
         ir.Pin("R1.b", "R1", ir.PinRole.B, None)),
        (ir.Net("nin", False), ir.Net("n0", True)),
        (ir.Connection("R1.a", "nin", (), confidence),
         ir.Connection("R1.b", "n0", (), confidence)),
        (ir.Label("label_in", "vin", "flat", "nin", None),),
        ir.VisualProvenance("original_pixels", ()), confidence, (), (),
        ir.ImportedValidationState(ir.WireValidationStatus.DRAFT, None, None, ()),
    )


def populated_document():
    doc = minimal_document()
    confidence = ir.Confidence(0.875, ir.ConfidenceBasis.PROVIDER_SCORE, False)
    voltage = ir.Quantity(" 0.1 ", "0.100000000000000000000000000000000001", "V",
                          ir.ValueGrammar.MANUAL)
    phase = ir.Quantity("-90", "-90", "deg", ir.ValueGrammar.SI)
    ac = ir.ACConfiguration(voltage, phase)
    waveform = ir.Waveform(ir.WaveformKind.SINE,
                           (("offset", voltage), ("amplitude", voltage),
                            ("frequency", ir.Quantity("1k", "1000", "Hz", ir.ValueGrammar.SPICE))))
    source = ir.SourceConfiguration(voltage, ac, waveform)
    dimension = ir.Quantity("1u", "0.000001", "m", ir.ValueGrammar.SPICE)
    mos = ir.Component("M1", ir.ComponentType.NMOS,
                       ("M1.d", "M1.g", "M1.s", "M1.b"), None, "educational_model",
                       (("width", dimension), ("length", dimension)), None, "symbol_M1")
    vsource = ir.Component("V1", ir.ComponentType.VOLTAGE_SOURCE,
                           ("V1.p", "V1.n"), None, None, (), source, None)
    visual = ir.VisualEntity("symbol_M1", ir.VisualKind.SYMBOL,
                             ir.BoundingBox(10, 20, 30.5, 40), ir.PixelPoint(25, 35),
                             ir.Orientation.R90_MIRROR,
                             (ir.PixelPoint(30, 40), ir.PixelPoint(10, 20)),
                             "일반 NMOS", "manual", confidence)
    ambiguity = ir.Ambiguity("choice_a", ir.AmbiguityKind.PIN_MAPPING, ("M1",),
                             (ir.Candidate("candidate_z", "Gate at terminal 2"),
                              ir.Candidate("candidate_a", "Gate at terminal 1")),
                             ir.AmbiguityStatus.RESOLVED, "candidate_z", "Manually reviewed draft")
    finding = ir.ImportedFinding("finding_a", "CHECK_DEFERRED", ir.IssueSeverity.WARNING,
                                 ("M1",), "Archival model lookup was deferred", ("symbol_M1",))
    return replace(doc, metadata=replace(doc.metadata, revision=7, origin=ir.Origin.IMAGE),
                   source_image_reference=ir.SourceImageReference("image_a", "a" * 64, 640, 480),
                   components=(mos, doc.components[0], vsource),
                   pins=doc.pins + (ir.Pin("M1.g", "M1", ir.PinRole.GATE, "symbol_M1"),),
                   visual=ir.VisualProvenance("original_pixels", (visual,)),
                   confidence=confidence, ambiguities=(ambiguity,), warnings=("finding_a",),
                   validation_state=ir.ImportedValidationState(ir.WireValidationStatus.REVIEWED,
                                                                7, "archival_rules", (finding,)))


class ProjectionTests(unittest.TestCase):
    def test_authored_wire_golden_and_primitive_round_trip(self):
        path = Path(__file__).parent / "fixtures/circuit_ir/serialization_draft.json"
        expected = json.loads(path.read_text(encoding="utf-8"))
        doc = minimal_document()
        self.assertEqual(document_to_dict(doc), expected)
        self.assertEqual(decode_json(dump_document(doc)), expected)

    def test_populated_nested_records_have_exact_wire_shapes(self):
        doc = populated_document()
        data = document_to_dict(doc)
        self.assertEqual(decode_json(dump_document(doc)), data)
        self.assertEqual(data["source_image_reference"],
                         {"asset_id": "image_a", "sha256": "a" * 64,
                          "width_px": 640, "height_px": 480})
        visual = data["visual"]["entities"][0]
        self.assertEqual(visual["bbox"], [10, 20, 30.5, 40])
        self.assertEqual(visual["position"], [25, 35])
        self.assertEqual(visual["points"], [[30, 40], [10, 20]])
        self.assertEqual(visual["orientation"], "r90_mirror")
        self.assertEqual(visual["text"], "일반 NMOS")
        ambiguity = data["ambiguities"][0]
        self.assertEqual(ambiguity["selected_candidate_id"], "candidate_z")
        self.assertEqual([c["id"] for c in ambiguity["candidates"]],
                         ["candidate_z", "candidate_a"])
        source = data["components"][2]["source"]
        self.assertEqual(source["ac"]["phase"]["si_value"], "-90")
        self.assertEqual(source["waveform"]["parameters"]["frequency"]["si_value"], "1000")

    def test_every_wire_enum_family_projects_plain_strings(self):
        doc = populated_document()
        for value in ir.ComponentType:
            changed = replace(doc.components[0], type=value)
            self.assertEqual(document_to_dict(replace(doc, components=(changed,)))["components"][0]["type"], value.value)
        for value in ir.PinRole:
            changed = replace(doc.pins[0], role=value)
            self.assertEqual(document_to_dict(replace(doc, pins=(changed,)))["pins"][0]["role"], value.value)
        for value in ir.Origin:
            changed = replace(doc.metadata, origin=value)
            self.assertEqual(document_to_dict(replace(doc, metadata=changed))["metadata"]["origin"], value.value)
        for value in ir.WireValidationStatus:
            changed = replace(doc.validation_state, status=value)
            self.assertEqual(document_to_dict(replace(doc, validation_state=changed))["validation_state"]["status"], value.value)
        for value in ir.IssueSeverity:
            finding = replace(doc.validation_state.findings[0], severity=value)
            state = replace(doc.validation_state, findings=(finding,))
            self.assertEqual(document_to_dict(replace(doc, validation_state=state))["validation_state"]["findings"][0]["severity"], value.value)
        for value in ir.ConfidenceBasis:
            changed = replace(doc.confidence, basis=value)
            self.assertEqual(document_to_dict(replace(doc, confidence=changed))["confidence"]["basis"], value.value)
        for value in ir.ValueGrammar:
            quantity = replace(doc.components[1].value, grammar=value)
            component = replace(doc.components[1], value=quantity)
            self.assertEqual(document_to_dict(replace(doc, components=(component,)))["components"][0]["value"]["grammar"], value.value)
        for value in ir.WaveformKind:
            component = doc.components[2]
            source = replace(component.source, waveform=replace(component.source.waveform, kind=value))
            changed = replace(component, source=source)
            self.assertEqual(document_to_dict(replace(doc, components=(changed,)))["components"][0]["source"]["waveform"]["kind"], value.value)
        for enum, field in ((ir.VisualKind, "kind"), (ir.Orientation, "orientation")):
            for value in enum:
                entity = replace(doc.visual.entities[0], **{field: value})
                changed = replace(doc, visual=replace(doc.visual, entities=(entity,)))
                self.assertEqual(document_to_dict(changed)["visual"]["entities"][0][field], value.value)
        for enum, field in ((ir.AmbiguityKind, "kind"), (ir.AmbiguityStatus, "state")):
            for value in enum:
                ambiguity = replace(doc.ambiguities[0], **{field: value})
                self.assertEqual(document_to_dict(replace(doc, ambiguities=(ambiguity,)))["ambiguities"][0][field], value.value)

    def test_projection_has_only_json_native_types(self):
        def check(value):
            self.assertNotIsInstance(value, Enum)
            self.assertIn(type(value), (dict, list, str, int, float, bool, type(None)))
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIs(type(key), str)
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        check(document_to_dict(populated_document()))

    def test_all_required_nullable_fields_are_emitted(self):
        data = document_to_dict(minimal_document())
        self.assertIsNone(data["source_image_reference"])
        component = data["components"][0]
        for key in ("model_ref", "source", "visual_ref"):
            self.assertIn(key, component)
            self.assertIsNone(component[key])
        self.assertIsNone(data["pins"][0]["visual_ref"])
        self.assertIsNone(data["confidence"]["score"])
        for key in ("validated_revision", "ruleset_version"):
            self.assertIsNone(data["validation_state"][key])
        doc = populated_document()
        visual = replace(doc.visual.entities[0], bbox=None, position=None, text=None)
        ambiguity = replace(doc.ambiguities[0], selected_candidate_id=None, resolution_note=None)
        unresolved = replace(doc.components[1].value, literal=None, si_value=None)
        changed = replace(doc, visual=replace(doc.visual, entities=(visual,)),
                          ambiguities=(ambiguity,),
                          components=(replace(doc.components[1], value=unresolved),),
                          labels=(replace(doc.labels[0], net_id=None, visual_ref=None),))
        result = decode_json(dump_document(changed))
        self.assertIsNone(result["visual"]["entities"][0]["bbox"])
        self.assertIsNone(result["visual"]["entities"][0]["position"])
        self.assertIsNone(result["visual"]["entities"][0]["text"])
        self.assertIsNone(result["ambiguities"][0]["selected_candidate_id"])
        self.assertIsNone(result["ambiguities"][0]["resolution_note"])
        self.assertIsNone(result["components"][0]["value"]["literal"])
        self.assertIsNone(result["components"][0]["value"]["si_value"])
        self.assertIsNone(result["labels"][0]["net_id"])

    def test_null_source_ac_and_dc_are_preserved(self):
        doc = populated_document()
        source = replace(doc.components[2].source, dc=None, ac=None)
        changed = replace(doc, components=(replace(doc.components[2], source=source),))
        result = decode_json(dump_document(changed))["components"][0]["source"]
        self.assertIsNone(result["dc"])
        self.assertIsNone(result["ac"])

    def test_original_literals_and_precision_are_preserved(self):
        doc = populated_document()
        quantity = doc.components[2].source.dc
        decoded = decode_json(dump_document(doc))["components"][2]["source"]["dc"]
        self.assertEqual(decoded["literal"], quantity.literal)
        self.assertEqual(decoded["si_value"], quantity.si_value)
        self.assertIs(type(decoded["si_value"]), str)

    def test_array_order_and_parameter_map_content_are_preserved(self):
        doc = populated_document()
        data = decode_json(dump_document(doc))
        self.assertEqual([c["id"] for c in data["components"]], [c.id for c in doc.components])
        self.assertEqual([p["id"] for p in data["pins"]], [p.id for p in doc.pins])
        self.assertEqual([n["id"] for n in data["nets"]], [n.id for n in doc.nets])
        self.assertEqual([c["pin_id"] for c in data["connections"]], [c.pin_id for c in doc.connections])
        self.assertEqual(set(data["components"][0]["parameters"]), {"length", "width"})

    def test_equal_parameter_maps_dump_identically(self):
        doc = populated_document()
        component = replace(doc.components[0], parameters=tuple(reversed(doc.components[0].parameters)))
        changed = replace(doc, components=(component,) + doc.components[1:])
        self.assertEqual(doc, changed)
        self.assertEqual(dump_document(doc), dump_document(changed))

    def test_output_is_deterministic_sorted_utf8_compatible_text(self):
        doc = populated_document()
        output = dump_document(doc)
        self.assertEqual(output, dump_document(doc))
        self.assertEqual(output, json.dumps(document_to_dict(doc), sort_keys=True,
                                            ensure_ascii=True, allow_nan=False, indent=2) + "\n")
        self.assertTrue(output.endswith("\n"))
        self.assertNotIn("\r", output)
        self.assertEqual(decode_json(output.encode("utf-8").decode("utf-8"))["visual"]["entities"][0]["text"], "일반 NMOS")

    def test_projection_mutation_cannot_modify_document_or_another_projection(self):
        doc = populated_document()
        before = dump_document(doc)
        data = document_to_dict(doc)
        data["components"][0]["pin_ids"].append("other_pin")
        data["components"][0]["parameters"]["width"]["si_value"] = "wrong"
        data["visual"]["entities"][0]["points"][0][0] = 999
        data["ambiguities"][0]["candidates"].reverse()
        data["validation_state"]["findings"].clear()
        self.assertEqual(dump_document(doc), before)
        self.assertNotEqual(document_to_dict(doc), data)

    def test_no_derived_connectivity_or_authorization_is_emitted(self):
        data = document_to_dict(populated_document())
        self.assertEqual(set(data["nets"][0]), {"id", "is_ground"})
        self.assertNotIn("net_id", data["pins"][0])
        self.assertNotIn("net_id", data["components"][0])
        self.assertNotIn("approved", data)
        self.assertNotIn("technical_state", data)
        self.assertEqual(data["validation_state"]["status"], "reviewed")
        self.assertEqual(data["warnings"], ["finding_a"])

    def test_projection_does_not_run_electrical_or_reference_validation(self):
        doc = minimal_document()
        changed = replace(doc, components=doc.components * 2, nets=(),
                          connections=(replace(doc.connections[0], net_id="missing_net"),))
        data = decode_json(dump_document(changed))
        self.assertEqual(len(data["components"]), 2)
        self.assertEqual(data["nets"], [])
        self.assertEqual(data["connections"][0]["net_id"], "missing_net")

    def test_projection_rejects_non_document_input(self):
        for value in (None, {}, [], "text"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                document_to_dict(value)


class DecodeTests(unittest.TestCase):
    def test_all_primitive_shapes_decode_without_typed_construction(self):
        for text, expected in (("null", None), ("true", True), ("[1,2]", [1, 2]),
                               ('"text"', "text"), ("{}", {}), ("0", 0)):
            with self.subTest(text=text):
                self.assertEqual(decode_json(text), expected)

    def test_duplicate_keys_rejected_at_any_depth_including_escaped_keys(self):
        for text in ('{"a":1,"a":2}', '{"nested":{"x":1,"x":2}}',
                     '[{"a":1,"\\u0061":2}]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_json(text)

    def test_nonfinite_constants_and_numeric_overflow_rejected(self):
        for text in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999",
                     '{"score":NaN}', "[1e999]"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_json(text)

    def test_syntax_failures_are_explicit(self):
        for text in ("", " ", "{", '{"a":1,}', "01", "{} {}", "/*comment*/{}"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_json(text)

    def test_decoder_does_not_guess_missing_fields_or_reject_schema_fields(self):
        # Version, unknown-key and enum checks await the bundled M1C schema.
        text = '{"schema_version":"future","unknown":1,"role":"not_an_enum"}'
        self.assertEqual(decode_json(text), json.loads(text))
        self.assertEqual(decode_json('{"value":null}'), {"value": None})
        self.assertEqual(decode_json('{}'), {})

    def test_finite_scores_coordinates_and_quantity_strings_retain_types(self):
        result = decode_json('{"revision":0,"coordinate":0.125,"score":1,"si_value":"1e-300"}')
        self.assertIs(type(result["revision"]), int)
        self.assertIs(type(result["coordinate"]), float)
        self.assertIs(type(result["score"]), int)
        self.assertEqual(result["si_value"], "1e-300")

    def test_decoder_rejects_non_text_without_coercion(self):
        for value in (b"{}", None, {}, 123):
            with self.subTest(value=value), self.assertRaises(TypeError):
                decode_json(value)

    def test_excessive_recursion_reports_value_error(self):
        with self.assertRaises(ValueError):
            decode_json("[" * 3000 + "]" * 3000)


if __name__ == "__main__":
    unittest.main()
