"""M1E structural report acceptance, with explicit unimplemented M1F boundaries."""
from dataclasses import FrozenInstanceError, replace
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


def quantity(literal="1", unit="V"):
    return ir.Quantity(literal, literal, unit, ir.ValueGrammar.MANUAL)


def circuit(kind="divider"):
    """Repository-authored neutral records, not a private schematic or simulation."""
    confidence = ir.Confidence(None, ir.ConfidenceBasis.MANUAL, False)
    dc = ir.SourceConfiguration(quantity(), None, ir.Waveform(ir.WaveformKind.NONE, ()))
    components, pins, connections = [], [], []

    def add(identity, device_type, role_nets, value=None, source=None, model=None, parameters=()):
        ids = tuple(f"{identity}.p{i}" for i in range(1, len(role_nets) + 1))
        components.append(ir.Component(identity, device_type, ids, value, model, parameters, source, None))
        for pin_id, (role, net) in zip(ids, role_nets):
            pins.append(ir.Pin(pin_id, identity, role, None))
            connections.append(ir.Connection(pin_id, net, (), confidence))

    A, B, P, N = ir.PinRole.A, ir.PinRole.B, ir.PinRole.POSITIVE, ir.PinRole.NEGATIVE
    add("V1", ir.ComponentType.VOLTAGE_SOURCE, ((P, "vin"), (N, "n0")), source=dc)
    net_ids = ("n0", "vin", "vout")
    if kind == "simple":
        add("R1", ir.ComponentType.RESISTOR, ((A, "vin"), (B, "n0")), quantity("1000", "ohm"))
        net_ids = ("n0", "vin")
    elif kind in ("divider", "rc"):
        add("R1", ir.ComponentType.RESISTOR, ((A, "vin"), (B, "vout")), quantity("1000", "ohm"))
        tail_type, unit = ((ir.ComponentType.CAPACITOR, "F") if kind == "rc"
                           else (ir.ComponentType.RESISTOR, "ohm"))
        add("C1" if kind == "rc" else "R2", tail_type,
            ((A, "vout"), (B, "n0")), quantity("0.000001" if kind == "rc" else "1000", unit))
    elif kind == "mos":
        add("V2", ir.ComponentType.VOLTAGE_SOURCE, ((P, "vdd"), (N, "n0")),
            source=replace(dc, dc=quantity("5")))
        add("R1", ir.ComponentType.RESISTOR, ((A, "vdd"), (B, "vout")), quantity("1000", "ohm"))
        add("M1", ir.ComponentType.NMOS,
            ((ir.PinRole.DRAIN, "vout"), (ir.PinRole.GATE, "vin"),
             (ir.PinRole.SOURCE, "n0"), (ir.PinRole.BULK, "n0")),
            model="repository_demo_nmos",
            parameters=(("width", quantity("0.00001", "m")), ("length", quantity("0.000001", "m"))))
        net_ids = ("n0", "vin", "vout", "vdd")
    else:
        raise ValueError("unknown test circuit")
    return ir.CircuitDocument(
        ir.SCHEMA_VERSION, ir.Metadata("m1e_demo", 3, ir.Origin.MANUAL, "manual_demo"), None,
        tuple(components), tuple(pins), tuple(ir.Net(name, name == "n0") for name in net_ids),
        tuple(connections), (ir.Label("label_in", "vin", "flat", "vin", None),),
        ir.VisualProvenance("original_pixels", ()), confidence, (), (),
        ir.ImportedValidationState(ir.WireValidationStatus.DRAFT, None, None, ()))


def remove_pin(doc, pin_id):
    return replace(doc,
                   components=tuple(replace(component, pin_ids=tuple(pin for pin in component.pin_ids
                                                                    if pin != pin_id)) for component in doc.components),
                   pins=tuple(pin for pin in doc.pins if pin.id != pin_id),
                   connections=tuple(row for row in doc.connections if row.pin_id != pin_id))


def change_role(doc, pin_id, role):
    return replace(doc, pins=tuple(replace(pin, role=role) if pin.id == pin_id else pin for pin in doc.pins))


