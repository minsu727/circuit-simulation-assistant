"""M1F contract scenarios; no simulator, private catalog, API or image decoding."""
from dataclasses import replace
from decimal import localcontext
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir
from circuit_ir import validation
from test_circuit_ir_validation import circuit, quantity, remove_pin, change_role


def edit_component(doc, identity, **changes):
    return replace(doc, components=tuple(replace(item, **changes) if item.id == identity else item
                                         for item in doc.components))


def omit_component(doc, identity):
    removed = {pin.id for pin in doc.pins if pin.component_id == identity}
    return replace(doc, components=tuple(item for item in doc.components if item.id != identity),
                   pins=tuple(pin for pin in doc.pins if pin.id not in removed),
                   connections=tuple(row for row in doc.connections if row.pin_id not in removed))


def add_voltage(doc, identity, positive="vin", negative="n0", dc="1"):
    ids = (f"{identity}.p1", f"{identity}.p2")
    source = ir.SourceConfiguration(quantity(dc), None, ir.Waveform(ir.WaveformKind.NONE, ()))
    return replace(doc, components=doc.components + (
        ir.Component(identity, ir.ComponentType.VOLTAGE_SOURCE, ids, None, None, (), source, None),),
        pins=doc.pins + (ir.Pin(ids[0], identity, ir.PinRole.POSITIVE, None),
                        ir.Pin(ids[1], identity, ir.PinRole.NEGATIVE, None)),
        connections=doc.connections + (ir.Connection(ids[0], positive, (), doc.confidence),
                                      ir.Connection(ids[1], negative, (), doc.confidence)))


def sine(unit="V"):
    return ir.Waveform(ir.WaveformKind.SINE, (("offset", quantity("-1", unit)),
        ("amplitude", quantity("1", unit)), ("frequency", quantity("1000", "Hz"))))


def pulse(unit="V"):
    return ir.Waveform(ir.WaveformKind.PULSE, (("level1", quantity("-1", unit)),
        ("level2", quantity("1", unit)), ("delay", quantity("0", "s")),
        ("rise", quantity("0.1", "s")), ("fall", quantity("0.2", "s")),
        ("width", quantity("0.7", "s")), ("period", quantity("1", "s"))))


def choice(kind=ir.AmbiguityKind.VALUE, targets=("R1",), *, resolved=False, note=None):
    return ir.Ambiguity("choice_a", kind, targets, (ir.Candidate("candidate_a", "Explicit authored choice"),),
                        ir.AmbiguityStatus.RESOLVED if resolved else ir.AmbiguityStatus.UNRESOLVED,
                        "candidate_a" if resolved else None, note)


