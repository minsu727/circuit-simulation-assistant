"""M2E exact conditions/approval/composition; no simulator or snapshot updater."""
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir
from tests.m2e_helpers import ROOT, BASES, chain, make_request


class ConditionTests(unittest.TestCase):
    def test_ac_digest_independent_canonical_vector(self):
        condition = ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000")
        vector = {"contract": "m2-analysis-condition-v1", "analysis_type": "AC", "sweep": "dec", "points": 100,
                  "start_frequency": "10", "stop_frequency": "1000000"}
        expected = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                              separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(ir.condition_digest(condition), expected)

    def test_equivalent_numeric_forms_same_digest(self):
        self.assertEqual(ir.condition_digest(ir.ACCondition(ir.ACSweep.DECADE, 100, "+10.0", "1e6")),
                         ir.condition_digest(ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000")))
        self.assertEqual(ir.condition_digest(ir.DCCondition("V1", "-0", "5.0", "0.5")),
                         ir.condition_digest(ir.DCCondition("V1", "0", "5", "5e-1")))

    def test_transient_dc_independent_canonical_vectors(self):
        for condition, vector in ((ir.TransientCondition("0.005", None, "0.00001"),
                                  {"contract": "m2-analysis-condition-v1", "analysis_type": "TRAN", "stop_time": "0.005",
                                   "start_saving_time": None, "maximum_timestep": "1e-5"}),
                                 (ir.DCCondition("V1", "-0.001", "0.001", "0.0001"),
                                  {"contract": "m2-analysis-condition-v1", "analysis_type": "DC", "sweep_source": "V1",
                                   "start_value": "-0.001", "stop_value": "0.001", "step_value": "1e-4"})):
            expected = hashlib.sha256(json.dumps(vector, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                                  separators=(",", ":")).encode("utf-8")).hexdigest()
            with self.subTest(condition=condition):
                self.assertEqual(ir.condition_digest(condition), expected)

    def test_any_ac_semantic_setting_changes_digest(self):
        base = ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000")
        for changes in ({"sweep": ir.ACSweep.OCTAVE}, {"points": 101}, {"start_frequency": "11"}, {"stop_frequency": "2000000"}):
            with self.subTest(changes=changes):
                self.assertNotEqual(ir.condition_digest(base), ir.condition_digest(replace(base, **changes)))

    def test_ac_invalid_range_points_and_types(self):
        base = ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000")
        for changes, error in (({"points": True}, TypeError), ({"points": 1.0}, TypeError), ({"points": 0}, ValueError),
                               ({"sweep": "dec"}, TypeError), ({"sweep": ir.ACSweep.LINEAR, "points": 1}, ValueError),
                               ({"start_frequency": "0"}, ValueError), ({"start_frequency": "-1"}, ValueError),
                               ({"stop_frequency": "10"}, ValueError), ({"start_frequency": 10}, TypeError)):
            with self.subTest(changes=changes), self.assertRaises(error):
                replace(base, **changes)

    def test_transient_optional_constraints(self):
        base = ir.TransientCondition("0.005")
        for changes in ({"stop_time": "0"}, {"start_saving_time": "-1"}, {"start_saving_time": "0.005"},
                        {"maximum_timestep": "0"}, {"maximum_timestep": "0.006"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(base, **changes)
        self.assertNotEqual(ir.condition_digest(base), ir.condition_digest(replace(base, maximum_timestep="0.00001")))

    def test_zero_saving_start_equivalent_to_default(self):
        implicit, explicit = ir.TransientCondition("0.005"), ir.TransientCondition("0.005", "-0.0")
        self.assertEqual(ir.condition_digest(implicit), ir.condition_digest(explicit))
        first = ir.compose_execution_netlist(**chain(request=ir.AnalysisRequest(implicit)))
        second = ir.compose_execution_netlist(**chain(request=ir.AnalysisRequest(explicit)))
        self.assertEqual(first, second)
        self.assertEqual(first.artifact.directive, ".tran 5m")

    def test_dc_exact_ascending_constraints(self):
        base = ir.DCCondition("V1", "-1", "1", "0.1")
        for changes in ({"stop_value": "-1"}, {"stop_value": "-2"}, {"step_value": "0"},
                        {"step_value": "-1"}, {"step_value": "3"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(base, **changes)

    def test_nonfinite_expressions_suffix_and_raw_tokens_rejected(self):
        for text in ("NaN", "Inf", "1k", "{x}", "1/2", "1\n.tran 1", "1; .step x", "1e301", "1" * 129):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ir.TransientCondition(text)

    def test_unsupported_raw_analysis_is_not_a_condition(self):
        for value in (".op", ".ac dec 100 10 1Meg", {"analysis_type": "STEP"}, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.AnalysisRequest(value)
        with self.assertRaises(TypeError):
            ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000", raw_directive=".step x")

    def test_request_ids_measurements_point_are_typed(self):
        condition = ir.DCCondition("V1", "0", "5", "0.5")
        for changes, error in (({"target_net": "V(out)"}, ValueError), ({"reference_net": "foo\n.lib x"}, ValueError),
                               ({"measurements": ["Minimum"]}, TypeError), ({"measurements": ("Minimum", "Minimum")}, ValueError),
                               ({"measurements": (".measure x",)}, ValueError), ({"requested_point": "6"}, ValueError)):
            with self.subTest(changes=changes), self.assertRaises(error):
                ir.AnalysisRequest(condition, **changes)
        with self.assertRaises(ValueError):
            ir.AnalysisRequest(ir.TransientCondition("1"), requested_point="0")

    def test_conditions_request_and_approval_frozen(self):
        data = chain()
        for record, field, value in ((data["request"], "target_net", "vin"), (data["request"].condition, "points", 1),
                                     (data["execution_approval"], "approved", False)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(record, field, value)
        self.assertFalse(hasattr(data["execution_approval"], "__dict__"))


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = chain()

    def compose(self, **changes):
        return ir.compose_execution_netlist(**dict(self.data, **changes))

    def blocked(self, result, code=None):
        self.assertIsNone(result.artifact)
        self.assertTrue(result.issues)
        if code:
            self.assertEqual(result.issues[0].code, code)

    def test_five_static_composition_goldens_and_hashes(self):
        root = ROOT / "tests/fixtures/netlist_execution"
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        self.assertEqual({p.name for p in root.iterdir() if p.is_dir()},
                         {"divider_dc", "rc_ac", "sine_transient", "current_dc", "mos_dc"})
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            manifest = json.loads((folder / "request.json").read_text(encoding="utf-8"))
            with self.subTest(case=folder.name):
                data = chain(manifest["base_fixture"], make_request(manifest))
                result = ir.compose_execution_netlist(**data)
                self.assertFalse(result.issues)
                artifact = result.artifact
                expected = (folder / "expected.cir").read_bytes()
                self.assertEqual(artifact.netlist_bytes, expected)
                self.assertEqual(artifact.directive, manifest["directive"])
                self.assertEqual(artifact.provenance.execution_netlist_sha256, manifest["execution_sha256"])
                self.assertEqual(hashlib.sha256(expected).hexdigest(), manifest["execution_sha256"])
                self.assertEqual(artifact.provenance.base_netlist_sha256, manifest["base_sha256"])
                self.assertEqual(data["export_result"].spice_text.encode("utf-8"),
                                 (BASES / manifest["base_fixture"] / "expected.cir").read_bytes())
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_all_ac_sweep_directives(self):
        for sweep in ir.ACSweep:
            request = ir.AnalysisRequest(ir.ACCondition(sweep, 100, "10", "1000000"))
            artifact = ir.compose_execution_netlist(**chain(request=request)).artifact
            with self.subTest(sweep=sweep):
                self.assertEqual(artifact.directive, f".ac {sweep.value} 100 10 1Meg")

    def test_transient_canonical_positional_forms(self):
        for condition, text in ((ir.TransientCondition("0.005"), ".tran 5m"),
                                (ir.TransientCondition("0.005", "0.001"), ".tran 0 5m 1m"),
                                (ir.TransientCondition("0.005", None, "0.00001"), ".tran 0 5m 0 10u"),
                                (ir.TransientCondition("0.005", "0.001", "0.00001"), ".tran 0 5m 1m 10u")):
            with self.subTest(condition=condition):
                artifact = ir.compose_execution_netlist(**chain(request=ir.AnalysisRequest(condition))).artifact
                self.assertEqual(artifact.directive, text)

    def test_dc_maps_exact_source_ir_id_not_its_prefix(self):
        data = chain()
        doc = data["document"]
        doc = replace(doc, components=tuple(replace(c, id="drive.x") if c.id == "V1" else c for c in doc.components),
                      pins=tuple(replace(p, component_id="drive.x") if p.component_id == "V1" else p for p in doc.pins))
        data = chain(doc=doc, request=ir.AnalysisRequest(ir.DCCondition("drive.x", "0", "5", "0.5")))
        artifact = ir.compose_execution_netlist(**data).artifact
        self.assertEqual(artifact.directive, ".dc V_0001 0 5 500m")
        self.assertEqual(artifact.sweep_source_map, ("drive.x", "V_0001"))
        self.assertNotIn("drive.x", artifact.spice_text)

    def test_dc_unknown_passive_wrong_case_and_emitted_token_rejected(self):
        for source in ("missing", "R1", "v1", "V_0001"):
            with self.subTest(source=source), self.assertRaises(ir.ApprovalError) as caught:
                chain(request=ir.AnalysisRequest(ir.DCCondition(source, "0", "5", "0.5")))
            self.assertEqual(caught.exception.code, "DC_SOURCE_UNSUPPORTED")

    def test_dc_inherited_unresolvable_step_is_blocked_not_rounded(self):
        with self.assertRaises(ValueError):
            chain(request=ir.AnalysisRequest(ir.DCCondition("V1", "1", "2", "1e-20")))

    def test_trace_selection_exact_maps_and_no_label_guess(self):
        artifact = self.compose().artifact
        self.assertEqual(artifact.trace_map, (("target_net", "vout", "V(n_0002)"), ("reference_net", "vin", "V(n_0001)")))
        with self.assertRaises(ir.ApprovalError):
            chain(request=replace(self.data["request"], target_net="out"))

    def test_measurement_order_equivalent_but_selection_changes_approval(self):
        request = replace(self.data["request"], measurements=("Gain", "-3 dB Bandwidth"))
        data = chain(request=request)
        reordered = replace(request, measurements=tuple(reversed(request.measurements)))
        self.assertEqual(ir.compose_execution_netlist(**dict(data, request=reordered)), ir.compose_execution_netlist(**data))
        self.blocked(ir.compose_execution_netlist(**dict(data, request=replace(request, measurements=("Gain",)))), "EXECUTION_BINDING_MISMATCH")

    def test_every_request_selection_is_bound(self):
        request = ir.AnalysisRequest(ir.DCCondition("V1", "0", "5", "0.5"), "vout", "vin", "vin", "3.5", ("Minimum",))
        data = chain(request=request)
        for changes in ({"target_net": "vin"}, {"reference_net": None}, {"comparison_net": None},
                        {"requested_point": "3.6"}, {"measurements": ("Maximum",)}):
            with self.subTest(changes=changes):
                self.blocked(ir.compose_execution_netlist(**dict(data, request=replace(request, **changes))), "EXECUTION_BINDING_MISMATCH")

    def test_changed_ac_transient_dc_conditions_stale(self):
        for old, new in ((ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000"), ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "2000000")),
                         (ir.TransientCondition("0.005"), ir.TransientCondition("0.006")),
                         (ir.DCCondition("V1", "0", "5", "0.5"), ir.DCCondition("V1", "0", "6", "0.5"))):
            with self.subTest(old=old):
                data = chain(request=ir.AnalysisRequest(old))
                self.blocked(ir.compose_execution_netlist(**dict(data, request=ir.AnalysisRequest(new))), "EXECUTION_BINDING_MISMATCH")

    def test_missing_execution_approval_or_wrong_record_type(self):
        for approval in (None, self.data["circuit_approval"], self.data["representation_approval"], True):
            with self.subTest(approval=type(approval).__name__):
                self.blocked(self.compose(execution_approval=approval), "EXECUTION_INPUT_INVALID")

    def test_wrong_scope_at_parent_representation_gate(self):
        self.blocked(self.compose(representation_approval=self.data["circuit_approval"]), "APPROVAL_SCOPE_INVALID")
        self.blocked(self.compose(circuit_approval=self.data["representation_approval"]), "APPROVAL_SCOPE_INVALID")

    def test_execution_version_false_and_hash_tampering(self):
        approval = self.data["execution_approval"]
        for changes, code in (({"contract_version": "future"}, "EXECUTION_VERSION_UNSUPPORTED"),
                              ({"adapter_contract": "future"}, "EXECUTION_VERSION_UNSUPPORTED"),
                              ({"approved": False}, "APPROVAL_NOT_GRANTED"),
                              ({"base_netlist_sha256": "a" * 64}, "EXECUTION_BINDING_MISMATCH"),
                              ({"representation_approval_sha256": "a" * 64}, "EXECUTION_BINDING_MISMATCH"),
                              ({"request_sha256": "a" * 64}, "EXECUTION_BINDING_MISMATCH")):
            with self.subTest(changes=changes):
                self.blocked(self.compose(execution_approval=replace(approval, **changes)), code)

    def test_explicit_execution_decision_and_warning_review_required(self):
        data = dict(self.data)
        data.pop("execution_approval")
        for value, error in ((False, ir.ApprovalError), (1, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                ir.make_execution_approval(**data, approved=value)

    def test_stale_representation_parent_and_source_chain(self):
        self.blocked(self.compose(representation_approval=replace(self.data["representation_approval"], parent_approval_sha256="a" * 64)),
                     "REPRESENTATION_BINDING_MISMATCH")
        doc = self.data["document"]
        self.blocked(self.compose(document=replace(doc, metadata=replace(doc.metadata, revision=1))))

    def test_base_tampering_endings_components_models_and_analysis_rejected(self):
        for name in ("resistor_divider", "nmos_common_source"):
            data = chain(name)
            base = data["export_result"]
            for text in (base.spice_text.replace("\n", "\r\n"), base.spice_text.rstrip("\n"), base.spice_text + ".end\n",
                         base.spice_text.replace(".end\n", ".ac dec 100 1 10\n.end\n"),
                         base.spice_text.replace("1000", "1001"), base.spice_text.replace("KP=1e-4", "KP=2e-4")):
                if text == base.spice_text:
                    continue
                with self.subTest(name=name, text=text[-40:]):
                    self.blocked(ir.compose_execution_netlist(**dict(data, export_result=replace(base, spice_text=text))), "ARTIFACT_MISMATCH")

    def test_forged_provenance_cannot_bless_changed_base(self):
        base = self.data["export_result"]
        text = base.spice_text.replace("1000", "1001")
        forged = replace(base, spice_text=text, provenance=replace(base.provenance, base_netlist_sha256=hashlib.sha256(text.encode()).hexdigest()))
        self.blocked(self.compose(export_result=forged), "ARTIFACT_MISMATCH")

    def test_one_analysis_before_terminal_end_base_preserved(self):
        before = ir.dump_document(self.data["document"])
        base = self.data["export_result"].spice_text
        artifact = self.compose().artifact
        self.assertEqual(artifact.spice_text, base[:-5] + artifact.directive + "\n.end\n")
        self.assertEqual(artifact.spice_text.splitlines()[-2:], [artifact.directive, ".end"])
        self.assertEqual(artifact.spice_text.count(".end\n"), 1)
        self.assertEqual(artifact.spice_text.count(".ac "), 1)
        self.assertNotIn("\r", artifact.spice_text)
        self.assertEqual(self.data["export_result"].spice_text, base)
        self.assertEqual(ir.dump_document(self.data["document"]), before)

    def test_long_exact_values_low_precision_and_small_emax(self):
        request = ir.AnalysisRequest(ir.ACCondition(ir.ACSweep.DECADE, 100, "10.12345678901234567890123456789", "1000000"))
        baseline = ir.compose_execution_netlist(**chain(request=request))
        with localcontext() as context:
            context.prec = 2
            context.Emax = 2
            result = ir.compose_execution_netlist(**chain(request=request))
        self.assertEqual(result, baseline)
        self.assertIn("10.12345678901234567890123456789", result.artifact.directive)

    def test_builder_output_numeric_rounding_or_extra_directive_blocked(self):
        for text in (".ac dec 100 10 2Meg", ".ac dec 100 10 1Meg\n.step x", ".ac dec 100 10 1Meg; .op"):
            with self.subTest(text=text), patch("ac_analysis.build_ac_directive", return_value=text):
                self.blocked(self.compose(), "EXECUTION_INPUT_INVALID")

    def test_verification_never_calls_approval_factories(self):
        with patch("circuit_ir.approval.make_representation_approval", side_effect=AssertionError("auto-review")), \
                patch("circuit_ir.execution.make_execution_approval", side_effect=AssertionError("auto-review")):
            self.assertIsNotNone(self.compose().artifact)

    def test_composition_pure_no_file_process_network_or_simulator(self):
        self.compose()  # warm inherited schema cache
        with patch("builtins.open", side_effect=AssertionError("file")), \
                patch("pathlib.Path.mkdir", side_effect=AssertionError("write")), \
                patch("subprocess.Popen", side_effect=AssertionError("process")), \
                patch("socket.socket", side_effect=AssertionError("network")):
            self.assertIsNotNone(self.compose().artifact)

    def test_all_provenance_links_and_repeat_determinism(self):
        first = self.compose()
        self.assertEqual(first, self.compose())
        p = first.artifact.provenance
        self.assertEqual(p.document_sha256, ir.document_digest(self.data["document"]))
        self.assertEqual(p.circuit_approval_sha256, ir.approval_digest(self.data["circuit_approval"]))
        self.assertEqual(p.representation_approval_sha256, ir.approval_digest(self.data["representation_approval"]))
        self.assertEqual(p.execution_approval_sha256, ir.execution_approval_digest(self.data["execution_approval"]))
        self.assertEqual(p.execution_netlist_sha256, hashlib.sha256(first.artifact.netlist_bytes).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            first.artifact.directive = ".op"

    def test_full_request_and_execution_approval_independent_vectors(self):
        vector = {"contract": "m2-analysis-request-v1", "condition": {"contract": "m2-analysis-condition-v1", "analysis_type": "AC",
                  "sweep": "dec", "points": 100, "start_frequency": "10", "stop_frequency": "1000000"},
                  "target_net": "vout", "reference_net": "vin", "comparison_net": None,
                  "requested_point": None, "measurements": [], "mapping_sha256": self.data["export_result"].provenance.mapping_sha256}
        native = lambda data: hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                                      separators=(",", ":")).encode("utf-8")).hexdigest()
        approval = self.data["execution_approval"]
        self.assertEqual(approval.request_sha256, native(vector))
        expected = {"contract_version": "m2-execution-approval-v1", "adapter_contract": "m2-netlist-adapter-v1", "approved": True,
                    "representation_approval_sha256": ir.approval_digest(self.data["representation_approval"]),
                    "base_netlist_sha256": self.data["export_result"].provenance.base_netlist_sha256,
                    "request_sha256": native(vector)}
        self.assertEqual(ir.execution_approval_digest(approval), native(expected))

    def test_hash_seeds_and_working_directories_same_execution_bytes(self):
        script = '''
import hashlib
import circuit_ir as ir
from tests.m2e_helpers import chain
result = ir.compose_execution_netlist(**chain("nmos_common_source"))
assert not result.issues
print(hashlib.sha256(result.artifact.netlist_bytes).hexdigest())
print(result.artifact.provenance.execution_approval_sha256)
'''
        result = ir.compose_execution_netlist(**chain("nmos_common_source"))
        expected = result.artifact.provenance.execution_netlist_sha256 + "\n" + result.artifact.provenance.execution_approval_sha256
        for seed, cwd in (("1", ROOT), ("42", BASES), ("random", ROOT / "tests")):
            process = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=cwd,
                env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT)), capture_output=True, text=True, check=True, timeout=30)
            self.assertEqual(process.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