class ValidationTests(unittest.TestCase):
    def checked(self, doc, state, codes):
        before = ir.dump_document(doc)
        result = ir.validate_document(doc)
        self.assertEqual(result.technical_state, state)
        self.assertEqual({issue.code for issue in result.issues}, set(codes))
        self.assertEqual(result.profile, "m1-local-v1")
        self.assertEqual(result.ruleset_version, "m1-local-v1")
        self.assertEqual(result.document_revision, doc.metadata.revision)
        self.assertEqual(ir.dump_document(doc), before)
        self.assertEqual(result, ir.validate_document(doc))
        return result

    def test_authored_structural_circuits_remain_incomplete_until_m1f(self):
        for kind in ("divider", "rc", "simple", "mos"):
            with self.subTest(kind=kind):
                result = self.checked(circuit(kind), ir.TechnicalState.UNVALIDATED, ())
                self.assertEqual(result.completed_stages,
                                 ("schema", "ids", "references", "incidence", "pins", "ground", "labels", "result"))
                self.assertEqual(dict(result.skipped_stages), {
                    "component_value_source": "not_implemented_m1f", "graph_dc": "not_implemented_m1f",
                    "ambiguity_confidence_provenance": "not_implemented_m1f"})
                self.assertIn("model_catalog_resolution", result.deferred_checks)
                self.assertEqual(result.blocking_issue_count, 0)

    def test_existing_graph_prerequisite_issues_are_reused_without_new_codes(self):
        doc = circuit("simple")
        cases = (replace(doc, components=doc.components * 2),
                 replace(doc, connections=(replace(doc.connections[0], net_id="absent"),)),
                 replace(doc, connections=doc.connections * 2))
        for changed in cases:
            with self.subTest(changed=changed):
                graph_result = ir.build_graph(changed)
                result = ir.validate_document(changed)
                self.assertEqual(result.issues, graph_result.issues)
                self.assertEqual(result.technical_state, ir.TechnicalState.INVALID)

    def test_schema_failure_skips_all_dependent_stages(self):
        doc = circuit("simple")
        invalid = replace(doc.components[1].value, si_value="NaN")
        doc = replace(doc, components=(doc.components[0], replace(doc.components[1], value=invalid)))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("SCHEMA_INVALID",))
        self.assertEqual(result.completed_stages, ("schema", "result"))
        self.assertEqual(dict(result.skipped_stages)["pins"], "blocked_by_schema_invalid")

    def test_duplicate_id_suppresses_ground_role_and_label_cascades(self):
        doc = circuit("simple")
        doc = replace(doc, components=doc.components * 2, nets=tuple(replace(net, is_ground=False) for net in doc.nets),
                      labels=(replace(doc.labels[0], net_id=None),))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("DUPLICATE_ID",))
        self.assertEqual(result.completed_stages, ("schema", "ids", "result"))
        self.assertEqual(dict(result.skipped_stages)["ground"], "blocked_by_duplicate_id")

    def test_reference_failure_never_runs_dependent_rules(self):
        doc = circuit("simple")
        doc = replace(doc, connections=(replace(doc.connections[0], net_id="absent"),),
                      nets=tuple(replace(net, is_ground=False) for net in doc.nets))
        with patch.object(validation, "_pins", side_effect=AssertionError("pin checks ran")), \
             patch.object(validation, "_ground", side_effect=AssertionError("ground checks ran")), \
             patch.object(validation, "_labels", side_effect=AssertionError("label checks ran")):
            result = self.checked(doc, ir.TechnicalState.INVALID, ("BROKEN_REFERENCE",))
        self.assertEqual(dict(result.skipped_stages)["pins"], "blocked_by_broken_reference")

    def test_duplicate_incidence_skips_component_rules(self):
        doc = circuit("simple")
        result = self.checked(replace(doc, connections=doc.connections * 2),
                              ir.TechnicalState.INVALID, ("PIN_NET_INVALID",))
        self.assertEqual(result.completed_stages, ("schema", "ids", "references", "incidence", "result"))
        self.assertEqual(dict(result.skipped_stages)["pins"], "blocked_by_pin_net_invalid")

    def test_valid_role_sets_for_each_supported_device(self):
        for component_type in (ir.ComponentType.RESISTOR, ir.ComponentType.CAPACITOR, ir.ComponentType.INDUCTOR):
            doc = circuit("simple")
            component = replace(doc.components[1], type=component_type)
            self.checked(replace(doc, components=(doc.components[0], component)), ir.TechnicalState.UNVALIDATED, ())
        doc = circuit("simple")
        self.checked(replace(doc, components=(replace(doc.components[0], type=ir.ComponentType.CURRENT_SOURCE),)
                             + doc.components[1:]), ir.TechnicalState.UNVALIDATED, ())
        doc = circuit("mos")
        self.checked(replace(doc, components=doc.components[:-1] + (replace(doc.components[-1], type=ir.ComponentType.PMOS),)),
                     ir.TechnicalState.UNVALIDATED, ())

    def test_missing_required_role_for_each_device_family(self):
        for component_type in (ir.ComponentType.RESISTOR, ir.ComponentType.CAPACITOR, ir.ComponentType.INDUCTOR):
            doc = remove_pin(circuit("simple"), "R1.p2")
            doc = replace(doc, components=(doc.components[0], replace(doc.components[1], type=component_type)))
            self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        for component_type in (ir.ComponentType.VOLTAGE_SOURCE, ir.ComponentType.CURRENT_SOURCE):
            doc = remove_pin(circuit("simple"), "V1.p2")
            doc = replace(doc, components=(replace(doc.components[0], type=component_type),) + doc.components[1:])
            self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        for component_type in (ir.ComponentType.NMOS, ir.ComponentType.PMOS):
            doc = remove_pin(circuit("mos"), "M1.p4")
            doc = replace(doc, components=doc.components[:-1] + (replace(doc.components[-1], type=component_type),))
            self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))

    def test_duplicate_known_role_is_error_for_each_family(self):
        for kind, pin_id, role in (("simple", "R1.p2", ir.PinRole.A),
                                  ("simple", "V1.p2", ir.PinRole.POSITIVE),
                                  ("mos", "M1.p4", ir.PinRole.SOURCE)):
            with self.subTest(kind=kind):
                self.checked(change_role(circuit(kind), pin_id, role), ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))

    def test_wrong_role_and_extra_pin_are_errors(self):
        self.checked(change_role(circuit("simple"), "R1.p2", ir.PinRole.GATE),
                     ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        doc = circuit("simple")
        resistor = replace(doc.components[1], pin_ids=doc.components[1].pin_ids + ("R1.p3",))
        doc = replace(doc, components=(doc.components[0], resistor),
                      pins=doc.pins + (ir.Pin("R1.p3", "R1", ir.PinRole.B, None),),
                      connections=doc.connections + (ir.Connection("R1.p3", "n0", (), doc.confidence),))
        self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))

    def test_unknown_role_is_ambiguous_without_known_contradiction(self):
        for kind, pin_id in (("simple", "R1.p2"), ("simple", "V1.p2"), ("mos", "M1.p4")):
            result = self.checked(change_role(circuit(kind), pin_id, ir.PinRole.UNKNOWN),
                                  ir.TechnicalState.AMBIGUOUS, ("PIN_ROLES_INVALID",))
            self.assertEqual(result.ambiguous_count, 1)

    def test_repeated_unknown_roles_are_not_falsely_known_duplicates(self):
        doc = circuit("simple")
        doc = change_role(change_role(doc, "R1.p1", ir.PinRole.UNKNOWN), "R1.p2", ir.PinRole.UNKNOWN)
        self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("PIN_ROLES_INVALID",))

    def test_role_count_contradiction_takes_precedence_over_unknown_role(self):
        doc = change_role(remove_pin(circuit("simple"), "R1.p2"), "R1.p1", ir.PinRole.UNKNOWN)
        result = self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        self.assertEqual(result.ambiguous_count, 0)

    def test_missing_generic_incidence_is_ambiguous(self):
        doc = circuit("simple")
        doc = replace(doc, connections=tuple(row for row in doc.connections if row.pin_id != "R1.p2"))
        result = self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("PIN_NET_INVALID",))
        self.assertEqual(result.issues[0].entity_id, "R1.p2")

    def test_orphan_zero_pins_suppresses_missing_role_noise(self):
        doc = circuit("simple")
        doc = remove_pin(remove_pin(doc, "R1.p1"), "R1.p2")
        result = self.checked(doc, ir.TechnicalState.INVALID, ("ORPHAN_DEVICE",))
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(dict(result.skipped_stages)["component[R1].pin_roles"], "orphan_device")

    def test_device_without_connected_terminals_is_orphan(self):
        doc = circuit("simple")
        doc = replace(doc, connections=tuple(row for row in doc.connections if not row.pin_id.startswith("R1.")))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("ORPHAN_DEVICE",))
        self.assertEqual(len(result.issues), 1)

    def test_empty_document_is_not_vacuously_valid(self):
        doc = replace(circuit("simple"), components=(), pins=(), connections=(), nets=(), labels=())
        self.checked(doc, ir.TechnicalState.INVALID, ("ORPHAN_DEVICE", "GROUND_MISSING"))

    def test_missing_ground(self):
        doc = circuit("simple")
        doc = replace(doc, nets=tuple(replace(net, is_ground=False) for net in doc.nets))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("GROUND_MISSING",))
        self.assertEqual(dict(result.skipped_stages)["graph_dc"], "blocked_by_ground_missing")

    def test_multiple_ground_nets_are_error(self):
        doc = circuit("simple")
        doc = replace(doc, nets=tuple(replace(net, is_ground=True) for net in doc.nets))
        result = self.checked(doc, ir.TechnicalState.INVALID, ("GROUND_MISSING",))
        self.assertEqual(result.issues[0].target_refs, ("n0", "vin"))

    def test_labels_and_coordinates_never_create_ground(self):
        doc = circuit("simple")
        doc = replace(doc, nets=tuple(replace(net, is_ground=False) for net in doc.nets),
                      labels=(replace(doc.labels[0], text="GND"),))
        self.checked(doc, ir.TechnicalState.INVALID, ("GROUND_MISSING",))

    def test_unused_and_single_pin_nets_have_no_invented_dangling_rule(self):
        doc = circuit("simple")
        doc = replace(doc, nets=doc.nets + (ir.Net("unused", False),))
        self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        doc = replace(doc, nets=doc.nets + (ir.Net("one_pin", False),),
                      connections=tuple(replace(row, net_id="one_pin") if row.pin_id == "R1.p2" else row
                                        for row in doc.connections))
        self.assertEqual(ir.build_graph(doc).graph.pins_for_net("one_pin"), ("R1.p2",))
        self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        # A separate incidence island is evaluated by the future graph/DC stage,
        # not silently treated as conductive or rejected with an invented code.
        doc = replace(doc, connections=tuple(replace(row, net_id="one_pin") if row.pin_id == "R1.p1" else row
                                            for row in doc.connections))
        result = self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        self.assertEqual(dict(result.skipped_stages)["graph_dc"], "not_implemented_m1f")

    def test_unattached_label_is_ambiguous(self):
        doc = circuit("simple")
        result = self.checked(replace(doc, labels=(replace(doc.labels[0], net_id=None),)),
                              ir.TechnicalState.AMBIGUOUS, ("LABEL_UNRESOLVED",))
        self.assertEqual(result.blocking_issue_count, 1)

    def test_whitespace_label_is_error(self):
        doc = circuit("simple")
        self.checked(replace(doc, labels=(replace(doc.labels[0], text=" \t "),)),
                     ir.TechnicalState.INVALID, ("LABEL_CONFLICT",))

    def test_trimmed_ascii_case_identity_conflict_on_different_nets(self):
        doc = circuit("simple")
        other = ir.Label("label_other", " VIN ", "flat", "n0", None)
        self.checked(replace(doc, labels=doc.labels + (other,)), ir.TechnicalState.INVALID, ("LABEL_CONFLICT",))

    def test_case_variants_on_same_net_are_not_alias_warning(self):
        doc = circuit("simple")
        other = ir.Label("label_other", " VIN ", "flat", "vin", None)
        self.checked(replace(doc, labels=doc.labels + (other,)), ir.TechnicalState.UNVALIDATED, ())

    def test_non_ascii_case_is_not_silently_normalized(self):
        doc = circuit("simple")
        labels = (ir.Label("label_omega", "Ω", "flat", "vin", None),
                  ir.Label("label_omega_lower", "ω", "flat", "vin", None))
        self.checked(replace(doc, labels=labels), ir.TechnicalState.UNVALIDATED, ("LABEL_ALIAS",))

    def test_alias_warning_is_fresh_nonblocking_and_requires_no_merge(self):
        doc = circuit("simple")
        other = ir.Label("label_alias", "input", "flat", "vin", None)
        result = self.checked(replace(doc, labels=doc.labels + (other,)),
                              ir.TechnicalState.UNVALIDATED, ("LABEL_ALIAS",))
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.blocking_issue_count, 0)
        self.assertFalse(result.issues[0].blocking)

    def test_conflicting_label_group_does_not_also_create_alias_noise(self):
        doc = circuit("simple")
        labels = doc.labels + (ir.Label("label_conflict", "VIN", "flat", "n0", None),
                              ir.Label("label_other", "input", "flat", "vin", None))
        result = self.checked(replace(doc, labels=labels), ir.TechnicalState.INVALID, ("LABEL_CONFLICT",))
        self.assertEqual(result.warning_count, 0)

    def test_reserved_zero_label_must_attach_to_explicit_ground(self):
        doc = circuit("simple")
        self.checked(replace(doc, labels=(replace(doc.labels[0], text="0", net_id="n0"),)),
                     ir.TechnicalState.UNVALIDATED, ())
        self.checked(replace(doc, labels=(replace(doc.labels[0], text="0"),)),
                     ir.TechnicalState.INVALID, ("LABEL_CONFLICT",))

    def test_independent_error_ambiguous_and_warning_preserve_severity_order(self):
        doc = circuit("simple")
        labels = (replace(doc.labels[0], net_id=None),
                  ir.Label("label_a", "ground_ref", "flat", "n0", None),
                  ir.Label("label_b", "zero_ref", "flat", "n0", None))
        doc = replace(doc, nets=tuple(replace(net, is_ground=False) for net in doc.nets), labels=labels)
        result = self.checked(doc, ir.TechnicalState.INVALID,
                              ("GROUND_MISSING", "LABEL_UNRESOLVED", "LABEL_ALIAS"))
        self.assertEqual([issue.severity for issue in result.issues],
                         [ir.IssueSeverity.ERROR, ir.IssueSeverity.AMBIGUOUS, ir.IssueSeverity.WARNING])
        self.assertEqual((result.blocking_issue_count, result.warning_count, result.ambiguous_count), (2, 1, 1))

    def test_local_role_error_does_not_stop_other_components(self):
        doc = change_role(circuit("divider"), "R1.p2", ir.PinRole.A)
        doc = change_role(doc, "R2.p2", ir.PinRole.UNKNOWN)
        result = self.checked(doc, ir.TechnicalState.INVALID, ("PIN_ROLES_INVALID",))
        self.assertEqual(len(result.issues), 2)
        self.assertEqual(result.ambiguous_count, 1)

    def test_source_specific_semantics_are_explicitly_deferred_to_m1f(self):
        doc = circuit("simple")
        rows = tuple(replace(row, net_id="vin") if row.pin_id.startswith("V1.") else row
                     for row in doc.connections)
        self.checked(replace(doc, connections=rows), ir.TechnicalState.UNVALIDATED, ())
        doc = replace(doc, components=(replace(doc.components[0], source=None),) + doc.components[1:])
        self.checked(doc, ir.TechnicalState.UNVALIDATED, ())

    def test_value_semantics_are_explicitly_deferred_to_m1f(self):
        doc = circuit("simple")
        component = replace(doc.components[1], value=quantity("-1", "ohm"))
        self.checked(replace(doc, components=(doc.components[0], component)), ir.TechnicalState.UNVALIDATED, ())

    def test_mos_bulk_incidence_waits_for_specific_m1f_rule(self):
        doc = circuit("mos")
        doc = replace(doc, connections=tuple(row for row in doc.connections if row.pin_id != "M1.p4"))
        result = self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        self.assertEqual(dict(result.skipped_stages)["pin[M1.p4].incidence"], "mos_bulk_deferred_to_m1f")
        self.assertNotIn("PIN_NET_INVALID", {issue.code for issue in result.issues})

    def test_mos_role_order_and_visual_orientation_never_determine_roles(self):
        doc = circuit("mos")
        visual = ir.VisualEntity("symbol_m", ir.VisualKind.SYMBOL, ir.BoundingBox(1, 1, 2, 2),
                                 None, ir.Orientation.R90_MIRROR, (), None, "manual", doc.confidence)
        doc = replace(doc, visual=ir.VisualProvenance("original_pixels", (visual,)),
                      components=tuple(replace(item, visual_ref="symbol_m", pin_ids=item.pin_ids[::-1])
                                       if item.id == "M1" else item for item in doc.components))
        result = self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        changed = replace(doc, visual=replace(doc.visual, entities=(replace(visual, orientation=ir.Orientation.R270),)))
        self.assertEqual(result, ir.validate_document(changed))

    def test_unknown_device_and_explicit_ambiguity_never_become_full_valid(self):
        doc = circuit("simple")
        candidate = ir.Candidate("candidate_a", "Resistor hypothesis")
        choice = ir.Ambiguity("choice_a", ir.AmbiguityKind.SYMBOL_TYPE, ("R1",),
                              (candidate,), ir.AmbiguityStatus.UNRESOLVED, None, None)
        doc = replace(doc, components=(doc.components[0], replace(doc.components[1], type=ir.ComponentType.UNKNOWN)),
                      ambiguities=(choice,))
        result = self.checked(doc, ir.TechnicalState.UNVALIDATED, ())
        self.assertIn("ambiguity_confidence_provenance", dict(result.skipped_stages))
        self.assertEqual(dict(result.skipped_stages)["component[R1].pins"], "type_unknown_deferred_to_m1f")

    def test_confidence_and_imported_reviewed_state_cannot_mask_current_errors(self):
        doc = circuit("simple")
        doc = replace(doc, nets=tuple(replace(net, is_ground=False) for net in doc.nets),
                      confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True),
                      validation_state=ir.ImportedValidationState(ir.WireValidationStatus.REVIEWED, 99, "stale", ()))
        self.checked(doc, ir.TechnicalState.INVALID, ("GROUND_MISSING",))

    def test_stale_imported_findings_are_not_copied_into_fresh_issues(self):
        doc = circuit("simple")
        finding = ir.ImportedFinding("old_error", "VALUE_INVALID", ir.IssueSeverity.ERROR,
                                     ("R1",), "Historical failure", ())
        doc = replace(doc, validation_state=ir.ImportedValidationState(ir.WireValidationStatus.BLOCKED,
                      99, "stale", (finding,)))
        self.checked(doc, ir.TechnicalState.UNVALIDATED, ())

    def test_fresh_report_remains_separate_from_wire_status_and_serialization(self):
        doc = circuit("simple")
        result = ir.validate_document(doc)
        self.assertIsInstance(result, ir.ValidationResult)
        self.assertEqual(doc.validation_state.status, ir.WireValidationStatus.DRAFT)
        for name in ("approved", "executable", "user_decision", "can_execute", "graph"):
            self.assertFalse(hasattr(result, name))
        with self.assertRaises(TypeError):
            ir.dump_document(result)
        with self.assertRaises(FrozenInstanceError):
            result.technical_state = ir.TechnicalState.VALID

    def test_skip_reasons_and_collections_are_immutable(self):
        result = ir.validate_document(circuit("simple"))
        self.assertIs(type(result.completed_stages), tuple)
        self.assertIs(type(result.skipped_stages), tuple)
        self.assertTrue(all(type(pair) is tuple for pair in result.skipped_stages))
        self.assertIs(type(result.deferred_checks), tuple)
        with self.assertRaises(TypeError):
            result.skipped_stages[0] = ("replacement", "reason")

    def test_input_permutations_preserve_report_and_source_order(self):
        doc = change_role(circuit("divider"), "R1.p2", ir.PinRole.UNKNOWN)
        doc = replace(doc, labels=doc.labels + (ir.Label("label_alias", "input", "flat", "vin", None),))
        expected = ir.validate_document(doc)
        rng = random.Random(32)
        for _ in range(8):
            fields = {}
            for name in ("components", "pins", "nets", "connections", "labels"):
                records = list(getattr(doc, name))
                rng.shuffle(records)
                fields[name] = tuple(records)
            changed = replace(doc, **fields)
            before = ir.dump_document(changed)
            self.assertEqual(ir.validate_document(changed), expected)
            self.assertEqual(ir.dump_document(changed), before)

    def test_issue_ids_targets_and_deduplication_are_deterministic(self):
        doc = circuit("simple")
        labels = doc.labels + (ir.Label("label_a", "VIN", "flat", "n0", None),
                              ir.Label("label_b", " Vin ", "flat", "n0", None))
        result = self.checked(replace(doc, labels=labels), ir.TechnicalState.INVALID, ("LABEL_CONFLICT",))
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].issue_id, "issue_0001")
        self.assertEqual(result.issues[0].target_refs, tuple(sorted(set(result.issues[0].target_refs))))

    def test_provenance_uses_only_existing_explicit_visual_refs(self):
        doc = change_role(circuit("simple"), "R1.p2", ir.PinRole.UNKNOWN)
        visual = ir.VisualEntity("symbol_r", ir.VisualKind.SYMBOL, None, None,
                                 ir.Orientation.R0, (), None, "manual", doc.confidence)
        doc = replace(doc, components=(doc.components[0], replace(doc.components[1], visual_ref="symbol_r")),
                      visual=ir.VisualProvenance("original_pixels", (visual,)))
        result = self.checked(doc, ir.TechnicalState.AMBIGUOUS, ("PIN_ROLES_INVALID",))
        self.assertEqual(result.issues[0].provenance, ("symbol_r",))

    def test_report_round_trip_and_revision_are_current_not_archival(self):
        doc = circuit("divider")
        result = ir.validate_document(doc)
        self.assertEqual(result, ir.validate_document(ir.load_document(ir.dump_document(doc)).document))
        self.assertEqual(ir.validate_document(replace(doc, metadata=replace(doc.metadata, revision=4))).document_revision, 4)

    def test_repeat_calls_after_schema_initialization_use_no_io_or_environment(self):
        doc = circuit("simple")
        expected = ir.validate_document(doc)
        with patch("builtins.open", side_effect=AssertionError("file")), \
             patch("pathlib.Path.open", side_effect=AssertionError("file")), \
             patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("process")), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "", "LLM_PROVIDER": "unavailable"}, clear=True):
            self.assertEqual(ir.validate_document(doc), expected)

    def test_api_rejects_non_documents_without_coercion(self):
        for value in (None, {}, "{}", []):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.validate_document(value)

    def test_hash_randomization_preserves_report(self):
        script = '''
import circuit_ir as ir
from dataclasses import replace
from pathlib import Path
doc = ir.load_document(Path("tests/fixtures/circuit_ir/serialization_draft.json").read_text(encoding="utf-8")).document
doc = replace(doc, labels=doc.labels + (ir.Label("alias_a", "input", "flat", "nin", None),))
print(ir.validate_document(doc))
'''
        outputs = []
        for seed in ("1", "983"):
            result = subprocess.run([sys.executable, "-B", "-c", script],
                                    cwd=Path(__file__).resolve().parents[1],
                                    env={**os.environ, "PYTHONHASHSEED": seed},
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_hand_authored_m1e_fixtures_match_independent_expectations(self):
        root = Path(__file__).parent / "fixtures/circuit_ir"
        for relative in ("invalid/missing_ground", "invalid/orphan_device", "ambiguous/pin_connection_pending"):
            with self.subTest(relative=relative):
                directory = root / relative
                doc = ir.load_document((directory / "circuit.json").read_text(encoding="utf-8")).document
                expected = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
                result = ir.validate_document(doc)
                self.assertEqual(result.profile, expected["profile"])
                self.assertEqual(result.technical_state.value, expected["technical_state"])
                self.assertEqual([(issue.code, issue.severity.value, list(issue.target_refs)) for issue in result.issues],
                                 [(item["code"], item["severity"], item["target_refs"]) for item in expected["issues"]])
                self.assertEqual(list(result.completed_stages), expected["completed_stages"])
                self.assertEqual(dict(result.skipped_stages), expected["skipped_stages"])
                self.assertEqual(list(result.deferred_checks), expected["deferred_checks"])


if __name__ == "__main__":
    unittest.main()
