"""M2C exact-byte authored goldens and fail-closed preview boundaries.

No LTspice/network/external model library/API is used. Test approvals are explicit trusted
test decisions, not human usability evidence. Tests never write/update goldens.
"""
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir
from circuit_ir import exporter


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/spice_export"
M1_FIXTURES = ROOT / "tests/fixtures/circuit_ir"
CONTEXT = ("m2-no-models-v1", hashlib.sha256(
    b'{"profiles":[],"registry_version":"m2-no-models-v1"}').hexdigest())
CASES = ("resistor_divider", "rc_low_pass", "current_source_load", "rlc_network",
         "sine_voltage", "pulse_voltage", "sine_current", "pulse_current")
MOS_CASES = ("nmos_common_source", "pmos_resistive_load", "nmos_shared_model", "mixed_mos_profiles")


def load(path):
    result = ir.load_document(path.read_text(encoding="utf-8"))
    if result.document is None:
        raise AssertionError(result.issues)
    return result.document


def fixture(name="resistor_divider"):
    return load(FIXTURES / name / "circuit.json")


def approve(doc, context=CONTEXT):
    report = ir.validate_document(doc)
    ids = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
    return ir.make_circuit_approval(doc, approved=True, acknowledged_warning_ids=ids,
                                    exporter_contract="m2-spice-v1",
                                    model_registry_version=context[0], model_registry_sha256=context[1])


def q(text, unit="V", literal=None, grammar=ir.ValueGrammar.SI):
    return ir.Quantity(text if literal is None else literal, text, unit, grammar)


def change_source(doc, **changes):
    component = next(c for c in doc.components if c.source is not None)
    modified = replace(component, source=replace(component.source, **changes))
    return replace(doc, components=tuple(modified if c.id == modified.id else c for c in doc.components))


class ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = fixture()
        cls.approval = approve(cls.doc)
        cls.report = ir.validate_document(cls.doc)

    def run_export(self, doc=None, approval=None):
        doc = self.doc if doc is None else doc
        return ir.export_document(doc, approve(doc) if approval is None else approval, model_context=CONTEXT)

    def blocked(self, result, codes):
        self.assertEqual(result.status, ir.ExportStatus.BLOCKED)
        self.assertIsNone(result.spice_text)
        self.assertIsNone(result.provenance)
        self.assertEqual((result.element_map, result.net_map, result.model_map), ((), (), ()))
        self.assertEqual({i.code for i in result.issues if i.blocking}, set(codes))
        self.assertTrue(all(isinstance(i, ir.ExportIssue) for i in result.issues))

    def test_eight_independent_complete_goldens(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in FIXTURES.rglob("*") if p.is_file()}
        self.assertEqual({p.name for p in FIXTURES.iterdir() if p.is_dir()}, set(CASES) | set(MOS_CASES))
        for name in CASES:
            with self.subTest(name=name):
                folder = FIXTURES / name
                doc = fixture(name)
                expected = json.loads((folder / "expected-export.json").read_text(encoding="utf-8"))
                result = self.run_export(doc)
                self.assertEqual(result.status.value, expected["status"])
                self.assertEqual(result.spice_text.encode("utf-8"), (folder / "expected.cir").read_bytes())
                self.assertEqual(result.issues, ())
                for key, pairs in (("element_map", result.element_map), ("net_map", result.net_map), ("model_map", result.model_map)):
                    self.assertEqual([list(pair) for pair in pairs], expected[key])
                for key in ("document_sha256", "electrical_sha256", "base_netlist_sha256", "mapping_sha256"):
                    self.assertEqual(getattr(result.provenance, key), expected[key])
                # Header/hash expectations are independently checkable projections.
                raw = json.loads((folder / "circuit.json").read_text(encoding="utf-8"))
                archival = json.dumps(raw, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
                self.assertEqual(hashlib.sha256(archival.encode("utf-8")).hexdigest(), expected["document_sha256"])
                vector = json.dumps(expected["electrical_projection"], sort_keys=True, ensure_ascii=True,
                                    allow_nan=False, separators=(",", ":")).encode("utf-8")
                self.assertEqual(hashlib.sha256(vector).hexdigest(), expected["electrical_sha256"])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_repeated_export_same_bytes_and_provenance(self):
        first = self.run_export(approval=self.approval)
        self.assertEqual(first, self.run_export(approval=self.approval))
        self.assertEqual(hashlib.sha256(first.spice_text.encode("utf-8")).hexdigest(), first.provenance.base_netlist_sha256)

    def test_preflight_is_diagnostic_only(self):
        with patch("circuit_ir.exporter._mappings", side_effect=AssertionError("artifact allocation")), \
                patch("circuit_ir.exporter.verify_circuit_approval", side_effect=AssertionError("approval workflow")):
            self.assertEqual(ir.check_export_eligibility(self.doc, model_context=CONTEXT), ())

    def test_provenance_binds_existing_m2b_contract(self):
        result = self.run_export(approval=self.approval)
        p = result.provenance
        self.assertEqual(p.document_id, self.doc.metadata.circuit_id)
        self.assertEqual(p.document_revision, self.doc.metadata.revision)
        self.assertEqual(p.document_sha256, ir.document_digest(self.doc))
        self.assertEqual(p.electrical_sha256, ir.electrical_digest(self.doc))
        self.assertEqual(p.validation_sha256, ir.validation_digest(self.report))
        self.assertEqual(p.circuit_approval_sha256, ir.approval_digest(self.approval))
        self.assertEqual((p.validation_profile, p.validation_ruleset), ("m1-local-v1", "m1-local-v1"))
        self.assertEqual(p.exporter_contract, "m2-spice-v1")
        self.assertEqual((p.model_registry_version, p.model_registry_sha256), CONTEXT)

    def test_mapping_digest_explicit_complete_projection(self):
        result = self.run_export()
        expected = {"mapping_profile": "m2-mapping-v1", "element_map": [
            ["R1", "R_0001"], ["R2", "R_0002"], ["V1", "V_0001"]],
            "net_map": [["n0", "0"], ["vin", "n_0001"], ["vout", "n_0002"]], "model_map": []}
        encoded = json.dumps(expected, sort_keys=True, ensure_ascii=True, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
        self.assertEqual(result.provenance.mapping_sha256, hashlib.sha256(encoded).hexdigest())

    def test_ground_is_explicit_not_a_name_or_label_guess(self):
        doc = replace(self.doc, nets=tuple(replace(n, id="earth") if n.id == "n0" else n for n in self.doc.nets),
                      connections=tuple(replace(c, net_id="earth") if c.net_id == "n0" else c for c in self.doc.connections))
        result = self.run_export(doc)
        self.assertEqual(dict(result.net_map)["earth"], "0")
        self.assertNotIn("earth", result.spice_text)

    def test_unused_net_keeps_mapping_without_invented_device(self):
        doc = replace(self.doc, nets=(*self.doc.nets, ir.Net("unused", False)))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        emitted = dict(result.net_map)["unused"]
        self.assertNotIn(emitted, "\n".join(result.spice_text.splitlines()[4:]))
        self.assertEqual(len(result.element_map), len(doc.components))

    def test_punctuation_and_case_distinct_net_names_do_not_collapse(self):
        doc = replace(self.doc, nets=(*self.doc.nets, ir.Net("A.x", False), ir.Net("A-x", False), ir.Net("a_x", False)))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        names = [name.lower() for _, name in result.net_map]
        self.assertEqual(len(names), len(set(names)))
        for _, name in result.net_map:
            self.assertRegex(name, r"^(0|n_[0-9]{4,})$")

    def test_element_prefix_groups_and_ascii_id_line_order(self):
        result = self.run_export(fixture("rlc_network"))
        lines = result.spice_text.splitlines()[4:-1]
        self.assertEqual([line.split()[0] for line in lines], ["C_0001", "L_0001", "R_0001", "V_0001"])
        self.assertIn(" Rser=0", lines[1])

    def test_ordinal_width_grows_above_9999(self):
        # Allocator boundary only, avoiding repeated 10k-record M1 validation.
        mapping = exporter._allocate([f"id_{i:05d}" for i in range(10001)], "n")
        self.assertEqual(mapping[9998][1], "n_9999")
        self.assertEqual(mapping[9999][1], "n_10000")
        self.assertEqual(mapping[10000][1], "n_10001")
        self.assertEqual(len(set(name for _, name in mapping)), 10001)

    def test_pin_and_component_array_order_cannot_swap_roles(self):
        doc = replace(self.doc, components=tuple(replace(c, pin_ids=tuple(reversed(c.pin_ids)))
                                                 for c in reversed(self.doc.components)),
                      pins=tuple(reversed(self.doc.pins)), nets=tuple(reversed(self.doc.nets)),
                      connections=tuple(reversed(self.doc.connections)))
        old = self.run_export(approval=self.approval)
        self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})
        fresh = self.run_export(doc)
        self.assertEqual(fresh.spice_text.splitlines()[4:], old.spice_text.splitlines()[4:])
        self.assertEqual(fresh.element_map, old.element_map)
        self.assertEqual(fresh.net_map, old.net_map)
        self.assertEqual(fresh.provenance.electrical_sha256, old.provenance.electrical_sha256)
        self.assertNotEqual(fresh.provenance.document_sha256, old.provenance.document_sha256)

    def test_waveform_parameter_insertion_order_irrelevant(self):
        doc = fixture("pulse_voltage")
        source = next(c.source for c in doc.components if c.source)
        changed = change_source(doc, waveform=replace(source.waveform, parameters=tuple(reversed(source.waveform.parameters))))
        self.assertEqual(changed, doc)
        self.assertEqual(self.run_export(changed), self.run_export(doc))

    def test_exact_numeric_cutoffs_signs_and_zero(self):
        for text, expected in (
            ("-0.000", "0"), ("+0", "0"), ("0.001", "0.001"), ("0.000999", "9.99e-4"),
            ("1000000", "1000000"), ("9999999", "9999999"), ("10000000", "1e7"),
            ("-0.0000000025", "-2.5e-9"), ("+1.2300e2", "123"), ("1e-300", "1e-300"), ("1e300", "1e300"),
        ):
            with self.subTest(text=text):
                doc = change_source(self.doc, dc=q(text), ac=None)
                result = self.run_export(doc)
                self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
                self.assertIn("V_0001 n_0001 0 DC " + expected + "\n", result.spice_text)

    def test_spice_m_milli_and_meg_are_rendered_as_si(self):
        for literal, si, expected in (("1M", "0.001", "0.001"), ("1m", "0.001", "0.001"),
                                     ("1Meg", "1000000", "1000000"), ("1k", "1000", "1000")):
            with self.subTest(literal=literal):
                doc = change_source(self.doc, dc=q(si, literal=literal, grammar=ir.ValueGrammar.SPICE), ac=None)
                self.assertIn(" DC " + expected + "\n", self.run_export(doc).spice_text)

    def test_precision_independent_exact_coefficients(self):
        value = "1.23456789012345678901234567890123456789"
        doc = change_source(self.doc, dc=q(value), ac=None)
        normal = self.run_export(doc)
        with localcontext() as context:
            context.prec = 2
            reduced = self.run_export(doc)
        self.assertEqual(normal, reduced)
        self.assertIn(" DC " + value + "\n", reduced.spice_text)

    def test_unrepresentable_token_blocks_in_m2_without_changing_m1(self):
        # 128-digit integer is M1-bounded, but M2 scientific form exceeds 128.
        doc = change_source(self.doc, dc=q("1" * 128), ac=None)
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.VALID)
        self.blocked(self.run_export(doc), {"EXPORT_VALUE_INVALID"})

    def test_numeric_injection_and_nonfinite_block_before_render(self):
        for value in ("NaN", "Infinity", "1e301", "{gain}", ".include evil.lib", "0\n.end"):
            with self.subTest(value=value):
                doc = change_source(self.doc, dc=q(value), ac=None)
                self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_source_polarity_comes_from_roles(self):
        doc = fixture("current_source_load")
        changed = replace(doc, connections=tuple(replace(c, net_id="n0" if c.net_id == "vin" else "vin")
                                                if c.pin_id.startswith("I1.") else c for c in doc.connections))
        result = self.run_export(changed)
        self.assertIn("I_0001 0 n_0001 DC -0.001\n", result.spice_text)

    def test_sine_and_pulse_preserve_typed_order_and_ac_attributes(self):
        for name, prefix in (("sine_voltage", "V"), ("sine_current", "I"),
                             ("pulse_voltage", "V"), ("pulse_current", "I")):
            with self.subTest(name=name):
                text = self.run_export(fixture(name)).spice_text
                self.assertIn(prefix + "_0001 n_0001 0 ", text)
                self.assertIn(" AC 2 0\n", text)
                self.assertNotIn(" DC ", text)
        self.assertIn("SINE(0 0.01 1000 0 0 0)", self.run_export(fixture("sine_voltage")).spice_text)
        self.assertIn("PULSE(-1 1 0 1e-6 1e-6 9.98e-4 0.001)", self.run_export(fixture("pulse_voltage")).spice_text)

    def test_sine_dc_offset_and_pulse_level1_mismatch_block(self):
        for name in ("sine_voltage", "pulse_voltage", "sine_current", "pulse_current"):
            with self.subTest(name=name):
                doc = fixture(name)
                unit = "A" if name.endswith("current") else "V"
                doc = change_source(doc, dc=q("3", unit))
                self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.VALID)
                self.blocked(self.run_export(doc), {"EXPORT_UNSUPPORTED_SOURCE"})

    def test_missing_or_extra_waveform_keys_are_not_dropped(self):
        doc = fixture("sine_voltage")
        waveform = next(c.source.waveform for c in doc.components if c.source)
        for params in (waveform.parameters[:-1], (*waveform.parameters, ("file", q("1")))):
            with self.subTest(params=params):
                bad = change_source(doc, waveform=replace(waveform, parameters=params))
                self.blocked(ir.export_document(bad, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_unsupported_raw_waveform_cannot_enter_typed_models(self):
        raw = ir.document_to_dict(self.doc)
        raw["components"][0]["source"]["waveform"]["kind"] = "pwl"
        self.assertIsNone(ir.document_from_dict(raw).document)
        with self.assertRaises(ValueError):
            ir.WaveformKind("pwl")

    def test_none_waveform_rejects_unexpected_parameters(self):
        doc = change_source(self.doc, waveform=ir.Waveform(ir.WaveformKind.NONE, (("offset", q("0")),)))
        self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_source_ac_zero_is_not_omitted(self):
        result = self.run_export(fixture("rc_low_pass"))
        self.assertIn(" AC 0 -45\n", result.spice_text)
        doc = change_source(self.doc, ac=None)
        self.assertNotIn(" AC ", self.run_export(doc).spice_text)

    def test_bad_units_and_literal_si_disagreement_block(self):
        for quantity in (q("1", "A"), q("2", literal="1")):
            with self.subTest(quantity=quantity):
                doc = change_source(self.doc, dc=quantity)
                self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_base_contains_only_end_directive_fixed_header_and_lf(self):
        for name in CASES:
            with self.subTest(name=name):
                text = self.run_export(fixture(name)).spice_text
                self.assertEqual([line for line in text.splitlines() if line.startswith(".")], [".end"])
                self.assertNotIn("\r", text)
                self.assertTrue(text.isascii())
                self.assertTrue(text.endswith(".end\n"))
                self.assertFalse(text.endswith("\n\n"))
                self.assertNotIn("\n\n", text)
                self.assertEqual(text.splitlines()[0], "Circuit Simulation Assistant restricted circuit")

    def test_labels_remain_data_never_comments_or_tokens(self):
        expected_body = self.run_export().spice_text.splitlines()[4:]
        for value in (".include evil.lib", ".tran 1", "0\n.end", "出力", "V(out)"):
            with self.subTest(value=value):
                doc = replace(self.doc, labels=(replace(self.doc.labels[0], text=value),))
                result = ir.export_document(doc, self.approval, model_context=CONTEXT)
                if ir.validate_document(doc).technical_state is ir.TechnicalState.VALID:
                    result = self.run_export(doc)
                    self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
                    # A substring like "0\n.end" can naturally span the final
                    # phase token and terminator. Compare actual lines instead.
                    self.assertEqual(result.spice_text.splitlines()[4:], expected_body)
                    self.assertEqual([l for l in result.spice_text.splitlines() if l.startswith(".")], [".end"])
                else:
                    self.assertIsNone(result.spice_text)

    def test_component_and_net_id_injection_rejected_by_public_models(self):
        for value in (".include evil.lib", "0\n.end", "R1; .tran 1", "{expr}", "bad\x00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    replace(self.doc.components[0], id=value)
                with self.assertRaises(ValueError):
                    ir.Net(value, False)
        raw = ir.document_to_dict(self.doc)
        raw["components"][0]["id"] = ".include evil.lib"
        self.assertIsNone(ir.document_from_dict(raw).document)

    def test_missing_approval_blocks_even_valid_preflight(self):
        self.assertEqual(ir.check_export_eligibility(self.doc, model_context=CONTEXT), ())
        self.blocked(ir.export_document(self.doc, None, model_context=CONTEXT), {"EXPORT_APPROVAL_MISSING"})

    def test_false_decision_and_imported_review_do_not_authorize(self):
        self.blocked(ir.export_document(self.doc, replace(self.approval, approved=False), model_context=CONTEXT),
                     {"EXPORT_APPROVAL_MISSING"})
        doc = replace(self.doc, validation_state=replace(self.doc.validation_state,
                      status=ir.WireValidationStatus.REVIEWED, validated_revision=0, ruleset_version="m1-local-v1"))
        self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_APPROVAL_MISSING"})

    def test_stale_same_revision_document_blocks(self):
        doc = change_source(self.doc, dc=q("2"))
        self.assertEqual(doc.metadata.revision, self.doc.metadata.revision)
        self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_revision_and_provenance_edits_block(self):
        for doc in (replace(self.doc, metadata=replace(self.doc.metadata, revision=1)),
                    replace(self.doc, confidence=replace(self.doc.confidence, score=1))):
            with self.subTest(doc=doc):
                self.blocked(ir.export_document(doc, self.approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_wrong_scope_or_future_approval_version_block(self):
        representation = replace(self.approval, scope=ir.ApprovalScope.REPRESENTATION,
                                 parent_approval_sha256="a" * 64, base_netlist_sha256="b" * 64,
                                 mapping_sha256="c" * 64)
        for approval in (representation, replace(self.approval, contract_version="m2-approval-v2")):
            with self.subTest(approval=approval):
                self.blocked(ir.export_document(self.doc, approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_tampered_report_ruleset_hash_and_registry_bindings_block(self):
        for field, value in (("validation_sha256", "a" * 64), ("validation_ruleset", "future"),
                             ("model_registry_sha256", "b" * 64), ("exporter_contract", "m2-spice-v2")):
            with self.subTest(field=field):
                self.blocked(ir.export_document(self.doc, replace(self.approval, **{field: value}), model_context=CONTEXT),
                             {"EXPORT_APPROVAL_STALE"})

    def test_changed_fresh_report_prevents_old_approval(self):
        issue = ir.ValidationIssue("new_confirmation", ir.IssueSeverity.CONFIRMED, "CONFIRMED_REVIEW",
                                   "Observation.", (), None, None, None, None, ())
        altered = replace(self.report, issues=(issue,))
        with patch("circuit_ir.exporter.validate_document", return_value=altered), \
                patch("circuit_ir.approval.validate_document", return_value=altered):
            self.blocked(ir.export_document(self.doc, self.approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_preflight_report_cannot_diverge_from_verified_approval_report(self):
        issue = ir.ValidationIssue("new_confirmation", ir.IssueSeverity.CONFIRMED, "CONFIRMED_REVIEW",
                                   "Observation.", (), None, None, None, None, ())
        with patch("circuit_ir.exporter.validate_document", return_value=replace(self.report, issues=(issue,))):
            self.blocked(ir.export_document(self.doc, self.approval, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_invalid_ambiguous_unvalidated_and_inconsistent_report_block(self):
        reports = [replace(self.report, technical_state=state) for state in
                   (ir.TechnicalState.INVALID, ir.TechnicalState.AMBIGUOUS, ir.TechnicalState.UNVALIDATED)]
        reports.extend((replace(self.report, document_revision=99),
                        replace(self.report, completed_stages=self.report.completed_stages[1:]),
                        replace(self.report, skipped_stages=(("schema", "not_done"),)),
                        replace(self.report, deferred_checks=(*self.report.deferred_checks, "graph_dc")),
                        replace(self.report, ruleset_version="future")))
        for report in reports:
            with self.subTest(report=report), patch("circuit_ir.exporter.validate_document", return_value=report):
                self.blocked(ir.export_document(self.doc, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_actual_invalid_and_ambiguous_inputs_fail_before_approval(self):
        docs = (replace(self.doc, connections=(replace(self.doc.connections[0], net_id="missing"), *self.doc.connections[1:])),
                replace(self.doc, connections=(replace(self.doc.connections[0], confidence=ir.Confidence(
                    0.9, ir.ConfidenceBasis.PROVIDER_SCORE, False)), *self.doc.connections[1:])))
        for doc in docs:
            with self.subTest(doc=doc):
                self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_missing_required_source_and_passive_values_fail_closed(self):
        docs = (change_source(self.doc, dc=None),
                replace(self.doc, components=tuple(replace(c, value=None) if c.type is ir.ComponentType.RESISTOR else c
                                                  for c in self.doc.components)))
        for doc in docs:
            with self.subTest(doc=doc):
                self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_mos_under_empty_registry_has_no_partial_output(self):
        for name in ("nmos_common_source", "pmos_current_source"):
            with self.subTest(name=name):
                doc = load(M1_FIXTURES / "valid" / name / "circuit.json")
                self.blocked(ir.export_document(doc, approve(doc), model_context=CONTEXT), {"EXPORT_MODEL_UNRESOLVED"})
                issues = ir.check_export_eligibility(doc, model_context=CONTEXT)
                self.assertTrue(any(i.code == "EXPORT_MODEL_UNRESOLVED" for i in issues))

    def test_unknown_component_is_never_omitted(self):
        doc = replace(self.doc, components=(replace(self.doc.components[0], type=ir.ComponentType.UNKNOWN),
                                           *self.doc.components[1:]))
        self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_extra_passive_parameters_do_not_leak(self):
        doc = replace(self.doc, components=tuple(replace(c, parameters=(("ic", q("1")),))
                         if c.type is ir.ComponentType.RESISTOR else c for c in self.doc.components))
        self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_image_origin_or_image_reference_not_admitted(self):
        image = ir.SourceImageReference("asset", "a" * 64, 10, 20)
        for doc in (replace(self.doc, source_image_reference=image),
                    replace(self.doc, metadata=replace(self.doc.metadata, origin=ir.Origin.IMAGE), source_image_reference=image)):
            with self.subTest(doc=doc):
                self.blocked(ir.export_document(doc, None, model_context=CONTEXT), {"EXPORT_UNSUPPORTED_FEATURE"})

    def test_empty_registry_digest_must_match_not_just_version(self):
        for context in ((CONTEXT[0], "a" * 64), ("m2-demo-models-v1", CONTEXT[1])):
            with self.subTest(context=context):
                self.blocked(ir.export_document(self.doc, self.approval, model_context=context), {"EXPORT_MODEL_INCOMPATIBLE"})

    def test_label_alias_requires_exact_warning_acknowledgement(self):
        doc = replace(self.doc, labels=(*self.doc.labels, ir.Label("other_label", "alias", "flat", "vin", None)))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        self.assertEqual([i.code for i in result.issues], ["LABEL_ALIAS"])
        self.assertFalse(result.issues[0].blocking)
        no_ack = replace(approve(doc), acknowledged_warning_ids=())
        self.blocked(ir.export_document(doc, no_ack, model_context=CONTEXT), {"EXPORT_APPROVAL_STALE"})

    def test_resolved_unused_stub_warns_but_unresolved_gap_blocks(self):
        item = ir.Ambiguity("wire_disposition", ir.AmbiguityKind.WIRE_GAP, ("vin",), (),
                            ir.AmbiguityStatus.RESOLVED, None, "Unused stub explicitly confirmed")
        doc = replace(self.doc, ambiguities=(item,))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        self.assertEqual([i.code for i in result.issues], ["DANGLING_WIRE"])
        unresolved = replace(doc, ambiguities=(replace(item, state=ir.AmbiguityStatus.UNRESOLVED, resolution_note=None),))
        self.blocked(ir.export_document(unresolved, None, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_unassociated_dangling_warning_is_not_waivable(self):
        issue = ir.ValidationIssue("gap_warning", ir.IssueSeverity.WARNING, "DANGLING_WIRE", "Gap.",
                                   ("vin",), "net", "vin", None, None, ())
        with patch("circuit_ir.exporter.validate_document", return_value=replace(self.report, issues=(issue,))):
            self.blocked(ir.export_document(self.doc, None, model_context=CONTEXT), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_passive_bypassed_warning_is_not_waivable(self):
        doc = replace(self.doc, connections=tuple(replace(c, net_id="vout") if c.pin_id == "R2.p2" else c
                                                 for c in self.doc.connections))
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.VALID)
        self.blocked(ir.export_document(doc, approve(doc), model_context=CONTEXT), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_unavailable_graph_fails_closed_at_public_gate_seam(self):
        with patch("circuit_ir.exporter.build_graph", return_value=ir.GraphBuildResult(None, ())):
            self.blocked(ir.export_document(self.doc, self.approval, model_context=CONTEXT), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_redundant_source_warning_is_not_waivable(self):
        doc = load(M1_FIXTURES / "valid/equal_parallel_dc_sources/circuit.json")
        self.blocked(ir.export_document(doc, approve(doc), model_context=CONTEXT), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_unknown_warning_and_deferral_fail_closed(self):
        issue = ir.ValidationIssue("future_warning", ir.IssueSeverity.WARNING, "NEW_WARNING", "Unreviewed warning.",
                                   ("R1",), "component", "R1", None, None, ())
        for report in (replace(self.report, issues=(issue,)),
                       replace(self.report, deferred_checks=(*self.report.deferred_checks, "new_required_proof")),
                       replace(self.report, deferred_checks=(*self.report.deferred_checks, "dynamic_source_constraint_proof"))):
            with self.subTest(report=report), patch("circuit_ir.exporter.validate_document", return_value=report):
                self.blocked(ir.export_document(self.doc, None, model_context=CONTEXT), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_multiple_independent_m2_failures_are_sorted_deduplicated(self):
        doc = change_source(fixture("sine_voltage"), dc=q("1"))
        # Add a second independent source with a distinct net pair, avoiding M1
        # ideal-source loops. Both mismatches are valid M1 but unsupported M2.
        src = doc.components[0]
        other = replace(src, id="A_source", pin_ids=("A_source.p1", "A_source.p2"))
        doc = replace(doc, components=(*doc.components, other), nets=(*doc.nets, ir.Net("aux", False)),
                      pins=(*doc.pins, ir.Pin("A_source.p1", "A_source", ir.PinRole.POSITIVE, None),
                            ir.Pin("A_source.p2", "A_source", ir.PinRole.NEGATIVE, None)),
                      connections=(*doc.connections, ir.Connection("A_source.p1", "aux", (), doc.confidence),
                                   ir.Connection("A_source.p2", "n0", (), doc.confidence)))
        result = ir.export_document(doc, None, model_context=CONTEXT)
        self.blocked(result, {"EXPORT_UNSUPPORTED_SOURCE"})
        self.assertEqual([i.target_refs for i in result.issues], [("A_source",), ("V1",)])
        self.assertEqual(result, ir.export_document(doc, None, model_context=CONTEXT))

    def test_approval_failure_never_reaches_artifact_allocation(self):
        with patch("circuit_ir.exporter._mappings", side_effect=AssertionError("render after refusal")):
            self.blocked(ir.export_document(self.doc, None, model_context=CONTEXT), {"EXPORT_APPROVAL_MISSING"})
            self.blocked(ir.export_document(self.doc, replace(self.approval, document_sha256="a" * 64), model_context=CONTEXT),
                         {"EXPORT_APPROVAL_STALE"})

    def test_records_are_immutable_and_blocked_shape_is_enforced(self):
        result = self.run_export()
        for record, field, value in ((result, "spice_text", "tampered"), (result.provenance, "document_revision", 99),
                                     (ir.ExportIssue("EXPORT_APPROVAL_MISSING", ir.IssueSeverity.ERROR, (), None, "Missing."), "code", "OTHER")):
            with self.subTest(record=record), self.assertRaises(FrozenInstanceError):
                setattr(record, field, value)
            self.assertFalse(hasattr(record, "__dict__"))
        with self.assertRaises(ValueError):
            replace(result, status=ir.ExportStatus.BLOCKED)
        with self.assertRaises(ValueError):
            ir.ExportResult(ir.ExportStatus.BLOCKED, None, (), None, (), (), ())
        for severity in (ir.IssueSeverity.AMBIGUOUS, ir.IssueSeverity.CONFIRMED):
            with self.assertRaises(ValueError):
                ir.ExportIssue("EXPORT_APPROVAL_MISSING", severity, (), None, "Missing.")

    def test_wrong_python_types_raise_not_blocked_results(self):
        for call in (lambda: ir.export_document({}, self.approval, model_context=CONTEXT),
                     lambda: ir.export_document(self.doc, {}, model_context=CONTEXT),
                     lambda: ir.check_export_eligibility({}, model_context=CONTEXT),
                     lambda: ir.export_document(self.doc, self.approval, model_context=list(CONTEXT)),
                     lambda: ir.check_export_eligibility(self.doc, model_context=(None, None))):
            with self.subTest(call=call), self.assertRaises(TypeError):
                call()

    def test_input_and_source_files_unchanged_after_success_and_failure(self):
        path = FIXTURES / "resistor_divider/circuit.json"
        before, typed = path.read_bytes(), ir.dump_document(self.doc)
        self.run_export(approval=self.approval)
        ir.export_document(self.doc, None, model_context=CONTEXT)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(ir.dump_document(self.doc), typed)
        self.assertEqual(ir.validate_document(self.doc), self.report)

    def test_pure_export_after_existing_schema_cache(self):
        self.run_export()
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
                patch("pathlib.Path.read_text", side_effect=AssertionError("file I/O")), \
                patch("pathlib.Path.write_text", side_effect=AssertionError("file I/O")), \
                patch("subprocess.Popen", side_effect=AssertionError("process I/O")), \
                patch("socket.socket", side_effect=AssertionError("network I/O")):
            self.assertEqual(self.run_export(approval=self.approval).status, ir.ExportStatus.SUCCESS)
            self.blocked(ir.export_document(self.doc, None, model_context=CONTEXT), {"EXPORT_APPROVAL_MISSING"})

    def test_preview_does_not_grant_representation_or_execution_approval(self):
        result = self.run_export()
        for name in ("can_execute", "representation_approval", "execution_approval", "raw_path", "log_path"):
            self.assertFalse(hasattr(result, name))
        self.assertFalse(hasattr(ir, "make_representation_approval"))
        for name in ("_allocate", "_number", "_mappings", "_source", "_model_line", "_mos_profile", "_si_token"):
            self.assertNotIn(name, ir.__all__)
            self.assertFalse(hasattr(ir, name))

    def test_hash_seeds_and_working_directories_do_not_change_artifact(self):
        script = '''
import hashlib, json
from pathlib import Path
import circuit_ir as ir
root = Path(__import__("sys").argv[1])
results = []
for name, version in (("resistor_divider", "m2-no-models-v1"), ("mixed_mos_profiles", "m2-demo-models-v1")):
    d = ir.load_document((root / "tests/fixtures/spice_export" / name / "circuit.json").read_text(encoding="utf-8")).document
    context = ir.repository_model_context(version)
    report = ir.validate_document(d)
    ids = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
    a = ir.make_circuit_approval(d, approved=True, acknowledged_warning_ids=ids, exporter_contract="m2-spice-v1", model_registry_version=context[0], model_registry_sha256=context[1])
    r = ir.export_document(d, a, model_context=context)
    results.append([r.spice_text, r.provenance.base_netlist_sha256, r.provenance.mapping_sha256, r.element_map, r.net_map, r.model_map, context])
print(json.dumps(results))
'''
        baseline = self.run_export()
        context = ir.repository_model_context()
        doc = fixture("mixed_mos_profiles")
        mos = ir.export_document(doc, approve(doc, context), model_context=context)
        expected = json.dumps([[r.spice_text, r.provenance.base_netlist_sha256, r.provenance.mapping_sha256,
                                r.element_map, r.net_map, r.model_map, ctx] for r, ctx in ((baseline, CONTEXT), (mos, context))])
        for seed, cwd in (("1", ROOT), ("42", FIXTURES), ("random", ROOT / "tests")):
            with self.subTest(seed=seed, cwd=cwd.name):
                result = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(ROOT)], cwd=cwd,
                    env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT)),
                    capture_output=True, text=True, check=True, timeout=30)
                self.assertEqual(result.stdout.strip(), expected)


class MOSExporterTests(unittest.TestCase):
    blocked = ExporterTests.blocked

    @classmethod
    def setUpClass(cls):
        cls.context = ir.repository_model_context()
        cls.doc = fixture("nmos_common_source")
        cls.approval = approve(cls.doc, cls.context)
        cls.report = ir.validate_document(cls.doc)

    def run_export(self, doc=None, approval=None, context=None):
        doc = self.doc if doc is None else doc
        context = self.context if context is None else context
        return ir.export_document(doc, approve(doc, context) if approval is None else approval, model_context=context)

    def changed_mos(self, **changes):
        return replace(self.doc, components=tuple(replace(c, **changes) if c.type is ir.ComponentType.NMOS else c
                                                   for c in self.doc.components))

    def test_four_independent_complete_mos_goldens(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for name in MOS_CASES for p in (FIXTURES / name).iterdir()}
        for name in MOS_CASES:
            with self.subTest(name=name):
                folder = FIXTURES / name
                doc = fixture(name)
                expected = json.loads((folder / "expected-export.json").read_text(encoding="utf-8"))
                result = self.run_export(doc)
                self.assertEqual(result.status.value, expected["status"])
                self.assertEqual(result.spice_text.encode("utf-8"), (folder / "expected.cir").read_bytes())
                self.assertEqual([{ "code": i.code, "severity": i.severity.value, "target_refs": list(i.target_refs),
                                    "field": i.field} for i in result.issues], expected["issues"])
                for key in ("element_map", "net_map", "model_map"):
                    self.assertEqual([list(pair) for pair in getattr(result, key)], expected[key])
                for key in ("document_sha256", "electrical_sha256", "base_netlist_sha256", "mapping_sha256", "model_registry_sha256"):
                    self.assertEqual(getattr(result.provenance, key), expected[key])
                raw = json.loads((folder / "circuit.json").read_text(encoding="utf-8"))
                archival = json.dumps(raw, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
                self.assertEqual(hashlib.sha256(archival.encode("utf-8")).hexdigest(), expected["document_sha256"])
                for field in ("electrical", "model_registry"):
                    vector = json.dumps(expected[field + "_projection"], sort_keys=True, ensure_ascii=True,
                                        allow_nan=False, separators=(",", ":")).encode("utf-8")
                    self.assertEqual(hashlib.sha256(vector).hexdigest(), expected[field + "_sha256"])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_original_m1_nmos_eligible_without_m1_change(self):
        doc = load(M1_FIXTURES / "valid/nmos_common_source/circuit.json")
        self.assertEqual(self.run_export(doc).status, ir.ExportStatus.SUCCESS)
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.VALID)

    def test_nonlinear_reference_stays_blocked_with_trusted_model(self):
        for name in ("pmos_current_source", "nmos_differential_pair"):
            with self.subTest(name=name):
                doc = load(M1_FIXTURES / "valid" / name / "circuit.json")
                report = ir.validate_document(doc)
                self.assertTrue(any(i.code == "DC_REFERENCE_UNPROVEN" for i in report.issues))
                self.blocked(self.run_export(doc), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_empty_model_context_blocks_mos_without_partial_artifact(self):
        self.blocked(self.run_export(context=CONTEXT), {"EXPORT_MODEL_UNRESOLVED"})

    def test_unknown_exact_model_id_no_fuzzy_or_default(self):
        for name in ("unknown", "Repository_demo_nmos", "repository_demo_nmo", "repository_demo_nmos.extra"):
            with self.subTest(name=name):
                doc = self.changed_mos(model_ref=name)
                self.blocked(self.run_export(doc), {"EXPORT_MODEL_UNRESOLVED"})

    def test_caller_constructed_valid_profile_is_not_trusted(self):
        profile = replace(ir.repository_model_profiles(self.context)[0], profile_id="caller_model")
        doc = self.changed_mos(model_ref=profile.profile_id)
        self.blocked(self.run_export(doc), {"EXPORT_MODEL_UNRESOLVED"})

    def test_polarity_mismatch_both_directions(self):
        for name, wrong in (("nmos_common_source", "repository_demo_pmos"),
                            ("pmos_resistive_load", "repository_demo_nmos")):
            doc = fixture(name)
            doc = replace(doc, components=tuple(replace(c, model_ref=wrong) if c.parameters else c for c in doc.components))
            with self.subTest(name=name):
                self.blocked(self.run_export(doc), {"EXPORT_MODEL_INCOMPATIBLE"})

    def test_missing_selected_model_is_m1_ambiguous_first(self):
        doc = self.changed_mos(model_ref=None)
        self.assertEqual(ir.validate_document(doc).technical_state, ir.TechnicalState.AMBIGUOUS)
        self.blocked(ir.export_document(doc, None, model_context=self.context), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_width_length_missing_rejected_by_m1_gate(self):
        mos = next(c for c in self.doc.components if c.parameters)
        for key in ("width", "length"):
            with self.subTest(key=key):
                doc = self.changed_mos(parameters=tuple(pair for pair in mos.parameters if pair[0] != key))
                self.blocked(ir.export_document(doc, None, model_context=self.context), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_width_length_wrong_dimension_nonpositive_nonfinite(self):
        mos = next(c for c in self.doc.components if c.parameters)
        for key in ("width", "length"):
            for value in (q("0", "m"), q("-1", "m"), q("NaN", "m"), q("1", "V")):
                params = tuple((k, value if k == key else v) for k, v in mos.parameters)
                with self.subTest(key=key, value=value):
                    self.blocked(ir.export_document(self.changed_mos(parameters=params), None, model_context=self.context),
                                 {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_width_length_exporter_guard_even_if_report_claims_valid(self):
        mos = next(c for c in self.doc.components if c.parameters)
        doc = self.changed_mos(parameters=tuple((k, q("0", "m") if k == "width" else v) for k, v in mos.parameters))
        # Defensive gate seam, not a claim that actual M1 admits zero width.
        with patch("circuit_ir.exporter.validate_document", return_value=self.report):
            self.blocked(ir.export_document(doc, None, model_context=self.context), {"EXPORT_VALUE_INVALID"})

    def test_extra_mos_instance_parameter_rejected(self):
        mos = next(c for c in self.doc.components if c.parameters)
        for key in ("ad", "as", "pd", "ps", "multiplicity", "raw_model"):
            doc = self.changed_mos(parameters=(*mos.parameters, (key, q("1", "m"))))
            with self.subTest(key=key):
                self.blocked(ir.export_document(doc, None, model_context=self.context), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_missing_bulk_connection_never_invents_body_tie(self):
        bulk = next(p.id for p in self.doc.pins if p.role is ir.PinRole.BULK)
        doc = replace(self.doc, connections=tuple(c for c in self.doc.connections if c.pin_id != bulk))
        self.blocked(ir.export_document(doc, None, model_context=self.context), {"EXPORT_DOCUMENT_NOT_VALID"})

    def test_terminal_roles_not_pin_list_or_connection_order(self):
        doc = replace(self.doc, components=tuple(replace(c, pin_ids=tuple(reversed(c.pin_ids))) for c in reversed(self.doc.components)),
                      pins=tuple(reversed(self.doc.pins)), connections=tuple(reversed(self.doc.connections)),
                      nets=tuple(reversed(self.doc.nets)))
        result = self.run_export(doc)
        original = self.run_export()
        self.assertEqual(result.spice_text.splitlines()[4:], original.spice_text.splitlines()[4:])
        self.assertEqual(result.element_map, original.element_map)
        self.assertEqual(result.net_map, original.net_map)
        self.assertEqual(result.provenance.electrical_sha256, original.provenance.electrical_sha256)
        self.assertNotEqual(result.provenance.document_sha256, original.provenance.document_sha256)

    def test_explicit_source_drain_and_bulk_never_swapped_or_tied(self):
        mos = next(c for c in self.doc.components if c.parameters)
        assignments = {p.role: p.id for p in self.doc.pins if p.component_id == mos.id}
        changed = {assignments[ir.PinRole.DRAIN]: "n0", assignments[ir.PinRole.SOURCE]: "vout",
                   assignments[ir.PinRole.BULK]: "vin"}
        doc = replace(self.doc, connections=tuple(replace(c, net_id=changed[c.pin_id]) if c.pin_id in changed else c
                                                   for c in self.doc.connections))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        self.assertIn("M_0001 0 n_0002 n_0003 n_0002 mdl_0001 W=1e-5 L=1e-6", result.spice_text)

    def test_exact_si_width_length_under_reduced_decimal_precision(self):
        text = "0.000012345678901234567890123456789"
        mos = next(c for c in self.doc.components if c.parameters)
        doc = self.changed_mos(parameters=tuple((k, q(text, "m") if k == "width" else v) for k, v in mos.parameters))
        with localcontext() as ctx:
            ctx.prec = 2
            result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        self.assertIn("W=1.2345678901234567890123456789e-5 L=1e-6", result.spice_text)

    def test_model_deduplication_and_unused_profile_not_emitted(self):
        result = self.run_export(fixture("nmos_shared_model"))
        self.assertEqual(result.spice_text.count(".model "), 1)
        self.assertEqual(result.model_map, (("repository_demo_nmos", "mdl_0001"),))
        self.assertNotIn("PMOS", result.spice_text)
        self.assertEqual(len([line for line in result.spice_text.splitlines() if line.startswith("M_")]), 2)

    def test_spice_width_literal_is_preserved_in_source_not_emitted(self):
        mos = next(c for c in self.doc.components if c.parameters)
        width = q("0.00001", "m", literal="10u", grammar=ir.ValueGrammar.SPICE)
        doc = self.changed_mos(parameters=tuple((k, width if k == "width" else v) for k, v in mos.parameters))
        result = self.run_export(doc)
        self.assertEqual(result.status, ir.ExportStatus.SUCCESS)
        self.assertIn("W=1e-5 L=1e-6", result.spice_text)
        self.assertNotIn("10u", result.spice_text)
        self.assertEqual(dict(next(c for c in doc.components if c.parameters).parameters)["width"].literal, "10u")

    def test_mixed_polarities_share_m_group_models_sort_by_profile_id(self):
        result = self.run_export(fixture("mixed_mos_profiles"))
        self.assertEqual(dict(result.element_map)["A_p"], "M_0001")
        self.assertEqual(dict(result.element_map)["B_n"], "M_0002")
        self.assertEqual(result.model_map, (("repository_demo_nmos", "mdl_0001"), ("repository_demo_pmos", "mdl_0002")))
        lines = result.spice_text.splitlines()
        self.assertTrue(lines[4].startswith(".model mdl_0001 NMOS"))
        self.assertTrue(lines[5].startswith(".model mdl_0002 PMOS"))
        self.assertTrue(lines[6].startswith("M_0001 "))

    def test_full_model_map_is_in_mapping_digest_and_registry_in_provenance(self):
        result = self.run_export(fixture("mixed_mos_profiles"))
        vector = {"mapping_profile": "m2-mapping-v1", "element_map": [list(p) for p in result.element_map],
                  "net_map": [list(p) for p in result.net_map], "model_map": [list(p) for p in result.model_map]}
        digest = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(result.provenance.mapping_sha256, digest)
        self.assertEqual((result.provenance.model_registry_version, result.provenance.model_registry_sha256), self.context)
        self.assertEqual(result.provenance.base_netlist_sha256, hashlib.sha256(result.spice_text.encode("utf-8")).hexdigest())

    def test_model_warning_and_deferral_preserved_and_acknowledged(self):
        before = ir.validate_document(self.doc)
        result = self.run_export(approval=self.approval)
        self.assertEqual(ir.validate_document(self.doc), before)
        self.assertIn("model_catalog_resolution", before.deferred_checks)
        self.assertEqual({i.code for i in result.issues}, {"CHECK_DEFERRED"})
        self.assertTrue(all(i.severity is ir.IssueSeverity.WARNING for i in result.issues))
        self.assertEqual(result.provenance.validation_sha256, ir.validation_digest(before))
        self.blocked(self.run_export(approval=replace(self.approval, acknowledged_warning_ids=())), {"EXPORT_APPROVAL_STALE"})

    def test_unrelated_check_deferred_cannot_be_discharged_by_registry(self):
        warning = next(i for i in self.report.issues if i.code == "CHECK_DEFERRED")
        for changes in ({"field": "value"}, {"entity_type": "net"}, {"target_refs": ("V1",)}, {"entity_id": "V1"}):
            report = replace(self.report, issues=tuple(replace(i, **changes) if i is warning else i for i in self.report.issues))
            with self.subTest(changes=changes), patch("circuit_ir.exporter.validate_document", return_value=report):
                self.blocked(ir.export_document(self.doc, None, model_context=self.context), {"EXPORT_PREREQUISITE_UNRESOLVED"})

    def test_no_approval_no_preview_or_representation_authority(self):
        self.blocked(ir.export_document(self.doc, None, model_context=self.context), {"EXPORT_APPROVAL_MISSING"})
        self.assertIsNone(self.approval.parent_approval_sha256)
        self.assertIsNone(self.approval.base_netlist_sha256)
        self.assertEqual(self.approval.scope, ir.ApprovalScope.CIRCUIT_EXPORT)
        self.assertFalse(hasattr(self.run_export(), "can_execute"))

    def test_old_empty_context_approval_cannot_authorize_mos(self):
        self.blocked(self.run_export(approval=approve(self.doc)), {"EXPORT_APPROVAL_STALE"})

    def test_same_version_updated_repo_coefficients_stales_approval(self):
        from circuit_ir import model_profiles as mp
        profiles = ir.repository_model_profiles(self.context)
        with patch.object(mp, "_DEMO_PROFILES", (replace(profiles[0], kp="0.0002"), profiles[1])):
            new_context = ir.repository_model_context()
            self.assertNotEqual(new_context[1], self.context[1])
            self.blocked(self.run_export(approval=self.approval, context=new_context), {"EXPORT_APPROVAL_STALE"})
            self.blocked(ir.export_document(self.doc, self.approval, model_context=self.context), {"EXPORT_MODEL_INCOMPATIBLE"})

    def test_unknown_forged_registry_context_cannot_export(self):
        for context in ((self.context[0], "a" * 64), ("future_models", self.context[1])):
            with self.subTest(context=context):
                self.blocked(ir.export_document(self.doc, self.approval, model_context=context), {"EXPORT_MODEL_INCOMPATIBLE"})

    def test_raw_model_include_and_model_identifier_injection_rejected(self):
        for text in (".include evil.lib", "foo\n.tran 1", "NMOS(...)", ".model x NMOS", "C:/models/foo.lib", "../evil"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.changed_mos(model_ref=text)
        raw = ir.document_to_dict(self.doc)
        for key in ("raw_model_text", "include", "model_path", "custom_directive"):
            changed = dict(raw, **{key: ".model x NMOS"})
            with self.subTest(key=key):
                self.assertIsNone(ir.document_from_dict(changed).document)

    def test_only_fixed_model_and_end_dot_statements_safe_names(self):
        for name in MOS_CASES:
            result = self.run_export(fixture(name))
            text = result.spice_text
            self.assertTrue(text.isascii())
            self.assertNotIn("\r", text)
            self.assertTrue(text.endswith(".end\n"))
            self.assertTrue(all(line.startswith(".model ") or line == ".end"
                                for line in text.splitlines() if line.startswith(".")))
            for forbidden in (".include", ".lib", ".ac", ".tran", ".dc", ".step", "repository_demo_", "R_n", "B_n"):
                self.assertNotIn(forbidden, text)
            for pairs in (result.element_map, result.net_map, result.model_map):
                self.assertEqual(len(pairs), len({token.casefold() for _, token in pairs}))

    def test_repeat_and_json_roundtrip_preserve_export_without_writes(self):
        first = self.run_export(approval=self.approval)
        self.assertEqual(self.run_export(approval=self.approval), first)
        doc = ir.load_document(ir.dump_document(self.doc)).document
        self.assertEqual(self.run_export(doc), first)

    def test_mos_export_has_no_process_environment_or_model_file_io(self):
        # Warm inherited bundled-schema cache before trapping external access.
        self.run_export(approval=self.approval)
        with patch("builtins.open", side_effect=AssertionError("filesystem")), \
                patch("pathlib.Path.read_text", side_effect=AssertionError("model file")), \
                patch("subprocess.Popen", side_effect=AssertionError("process")), \
                patch("os.getenv", side_effect=AssertionError("environment")):
            self.assertEqual(self.run_export(approval=self.approval).status, ir.ExportStatus.SUCCESS)

    def test_existing_passives_under_demo_context_emit_no_models(self):
        for name in CASES:
            result = self.run_export(fixture(name))
            self.assertEqual(result.spice_text.encode("utf-8"), (FIXTURES / name / "expected.cir").read_bytes())
            self.assertEqual(result.model_map, ())


if __name__ == "__main__":
    unittest.main()
