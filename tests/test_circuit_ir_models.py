"""M1A records only: no schema, value parser, graph or electrical validation."""
from dataclasses import FrozenInstanceError, MISSING, fields, replace
from pathlib import Path
import subprocess
import sys
import unittest

import circuit_ir as ir


def manual_confidence():
    return ir.Confidence(None, ir.ConfidenceBasis.MANUAL, False)


def resistor(identifier="R1"):
    return ir.Component(
        identifier, ir.ComponentType.RESISTOR,
        (f"{identifier}.a", f"{identifier}.b"),
        ir.Quantity("2k", "2000", "ohm", ir.ValueGrammar.SPICE),
        None, (), None, None,
    )


def document():
    """A manually authored structural record, not a validation success."""
    return ir.CircuitDocument(
        ir.SCHEMA_VERSION,
        ir.Metadata("divider_demo", 0, ir.Origin.MANUAL, "phase_a_draft1"),
        None,
        (resistor(),),
        (ir.Pin("R1.a", "R1", ir.PinRole.A, None),
         ir.Pin("R1.b", "R1", ir.PinRole.B, None)),
        (ir.Net("nin", False), ir.Net("n0", True)),
        (ir.Connection("R1.a", "nin", (), manual_confidence()),
         ir.Connection("R1.b", "n0", (), manual_confidence())),
        (ir.Label("label_in", "vin", "flat", "nin", None),),
        ir.VisualProvenance("original_pixels", ()),
        manual_confidence(), (), (),
        ir.ImportedValidationState(ir.WireValidationStatus.DRAFT, None, None, ()),
    )


class EnumTests(unittest.TestCase):
    def test_exact_stable_values_and_no_extra_members(self):
        expected = {
            ir.ComponentType: ("resistor", "capacitor", "inductor", "voltage_source",
                               "current_source", "nmos", "pmos", "unknown"),
            ir.PinRole: ("a", "b", "positive", "negative", "drain", "gate", "source",
                         "bulk", "unknown"),
            ir.IssueSeverity: ("ERROR", "WARNING", "AMBIGUOUS", "CONFIRMED"),
            ir.WireValidationStatus: ("draft", "blocked", "ready_for_review", "reviewed"),
            ir.TechnicalState: ("UNVALIDATED", "INVALID", "AMBIGUOUS", "VALID"),
            ir.NetRole: ("GROUND", "NORMAL"),
            ir.WaveformKind: ("none", "sine", "pulse"),
            ir.ValueGrammar: ("spice", "si", "manual", "unresolved"),
            ir.ConfidenceBasis: ("provider_score", "heuristic", "manual", "unknown"),
            ir.Origin: ("image", "manual"),
            ir.VisualKind: ("symbol", "pin", "wire", "junction", "ground", "label",
                            "text", "unknown"),
            ir.Orientation: ("r0", "r90", "r180", "r270", "r0_mirror", "r90_mirror",
                             "r180_mirror", "r270_mirror", "unknown"),
            ir.AmbiguityKind: ("symbol_type", "value", "crossing", "wire_gap",
                               "label_attachment", "pin_mapping", "body_connection"),
            ir.AmbiguityStatus: ("unresolved", "resolved"),
        }
        for enum, values in expected.items():
            with self.subTest(enum=enum.__name__):
                self.assertEqual(tuple(member.value for member in enum), values)
                self.assertEqual(len(enum.__members__), len(values))
                for value in values:
                    self.assertIsInstance(enum(value), str)
                    self.assertEqual(enum(value), value)

    def test_invalid_enum_values_fail_without_coercion(self):
        for enum in (ir.ComponentType, ir.PinRole, ir.IssueSeverity,
                     ir.WireValidationStatus, ir.TechnicalState, ir.NetRole,
                     ir.WaveformKind, ir.ValueGrammar, ir.ConfidenceBasis,
                     ir.Origin, ir.VisualKind, ir.Orientation, ir.AmbiguityKind,
                     ir.AmbiguityStatus):
            for value in ("not_supported", "", 1, None):
                with self.subTest(enum=enum.__name__, value=value):
                    with self.assertRaises(ValueError):
                        enum(value)

    def test_wire_state_is_distinct_from_technical_validity(self):
        self.assertIsNot(ir.WireValidationStatus, ir.TechnicalState)
        self.assertFalse(hasattr(ir.TechnicalState, "APPROVED"))
        self.assertFalse(hasattr(ir, "PinType"))
        self.assertFalse(hasattr(ir, "SourceType"))


