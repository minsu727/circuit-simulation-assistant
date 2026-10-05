"""M1D structural prerequisites and derived incidence; no electrical validation."""
from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir


def source_document():
    # Reuse the independently authored M1B golden without rewriting its evidence.
    path = Path(__file__).parent / "fixtures/circuit_ir/serialization_draft.json"
    result = ir.load_document(path.read_text(encoding="utf-8"))
    if result.issues:
        raise AssertionError(result.issues)
    return result.document


def two_components():
    doc = source_document()
    second = replace(doc.components[0], id="R2", pin_ids=("R2.a", "R2.b"))
    pins = (ir.Pin("R2.a", "R2", ir.PinRole.A, None),
            ir.Pin("R2.b", "R2", ir.PinRole.B, None))
    connections = (ir.Connection("R2.a", "nin", (), doc.confidence),
                   ir.Connection("R2.b", "nout", (), doc.confidence))
    return replace(doc, components=(second,) + doc.components, pins=pins + doc.pins,
                   nets=(ir.Net("nout", False),) + doc.nets,
                   connections=connections + doc.connections)


def referenced_document():
    doc = source_document()
    visual = ir.VisualEntity("symbol_a", ir.VisualKind.SYMBOL, None, None,
                             ir.Orientation.R0, (), "Resistor", "manual", doc.confidence)
    second = replace(visual, id="pin_mark", kind=ir.VisualKind.PIN)
    ambiguity = ir.Ambiguity("choice_a", ir.AmbiguityKind.VALUE, ("R1", "symbol_a"),
                             (ir.Candidate("option_a", "Keep original value"),
                              ir.Candidate("option_b", "Review another value")),
                             ir.AmbiguityStatus.UNRESOLVED, None, None)
    finding = ir.ImportedFinding("archive_a", "CHECK_DEFERRED", ir.IssueSeverity.WARNING,
                                 ("R1", "label_in"), "Archival note only", ("symbol_a",))
    return replace(doc,
                   components=(replace(doc.components[0], visual_ref="symbol_a"),),
                   pins=tuple(replace(pin, visual_ref="pin_mark") for pin in doc.pins),
                   connections=tuple(replace(row, visual_refs=("symbol_a", "pin_mark"))
                                     for row in doc.connections),
                   labels=(replace(doc.labels[0], visual_ref="symbol_a"),),
                   visual=ir.VisualProvenance("original_pixels", (second, visual)),
                   ambiguities=(ambiguity,), warnings=("archive_a",),
                   validation_state=ir.ImportedValidationState(
                       ir.WireValidationStatus.REVIEWED, 99, "older_rules", (finding,)))