class SemanticTests(unittest.TestCase):
    def checked(self, doc, state, codes=()):
        before = ir.dump_document(doc)
        result = ir.validate_document(doc)
        self.assertEqual(result.technical_state, state)
        self.assertEqual({issue.code for issue in result.issues}, set(codes))
        self.assertEqual(result, ir.validate_document(doc))
        self.assertEqual(ir.dump_document(doc), before)
        return result

    def test_complete_source_resistor_and_rc_profiles_are_valid(self):
        for kind in ("simple", "divider", "rc"):
            with self.subTest(kind=kind):
                result = self.checked(circuit(kind), ir.TechnicalState.VALID)
                self.assertEqual(result.skipped_stages, ())
                self.assertTrue(set(validation._REQUIRED_STAGES).issubset(result.completed_stages))

    def test_warning_only_profile_is_valid_without_authorization(self):
        doc = circuit()
        doc = replace(doc, labels=doc.labels + (ir.Label("alias", "input", "flat", "vin", None),))
        result = self.checked(doc, ir.TechnicalState.VALID, ("LABEL_ALIAS",))
        self.assertEqual(result.blocking_issue_count, 0)
        for field in ("approved", "executable", "can_execute", "user_decision"):
            self.assertFalse(hasattr(result, field))

    def test_required_stage_absent_cannot_be_valid_with_empty_issues(self):
        stages = tuple(stage for stage in validation._REQUIRED_STAGES if stage != "graph_dc")
        result = validation._result(circuit(), (), stages, ())
        self.assertEqual(result.technical_state, ir.TechnicalState.UNVALIDATED)

    def test_required_stage_skipped_cannot_be_valid_even_when_listed_complete(self):
        result = validation._result(circuit(), (), validation._REQUIRED_STAGES, (("graph_dc", "not_run"),))
        self.assertEqual(result.technical_state, ir.TechnicalState.UNVALIDATED)

    def test_required_stage_deferred_cannot_be_valid_with_empty_issues(self):
        result = validation._result(circuit(), (), validation._REQUIRED_STAGES, (), ("graph_dc",))
        self.assertEqual(result.technical_state, ir.TechnicalState.UNVALIDATED)

    def test_external_scoped_deferral_does_not_prevent_local_valid(self):
        result = validation._result(circuit(), (), validation._REQUIRED_STAGES, (), ("model_catalog_resolution",))
        self.assertEqual(result.technical_state, ir.TechnicalState.VALID)

    def test_error_and_ambiguity_take_precedence_over_incomplete_stages(self):
        doc = circuit()
        for severity, state in ((ir.IssueSeverity.ERROR, ir.TechnicalState.INVALID),
                                (ir.IssueSeverity.AMBIGUOUS, ir.TechnicalState.AMBIGUOUS)):
            issue = validation._finding("VALUE_INVALID", severity, ("R1",), "component", "R1", "value", "Test root")
            result = validation._result(doc, (issue,), (), (("graph_dc", "not_run"),))
            self.assertEqual(result.technical_state, state)

    def test_signed_and_zero_source_dc_are_legal(self):
        for literal in ("-2.5", "0", "1e-100"):
            doc = circuit("simple")
            doc = edit_component(doc, "V1", source=replace(doc.components[0].source, dc=quantity(literal)))
            self.checked(doc, ir.TechnicalState.VALID)

    def test_current_source_with_resistive_reference_is_valid(self):
        doc = circuit("simple")
        doc = edit_component(doc, "V1", type=ir.ComponentType.CURRENT_SOURCE,
                             source=replace(doc.components[0].source, dc=quantity("-0.001", "A"), waveform=sine("A")))
        self.checked(doc, ir.TechnicalState.VALID)

    def test_same_net_voltage_and_current_sources_are_invalid_even_at_zero(self):
        for kind, unit in ((ir.ComponentType.VOLTAGE_SOURCE, "V"), (ir.ComponentType.CURRENT_SOURCE, "A")):
            doc = circuit("simple")
            doc = edit_component(doc, "V1", type=kind, source=replace(doc.components[0].source, dc=quantity("0", unit)))
            doc = replace(doc, connections=tuple(replace(row, net_id="vin") if row.pin_id == "V1.p2" else row
                                                 for row in doc.connections))
            result = self.checked(doc, ir.TechnicalState.INVALID, ("SOURCE_SAME_NET",))
            self.assertEqual(result.issues[0].target_refs, ("V1", "vin"))

    def test_missing_source_configuration_or_dc_is_ambiguous(self):
        doc = circuit("simple")
        for source in (None, replace(doc.components[0].source, dc=None)):
            self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.AMBIGUOUS, ("SOURCE_INVALID",))

    def test_missing_source_pin_suppresses_same_net_and_config_derivatives(self):
        doc = edit_component(remove_pin(circuit("simple"), "V1.p2"), "V1", source=None)
        result = self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        self.assertEqual(dict(result.skipped_stages)["component[V1].component_value_source"], "pin_prerequisite_failed")

    def test_source_dimension_is_not_inferred_from_device_name(self):
        doc = circuit("simple")
        source = replace(doc.components[0].source, dc=quantity("1", "A"))
        self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.INVALID, ("SOURCE_INVALID",))

    def test_valid_ac_zero_magnitude_and_signed_phase(self):
        doc = circuit("simple")
        source = replace(doc.components[0].source,
                         ac=ir.ACConfiguration(quantity("0"), quantity("-90", "deg")))
        self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.VALID)

    def test_ac_negative_magnitude_and_wrong_phase_dimension(self):
        doc = circuit("simple")
        for ac in (ir.ACConfiguration(quantity("-1"), quantity("0", "deg")),
                   ir.ACConfiguration(quantity("1"), quantity("0", "Hz"))):
            self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, ac=ac)),
                         ir.TechnicalState.INVALID, ("SOURCE_INVALID",))

    def test_sine_contract_and_signed_levels(self):
        doc = circuit("simple")
        source = replace(doc.components[0].source, waveform=sine())
        self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.VALID)

    def test_sine_missing_extra_or_wrong_unit_parameters(self):
        doc = circuit("simple")
        wave = sine()
        cases = (replace(wave, parameters=wave.parameters[:-1]),
                 replace(wave, parameters=wave.parameters + (("phase", quantity("0", "deg")),)),
                 replace(wave, parameters=tuple((key, quantity("1", "s")) if key == "frequency" else (key, q)
                                               for key, q in wave.parameters)))
        for changed in cases:
            source = replace(doc.components[0].source, waveform=changed)
            self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.INVALID, ("SOURCE_INVALID",))

    def test_sine_frequency_must_be_positive(self):
        doc = circuit("simple")
        for literal in ("0", "-1"):
            wave = replace(sine(), parameters=tuple((key, quantity(literal, "Hz")) if key == "frequency" else (key, q)
                                                    for key, q in sine().parameters))
            self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=wave)),
                         ir.TechnicalState.INVALID, ("SOURCE_INVALID",))

    def test_none_waveform_rejects_parameters(self):
        doc = circuit("simple")
        wave = ir.Waveform(ir.WaveformKind.NONE, (("offset", quantity()),))
        self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=wave)),
                     ir.TechnicalState.INVALID, ("SOURCE_INVALID",))

    def test_pulse_timing_equality_is_exact_under_low_decimal_precision(self):
        doc = circuit("simple")
        doc = edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=pulse()))
        with localcontext() as context:
            context.prec = 2
            self.checked(doc, ir.TechnicalState.VALID)

    def test_pulse_period_conflict_is_one_timing_root(self):
        doc = circuit("simple")
        wave = replace(pulse(), parameters=tuple((key, quantity("0.9", "s")) if key == "period" else (key, q)
                                                 for key, q in pulse().parameters))
        result = self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=wave)),
                              ir.TechnicalState.INVALID, ("SOURCE_INVALID",))
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].field, "component[V1].source.waveform.timing")

    def test_missing_dc_does_not_hide_independent_known_pulse_timing_error(self):
        doc = circuit("simple")
        wave = replace(pulse(), parameters=tuple((key, quantity("0.9", "s")) if key == "period" else (key, q)
                                                 for key, q in pulse().parameters))
        source = replace(doc.components[0].source, dc=None, waveform=wave)
        result = self.checked(edit_component(doc, "V1", source=source), ir.TechnicalState.INVALID, ("SOURCE_INVALID",))
        self.assertEqual([issue.severity for issue in result.issues], [ir.IssueSeverity.ERROR, ir.IssueSeverity.AMBIGUOUS])

    def test_pulse_negative_delay_zero_rise_and_unknown_keys(self):
        doc = circuit("simple")
        for name, literal in (("delay", "-1"), ("rise", "0"), ("width", "0"), ("period", "0")):
            wave = replace(pulse(), parameters=tuple((key, quantity(literal, "s")) if key == name else (key, q)
                                                     for key, q in pulse().parameters))
            result = self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=wave)),
                                  ir.TechnicalState.INVALID, ("SOURCE_INVALID",))
            self.assertEqual(len(result.issues), 1)

    def test_passive_units_and_strict_positivity(self):
        for kind, unit in ((ir.ComponentType.RESISTOR, "ohm"), (ir.ComponentType.CAPACITOR, "F"),
                           (ir.ComponentType.INDUCTOR, "H")):
            for literal in ("0", "-1"):
                doc = edit_component(circuit("simple"), "R1", type=kind, value=quantity(literal, unit))
                self.checked(doc, ir.TechnicalState.INVALID, ("VALUE_INVALID",))
        self.checked(edit_component(circuit("rc"), "C1", value=quantity("1", "H")),
                     ir.TechnicalState.INVALID, ("VALUE_INVALID",))

    def test_missing_selected_passive_value_is_invalid(self):
        self.checked(edit_component(circuit("simple"), "R1", value=None),
                     ir.TechnicalState.INVALID, ("VALUE_INVALID",))

    def test_selected_literal_si_mismatch_is_not_normalized(self):
        q = ir.Quantity("1M", "1000000", "ohm", ir.ValueGrammar.SPICE)
        doc = edit_component(circuit("simple"), "R1", value=q)
        result = self.checked(doc, ir.TechnicalState.INVALID, ("VALUE_INVALID",))
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(doc.components[1].value.si_value, "1000000")

    def test_si_only_values_and_equivalent_decimal_spellings(self):
        for q in (ir.Quantity(None, "1000", "ohm", ir.ValueGrammar.SI),
                  ir.Quantity("1k", "1e3", "ohm", ir.ValueGrammar.SPICE)):
            self.checked(edit_component(circuit("simple"), "R1", value=q), ir.TechnicalState.VALID)

    def test_selected_quantity_without_si_value_does_not_acquire_defaults(self):
        q = ir.Quantity("1k", None, "ohm", ir.ValueGrammar.SPICE)
        self.checked(edit_component(circuit("simple"), "R1", value=q), ir.TechnicalState.INVALID, ("VALUE_INVALID",))

    def test_parse_failure_suppresses_sign_range_duplicate(self):
        for literal in ("bad", "-1/2", "{R}"):
            q = ir.Quantity(literal, "-1", "ohm", ir.ValueGrammar.SPICE)
            result = self.checked(edit_component(circuit("simple"), "R1", value=q),
                                  ir.TechnicalState.INVALID, ("VALUE_INVALID",))
            self.assertEqual(len(result.issues), 1)

    def test_source_parse_failure_retains_value_root_code(self):
        doc = circuit("simple")
        q = ir.Quantity("bad", "-1", "V", ir.ValueGrammar.SPICE)
        result = self.checked(edit_component(doc, "V1", source=replace(doc.components[0].source, dc=q)),
                              ir.TechnicalState.INVALID, ("VALUE_INVALID",))
        self.assertEqual(len(result.issues), 1)

    def test_unresolved_value_choice_is_one_ambiguous_root(self):
        doc = edit_component(circuit("simple"), "R1", value=ir.Quantity("1k or 10k", None, "ohm", ir.ValueGrammar.UNRESOLVED))
        doc = replace(doc, ambiguities=(choice(),))
        result = self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("VALUE_INVALID",))
        self.assertEqual(len(result.issues), 1)

    def test_unresolved_number_cannot_soften_known_wrong_dimension(self):
        for q in (ir.Quantity(None, None, "F", ir.ValueGrammar.UNRESOLVED),
                  ir.Quantity("1", None, "F", ir.ValueGrammar.MANUAL)):
            doc = edit_component(circuit("simple"), "R1", value=q)
            doc = replace(doc, ambiguities=(choice(),))
            self.checked(doc, ir.TechnicalState.INVALID, ("VALUE_INVALID",))

    def test_non_mos_model_and_sizing_fields_are_invalid(self):
        for changes in ({"model_ref": "model_a"}, {"parameters": (("width", quantity("1", "m")),)}):
            self.checked(edit_component(circuit("simple"), "R1", **changes),
                         ir.TechnicalState.INVALID, ("MODEL_INVALID",))

    def test_wrong_device_source_and_value_fields_are_invalid(self):
        doc = circuit("simple")
        self.checked(edit_component(doc, "R1", source=doc.components[0].source),
                     ir.TechnicalState.INVALID, ("SOURCE_INVALID",))
        self.checked(edit_component(doc, "V1", value=quantity()), ir.TechnicalState.INVALID, ("VALUE_INVALID",))

    def test_valid_nmos_and_pmos_warn_about_unresolved_catalog(self):
        for kind in (ir.ComponentType.NMOS, ir.ComponentType.PMOS):
            doc = edit_component(circuit("mos"), "M1", type=kind)
            result = self.checked(doc, ir.TechnicalState.VALID, ("CHECK_DEFERRED",))
            self.assertIn("model_catalog_resolution", result.deferred_checks)
            self.assertFalse(any(issue.severity is ir.IssueSeverity.CONFIRMED for issue in result.issues))

    def test_missing_mos_model_is_ambiguous_not_lookup_failure(self):
        doc = edit_component(circuit("mos"), "M1", model_ref=None)
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("MODEL_INVALID",))

    def test_mos_missing_nonpositive_and_wrong_unit_dimensions(self):
        for params in ((), (("width", quantity("-1", "m")), ("length", quantity("1", "m"))),
                       (("width", quantity("1", "V")), ("length", quantity("1", "m")))):
            self.checked(edit_component(circuit("mos"), "M1", parameters=params),
                         ir.TechnicalState.INVALID, ("VALUE_INVALID", "CHECK_DEFERRED"))

    def test_mos_bulk_unconnected_is_specific_ambiguity_without_generic_duplicate(self):
        doc = circuit("mos")
        doc = replace(doc, connections=tuple(row for row in doc.connections if row.pin_id != "M1.p4"))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("MOS_BODY_UNRESOLVED", "CHECK_DEFERRED"))

    def test_missing_mos_bulk_role_suppresses_body_and_model_derivatives(self):
        doc = edit_component(remove_pin(circuit("mos"), "M1.p4"), "M1", model_ref=None, parameters=())
        self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))

    def test_unknown_mos_role_consumes_matching_declared_ambiguity(self):
        doc = change_role(circuit("mos"), "M1.p4", ir.PinRole.UNKNOWN)
        doc = replace(doc, ambiguities=(choice(ir.AmbiguityKind.PIN_MAPPING, ("M1",)),))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("PIN_ROLES_INVALID",))

    def test_unknown_type_with_pending_choice_is_ambiguous_without_choice_is_error(self):
        doc = edit_component(circuit("simple"), "R1", type=ir.ComponentType.UNKNOWN)
        self.checked(doc, ir.TechnicalState.INVALID, ("UNSUPPORTED_FEATURE",))
        self.checked(replace(doc, ambiguities=(choice(ir.AmbiguityKind.SYMBOL_TYPE),)),
                     ir.TechnicalState.AMBIGUOUS, ("UNSUPPORTED_FEATURE",))

    def test_unresolved_generic_choice_and_resolution_do_not_change_connectivity(self):
        doc = replace(circuit("simple"), ambiguities=(choice(),))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("AMBIGUITY_UNRESOLVED",))
        resolved = replace(doc, ambiguities=(choice(resolved=True),))
        self.checked(resolved, ir.TechnicalState.VALID)
        self.assertEqual(doc.connections, resolved.connections)

    def test_resolved_choice_requires_candidate_or_nonempty_manual_note(self):
        selected = choice(resolved=True)
        for note in (None, "   "):
            item = replace(selected, selected_candidate_id=None, resolution_note=note)
            self.checked(replace(circuit(), ambiguities=(item,)), ir.TechnicalState.INVALID, ("BROKEN_REFERENCE",))
        item = replace(selected, selected_candidate_id=None, resolution_note="Manually confirmed recorded value")
        self.checked(replace(circuit(), ambiguities=(item,)), ir.TechnicalState.VALID)

    def test_bad_selected_candidate_is_still_the_existing_graph_reference_root(self):
        item = replace(choice(resolved=True), selected_candidate_id="missing")
        result = self.checked(replace(circuit(), ambiguities=(item,)), ir.TechnicalState.INVALID, ("BROKEN_REFERENCE",))
        self.assertNotIn("component_value_source", result.completed_stages)

    def test_selected_candidate_in_unresolved_record_does_not_auto_resolve(self):
        item = replace(choice(), selected_candidate_id="candidate_a")
        self.checked(replace(circuit(), ambiguities=(item,)), ir.TechnicalState.AMBIGUOUS, ("AMBIGUITY_UNRESOLVED",))

    def test_crossing_and_wire_gap_records_have_specific_root_codes(self):
        for kind, code in ((ir.AmbiguityKind.CROSSING, "CROSSING_UNRESOLVED"),
                           (ir.AmbiguityKind.WIRE_GAP, "DANGLING_WIRE")):
            self.checked(replace(circuit(), ambiguities=(choice(kind, ("vin",)),)),
                         ir.TechnicalState.AMBIGUOUS, (code,))

    def test_resolved_declared_wire_gap_remains_a_nonblocking_warning(self):
        item = choice(ir.AmbiguityKind.WIRE_GAP, ("vin",), resolved=True, note="Unused stub explicitly confirmed")
        self.checked(replace(circuit(), ambiguities=(item,)), ir.TechnicalState.VALID, ("DANGLING_WIRE",))

    def test_high_score_and_calibration_flags_do_not_approve_inferred_connections(self):
        for score, calibrated in ((None, False), (0.01, False), (1.0, True)):
            doc = circuit("simple")
            row = replace(doc.connections[0], confidence=ir.Confidence(score, ir.ConfidenceBasis.PROVIDER_SCORE, calibrated))
            doc = replace(doc, connections=(row,) + doc.connections[1:])
            self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("CONFIDENCE_REVIEW_REQUIRED",))

    def test_explicit_item_resolution_accepts_inferred_record_without_authorization(self):
        doc = circuit("simple")
        row = replace(doc.connections[0], confidence=ir.Confidence(0.8, ir.ConfidenceBasis.HEURISTIC, False))
        doc = replace(doc, connections=(row,) + doc.connections[1:],
                      ambiguities=(choice(ir.AmbiguityKind.PIN_MAPPING, (row.pin_id,), resolved=True),))
        self.checked(doc, ir.TechnicalState.VALID)

    def test_unrelated_resolved_value_does_not_review_inferred_connection(self):
        doc = circuit("simple")
        row = replace(doc.connections[0], confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True))
        doc = replace(doc, connections=(row,) + doc.connections[1:], ambiguities=(choice(resolved=True),))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("CONFIDENCE_REVIEW_REQUIRED",))

    def test_independent_value_error_does_not_hide_inferred_connectivity_review(self):
        doc = edit_component(circuit("simple"), "R1", value=quantity("-1", "ohm"))
        doc = replace(doc, connections=tuple(replace(row, confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True))
                                            if row.pin_id == "R1.p1" else row for row in doc.connections))
        self.checked(doc, ir.TechnicalState.INVALID, ("VALUE_INVALID", "CONFIDENCE_REVIEW_REQUIRED"))

    def test_bulk_resolution_cannot_review_inferred_gate_connection(self):
        doc = circuit("mos")
        doc = replace(doc, connections=tuple(replace(row, confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True))
                                            if row.pin_id == "M1.p2" else row for row in doc.connections),
                      ambiguities=(choice(ir.AmbiguityKind.BODY_CONNECTION, ("M1",), resolved=True),))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("CHECK_DEFERRED", "CONFIDENCE_REVIEW_REQUIRED"))

    def test_high_confidence_imported_reviewed_cannot_override_source_short(self):
        doc = circuit("simple")
        doc = replace(doc, connections=tuple(replace(row, net_id="vin") if row.pin_id == "V1.p2" else row
                                             for row in doc.connections),
                      confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True),
                      validation_state=ir.ImportedValidationState(ir.WireValidationStatus.REVIEWED, 3, "m1-local-v1", ()))
        self.checked(doc, ir.TechnicalState.INVALID, ("SOURCE_SAME_NET",))

    def test_noncritical_document_summary_confidence_is_metadata(self):
        doc = replace(circuit(), confidence=ir.Confidence(None, ir.ConfidenceBasis.UNKNOWN, False))
        self.checked(doc, ir.TechnicalState.VALID)

    def test_referenced_inferred_visual_requires_explicit_review(self):
        doc = circuit("simple")
        visual = ir.VisualEntity("symbol_r", ir.VisualKind.SYMBOL, None, None, ir.Orientation.R0,
                                 (), None, "synthetic_provider", ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True))
        doc = edit_component(doc, "R1", visual_ref=visual.id)
        doc = replace(doc, visual=ir.VisualProvenance("original_pixels", (visual,)))
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("CONFIDENCE_REVIEW_REQUIRED",))
        self.checked(replace(doc, ambiguities=(choice(ir.AmbiguityKind.SYMBOL_TYPE, ("R1",), resolved=True),)),
                     ir.TechnicalState.VALID)

    def test_image_origin_requires_reference_without_fetching_asset(self):
        doc = replace(circuit(), metadata=replace(circuit().metadata, origin=ir.Origin.IMAGE))
        self.checked(doc, ir.TechnicalState.INVALID, ("IMAGE_PROVENANCE_INVALID",))

    def test_declared_geometry_bounds_are_checked_without_image_decoding(self):
        doc = circuit("simple")
        image = ir.SourceImageReference("authored_image", "a" * 64, 100, 50)
        visual = ir.VisualEntity("symbol_r", ir.VisualKind.SYMBOL, ir.BoundingBox(0, 0, 100, 50),
                                 ir.PixelPoint(99, 49), ir.Orientation.R0, (), None, "manual", doc.confidence)
        doc = replace(doc, source_image_reference=image, visual=ir.VisualProvenance("original_pixels", (visual,)))
        self.checked(doc, ir.TechnicalState.VALID)
        for changed in (replace(visual, position=ir.PixelPoint(100, 0)),
                        replace(visual, bbox=ir.BoundingBox(1, 0, 100, 50)),
                        replace(visual, points=(ir.PixelPoint(0, 50),))):
            self.checked(replace(doc, visual=replace(doc.visual, entities=(changed,))),
                         ir.TechnicalState.INVALID, ("IMAGE_PROVENANCE_INVALID",))

    def test_floating_capacitive_node_is_not_a_conductive_ownership_path(self):
        doc = omit_component(circuit("rc"), "R1")
        result = self.checked(doc, ir.TechnicalState.INVALID, ("FLOATING_DC_NODE",))
        self.assertEqual(result.issues[0].target_refs, ("vout",))

    def test_current_source_does_not_prove_voltage_reference(self):
        doc = omit_component(circuit("simple"), "R1")
        doc = edit_component(doc, "V1", type=ir.ComponentType.CURRENT_SOURCE,
                             source=replace(doc.components[0].source, dc=quantity("1", "A")))
        self.checked(doc, ir.TechnicalState.INVALID, ("FLOATING_DC_NODE",))

    def test_nonlinear_drain_reference_is_warning_not_operating_point_proof(self):
        doc = omit_component(circuit("mos"), "R1")
        result = self.checked(doc, ir.TechnicalState.VALID, ("CHECK_DEFERRED", "DC_REFERENCE_UNPROVEN"))
        self.assertIn("nonlinear_dc_reference", result.deferred_checks)

    def test_mos_gate_does_not_provide_conditional_dc_reference(self):
        doc = circuit("mos")
        doc = replace(doc, nets=doc.nets + (ir.Net("gate_only", False),),
                      connections=tuple(replace(row, net_id="gate_only") if row.pin_id == "M1.p2" else row
                                        for row in doc.connections))
        self.checked(doc, ir.TechnicalState.INVALID, ("CHECK_DEFERRED", "FLOATING_DC_NODE"))

    def test_isolated_island_suppresses_derived_floating_errors(self):
        doc = circuit("simple")
        doc = replace(doc, nets=doc.nets + (ir.Net("island_a", False), ir.Net("island_b", False)),
                      connections=tuple(replace(row, net_id="island_a" if row.pin_id == "R1.p1" else "island_b")
                                        if row.pin_id.startswith("R1.") else row for row in doc.connections))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("ISOLATED_SUBNETWORK",))
        self.assertEqual(len(result.issues), 1)

    def test_passive_bypass_is_warning_without_deleting_device(self):
        doc = circuit("simple")
        doc = replace(doc, connections=tuple(replace(row, net_id="vin") if row.pin_id == "R1.p2" else row
                                             for row in doc.connections))
        self.checked(doc, ir.TechnicalState.VALID, ("PASSIVE_BYPASSED",))

    def test_equal_parallel_dc_sources_warn_about_redundancy(self):
        doc = add_voltage(circuit("simple"), "V2")
        result = self.checked(doc, ir.TechnicalState.VALID, ("SOURCE_CONSTRAINT_CONFLICT",))
        self.assertEqual(result.issues[0].severity, ir.IssueSeverity.WARNING)
        self.assertEqual(result.issues[0].target_refs, ("V1", "V2"))

    def test_parallel_dc_source_difference_is_exact_beyond_float_precision(self):
        doc = add_voltage(circuit("simple"), "V2", dc="1.00000000000000000000000000000000000000001")
        with localcontext() as context:
            context.prec = 2
            self.checked(doc, ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))

    def test_reversed_polarity_dc_constraints_use_explicit_sign(self):
        doc = add_voltage(circuit("simple"), "V2", "n0", "vin", "-1")
        self.checked(doc, ir.TechnicalState.VALID, ("SOURCE_CONSTRAINT_CONFLICT",))
        source = replace(doc.components[-1].source, dc=quantity("1"))
        self.checked(edit_component(doc, "V2", source=source), ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))

    def test_series_dc_loop_constraints_use_exact_sum(self):
        doc = add_voltage(circuit(), "V2", "vout", "n0", "0.3")
        doc = add_voltage(doc, "V3", "vin", "vout", "0.7")
        self.checked(doc, ir.TechnicalState.VALID, ("SOURCE_CONSTRAINT_CONFLICT",))
        self.checked(edit_component(doc, "V3", source=replace(doc.components[-1].source, dc=quantity("0.8"))),
                     ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))

    def test_inductor_zero_potential_constraint_conflicts_with_nonzero_dc_source(self):
        doc = edit_component(circuit("simple"), "R1", type=ir.ComponentType.INDUCTOR, value=quantity("1", "H"))
        self.checked(doc, ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))

    def test_parallel_explicit_ac_settings_are_compared_without_solver(self):
        doc = add_voltage(circuit("simple"), "V2")
        for identity, magnitude, phase in (("V1", "1", "0"), ("V2", "1", "360")):
            source = next(item.source for item in doc.components if item.id == identity)
            doc = edit_component(doc, identity, source=replace(source, ac=ir.ACConfiguration(quantity(magnitude), quantity(phase, "deg"))))
        self.checked(doc, ir.TechnicalState.VALID, ("SOURCE_CONSTRAINT_CONFLICT",))
        source = replace(doc.components[-1].source, ac=ir.ACConfiguration(quantity("2"), quantity("0", "deg")))
        result = self.checked(edit_component(doc, "V2", source=source), ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))
        self.assertEqual([issue.severity for issue in result.issues], [ir.IssueSeverity.ERROR, ir.IssueSeverity.WARNING])

    def test_general_dynamic_equivalence_is_deferred_not_guessed(self):
        doc = add_voltage(circuit("simple"), "V2", "n0", "vin", "-1")
        source = replace(doc.components[-1].source, waveform=sine())
        result = self.checked(edit_component(doc, "V2", source=source), ir.TechnicalState.VALID,
                              ("CHECK_DEFERRED", "SOURCE_CONSTRAINT_CONFLICT"))
        self.assertIn("dynamic_source_constraint_proof", result.deferred_checks)

    def test_general_voltage_inductor_and_series_source_loops_defer_dynamic_proof(self):
        inductor = edit_component(circuit("simple"), "R1", type=ir.ComponentType.INDUCTOR, value=quantity("1", "H"))
        inductor = edit_component(inductor, "V1", source=replace(inductor.components[0].source, dc=quantity("0"), waveform=sine()))
        series = add_voltage(add_voltage(circuit(), "V2", "vout", "n0", "0.3"), "V3", "vin", "vout", "0.7")
        series = edit_component(series, "V3", source=replace(series.components[-1].source, waveform=sine()))
        for doc in (inductor, series):
            result = self.checked(doc, ir.TechnicalState.VALID, ("CHECK_DEFERRED", "SOURCE_CONSTRAINT_CONFLICT"))
            self.assertIn("dynamic_source_constraint_proof", result.deferred_checks)
            self.assertFalse(any(issue.blocking for issue in result.issues))

    def test_direct_parallel_sine_and_pulse_conflicts_are_not_simulated(self):
        for wave in (sine(), pulse()):
            doc = add_voltage(circuit("simple"), "V2")
            source1 = replace(doc.components[0].source, waveform=wave)
            key, unit = ("frequency", "Hz") if wave.kind is ir.WaveformKind.SINE else ("level2", "V")
            changed = replace(wave, parameters=tuple((name, quantity("2", unit)) if name == key else (name, q)
                                                     for name, q in wave.parameters))
            source2 = replace(doc.components[-1].source, waveform=changed)
            doc = edit_component(edit_component(doc, "V1", source=source1), "V2", source=source2)
            result = self.checked(doc, ir.TechnicalState.INVALID, ("SOURCE_CONSTRAINT_CONFLICT",))
            self.assertEqual(result.blocking_issue_count, 1)

    def test_constant_sine_and_pulse_ignore_irrelevant_frequency_or_timing(self):
        for wave in (sine(), pulse()):
            key = "amplitude" if wave.kind is ir.WaveformKind.SINE else "level2"
            constant = replace(wave, parameters=tuple((name, quantity("0" if name == "amplitude" else "-1"))
                                                      if name == key else (name, q) for name, q in wave.parameters))
            differing_key = "frequency" if wave.kind is ir.WaveformKind.SINE else "delay"
            differing_unit = "Hz" if differing_key == "frequency" else "s"
            changed = replace(constant, parameters=tuple((name, quantity("2", differing_unit))
                                                         if name == differing_key else (name, q)
                                                         for name, q in constant.parameters))
            doc = add_voltage(circuit("simple"), "V2")
            doc = edit_component(doc, "V1", source=replace(doc.components[0].source, waveform=constant))
            doc = edit_component(doc, "V2", source=replace(doc.components[-1].source, waveform=changed))
            self.checked(doc, ir.TechnicalState.VALID, ("SOURCE_CONSTRAINT_CONFLICT",))

    def test_missing_ground_skips_reference_checks_but_keeps_safe_value_checks(self):
        doc = circuit("simple")
        doc = replace(doc, nets=tuple(replace(net, is_ground=False) for net in doc.nets))
        result = self.checked(edit_component(doc, "R1", value=quantity("-1", "ohm")),
                              ir.TechnicalState.INVALID, ("GROUND_MISSING", "VALUE_INVALID"))
        self.assertNotIn("graph_dc", result.completed_stages)
        self.assertEqual(dict(result.skipped_stages)["graph_dc"], "blocked_by_ground_missing")

    def test_semantic_results_survive_roundtrip_and_array_permutations(self):
        doc = add_voltage(circuit("simple"), "V2", dc="2")
        doc = replace(doc, ambiguities=(choice(),))
        expected = ir.validate_document(doc)
        self.assertEqual(expected.technical_state, ir.TechnicalState.INVALID)
        self.assertEqual(expected, ir.validate_document(ir.load_document(ir.dump_document(doc)).document))
        rng = random.Random(33)
        for _ in range(6):
            fields = {}
            for name in ("components", "pins", "nets", "connections", "labels", "ambiguities"):
                records = list(getattr(doc, name))
                rng.shuffle(records)
                fields[name] = tuple(records)
            self.assertEqual(expected, ir.validate_document(replace(doc, **fields)))

    def test_complete_validation_uses_no_asset_model_network_or_process_access(self):
        doc = circuit("mos")
        expected = ir.validate_document(doc)  # Existing M1C bundled schema initialized once.
        with patch("builtins.open", side_effect=AssertionError("file")), \
             patch("pathlib.Path.open", side_effect=AssertionError("file")), \
             patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("process")), \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ir.validate_document(doc), expected)

    def test_semantic_reports_are_stable_across_python_hash_seeds(self):
        script = '''
from test_circuit_ir_validation import circuit
from test_circuit_ir_semantics import add_voltage, choice
from dataclasses import replace
import circuit_ir as ir
doc = replace(add_voltage(circuit("simple"), "V2", dc="2"), ambiguities=(choice(),))
print(ir.validate_document(doc))
'''
        outputs = []
        for seed in ("2", "994"):
            result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[1],
                                    env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "tests"},
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_independently_authored_semantic_fixtures_match_full_report_contract(self):
        root = Path(__file__).parent / "fixtures/circuit_ir"
        names = ("valid/simple_source_resistor", "valid/rc_low_pass", "valid/current_source_load",
                 "valid/nmos_common_source", "invalid/voltage_source_short", "invalid/negative_resistor",
                 "invalid/pulse_timing_conflict", "ambiguous/source_dc_missing", "ambiguous/mos_model_missing")
        for name in names:
            with self.subTest(name=name):
                directory = root / name
                loaded = ir.load_document((directory / "circuit.json").read_text(encoding="utf-8"))
                self.assertIsNotNone(loaded.document, loaded.issues)
                expected = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
                result = self.checked(loaded.document, ir.TechnicalState(expected["technical_state"]),
                                      tuple(item["code"] for item in expected["issues"]))
                self.assertEqual(result.profile, expected["profile"])
                self.assertEqual([(issue.code, issue.severity.value, list(issue.target_refs)) for issue in result.issues],
                                 [(item["code"], item["severity"], item["target_refs"]) for item in expected["issues"]])
                self.assertEqual(list(result.completed_stages), expected["completed_stages"])
                self.assertEqual(dict(result.skipped_stages), expected["skipped_stages"])
                self.assertEqual(list(result.deferred_checks), expected["deferred_checks"])


if __name__ == "__main__":
    unittest.main()