class PrimitiveTests(unittest.TestCase):
    def test_confidence_explicit_null_and_range_boundaries(self):
        self.assertIsNone(manual_confidence().score)
        for score in (0, 0.5, 1):
            self.assertEqual(ir.Confidence(score, ir.ConfidenceBasis.UNKNOWN, False).score,
                             score)

    def test_invalid_confidence_values_and_types(self):
        for score in (-0.01, 1.01, float("nan"), float("inf"), -float("inf")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                ir.Confidence(score, ir.ConfidenceBasis.HEURISTIC, False)
        for score in (True, False, "0.5"):
            with self.subTest(score=score), self.assertRaises(TypeError):
                ir.Confidence(score, ir.ConfidenceBasis.MANUAL, False)
        with self.assertRaises(TypeError):
            ir.Confidence(None, "manual", False)
        with self.assertRaises(TypeError):
            ir.Confidence(None, ir.ConfidenceBasis.MANUAL, 0)

    def test_geometry_equality_and_zero_dimensions(self):
        self.assertEqual(ir.BoundingBox(0, 2.5, 10, 0), ir.BoundingBox(0, 2.5, 10, 0))
        self.assertNotEqual(ir.PixelPoint(2, 3), ir.PixelPoint(3, 2))
        self.assertEqual(ir.PixelPoint(0, 0), ir.PixelPoint(0, 0))

    def test_geometry_rejects_nonfinite_negative_bool_and_coercion(self):
        for value in (-1, float("nan"), float("inf"), True, "1"):
            error = TypeError if isinstance(value, (bool, str)) else ValueError
            for field in ("x", "y", "width", "height"):
                data = dict(x=0, y=0, width=0, height=0)
                data[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(error):
                    ir.BoundingBox(**data)
            for field in ("x", "y"):
                data = dict(x=0, y=0)
                data[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(error):
                    ir.PixelPoint(**data)

    def test_metadata_has_explicit_revision_and_no_defaults(self):
        metadata = document().metadata
        self.assertEqual(metadata.revision, 0)
        self.assertEqual(metadata.origin, ir.Origin.MANUAL)
        for value, error in ((-1, ValueError), (True, TypeError), (1.0, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                replace(metadata, revision=value)
        with self.assertRaises(TypeError):
            ir.Metadata("demo")
        with self.assertRaises(TypeError):
            replace(metadata, origin="manual")

    def test_ids_are_bounded_opaque_strings(self):
        self.assertEqual(ir.Net("N_1.a-b", False).id, "N_1.a-b")
        for identifier in ("", "1net", "n space", "n/1", "n" * 65, "n\n"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                ir.Net(identifier, False)
        with self.assertRaises(TypeError):
            ir.Net(1, False)

    def test_source_image_reference_is_metadata_not_file_access(self):
        reference = ir.SourceImageReference("image_a", "a" * 64, 640, 480)
        self.assertEqual(reference.width_px, 640)
        for changes in ({"sha256": "A" * 64}, {"sha256": "a" * 63},
                        {"width_px": 0}, {"height_px": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(reference, **changes)
        for changes in ({"width_px": True}, {"height_px": 1.5}):
            with self.subTest(changes=changes), self.assertRaises(TypeError):
                replace(reference, **changes)

    def test_quantity_retains_strings_without_parsing_or_normalization(self):
        literal = " 2.200000000000000000000000000000000001k "
        si = "2200.000000000000000000000000000000001"
        value = ir.Quantity(literal, si, "ohm", ir.ValueGrammar.SPICE)
        self.assertEqual(value.literal, literal)
        self.assertEqual(value.si_value, si)
        self.assertIsInstance(value.si_value, str)
        self.assertIsNone(ir.Quantity(None, None, "V", ir.ValueGrammar.UNRESOLVED).si_value)
        # Parsing and literal/SI consistency belong to M1B and later validation.
        self.assertEqual(replace(value, si_value="unparsed").si_value, "unparsed")
        for unit in ("ohm", "F", "H", "V", "A", "Hz", "s", "deg", "m"):
            self.assertEqual(replace(value, unit=unit).unit, unit)

    def test_quantity_rejects_numeric_storage_and_unknown_units(self):
        value = resistor().value
        with self.assertRaises(TypeError):
            replace(value, si_value=2000.0)
        with self.assertRaises(ValueError):
            replace(value, unit="W")
        with self.assertRaises(ValueError):
            replace(value, literal="1" * 129)


class RecordTests(unittest.TestCase):
    def test_pin_role_is_explicit_and_required(self):
        pin = ir.Pin("M1.p1", "M1", ir.PinRole.GATE, None)
        self.assertEqual(pin.role, ir.PinRole.GATE)
        self.assertIsNone(pin.visual_ref)
        with self.assertRaises(TypeError):
            ir.Pin("M1.p1", "M1", ir.PinRole.GATE)
        with self.assertRaises(TypeError):
            replace(pin, role="gate")

    def test_all_supported_components_preserve_explicit_pin_order(self):
        passive = resistor()
        for kind in ir.ComponentType:
            with self.subTest(kind=kind):
                component = replace(passive, type=kind)
                self.assertEqual(component.type, kind)
                self.assertEqual(component.pin_ids, ("R1.a", "R1.b"))
        with self.assertRaises(TypeError):
            replace(passive, type="resistor")

    def test_mos_four_roles_and_parameters_without_body_inference(self):
        roles = (ir.PinRole.DRAIN, ir.PinRole.GATE, ir.PinRole.SOURCE, ir.PinRole.BULK)
        pins = tuple(ir.Pin(f"M1.p{i}", "M1", role, None)
                     for i, role in enumerate(roles))
        dimension = ir.Quantity("1u", "0.000001", "m", ir.ValueGrammar.SPICE)
        mos = ir.Component("M1", ir.ComponentType.NMOS, tuple(p.id for p in pins),
                           None, "educational_nmos", (("width", dimension),
                                                     ("length", dimension)), None, None)
        self.assertEqual(tuple(p.role for p in pins), roles)
        self.assertEqual(dict(mos.parameters)["width"], dimension)
        self.assertEqual(len(replace(mos, pin_ids=mos.pin_ids[:3]).pin_ids), 3)

    def test_visual_records_remain_separate_and_nullable(self):
        point = ir.PixelPoint(10, 20)
        entity = ir.VisualEntity("symbol_R1", ir.VisualKind.SYMBOL,
                                 ir.BoundingBox(0, 0, 20, 40), point,
                                 ir.Orientation.R90_MIRROR, (point,), "R1", "manual",
                                 manual_confidence())
        visual = ir.VisualProvenance("original_pixels", (entity,))
        component = replace(resistor(), visual_ref=entity.id)
        self.assertEqual(component.visual_ref, visual.entities[0].id)
        self.assertIsNone(resistor().visual_ref)
        self.assertIsNone(replace(entity, bbox=None, position=None, text=None).bbox)
        with self.assertRaises(ValueError):
            replace(visual, coordinate_space="normalized_pixels")
        with self.assertRaises(TypeError):
            replace(entity, points=([10, 20],))

    def test_nets_store_ground_flag_and_labels_are_independent(self):
        self.assertEqual(ir.Net("n0", True).role, ir.NetRole.GROUND)
        self.assertEqual(ir.Net("nout", False).role, ir.NetRole.NORMAL)
        label = ir.Label("label_out", "vout", "flat", "nout", None)
        self.assertEqual(label.text, "vout")
        self.assertIsNone(replace(label, net_id=None).net_id)
        self.assertEqual(tuple(f.name for f in fields(ir.Net)), ("id", "is_ground"))
        with self.assertRaises(TypeError):
            ir.Net("n0", 1)
        with self.assertRaises(ValueError):
            replace(label, scope="hierarchical")

    def test_connection_holds_ids_without_reference_existence_checks(self):
        connection = ir.Connection("missing.pin", "missing_net", (), manual_confidence())
        self.assertEqual(connection.pin_id, "missing.pin")
        self.assertEqual(connection.net_id, "missing_net")
        self.assertEqual(connection.visual_refs, ())

    def test_typed_source_and_waveform_parameters_preserve_values(self):
        dc = ir.Quantity("0", "0", "V", ir.ValueGrammar.MANUAL)
        ac = ir.ACConfiguration(ir.Quantity("1", "1", "V", ir.ValueGrammar.MANUAL),
                                ir.Quantity("0", "0", "deg", ir.ValueGrammar.MANUAL))
        frequency = ir.Quantity("1k", "1000", "Hz", ir.ValueGrammar.SPICE)
        waveform = ir.Waveform(ir.WaveformKind.SINE,
                               (("offset", dc), ("amplitude", ac.magnitude),
                                ("frequency", frequency)))
        source = ir.SourceConfiguration(dc, ac, waveform)
        component = replace(resistor("V1"), type=ir.ComponentType.VOLTAGE_SOURCE,
                            value=None, source=source)
        self.assertEqual(component.source.dc.si_value, "0")
        self.assertEqual(dict(waveform.parameters),
                         {"offset": dc, "amplitude": ac.magnitude, "frequency": frequency})
        self.assertIsNone(replace(source, dc=None, ac=None).dc)

    def test_parameter_collections_reject_mutable_or_malformed_storage(self):
        value = resistor().value
        for params, error in (({"width": value}, TypeError),
                              ([('width', value)], TypeError),
                              ((["width", value],), TypeError),
                              ((("width",),), ValueError),
                              ((("width", 1),), TypeError),
                              ((("width", value), ("width", value)), ValueError)):
            with self.subTest(params=params), self.assertRaises(error):
                replace(resistor(), parameters=params)

    def test_parameter_mapping_order_does_not_change_equality_or_hash(self):
        width = ir.Quantity("2u", "0.000002", "m", ir.ValueGrammar.SPICE)
        length = ir.Quantity("1u", "0.000001", "m", ir.ValueGrammar.SPICE)
        pairs = (("width", width), ("length", length))
        component = ir.Component("M1", ir.ComponentType.NMOS, (), None, "model_a",
                                 pairs, None, None)
        reordered = replace(component, parameters=tuple(reversed(pairs)))
        self.assertEqual(component, reordered)
        self.assertEqual(hash(component), hash(reordered))
        self.assertEqual(pairs, (("width", width), ("length", length)))
        self.assertNotEqual(component, replace(component, parameters=(("width", length),)))

        offset = ir.Quantity("0", "0", "V", ir.ValueGrammar.MANUAL)
        amplitude = ir.Quantity("1", "1", "V", ir.ValueGrammar.MANUAL)
        frequency = ir.Quantity("1k", "1000", "Hz", ir.ValueGrammar.SPICE)
        waveform = ir.Waveform(ir.WaveformKind.SINE,
                               (("offset", offset), ("amplitude", amplitude),
                                ("frequency", frequency)))
        reordered_waveform = replace(waveform, parameters=tuple(reversed(waveform.parameters)))
        self.assertEqual(waveform, reordered_waveform)
        self.assertEqual(hash(waveform), hash(reordered_waveform))
        source = ir.SourceConfiguration(offset, None, waveform)
        source_component = replace(resistor("V1"), type=ir.ComponentType.VOLTAGE_SOURCE,
                                   value=None, source=source)
        doc = replace(document(), components=(component, source_component))
        reordered_doc = replace(doc, components=(reordered, replace(source_component,
            source=replace(source, waveform=reordered_waveform))))
        self.assertEqual(doc, reordered_doc)
        self.assertEqual(hash(doc), hash(reordered_doc))

    def test_ambiguities_preserve_alternatives_and_resolution_snapshot(self):
        candidate = ir.Candidate("candidate_a", "Resistor")
        ambiguity = ir.Ambiguity("decision_a", ir.AmbiguityKind.SYMBOL_TYPE,
                                 ("U1",), (candidate,), ir.AmbiguityStatus.UNRESOLVED,
                                 None, None)
        self.assertIsNone(ambiguity.selected_candidate_id)
        resolved = replace(ambiguity, state=ir.AmbiguityStatus.RESOLVED,
                           selected_candidate_id="candidate_a")
        self.assertEqual(resolved.candidates, (candidate,))
        # Candidate lookup and resolution completeness are later validation rules.
        self.assertEqual(replace(resolved, selected_candidate_id="missing").selected_candidate_id,
                         "missing")

    def test_imported_findings_remain_untrusted_data(self):
        finding = ir.ImportedFinding("finding_a", "VALUE_INVALID", ir.IssueSeverity.WARNING,
                                     ("R1",), "Authored archival note", ())
        state = ir.ImportedValidationState(ir.WireValidationStatus.REVIEWED, 0,
                                           "old_ruleset", (finding,))
        doc = replace(document(), validation_state=state, warnings=(finding.id,))
        self.assertEqual(doc.validation_state.findings[0], finding)
        self.assertFalse(hasattr(doc, "approved"))
        self.assertFalse(hasattr(doc, "can_execute"))
        with self.assertRaises(TypeError):
            replace(state, validated_revision=True)


class DocumentTests(unittest.TestCase):
    def test_minimal_structure_is_explicit_and_versioned(self):
        doc = document()
        empty = replace(doc, components=(), pins=(), nets=(), connections=(), labels=())
        self.assertEqual(empty.schema_version, "0.2-draft1")
        self.assertEqual(empty.nets, ())
        self.assertIsNone(empty.source_image_reference)
        self.assertEqual(empty.validation_state.status, ir.WireValidationStatus.DRAFT)
        with self.assertRaises(ValueError):
            replace(doc, schema_version="0.2-m1")
        with self.assertRaises(TypeError):
            ir.CircuitDocument()

    def test_wire_fields_have_no_missing_key_defaults(self):
        for model in (ir.CircuitDocument, ir.Metadata, ir.SourceImageReference,
                      ir.Component, ir.Pin, ir.Net, ir.Connection, ir.Label, ir.Quantity,
                      ir.SourceConfiguration, ir.ACConfiguration, ir.Waveform,
                      ir.VisualProvenance, ir.VisualEntity, ir.BoundingBox, ir.PixelPoint,
                      ir.Confidence, ir.Ambiguity, ir.Candidate, ir.ImportedFinding,
                      ir.ImportedValidationState):
            for field in fields(model):
                with self.subTest(model=model.__name__, field=field.name):
                    self.assertIs(field.default, MISSING)
                    self.assertIs(field.default_factory, MISSING)

    def test_deterministic_order_and_structural_equality(self):
        doc = replace(document(), components=(resistor("R2"), resistor("R1")))
        self.assertEqual(tuple(c.id for c in doc.components), ("R2", "R1"))
        self.assertEqual(document(), document())
        self.assertEqual(hash(document()), hash(document()))
        self.assertNotEqual(doc, replace(doc, components=tuple(reversed(doc.components))))
        self.assertNotEqual(doc, replace(doc, confidence=ir.Confidence(
            0.9, ir.ConfidenceBasis.PROVIDER_SCORE, False)))

    def test_immutable_records_allow_explicit_replacement_edits(self):
        doc = document()
        records = (doc, doc.metadata, doc.components[0], doc.pins[0], doc.nets[0],
                   doc.connections[0], doc.visual, doc.confidence, doc.validation_state,
                   doc.components[0].value)
        for record in records:
            field = fields(record)[0]
            with self.subTest(model=type(record).__name__):
                self.assertFalse(hasattr(record, "__dict__"))
                with self.assertRaises(FrozenInstanceError):
                    setattr(record, field.name, getattr(record, field.name))
        edited = replace(doc, metadata=replace(doc.metadata, revision=1))
        self.assertEqual(doc.metadata.revision, 0)
        self.assertEqual(edited.metadata.revision, 1)

    def test_nested_collections_reject_mutable_lists_and_wrong_records(self):
        doc = document()
        for field in ("components", "pins", "nets", "connections", "labels", "ambiguities",
                      "warnings"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(doc, **{field: []})
        for field in ("components", "pins", "nets", "connections", "labels", "ambiguities"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(doc, **{field: ("not_a_record",)})
        with self.assertRaises(TypeError):
            replace(resistor(), pin_ids=["R1.a", "R1.b"])
        with self.assertRaises(TypeError):
            replace(doc.visual, entities=[])
        with self.assertRaises(TypeError):
            replace(doc.validation_state, findings=[])

    def test_only_connections_store_authoritative_pin_net_membership(self):
        doc = document()
        for model in (ir.Component, ir.Pin, ir.Net):
            names = {f.name for f in fields(model)}
            self.assertFalse(names & {"net_id", "connected_pins", "net_ids", "connections"})
        changed = replace(doc, connections=(replace(doc.connections[0], net_id="n0"),))
        self.assertEqual(changed.components, doc.components)
        self.assertEqual(changed.pins, doc.pins)
        self.assertEqual(changed.nets, doc.nets)
        self.assertNotEqual(changed.connections, doc.connections)

    def test_cross_document_electrical_errors_are_not_constructor_validation(self):
        doc = document()
        duplicate = replace(doc, components=(resistor(), resistor()), nets=(),
                            pins=(ir.Pin("R1.a", "missing_owner", ir.PinRole.UNKNOWN, None),),
                            connections=(ir.Connection("missing_pin", "missing_net", (),
                                                       manual_confidence()),))
        self.assertEqual(len(duplicate.components), 2)
        self.assertEqual(duplicate.nets, ())
        # Ground, ownership, pin count, source timing and passive positivity await M1E/F.
        negative = ir.Quantity("-1", "-1", "ohm", ir.ValueGrammar.MANUAL)
        self.assertEqual(replace(resistor(), value=negative, pin_ids=()).value, negative)
        self.assertEqual(ir.Waveform(ir.WaveformKind.PULSE, ()).parameters, ())

    def test_fresh_import_has_no_io_or_v01_external_dependencies(self):
        script = '''
import dataclasses, enum, math, re, typing, pathlib, socket, subprocess, sys
from unittest.mock import patch
before = set(sys.modules)
with patch("builtins.open", side_effect=AssertionError("file I/O")), \\
     patch("pathlib.Path.open", side_effect=AssertionError("file I/O")), \\
     patch("pathlib.Path.mkdir", side_effect=AssertionError("directory I/O")), \\
     patch("socket.create_connection", side_effect=AssertionError("network I/O")), \\
     patch("subprocess.Popen", side_effect=AssertionError("process I/O")):
    import circuit_ir
added = set(sys.modules) - before
for prefix in ("app", "launcher", "simulation_runner", "streamlit", "numpy", "PyLTSpice",
               "openai", "jsonschema"):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in added), prefix
assert callable(circuit_ir.load_document)
assert callable(circuit_ir.build_graph)
assert callable(circuit_ir.validate_document)
assert callable(circuit_ir.parse_quantity)
'''
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
