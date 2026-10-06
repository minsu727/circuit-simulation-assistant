"""M2B bindings: independent projections, stale-review refusals and purity.

No export, simulator, private schematic, network, model resolver or API is used.
Existing authored M1 fixtures are read only; expected hash projections below are
hand-authored from the committed M2 contract, not produced by approval helpers.
"""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "circuit_ir" / "valid"
EMPTY_CONTEXT = {
    "exporter_contract": "m2-spice-v1",
    "model_registry_version": "m2-no-models-v1",
    "model_registry_sha256": hashlib.sha256(
        b'{"profiles":[],"registry_version":"m2-no-models-v1"}').hexdigest(),
}
STAGES = ("schema", "ids", "references", "incidence", "pins", "ground", "labels",
          "component_value_source", "graph_dc", "ambiguity_confidence_provenance", "result")
DEFERRED = ("full_export_readiness", "human_approval", "image_asset_resolution",
            "inference_calibration", "model_catalog_resolution")


def native_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_fixture(name):
    result = ir.load_document((FIXTURES / name / "circuit.json").read_text(encoding="utf-8"))
    if result.document is None:
        raise AssertionError(result.issues)
    return result.document


def archival_warning(doc):
    finding = ir.ImportedFinding("archival_warning", "CHECK_DEFERRED", ir.IssueSeverity.WARNING,
                                 ("R1",), "Archived observation.", ())
    return replace(doc, warnings=(finding.id,), validation_state=replace(
        doc.validation_state, findings=(finding,)))


class ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load_fixture("simple_source_resistor")
        cls.report = ir.validate_document(cls.doc)
        cls.mos = load_fixture("nmos_common_source")

    def make(self, doc=None, **changes):
        kwargs = dict(EMPTY_CONTEXT, approved=True, acknowledged_warning_ids=())
        kwargs.update(changes)
        return ir.make_circuit_approval(self.doc if doc is None else doc, **kwargs)

    def verify(self, doc, envelope, **changes):
        kwargs = dict(EMPTY_CONTEXT, **changes)
        return ir.verify_circuit_approval(doc, envelope, **kwargs)

    def refused(self, code, call, field=None):
        with self.assertRaises(ir.ApprovalError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        if field is not None:
            self.assertEqual(caught.exception.field, field)
        self.assertIsInstance(caught.exception, ValueError)
        return caught.exception

    def test_document_digest_matches_independent_canonical_bytes(self):
        raw = json.loads((FIXTURES / "simple_source_resistor" / "circuit.json").read_text(encoding="utf-8"))
        expected = json.dumps(raw, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
        self.assertEqual(ir.dump_document(self.doc), expected)
        self.assertEqual(ir.document_digest(self.doc), hashlib.sha256(expected.encode("utf-8")).hexdigest())
        self.assertNotIn("\r", expected)
        self.assertTrue(expected.endswith("}\n"))
        self.assertNotEqual(ir.document_digest(self.doc), hashlib.sha256(expected.rstrip("\n").encode("utf-8")).hexdigest())

    def test_document_digest_round_trip_and_raw_formatting(self):
        primitive = ir.document_to_dict(self.doc)
        primitive = dict(reversed(list(primitive.items())))
        alternate = json.dumps(primitive, ensure_ascii=False, indent=4).replace("\n", "\r\n")
        restored = ir.load_document(alternate).document
        self.assertEqual(restored, self.doc)
        self.assertEqual(ir.document_digest(restored), ir.document_digest(self.doc))

    def test_unicode_snapshot_uses_existing_ascii_escaped_utf8(self):
        doc = replace(self.doc, labels=(replace(self.doc.labels[0], text="출력 Ω"),))
        text = ir.dump_document(doc)
        self.assertIn("\\ucd9c", text)
        self.assertNotIn("\r", text)
        self.assertEqual(ir.document_digest(doc), hashlib.sha256(text.encode("utf-8")).hexdigest())

    def test_parameter_map_insertion_order_is_irrelevant(self):
        # Find the actual parameter-bearing device without relying on fixture order.
        mos = next(component for component in self.mos.components if component.parameters)
        changed = replace(self.mos, components=tuple(
            replace(c, parameters=tuple(reversed(c.parameters))) if c.id == mos.id else c
            for c in self.mos.components))
        self.assertEqual(changed, self.mos)
        self.assertEqual(ir.document_digest(changed), ir.document_digest(self.mos))
        self.assertEqual(ir.electrical_digest(changed), ir.electrical_digest(self.mos))

    def test_hand_authored_electrical_vector(self):
        # Full explicit vector for the independently authored source/resistor case.
        expected = {
            "digest_profile": "m2-electrical-digest-v1", "schema_version": "0.2-draft1",
            "metadata": {"catalog_version": "phase_a_draft1"},
            "components": [
                {"id": "R1", "type": "resistor", "pin_ids": ["R1.p1", "R1.p2"],
                 "value": {"si_value": "1000", "unit": "ohm"}, "model_ref": None,
                 "parameters": {}, "source": None},
                {"id": "V1", "type": "voltage_source", "pin_ids": ["V1.p1", "V1.p2"],
                 "value": None, "model_ref": None, "parameters": {},
                 "source": {"dc": {"si_value": "1", "unit": "V"}, "ac": None,
                            "waveform": {"kind": "none", "parameters": {}}}},
            ],
            "pins": [{"id": "R1.p1", "component_id": "R1", "role": "a"},
                     {"id": "R1.p2", "component_id": "R1", "role": "b"},
                     {"id": "V1.p1", "component_id": "V1", "role": "positive"},
                     {"id": "V1.p2", "component_id": "V1", "role": "negative"}],
            "nets": [{"id": "n0", "is_ground": True}, {"id": "vin", "is_ground": False}],
            "connections": [{"pin_id": "R1.p1", "net_id": "vin"},
                            {"pin_id": "R1.p2", "net_id": "n0"},
                            {"pin_id": "V1.p1", "net_id": "vin"},
                            {"pin_id": "V1.p2", "net_id": "n0"}],
            "labels": [{"id": "label_in", "text": "vin", "scope": "flat", "net_id": "vin"}],
        }
        self.assertEqual(ir.electrical_digest(self.doc), native_hash(expected))

    def test_electrical_normalizes_si_not_literal(self):
        r = self.doc.components[1]
        doc = replace(self.doc, components=(self.doc.components[0], replace(
            r, value=ir.Quantity("1k", "1.000e3", "ohm", ir.ValueGrammar.SPICE))))
        self.assertEqual(ir.electrical_digest(doc), ir.electrical_digest(self.doc))
        self.assertNotEqual(ir.document_digest(doc), ir.document_digest(self.doc))

    def test_electrical_ignores_identity_revision_and_provenance(self):
        doc = replace(archival_warning(self.doc), metadata=replace(self.doc.metadata, circuit_id="other", revision=1),
                      confidence=replace(self.doc.confidence, score=1),
                      connections=tuple(replace(c, confidence=replace(c.confidence, score=1))
                                        for c in self.doc.connections),
                      validation_state=replace(archival_warning(self.doc).validation_state,
                                               status=ir.WireValidationStatus.REVIEWED))
        self.assertNotEqual(ir.document_digest(doc), ir.document_digest(self.doc))
        self.assertEqual(ir.electrical_digest(doc), ir.electrical_digest(self.doc))

    def test_array_order_changes_snapshot_but_not_electrical_digest(self):
        doc = replace(self.doc, components=tuple(replace(c, pin_ids=tuple(reversed(c.pin_ids)))
                                                 for c in reversed(self.doc.components)),
                      pins=tuple(reversed(self.doc.pins)), nets=tuple(reversed(self.doc.nets)),
                      connections=tuple(reversed(self.doc.connections)))
        self.assertNotEqual(ir.document_digest(doc), ir.document_digest(self.doc))
        self.assertEqual(ir.electrical_digest(doc), ir.electrical_digest(self.doc))
        self.refused("DOCUMENT_DIGEST_MISMATCH", lambda: self.verify(doc, self.make()))

    def test_label_identity_is_ascii_only(self):
        def labeled(text):
            return replace(self.doc, labels=(replace(self.doc.labels[0], text=text),))
        self.assertEqual(ir.electrical_digest(labeled("  VIN  ")), ir.electrical_digest(self.doc))
        self.assertNotEqual(ir.electrical_digest(labeled("Ä")), ir.electrical_digest(labeled("ä")))
        self.assertNotEqual(ir.document_digest(labeled("VIN")), ir.document_digest(self.doc))

    def test_electrical_includes_all_source_settings(self):
        v = self.doc.components[0]
        q = lambda n, unit: ir.Quantity(n, n, unit, ir.ValueGrammar.SI)
        sources = (
            replace(v.source, dc=q("2", "V")),
            replace(v.source, ac=ir.ACConfiguration(q("0", "V"), q("0", "deg"))),
            replace(v.source, ac=ir.ACConfiguration(q("2", "V"), q("90", "deg"))),
            replace(v.source, waveform=ir.Waveform(ir.WaveformKind.SINE,
                    (("offset", q("1", "V")), ("amplitude", q("0.1", "V")),
                     ("frequency", q("1000", "Hz"))))),
        )
        digests = [ir.electrical_digest(replace(self.doc, components=(replace(v, source=s),
                                            self.doc.components[1]))) for s in sources]
        self.assertEqual(len(set(digests + [ir.electrical_digest(self.doc)])), 5)

    def test_electrical_preserves_null_quantities(self):
        r = self.doc.components[1]
        absent = replace(self.doc, components=(self.doc.components[0], replace(r, value=None)))
        unresolved = replace(self.doc, components=(self.doc.components[0], replace(
            r, value=ir.Quantity(None, None, "ohm", ir.ValueGrammar.UNRESOLVED))))
        self.assertNotEqual(ir.electrical_digest(absent), ir.electrical_digest(unresolved))

    def test_electrical_nonfinite_si_rejects(self):
        r = self.doc.components[1]
        doc = replace(self.doc, components=(self.doc.components[0], replace(
            r, value=ir.Quantity("NaN", "NaN", "ohm", ir.ValueGrammar.SI))))
        # NaN is already rejected by the existing M1 schema/graph prerequisite.
        self.refused("DOCUMENT_STRUCTURE_INVALID", lambda: ir.electrical_digest(doc))

    def test_electrical_out_of_range_si_rejects_after_shape_gate(self):
        r = self.doc.components[1]
        doc = replace(self.doc, components=(self.doc.components[0], replace(
            r, value=ir.Quantity("1e301", "1e301", "ohm", ir.ValueGrammar.SI))))
        self.refused("ELECTRICAL_VALUE_INVALID", lambda: ir.electrical_digest(doc))

    def test_electrical_does_not_hash_partial_graph(self):
        doc = replace(self.doc, connections=(replace(self.doc.connections[0], net_id="missing"),
                                             *self.doc.connections[1:]))
        self.refused("DOCUMENT_STRUCTURE_INVALID", lambda: ir.electrical_digest(doc))
        self.refused("DOCUMENT_NOT_VALID", lambda: self.make(doc))

    def test_hand_authored_validation_vector(self):
        expected = {
            "digest_profile": "m2-validation-digest-v1", "profile": "m1-local-v1",
            "ruleset_version": "m1-local-v1", "document_revision": 0, "technical_state": "VALID",
            "completed_stages": list(STAGES), "skipped_stages": [],
            "deferred_checks": list(DEFERRED), "issues": [],
        }
        self.assertEqual(ir.validation_digest(self.report), native_hash(expected))

    def test_report_digest_covers_each_stored_nonprose_field(self):
        changes = {
            "profile": "other", "ruleset_version": "m1-local-v2", "document_revision": 1,
            "technical_state": ir.TechnicalState.UNVALIDATED,
            "completed_stages": tuple(reversed(self.report.completed_stages)),
            "skipped_stages": (("schema", "not_done"),),
            "deferred_checks": tuple(reversed(self.report.deferred_checks)),
        }
        original = ir.validation_digest(self.report)
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertNotEqual(ir.validation_digest(replace(self.report, **{field: value})), original)

    def test_report_issues_hash_stable_fields_not_prose(self):
        issue = ir.ValidationIssue("warning_1", ir.IssueSeverity.WARNING, "LABEL_ALIAS", "Review alias.",
                                   ("label_in",), "label", "label_in", "text", "Review.", ())
        report = replace(self.report, issues=(issue,))
        expected = {
            "digest_profile": "m2-validation-digest-v1", "profile": "m1-local-v1",
            "ruleset_version": "m1-local-v1", "document_revision": 0, "technical_state": "VALID",
            "completed_stages": list(STAGES), "skipped_stages": [], "deferred_checks": list(DEFERRED),
            "issues": [{"issue_id": "warning_1", "severity": "WARNING", "code": "LABEL_ALIAS",
                        "target_refs": ["label_in"], "entity_type": "label", "entity_id": "label_in",
                        "field": "text", "provenance": []}],
        }
        self.assertEqual(ir.validation_digest(report), native_hash(expected))
        self.assertEqual(ir.validation_digest(replace(report, issues=(replace(
            issue, message="다른 설명", suggested_action=None),))), ir.validation_digest(report))
        for field, value in {
            "issue_id": "warning_2", "severity": ir.IssueSeverity.CONFIRMED, "code": "CHECK_DEFERRED",
            "target_refs": ("R1",), "entity_type": None, "entity_id": None, "field": None,
            "provenance": ("visual_1",),
        }.items():
            with self.subTest(field=field):
                altered = replace(report, issues=(replace(issue, **{field: value}),))
                self.assertNotEqual(ir.validation_digest(altered), ir.validation_digest(report))

    def test_issue_order_preserved_and_skip_pairs_sorted(self):
        issue = ir.ValidationIssue("i1", ir.IssueSeverity.WARNING, "LABEL_ALIAS", "Alias.",
                                   (), None, None, None, None, ())
        report = replace(self.report, issues=(issue, replace(issue, issue_id="i2")),
                         skipped_stages=(("z", "reason"), ("a", "reason")))
        self.assertNotEqual(ir.validation_digest(report), ir.validation_digest(replace(report, issues=tuple(reversed(report.issues)))))
        self.assertEqual(ir.validation_digest(report), ir.validation_digest(replace(report, skipped_stages=tuple(reversed(report.skipped_stages)))))

    def test_creation_and_verification_bind_fresh_complete_report(self):
        envelope = self.make()
        self.assertIsNone(self.verify(self.doc, envelope))
        self.assertEqual(envelope.document_id, self.doc.metadata.circuit_id)
        self.assertEqual(envelope.document_revision, 0)
        self.assertEqual(envelope.document_sha256, ir.document_digest(self.doc))
        self.assertEqual(envelope.electrical_sha256, ir.electrical_digest(self.doc))
        self.assertEqual(envelope.validation_sha256, ir.validation_digest(self.report))
        self.assertEqual(envelope.scope, ir.ApprovalScope.CIRCUIT_EXPORT)
        self.assertTrue(envelope.approved)
        self.assertIsNone(envelope.parent_approval_sha256)
        self.assertEqual(envelope, self.make())

    def test_explicit_decision_required(self):
        self.refused("APPROVAL_NOT_GRANTED", lambda: self.make(approved=False))
        for value in (1, "true", None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.make(approved=value)
        with self.assertRaises(TypeError):
            ir.make_circuit_approval(self.doc, acknowledged_warning_ids=(), **EMPTY_CONTEXT)

    def test_invalid_document_refused(self):
        self.refused("DOCUMENT_NOT_VALID", lambda: self.make(replace(self.doc, labels=(
            replace(self.doc.labels[0], net_id=None),))))

    def test_ambiguous_document_refused(self):
        connection = replace(self.doc.connections[0],
                             confidence=ir.Confidence(0.1, ir.ConfidenceBasis.PROVIDER_SCORE, False))
        doc = replace(self.doc, connections=(connection, *self.doc.connections[1:]))
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.AMBIGUOUS)
        self.refused("DOCUMENT_NOT_VALID", lambda: self.make(doc))

    def test_nonvalid_report_states_refused_by_both_gates(self):
        envelope = self.make()
        for state in (ir.TechnicalState.INVALID, ir.TechnicalState.AMBIGUOUS, ir.TechnicalState.UNVALIDATED):
            with self.subTest(state=state), patch("circuit_ir.approval.validate_document",
                                                return_value=replace(self.report, technical_state=state)):
                self.refused("DOCUMENT_NOT_VALID", lambda: self.make())
                self.refused("DOCUMENT_NOT_VALID", lambda: self.verify(self.doc, envelope))

    def test_inconsistent_valid_report_with_blocking_issue_refused(self):
        issue = ir.ValidationIssue("i1", ir.IssueSeverity.ERROR, "VALUE_INVALID", "Invalid value.",
                                   (), None, None, None, None, ())
        for severity in (ir.IssueSeverity.ERROR, ir.IssueSeverity.AMBIGUOUS):
            with self.subTest(severity=severity), patch("circuit_ir.approval.validate_document",
                    return_value=replace(self.report, issues=(replace(issue, severity=severity),))):
                self.refused("DOCUMENT_NOT_VALID", lambda: self.make())

    def test_stale_result_revision_refused(self):
        with patch("circuit_ir.approval.validate_document", return_value=replace(self.report, document_revision=1)):
            self.refused("VALIDATION_REVISION_MISMATCH", lambda: self.make())

    def test_every_required_stage_must_be_complete_not_skipped_or_deferred(self):
        envelope = self.make()
        for stage in STAGES[:-1]:
            for changes in (
                {"completed_stages": tuple(s for s in STAGES if s != stage)},
                {"skipped_stages": ((stage, "not_done"),)}, {"deferred_checks": (*DEFERRED, stage)},
            ):
                with self.subTest(stage=stage, changes=changes), patch("circuit_ir.approval.validate_document",
                        return_value=replace(self.report, **changes)):
                    self.refused("VALIDATION_INCOMPLETE", lambda: self.make())
                    self.refused("VALIDATION_INCOMPLETE", lambda: self.verify(self.doc, envelope))

    def test_unsupported_validation_identity_refused(self):
        envelope = self.make()
        for field, code in (("profile", "VALIDATION_PROFILE_UNSUPPORTED"),
                            ("ruleset_version", "VALIDATION_RULESET_UNSUPPORTED")):
            with self.subTest(field=field), patch("circuit_ir.approval.validate_document",
                    return_value=replace(self.report, **{field: "future-v2"})):
                self.refused(code, lambda: self.make())
                self.refused(code, lambda: self.verify(self.doc, envelope))

    def test_current_warning_ids_must_be_acknowledged_exactly(self):
        report = ir.validate_document(self.mos)
        ids = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
        self.assertTrue(ids)
        self.refused("WARNING_ACKNOWLEDGEMENT_MISMATCH", lambda: self.make(self.mos))
        envelope = self.make(self.mos, acknowledged_warning_ids=ids)
        self.assertEqual(envelope.acknowledged_warning_ids, ids)
        self.assertIsNone(self.verify(self.mos, envelope))
        self.refused("WARNING_ACKNOWLEDGEMENT_MISMATCH", lambda: self.make(
            self.mos, acknowledged_warning_ids=tuple(sorted((*ids, "extra_warning")))))
        self.refused("WARNING_ACKNOWLEDGEMENT_MISMATCH", lambda: self.verify(
            self.mos, replace(envelope, acknowledged_warning_ids=())))

    def test_archival_review_and_warnings_are_not_authority(self):
        doc = replace(archival_warning(self.doc), validation_state=replace(
            archival_warning(self.doc).validation_state, status=ir.WireValidationStatus.REVIEWED,
            validated_revision=0, ruleset_version="m1-local-v1"))
        self.refused("APPROVAL_NOT_GRANTED", lambda: self.make(doc, approved=False))
        self.refused("WARNING_ACKNOWLEDGEMENT_MISMATCH", lambda: self.make(
            doc, acknowledged_warning_ids=("archival_warning",)))
        self.assertEqual(self.make(doc).acknowledged_warning_ids, ())

    def test_same_revision_value_edit_invalidates_approval(self):
        r = self.doc.components[1]
        edited = replace(self.doc, components=(self.doc.components[0], replace(
            r, value=ir.Quantity("2000", "2000", "ohm", ir.ValueGrammar.SI))))
        self.assertEqual(ir.validate_document(edited), self.report)
        self.refused("DOCUMENT_DIGEST_MISMATCH", lambda: self.verify(edited, self.make()))

    def test_same_revision_connection_edit_invalidates_approval(self):
        # Swap both resistor terminals: still valid and electrically measurable,
        # but an exact connection edit cannot retain the reviewed authority.
        connections = tuple(replace(c, net_id="n0" if c.net_id == "vin" else "vin")
                            if c.pin_id.startswith("R1.") else c for c in self.doc.connections)
        doc = replace(self.doc, connections=connections)
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.VALID)
        self.refused("DOCUMENT_DIGEST_MISMATCH", lambda: self.verify(doc, self.make()))

    def test_revision_change_rejects_even_same_electrical_content(self):
        doc = replace(self.doc, metadata=replace(self.doc.metadata, revision=1))
        self.assertEqual(ir.electrical_digest(doc), ir.electrical_digest(self.doc))
        self.refused("DOCUMENT_REVISION_MISMATCH", lambda: self.verify(doc, self.make()))

    def test_identity_change_rejects(self):
        doc = replace(self.doc, metadata=replace(self.doc.metadata, circuit_id="different"))
        self.refused("DOCUMENT_ID_MISMATCH", lambda: self.verify(doc, self.make()))

    def test_provenance_and_imported_snapshot_edits_reject(self):
        for doc in (
            replace(self.doc, confidence=replace(self.doc.confidence, score=1)),
            archival_warning(self.doc),
            replace(self.doc, validation_state=replace(self.doc.validation_state, status=ir.WireValidationStatus.REVIEWED)),
            replace(self.doc, source_image_reference=ir.SourceImageReference("asset", "a" * 64, 10, 20)),
        ):
            with self.subTest(doc=doc):
                self.assertEqual(ir.electrical_digest(doc), ir.electrical_digest(self.doc))
                self.refused("DOCUMENT_DIGEST_MISMATCH", lambda: self.verify(doc, self.make()))

    def test_changed_fresh_report_rejects_without_document_edit(self):
        envelope = self.make()
        report = replace(self.report, deferred_checks=(*self.report.deferred_checks, "future_check"))
        with patch("circuit_ir.approval.validate_document", return_value=report):
            self.refused("VALIDATION_DIGEST_MISMATCH", lambda: self.verify(self.doc, envelope))
        issue = ir.ValidationIssue("confirmation", ir.IssueSeverity.CONFIRMED, "OBSERVATION_CONFIRMED",
                                   "Confirmed.", (), None, None, None, None, ())
        with patch("circuit_ir.approval.validate_document", return_value=replace(self.report, issues=(issue,))):
            self.refused("VALIDATION_DIGEST_MISMATCH", lambda: self.verify(self.doc, envelope))

    def test_prose_translation_does_not_invalidate_report_binding(self):
        report = ir.validate_document(self.mos)
        ids = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
        envelope = self.make(self.mos, acknowledged_warning_ids=ids)
        translated = replace(report, issues=tuple(replace(i, message="설명", suggested_action=None)
                                                  for i in report.issues))
        with patch("circuit_ir.approval.validate_document", return_value=translated):
            self.assertIsNone(self.verify(self.mos, envelope))

    def test_changed_report_bindings_in_envelope_refused(self):
        envelope = self.make()
        for field, value, code in (
            ("electrical_sha256", "a" * 64, "ELECTRICAL_DIGEST_MISMATCH"),
            ("validation_profile", "future", "VALIDATION_PROFILE_MISMATCH"),
            ("validation_ruleset", "future", "VALIDATION_RULESET_MISMATCH"),
            ("validation_sha256", "a" * 64, "VALIDATION_DIGEST_MISMATCH"),
        ):
            with self.subTest(field=field):
                self.refused(code, lambda: self.verify(self.doc, replace(envelope, **{field: value})), field)

    def test_wrong_scope_refused(self):
        circuit = self.make()
        representation = replace(circuit, scope=ir.ApprovalScope.REPRESENTATION,
                                 parent_approval_sha256=ir.approval_digest(circuit),
                                 base_netlist_sha256="a" * 64, mapping_sha256="b" * 64)
        self.refused("APPROVAL_SCOPE_INVALID", lambda: self.verify(self.doc, representation))

    def test_unsupported_contract_and_unapproved_envelope_refused(self):
        envelope = self.make()
        for version in ("m2-approval-v0", "m2-approval-v2", "unknown"):
            with self.subTest(version=version):
                self.refused("APPROVAL_VERSION_UNSUPPORTED", lambda: self.verify(
                    self.doc, replace(envelope, contract_version=version)))
        self.refused("APPROVAL_NOT_GRANTED", lambda: self.verify(self.doc, replace(envelope, approved=False)))

    def test_context_is_exact_empty_structured_registry_only(self):
        self.assertEqual(self.make().model_registry_sha256, EMPTY_CONTEXT["model_registry_sha256"])
        for changes in ({"model_registry_version": "m2-demo-models-v1"},
                        {"model_registry_sha256": "a" * 64}):
            with self.subTest(changes=changes):
                self.refused("MODEL_CONTEXT_UNSUPPORTED", lambda: self.make(**changes))
                self.refused("MODEL_CONTEXT_UNSUPPORTED", lambda: self.verify(self.doc, self.make(), **changes))
                self.refused("MODEL_CONTEXT_MISMATCH", lambda: self.verify(self.doc, replace(self.make(), **changes)))

    def test_exporter_contract_change_refused(self):
        self.refused("EXPORTER_CONTRACT_UNSUPPORTED", lambda: self.make(exporter_contract="m2-spice-v2"))
        self.refused("EXPORTER_CONTRACT_UNSUPPORTED", lambda: self.verify(
            self.doc, self.make(), exporter_contract="m2-spice-v2"))
        self.refused("EXPORTER_CONTRACT_MISMATCH", lambda: self.verify(
            self.doc, replace(self.make(), exporter_contract="m2-spice-v2")))

    def test_shape_checks_and_scope_null_fields(self):
        envelope = self.make()
        for changes, error in (
            ({"scope": "CIRCUIT_EXPORT"}, TypeError), ({"approved": 1}, TypeError),
            ({"document_revision": True}, TypeError), ({"document_revision": -1}, ValueError),
            ({"acknowledged_warning_ids": []}, TypeError),
            ({"acknowledged_warning_ids": ("w2", "w1")}, ValueError),
            ({"acknowledged_warning_ids": ("w1", "w1")}, ValueError),
            ({"document_sha256": "A" * 64}, ValueError),
            ({"model_registry_version": "models/library"}, ValueError),
            ({"document_id": "bad\n.include"}, ValueError),
            ({"parent_approval_sha256": "a" * 64}, ValueError),
            ({"base_netlist_sha256": "a" * 64}, ValueError),
            ({"mapping_sha256": "a" * 64}, ValueError),
            ({"scope": ir.ApprovalScope.REPRESENTATION}, TypeError),
        ):
            with self.subTest(changes=changes), self.assertRaises(error):
                replace(envelope, **changes)

    def test_hand_authored_envelope_vector(self):
        # Independent fixed fields; hash function need not verify this snapshot.
        kwargs = dict(contract_version="m2-approval-v1", scope=ir.ApprovalScope.CIRCUIT_EXPORT,
                      approved=True, document_id="demo", document_revision=7,
                      document_sha256="a" * 64, electrical_sha256="b" * 64,
                      validation_profile="m1-local-v1", validation_ruleset="m1-local-v1",
                      validation_sha256="c" * 64, exporter_contract="m2-spice-v1",
                      model_registry_version="m2-no-models-v1", model_registry_sha256="d" * 64,
                      acknowledged_warning_ids=("warning_1",), parent_approval_sha256=None,
                      base_netlist_sha256=None, mapping_sha256=None)
        expected = dict(kwargs, scope="CIRCUIT_EXPORT", acknowledged_warning_ids=["warning_1"])
        self.assertEqual(ir.approval_digest(ir.ApprovalEnvelope(**kwargs)), native_hash(expected))

    def test_approval_digest_covers_all_fields(self):
        envelope = self.make()
        for field, value in {
            "contract_version": "m2-approval-v2", "approved": False, "document_id": "other",
            "document_revision": 1, "document_sha256": "a" * 64, "electrical_sha256": "b" * 64,
            "validation_profile": "future", "validation_ruleset": "future",
            "validation_sha256": "c" * 64, "exporter_contract": "m2-spice-v2",
            "model_registry_version": "future", "model_registry_sha256": "d" * 64,
            "acknowledged_warning_ids": ("w1",),
        }.items():
            with self.subTest(field=field):
                self.assertNotEqual(ir.approval_digest(replace(envelope, **{field: value})), ir.approval_digest(envelope))
        artifact = replace(envelope, scope=ir.ApprovalScope.REPRESENTATION,
                           parent_approval_sha256="a" * 64, base_netlist_sha256="b" * 64,
                           mapping_sha256="c" * 64)
        self.assertNotEqual(ir.approval_digest(artifact), ir.approval_digest(envelope))
        for field in ("parent_approval_sha256", "base_netlist_sha256", "mapping_sha256"):
            with self.subTest(field=field):
                self.assertNotEqual(ir.approval_digest(replace(artifact, **{field: "d" * 64})), ir.approval_digest(artifact))

    def test_envelope_is_frozen_hashable_and_does_not_mutate_inputs(self):
        before = ir.dump_document(self.doc)
        fixture = FIXTURES / "simple_source_resistor" / "circuit.json"
        bytes_before = fixture.read_bytes()
        envelope = self.make()
        with self.assertRaises(FrozenInstanceError):
            envelope.approved = False
        self.assertFalse(hasattr(envelope, "__dict__"))
        self.assertEqual(len({envelope, self.make()}), 1)
        original = ir.approval_digest(envelope)
        self.verify(self.doc, envelope)
        self.assertEqual(ir.approval_digest(envelope), original)
        self.assertEqual(ir.dump_document(self.doc), before)
        self.assertEqual(fixture.read_bytes(), bytes_before)

    def test_purity_after_existing_schema_lazy_load(self):
        # Warm the established M1 bundled-schema cache, then disallow user I/O.
        self.make()
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
                patch("pathlib.Path.read_text", side_effect=AssertionError("file I/O")), \
                patch("pathlib.Path.write_text", side_effect=AssertionError("file I/O")), \
                patch("subprocess.Popen", side_effect=AssertionError("process I/O")), \
                patch("socket.socket", side_effect=AssertionError("network I/O")):
            envelope = self.make()
            self.verify(self.doc, envelope)
            self.assertEqual(envelope, self.make())

    def test_wrong_api_types_are_programming_errors(self):
        for call in (
            lambda: ir.document_digest({}), lambda: ir.electrical_digest({}),
            lambda: ir.validation_digest({}), lambda: ir.approval_digest({}),
            lambda: self.make({}), lambda: self.verify({}, self.make()),
            lambda: self.verify(self.doc, {}),
        ):
            with self.subTest(call=call), self.assertRaises(TypeError):
                call()

    def test_failed_verification_is_deterministic_without_refresh(self):
        envelope = self.make()
        stale = replace(envelope, document_id="other", document_revision=5, validation_sha256="a" * 64)
        first = self.refused("DOCUMENT_ID_MISMATCH", lambda: self.verify(self.doc, stale))
        second = self.refused("DOCUMENT_ID_MISMATCH", lambda: self.verify(self.doc, stale))
        self.assertEqual((first.code, first.field, str(first)), (second.code, second.field, str(second)))
        self.assertEqual(stale.document_id, "other")
        self.assertEqual(stale.document_revision, 5)

    def test_public_surface_has_no_export_or_execution_authority(self):
        envelope = self.make()
        for name in ("is_exportable", "can_execute", "spice_text", "timestamp", "reviewer"):
            self.assertFalse(hasattr(envelope, name))
        for name in ("_digest", "_context", "make_representation_approval", "export_document", "ExecutionApproval"):
            self.assertNotIn(name, ir.__all__)
            self.assertFalse(hasattr(ir, name))

    def test_digests_stable_across_hash_seeds(self):
        script = '''
import json
from pathlib import Path
import circuit_ir as ir
d = ir.load_document(Path("tests/fixtures/circuit_ir/valid/simple_source_resistor/circuit.json").read_text(encoding="utf-8")).document
context = dict(exporter_contract="m2-spice-v1", model_registry_version="m2-no-models-v1", model_registry_sha256="CONTEXT_HASH")
a = ir.make_circuit_approval(d, approved=True, acknowledged_warning_ids=(), **context)
ir.verify_circuit_approval(d, a, **context)
print(json.dumps([ir.document_digest(d), ir.electrical_digest(d), ir.validation_digest(ir.validate_document(d)), ir.approval_digest(a)]))
'''.replace("CONTEXT_HASH", EMPTY_CONTEXT["model_registry_sha256"])
        expected = json.dumps([ir.document_digest(self.doc), ir.electrical_digest(self.doc),
                               ir.validation_digest(self.report), ir.approval_digest(self.make())])
        for seed in ("1", "42", "random"):
            with self.subTest(seed=seed):
                result = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=ROOT,
                                        env=dict(os.environ, PYTHONHASHSEED=seed),
                                        capture_output=True, text=True, check=True, timeout=30)
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