class GraphTests(unittest.TestCase):
    def graph(self, doc):
        result = ir.build_graph(doc)
        self.assertEqual(result.issues, ())
        self.assertIsInstance(result.graph, ir.CircuitGraph)
        return result.graph

    def rejected(self, doc, code, field=None):
        before = ir.dump_document(doc)
        result = ir.build_graph(doc)
        self.assertIsNone(result.graph)
        self.assertTrue(result.issues)
        self.assertEqual({issue.code for issue in result.issues}, {code})
        if field is not None:
            self.assertTrue(any(issue.field == field or issue.field.endswith("." + field)
                                for issue in result.issues), result.issues)
        self.assertTrue(all(issue.severity is ir.IssueSeverity.ERROR and issue.blocking
                            for issue in result.issues))
        self.assertEqual(ir.dump_document(doc), before)
        return result

    def test_authored_minimal_document_builds_indexes_and_lookups(self):
        doc = source_document()
        graph = self.graph(doc)
        self.assertEqual(tuple(graph.component_by_id), ("R1",))
        self.assertEqual(tuple(graph.pin_by_id), ("R1.a", "R1.b"))
        self.assertEqual(tuple(graph.net_by_id), ("n0", "nin"))
        self.assertIs(graph.component_by_id["R1"], doc.components[0])
        self.assertIs(graph.pin_by_id["R1.a"], doc.pins[0])
        self.assertIs(graph.net_by_id["nin"], doc.nets[0])
        self.assertEqual(graph.pins_for_component("R1"), ("R1.a", "R1.b"))
        self.assertEqual(graph.net_for_pin("R1.a"), "nin")
        self.assertEqual(graph.pins_for_net("n0"), ("R1.b",))

    def test_typed_adjacency_has_only_explicit_ownership_and_incidence(self):
        graph = self.graph(source_document())
        self.assertEqual(dict(graph.adjacency), {
            ("component", "R1"): (("pin", "R1.a"), ("pin", "R1.b")),
            ("pin", "R1.a"): (("component", "R1"), ("net", "nin")),
            ("pin", "R1.b"): (("component", "R1"), ("net", "n0")),
            ("net", "n0"): (("pin", "R1.b"),),
            ("net", "nin"): (("pin", "R1.a"),),
        })

    def test_multiple_components_have_sorted_membership(self):
        graph = self.graph(two_components())
        self.assertEqual(tuple(graph.component_by_id), ("R1", "R2"))
        self.assertEqual(graph.pins_for_net("nin"), ("R1.a", "R2.a"))
        self.assertEqual(graph.pins_for_component("R2"), ("R2.a", "R2.b"))

    def test_bfs_groups_include_unused_nodes_without_issuing_electrical_findings(self):
        doc = source_document()
        original = self.graph(doc)
        self.assertEqual(original.connected_components(), (tuple(original.adjacency),))
        graph = self.graph(replace(doc, nets=doc.nets + (ir.Net("unused_net", False),)))
        self.assertEqual(graph.connected_components(),
                         (tuple(original.adjacency), (("net", "unused_net"),)))

    def test_connection_views_retain_source_records_without_backwriting(self):
        doc = source_document()
        before = ir.dump_document(doc)
        graph = self.graph(doc)
        self.assertIs(graph.connection_by_pin["R1.a"], doc.connections[0])
        self.assertEqual(ir.dump_document(doc), before)
        self.assertFalse(hasattr(doc.pins[0], "net_id"))
        self.assertFalse(hasattr(doc.nets[0], "connected_pins"))
        changed = replace(doc, connections=(replace(doc.connections[0], net_id="n0"),)
                          + doc.connections[1:])
        self.assertEqual(self.graph(changed).net_for_pin("R1.a"), "n0")
        self.assertEqual(graph.net_for_pin("R1.a"), "nin")

    def test_graph_and_nested_views_are_read_only(self):
        graph = self.graph(source_document())
        for mapping in (graph.component_by_id, graph.pin_by_id, graph.net_by_id,
                        graph.connection_by_pin, graph.adjacency):
            with self.subTest(mapping=type(mapping)), self.assertRaises(TypeError):
                mapping["extra"] = None
        self.assertIs(type(graph.adjacency[("component", "R1")]), tuple)
        with self.assertRaises(FrozenInstanceError):
            graph.adjacency = {}

    def test_graph_copies_exposed_mapping_inputs(self):
        built = self.graph(source_document())
        components, adjacency = dict(built.component_by_id), dict(built.adjacency)
        copied = ir.CircuitGraph(components, built.pin_by_id, built.net_by_id,
                                 built.connection_by_pin, adjacency)
        components.clear()
        adjacency.clear()
        self.assertEqual(copied, built)

    def test_unknown_lookup_is_distinct_from_unresolved_incidence(self):
        doc = source_document()
        graph = self.graph(replace(doc, connections=doc.connections[1:]))
        self.assertIsNone(graph.net_for_pin("R1.a"))
        self.assertEqual(graph.adjacency[("pin", "R1.a")], (("component", "R1"),))
        for method in (graph.pins_for_component, graph.net_for_pin, graph.pins_for_net):
            with self.subTest(method=method), self.assertRaises(KeyError):
                method("undefined")

    def test_empty_net_and_component_are_retained_without_electrical_judgment(self):
        doc = source_document()
        graph = self.graph(replace(doc, components=(replace(doc.components[0], pin_ids=()),),
                                   pins=(), connections=(), labels=()))
        self.assertEqual(graph.pins_for_component("R1"), ())
        self.assertEqual(graph.pins_for_net("nin"), ())
        self.assertIn(("net", "nin"), graph.adjacency)

    def test_input_permutations_preserve_sorted_views_and_source_order(self):
        doc = two_components()
        expected = self.graph(doc)
        rng = random.Random(31)
        for _ in range(8):
            fields = {}
            for name in ("components", "pins", "nets", "connections", "labels"):
                records = list(getattr(doc, name))
                rng.shuffle(records)
                if name == "components":
                    records = [replace(item, pin_ids=tuple(reversed(item.pin_ids))) for item in records]
                fields[name] = tuple(records)
            changed = replace(doc, **fields)
            before = ir.dump_document(changed)
            graph = self.graph(changed)
            self.assertEqual(graph.adjacency, expected.adjacency)
            self.assertEqual(graph.connected_components(), expected.connected_components())
            self.assertEqual(tuple(graph.component_by_id), tuple(expected.component_by_id))
            self.assertEqual(tuple(graph.connection_by_pin), tuple(expected.connection_by_pin))
            self.assertEqual(ir.dump_document(changed), before)

    def test_round_trip_and_harmless_geometry_changes_preserve_topology(self):
        doc = referenced_document()
        original = self.graph(doc)
        loaded = ir.load_document(ir.dump_document(doc)).document
        self.assertEqual(self.graph(loaded), original)
        visual = replace(doc.visual.entities[0], position=ir.PixelPoint(900, 1200),
                         orientation=ir.Orientation.R270_MIRROR)
        changed = replace(doc, visual=replace(doc.visual, entities=(visual,) + doc.visual.entities[1:]))
        self.assertEqual(self.graph(changed), original)

    def test_valid_references_and_archival_reviewed_snapshot_grant_no_approval(self):
        doc = referenced_document()
        result = ir.build_graph(doc)
        self.assertEqual(result.issues, ())
        self.assertIsNotNone(result.graph)
        self.assertEqual(doc.validation_state.validated_revision, 99)
        for capability in ("technical_state", "approved", "can_execute"):
            self.assertFalse(hasattr(result, capability))
        self.assertTrue(callable(ir.validate_document))

    def test_duplicate_definitions_for_every_global_namespace(self):
        doc = referenced_document()
        for name in ("components", "pins", "nets", "labels", "ambiguities"):
            with self.subTest(namespace=name):
                records = getattr(doc, name)
                result = self.rejected(replace(doc, **{name: records + (records[0],)}), "DUPLICATE_ID")
                self.assertEqual(len(result.issues), 1)
        self.rejected(replace(doc, visual=replace(doc.visual, entities=doc.visual.entities * 2)), "DUPLICATE_ID")
        self.rejected(replace(doc, validation_state=replace(doc.validation_state,
                      findings=doc.validation_state.findings * 2)), "DUPLICATE_ID")

    def test_cross_namespace_definition_collision_is_rejected(self):
        doc = source_document()
        self.rejected(replace(doc, nets=(replace(doc.nets[0], id="R1"), doc.nets[1])), "DUPLICATE_ID")

    def test_component_case_collision_is_rejected_without_renaming(self):
        doc = source_document()
        result = self.rejected(replace(doc, components=doc.components +
                               (replace(doc.components[0], id="r1", pin_ids=()),)), "DUPLICATE_ID")
        self.assertEqual(result.issues[0].target_refs, ("R1", "r1"))

    def test_noncomponent_ids_use_exact_identity(self):
        doc = source_document()
        graph = self.graph(replace(doc, nets=doc.nets + (ir.Net("NIN", False),)))
        self.assertEqual(tuple(graph.net_by_id), ("NIN", "n0", "nin"))

    def test_candidate_ids_are_local_but_locally_unique(self):
        doc = referenced_document()
        ambiguity = doc.ambiguities[0]
        reused = replace(ambiguity, id="choice_b")
        self.graph(replace(doc, ambiguities=(ambiguity, reused)))
        duplicate = replace(ambiguity, candidates=ambiguity.candidates * 2)
        self.rejected(replace(doc, ambiguities=(duplicate,)), "DUPLICATE_ID", "candidates")

    def test_duplicate_gate_suppresses_references_and_incidence(self):
        doc = source_document()
        changed = replace(doc, components=doc.components * 2,
                          connections=(ir.Connection("absent_pin", "absent_net", (), doc.confidence),) * 2)
        self.rejected(changed, "DUPLICATE_ID")

    def test_connection_unknown_pin(self):
        doc = source_document()
        self.rejected(replace(doc, connections=(replace(doc.connections[0], pin_id="absent_pin"),)),
                      "BROKEN_REFERENCE", "pin_id")

    def test_connection_unknown_net(self):
        doc = source_document()
        self.rejected(replace(doc, connections=(replace(doc.connections[0], net_id="absent_net"),)),
                      "BROKEN_REFERENCE", "net_id")

    def test_reference_types_do_not_resolve_against_unrelated_namespace(self):
        doc = referenced_document()
        self.rejected(replace(doc, connections=(replace(doc.connections[0], net_id="R1"),)), "BROKEN_REFERENCE")
        self.rejected(replace(doc, components=(replace(doc.components[0], visual_ref="n0"),)),
                      "BROKEN_REFERENCE", "visual_ref")
        self.rejected(replace(doc, warnings=("R1",)), "BROKEN_REFERENCE", "warnings")

    def test_symmetric_wrong_namespace_references_remain_independent_issues(self):
        doc = source_document()
        pins = (replace(doc.pins[0], visual_ref=doc.pins[1].id),
                replace(doc.pins[1], visual_ref=doc.pins[0].id))
        result = self.rejected(replace(doc, pins=pins), "BROKEN_REFERENCE", "visual_ref")
        self.assertEqual(len(result.issues), 2)
        self.assertEqual({issue.field for issue in result.issues},
                         {"pin[R1.a].visual_ref", "pin[R1.b].visual_ref"})

    def test_swapped_connection_endpoints_keep_distinct_diagnostics(self):
        doc = source_document()
        rows = (ir.Connection("n0", "nin", (), doc.confidence),
                ir.Connection("nin", "n0", (), doc.confidence))
        changed = replace(doc, connections=rows)
        result = self.rejected(changed, "BROKEN_REFERENCE", "pin_id")
        self.assertEqual(len(result.issues), 2)
        self.assertEqual(result, ir.build_graph(replace(changed, connections=rows[::-1])))

    def test_diagnostics_retain_existing_explicit_visual_evidence(self):
        doc = referenced_document()
        result = self.rejected(replace(doc, connections=doc.connections + (doc.connections[0],)),
                               "PIN_NET_INVALID")
        self.assertEqual(result.issues[0].provenance, ("pin_mark", "symbol_a"))
        bad = replace(doc, connections=(replace(doc.connections[0], net_id="absent_net"),))
        self.assertEqual(self.rejected(bad, "BROKEN_REFERENCE").issues[0].provenance,
                         ("pin_mark", "symbol_a"))

    def test_unknown_owner_has_one_root_issue(self):
        doc = source_document()
        result = self.rejected(replace(doc, pins=(replace(doc.pins[0], component_id="absent_owner"),)
                                      + doc.pins[1:]), "BROKEN_REFERENCE", "component_id")
        self.assertEqual(len(result.issues), 1)

    def test_component_declares_unknown_pin(self):
        doc = source_document()
        self.rejected(replace(doc, components=(replace(doc.components[0],
                       pin_ids=doc.components[0].pin_ids + ("absent_pin",)),)), "BROKEN_REFERENCE", "pin_ids")

    def test_reverse_ownership_requires_pin_in_owners_collection(self):
        doc = source_document()
        result = self.rejected(replace(doc, components=(replace(doc.components[0], pin_ids=("R1.b",)),)),
                               "BROKEN_REFERENCE", "ownership")
        self.assertEqual(result.issues[0].entity_id, "R1.a")

    def test_pin_claimed_by_multiple_components_is_rejected(self):
        doc = two_components()
        second = replace(doc.components[0], pin_ids=doc.components[0].pin_ids + ("R1.a",))
        result = self.rejected(replace(doc, components=(second,) + doc.components[1:]),
                               "BROKEN_REFERENCE", "ownership")
        self.assertEqual(len(result.issues), 1)

    def test_pin_declared_by_wrong_component_is_rejected(self):
        doc = two_components()
        second = replace(doc.components[0], pin_ids=doc.components[0].pin_ids + ("R1.a",))
        first = replace(doc.components[1], pin_ids=("R1.b",))
        self.rejected(replace(doc, components=(second, first)), "BROKEN_REFERENCE", "ownership")

    def test_exact_duplicate_connection_is_error(self):
        doc = source_document()
        result = self.rejected(replace(doc, connections=doc.connections + (doc.connections[0],)),
                               "PIN_NET_INVALID", "connections")
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].target_refs, ("R1.a", "nin"))

    def test_distinct_connection_rows_to_same_net_are_error(self):
        doc = referenced_document()
        row = replace(doc.connections[0], visual_refs=())
        self.rejected(replace(doc, connections=doc.connections + (row,)), "PIN_NET_INVALID")

    def test_pin_assigned_to_two_nets_is_error(self):
        doc = source_document()
        row = replace(doc.connections[0], net_id="n0")
        result = self.rejected(replace(doc, connections=doc.connections + (row,)), "PIN_NET_INVALID")
        self.assertEqual(result.issues[0].target_refs, ("R1.a", "n0", "nin"))

    def test_connection_conflict_has_one_root_per_pin(self):
        doc = source_document()
        changed = replace(doc, connections=doc.connections +
                          (doc.connections[0], replace(doc.connections[0], net_id="n0")))
        self.assertEqual(len(self.rejected(changed, "PIN_NET_INVALID").issues), 1)

    def test_broken_reference_gate_suppresses_dependent_incidence(self):
        doc = source_document()
        row = replace(doc.connections[0], net_id="absent_net")
        changed = replace(doc, connections=doc.connections + (doc.connections[0], row))
        self.rejected(changed, "BROKEN_REFERENCE")

    def test_multiple_independent_missing_references_are_collected(self):
        doc = source_document()
        rows = (ir.Connection("missing_a", "missing_n", (), doc.confidence),
                ir.Connection("missing_b", "missing_n", (), doc.confidence))
        changed = replace(doc, connections=rows,
                          labels=(replace(doc.labels[0], net_id="missing_label_net"),))
        result = self.rejected(changed, "BROKEN_REFERENCE")
        self.assertEqual(len(result.issues), 5)
        self.assertEqual(result, ir.build_graph(replace(changed, connections=rows[::-1])))

    def test_label_null_attachment_is_preserved_unknown_attachment_fails(self):
        doc = source_document()
        self.graph(replace(doc, labels=(replace(doc.labels[0], net_id=None),)))
        self.rejected(replace(doc, labels=(replace(doc.labels[0], net_id="absent_net"),)),
                      "BROKEN_REFERENCE", "net_id")

    def test_missing_visual_references_in_each_supported_location(self):
        doc = referenced_document()
        candidates = (
            replace(doc, components=(replace(doc.components[0], visual_ref="absent_visual"),)),
            replace(doc, pins=(replace(doc.pins[0], visual_ref="absent_visual"),) + doc.pins[1:]),
            replace(doc, labels=(replace(doc.labels[0], visual_ref="absent_visual"),)),
            replace(doc, connections=(replace(doc.connections[0], visual_refs=("absent_visual",)),)
                    + doc.connections[1:]),
            replace(doc, validation_state=replace(doc.validation_state,
                    findings=(replace(doc.validation_state.findings[0], visual_refs=("absent_visual",)),))),
        )
        for changed in candidates:
            with self.subTest(changed=changed):
                self.rejected(changed, "BROKEN_REFERENCE")

    def test_ambiguity_and_imported_finding_target_references(self):
        doc = referenced_document()
        self.rejected(replace(doc, ambiguities=(replace(doc.ambiguities[0], target_refs=("absent_target",)),)),
                      "BROKEN_REFERENCE", "target_refs")
        self.rejected(replace(doc, validation_state=replace(doc.validation_state,
                      findings=(replace(doc.validation_state.findings[0], target_refs=("absent_target",)),))),
                      "BROKEN_REFERENCE", "target_refs")
        # Local candidates are not global target_refs.
        self.rejected(replace(doc, ambiguities=(replace(doc.ambiguities[0], target_refs=("option_a",)),)),
                      "BROKEN_REFERENCE", "target_refs")

    def test_selected_candidate_must_resolve_within_its_ambiguity(self):
        doc = referenced_document()
        ambiguity = doc.ambiguities[0]
        self.graph(replace(doc, ambiguities=(replace(ambiguity, selected_candidate_id="option_a"),)))
        other = replace(ambiguity, id="choice_b", candidates=(ir.Candidate("other_option", "Other choice"),))
        bad = replace(ambiguity, selected_candidate_id="other_option")
        self.rejected(replace(doc, ambiguities=(bad, other)), "BROKEN_REFERENCE", "selected_candidate_id")

    def test_imported_warning_references_resolve_only_to_warning_findings(self):
        doc = referenced_document()
        self.rejected(replace(doc, warnings=("absent_finding",)), "BROKEN_REFERENCE", "warnings")
        changed = replace(doc, validation_state=replace(doc.validation_state,
                          findings=(replace(doc.validation_state.findings[0], severity=ir.IssueSeverity.ERROR),)))
        self.rejected(changed, "BROKEN_REFERENCE", "warnings")

    def test_reviewed_status_and_confidence_cannot_mask_structural_error(self):
        doc = referenced_document()
        changed = replace(doc, confidence=ir.Confidence(1, ir.ConfidenceBasis.PROVIDER_SCORE, True),
                          connections=doc.connections * 2)
        self.rejected(changed, "PIN_NET_INVALID")
        self.assertEqual(changed.validation_state.status, ir.WireValidationStatus.REVIEWED)

    def test_id_issue_order_and_ids_are_deterministic(self):
        doc = two_components()
        changed = replace(doc, components=doc.components * 2, pins=doc.pins * 2, nets=doc.nets * 2)
        first = self.rejected(changed, "DUPLICATE_ID")
        self.assertEqual(first, ir.build_graph(replace(changed, components=changed.components[::-1],
                                                     pins=changed.pins[::-1], nets=changed.nets[::-1])))
        self.assertEqual([issue.issue_id for issue in first.issues],
                         [f"issue_{i:04d}" for i in range(1, len(first.issues) + 1)])
        self.assertTrue(all(issue.target_refs == tuple(sorted(set(issue.target_refs)))
                            for issue in first.issues))

    def test_direct_construction_must_pass_existing_schema_before_id_checks(self):
        doc = source_document()
        quantity = replace(doc.components[0].value, si_value="NaN")
        changed = replace(doc, components=(replace(doc.components[0], value=quantity),) * 2)
        self.rejected(changed, "SCHEMA_INVALID")

    def test_wrong_api_input_type_is_not_coerced(self):
        for value in (None, {}, "{}", []):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.build_graph(value)

    def test_graph_checks_need_no_network_or_external_service(self):
        doc = referenced_document()
        with patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("external process")):
            self.graph(doc)

    def test_hash_randomization_does_not_change_issues_or_adjacency(self):
        script = '''
import circuit_ir as ir
from dataclasses import replace
from pathlib import Path
doc = ir.load_document(Path("tests/fixtures/circuit_ir/serialization_draft.json").read_text(encoding="utf-8")).document
graph = ir.build_graph(doc).graph
print(tuple(graph.adjacency.items()))
bad = replace(doc, connections=doc.connections + (replace(doc.connections[0], net_id="n0"),))
print(ir.build_graph(bad).issues)
'''
        outputs = []
        for seed in ("1", "731"):
            result = subprocess.run([sys.executable, "-B", "-c", script],
                                    cwd=Path(__file__).resolve().parents[1],
                                    env={**os.environ, "PYTHONHASHSEED": seed},
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
