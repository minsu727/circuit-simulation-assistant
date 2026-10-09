"""M2G public-chain acceptance. Fixture decisions are explicit test authority only.

No network, live simulator or private assets. Opaque fake files are process/file
evidence, never physical RAW. Existing independent goldens remain read-only.
"""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest
from unittest.mock import patch

import numpy as np
import circuit_ir as ir
import netlist_runner as nr
import netlist_result_analysis as na
from tests.m2e_helpers import make_request
from tests.test_netlist_runner import FakeRunner
from tests.test_netlist_ltspice import SampleRaw

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests/fixtures/m2_acceptance/catalog.json"
CASES = json.loads(CATALOG.read_text(encoding="utf8"))["cases"]


def load(path):
    result = ir.load_document((ROOT / path).read_text(encoding="utf8"))
    if result.document is None:
        raise AssertionError(result.issues)
    return result.document


def context(doc):
    return ir.repository_model_context("m2-demo-models-v1" if any(c.parameters for c in doc.components)
                                       else "m2-no-models-v1")


def circuit_decision(doc, ctx, approved=True):
    report = ir.validate_document(doc)
    warnings = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
    return ir.make_circuit_approval(doc, approved=approved, acknowledged_warning_ids=warnings,
                                   exporter_contract="m2-spice-v1",
                                   model_registry_version=ctx[0], model_registry_sha256=ctx[1])


def request_for(mode="ac"):
    if mode == "tran":
        return ir.AnalysisRequest(ir.TransientCondition("0.01", "0", "0.00001"),
                                  "vout", "vin", measurements=("Voltage Gain", "Output Swing"))
    if mode == "dc":
        return ir.AnalysisRequest(ir.DCCondition("V1", "0", "5", "0.5"),
                                  "vout", "vin", "vin", "3.5", ("Minimum", "Value at Sweep Point"))
    return ir.AnalysisRequest(ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000"),
                              "vout", "vin", measurements=("Gain", "-3 dB Bandwidth"))


def reviewed(doc, request=None):
    # Three independent, deliberate decisions made by this fixture controller.
    ctx = context(doc)
    circuit = circuit_decision(doc, ctx)
    base = ir.export_document(doc, circuit, model_context=ctx)
    representation = ir.make_representation_approval(doc, base, circuit, approved=True, model_context=ctx)
    req = request or request_for()
    execution = ir.make_execution_approval(doc, base, circuit, representation, req,
                                          approved=True, model_context=ctx)
    return dict(document=doc, export_result=base, circuit_approval=circuit,
                representation_approval=representation, request=req,
                execution_approval=execution, model_context=ctx)


class M2AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_bytes = {p: p.read_bytes() for p in (ROOT / "tests/fixtures").rglob("*") if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        if any(p.read_bytes() != content for p, content in cls.fixture_bytes.items()):
            raise AssertionError("Acceptance changed a source/golden fixture")

    def blocked(self, data, code):
        composed = ir.compose_execution_netlist(**data)
        self.assertIsNone(composed.artifact)
        self.assertEqual(composed.issues[0].code, code)
        with TemporaryDirectory() as temp:
            root, runner = Path(temp), FakeRunner()
            result = nr.run_generated_netlist(**data, workspace_root=root, runner=runner)
            self.assertEqual(result.status, nr.RunStatus.BLOCKED)
            self.assertEqual(result.issues[0].code, code)
            self.assertEqual(runner.calls, [])
            self.assertEqual(list(root.iterdir()), [])
            for field in ("artifact", "working_file", "raw_file", "log_file", "runner_result"):
                self.assertIsNone(getattr(result, field))
            # Same preflight at the real public entry point; backend must not exist.
            with patch.object(nr, "_LTspiceRunner", side_effect=AssertionError("backend reached")):
                real = nr.run_ltspice_netlist(**data, workspace_root=root)
            self.assertEqual(real.status, nr.RunStatus.BLOCKED)
            self.assertIsNone(real.analysis)
            self.assertEqual(list(root.iterdir()), [])

    def exercise(self, case):
        category, scenario, expected = case["category"], case["scenario"], case["expected"]
        doc = load(case["fixture"])
        if category == "export":
            ctx = context(doc)
            report = ir.validate_document(doc)
            self.assertEqual(report.technical_state, ir.TechnicalState.VALID)
            base = ir.export_document(doc, circuit_decision(doc, ctx), model_context=ctx)
            self.assertEqual(base.status.value, expected["export"])
            golden = (ROOT / case["golden"]).read_bytes()
            vectors = json.loads((ROOT / case["expectation"]).read_text(encoding="utf8"))
            self.assertEqual(base.spice_text.encode("utf8"), golden)
            self.assertNotIn(b"\r", golden)
            self.assertTrue(golden.endswith(b".end\n"))
            self.assertEqual(hashlib.sha256(golden).hexdigest(), vectors["base_netlist_sha256"])
            for field in ("element_map", "net_map", "model_map"):
                self.assertEqual([list(v) for v in getattr(base, field)], vectors[field])
            for field in ("document_sha256", "electrical_sha256", "mapping_sha256"):
                self.assertEqual(getattr(base.provenance, field), vectors[field])
            again = ir.export_document(doc, circuit_decision(doc, ctx), model_context=ctx)
            self.assertEqual(base, again)
            self.assertEqual([v for v in base.spice_text.splitlines() if v.startswith(".model ")],
                             [v for v in golden.decode("utf8").splitlines() if v.startswith(".model ")])
            return
        if category == "execution":
            manifest = json.loads((ROOT / case["request"]).read_text(encoding="utf8"))
            data = reviewed(doc, make_request(manifest))
            artifact = ir.compose_execution_netlist(**data).artifact
            self.assertIsNotNone(artifact)
            golden = (ROOT / case["golden"]).read_bytes()
            self.assertEqual(artifact.netlist_bytes, golden)
            self.assertEqual(artifact.provenance.execution_netlist_sha256, manifest["execution_sha256"])
            self.assertEqual(artifact.directive, manifest["directive"])
            base_bytes = data["export_result"].spice_text.encode("utf8")
            self.assertEqual(artifact.netlist_bytes, base_bytes[:-5] + artifact.directive.encode() + b"\n.end\n")
            directives = [s for s in artifact.spice_text.splitlines() if s.startswith((".ac ", ".tran ", ".dc "))]
            self.assertEqual(directives, [manifest["directive"]])
            self.assertEqual(artifact.spice_text.splitlines()[-2:], [manifest["directive"], ".end"])
            self.assertEqual(artifact, ir.compose_execution_netlist(**data).artifact)
            with TemporaryDirectory() as temp:
                root, runner = Path(temp), FakeRunner()
                source, base = root / "user.json", root / "approved.cir"
                source.write_bytes((ROOT / case["fixture"]).read_bytes())
                base.write_bytes(base_bytes)
                preserved = {source: source.read_bytes(), base: base.read_bytes()}
                result = nr.run_generated_netlist(**data, workspace_root=root, runner=runner)
                self.assertEqual(result.status.value, expected["run"])
                self.assertEqual(len(runner.calls), expected["runner_calls"])
                path, output, content = runner.calls[0]
                self.assertEqual(path, result.working_file)
                self.assertNotIn(path, preserved)
                self.assertEqual(content, golden)
                self.assertEqual((path.parent / "base.cir").read_bytes(), base_bytes)
                self.assertEqual((path.parent / "source.circuit.json").read_bytes(), ir.dump_document(doc).encode())
                self.assertTrue(output.is_relative_to(root))
                for p, content in preserved.items():
                    self.assertEqual(p.read_bytes(), content)
            return
        if category == "circuit_gate":
            report = ir.validate_document(doc)
            with ExitStack() as stack:
                if scenario == "unvalidated":
                    report = replace(report, technical_state=ir.TechnicalState.UNVALIDATED)
                    stack.enter_context(patch("circuit_ir.approval.validate_document", return_value=report))
                self.assertEqual(report.technical_state.value, expected["technical_state"])
                with self.assertRaises(ir.ApprovalError) as caught:
                    circuit_decision(doc, context(doc))
                self.assertEqual(caught.exception.code, expected["approval_error"])
            data = reviewed(load("tests/fixtures/spice_export/resistor_divider/circuit.json"))
            data["document"] = doc
            with ExitStack() as stack:
                if scenario == "unvalidated":
                    stack.enter_context(patch("circuit_ir.approval.validate_document", return_value=report))
                self.blocked(data, "DOCUMENT_NOT_VALID")
            return
        if category == "decision":
            data = reviewed(doc)
            with self.assertRaises(ir.ApprovalError) as caught:
                if scenario == "circuit":
                    circuit_decision(doc, data["model_context"], approved=False)
                elif scenario == "representation":
                    ir.make_representation_approval(doc, data["export_result"], data["circuit_approval"],
                                                    approved=False, model_context=data["model_context"])
                else:
                    fields = dict(data); fields.pop("execution_approval")
                    ir.make_execution_approval(**fields, approved=False)
            self.assertEqual(caught.exception.code, expected["approval_error"])
            return
        if category == "injection":
            token = case["token"]
            with self.assertRaises(ValueError):
                replace(doc.components[0], id=token)
            raw = ir.document_to_dict(doc)
            raw["components"][0]["id"] = token
            loaded = ir.document_from_dict(raw)
            self.assertIsNone(loaded.document)
            self.assertTrue(loaded.issues)
            # Arbitrary commands cannot enter typed analysis conditions either.
            with self.assertRaises(ValueError):
                ir.TransientCondition(token)
            return
        if category == "model_rejection":
            model = "unknown" if scenario == "unknown" else "repository_demo_pmos"
            doc = replace(doc, components=tuple(replace(c, model_ref=model) if c.parameters else c for c in doc.components))
            ctx = context(doc); circuit = circuit_decision(doc, ctx)
            base = ir.export_document(doc, circuit, model_context=ctx)
            self.assertEqual(base.status.value, expected["export"])
            self.assertIn(expected["issue_code"], [i.code for i in base.issues])
            self.assertIsNone(base.spice_text); self.assertIsNone(base.provenance)
            self.assertEqual((base.element_map, base.net_map, base.model_map), ((), (), ()))
            with self.assertRaises(ir.ApprovalError):
                ir.make_representation_approval(doc, base, circuit, approved=True, model_context=ctx)
            data = reviewed(load(case["fixture"]))
            data.update(document=doc, circuit_approval=circuit, export_result=base)
            self.blocked(data, "ARTIFACT_NOT_EXPORTABLE")
            return
        if category == "staleness":
            mode = "tran" if scenario.startswith("tran_") else "dc" if scenario.startswith("dc_") or scenario in ("comparison", "requested_point") else "ac"
            data = reviewed(doc, request_for(mode))
            with ExitStack() as stack:
                self.mutate(data, scenario, stack)
                self.blocked(data, expected["issue_code"])
            return
        if category == "runner_fault":
            data = reviewed(doc)
            with TemporaryDirectory() as temp:
                runner = FakeRunner(scenario)
                result = nr.run_generated_netlist(**data, workspace_root=Path(temp), runner=runner)
                self.assertEqual(result.status.value, expected["run"])
                self.assertEqual(len(runner.calls), expected["runner_calls"])
                self.assertEqual(result.issues[0].code, expected["issue_code"])
            return
        if category in ("analysis", "raw_fault"):
            mode = scenario if category == "analysis" else "ac"
            data = reviewed(doc, request_for(mode))
            raw = SampleRaw(mode)
            if scenario == "wrong_mode": raw = SampleRaw("dc")
            elif scenario == "missing_trace": raw = SampleRaw(missing=True)
            elif scenario == "invalid_axis": raw.axis[1] = raw.axis[0]
            elif scenario == "empty_samples":
                raw.axis = np.array([]); raw.waves[raw.names[0]] = raw.axis
            elif scenario == "nonfinite": raw.waves["V(n_0002)"][0] = np.nan
            if scenario == "unsupported_current":
                mos = reviewed(load("tests/fixtures/spice_export/nmos_common_source/circuit.json"))
                art = ir.compose_execution_netlist(**mos).artifact
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    na.read_generated_current("unused.raw", art, mos["export_result"], "M1")
                return
            with TemporaryDirectory() as temp:
                runner = FakeRunner()
                with ExitStack() as stack:
                    stack.enter_context(patch.object(nr._LTspiceRunner, "run", new=lambda self, p, o: runner.run(p, o)))
                    stack.enter_context(patch.object(na, "RawRead", side_effect=ValueError("Synthetic corrupt RAW")) if scenario == "corrupt"
                                        else patch.object(na, "RawRead", return_value=raw))
                    result = nr.run_ltspice_netlist(**data, workspace_root=Path(temp))
                self.assertEqual(len(runner.calls), 1)
                self.assertEqual(result.run.status, nr.RunStatus.SUCCESS)
                self.assertIsNone(result.executable)  # explicitly synthetic, not live LTspice
                if category == "raw_fault":
                    self.assertEqual(result.status, nr.RunStatus.FAILED)
                    self.assertIsNone(result.analysis); self.assertTrue(result.diagnostics)
                    if scenario == "missing_trace":
                        self.assertIn("V(n_0002)", result.diagnostics[0])
                        self.assertIn("V(n_0001)", result.diagnostics[0])
                else:
                    self.assertEqual(result.status, nr.RunStatus.SUCCESS)
                    measured = result.analysis.result
                    if mode == "ac":
                        self.assertAlmostEqual(measured.bandwidth_hz, 159.154943, delta=1)
                        self.assertEqual(abs(measured.reference[0]), 2)
                    elif mode == "tran":
                        self.assertAlmostEqual(measured.measurements["Voltage Gain"].values["Voltage Gain"][0], 2, places=6)
                    else:
                        self.assertAlmostEqual(measured.point_value, 3.5 * 2 / 3)
                    self.assertEqual(result.analysis.selected_traces, result.run.artifact.trace_map)
            return
        self.fail("Unimplemented catalog category")

    def mutate(self, data, scenario, stack):
        doc, base, req = data["document"], data["export_result"], data["request"]
        if scenario == "document_content":
            data["document"] = replace(doc, components=tuple(replace(c, value=ir.Quantity("1001", "1001", "ohm", ir.ValueGrammar.SI))
                                                             if c.id == "R1" else c for c in doc.components))
        elif scenario in ("document_id", "revision"):
            field, value = ("circuit_id", "other") if scenario == "document_id" else ("revision", doc.metadata.revision + 1)
            data["document"] = replace(doc, metadata=replace(doc.metadata, **{field: value}))
        elif scenario == "provenance":
            data["document"] = replace(doc, confidence=replace(doc.confidence, calibrated=not doc.confidence.calibrated))
        elif scenario in ("report", "ruleset"):
            report = ir.validate_document(doc)
            report = replace(report, deferred_checks=report.deferred_checks + ("test_report_change",)) if scenario == "report" else replace(report, ruleset_version="future")
            stack.enter_context(patch("circuit_ir.approval.validate_document", return_value=report))
        elif scenario == "model_context":
            data["model_context"] = ir.repository_model_context("m2-demo-models-v1")
        elif scenario.startswith("base_"):
            suffix = scenario[5:]
            if suffix in ("crlf", "final_newline", "component", "model"):
                text = (base.spice_text.replace("\n", "\r\n") if suffix == "crlf" else base.spice_text.rstrip("\n") if suffix == "final_newline"
                        else base.spice_text.replace("1000", "1001") if suffix == "component" else base.spice_text.replace("KP=1e-4", "KP=2e-4"))
                assert text != base.spice_text
                base = replace(base, spice_text=text)
            elif suffix in ("mapping", "model_mapping"):
                field = "net_map" if suffix == "mapping" else "model_map"
                mapping = getattr(base, field)
                base = replace(base, **{field: ((mapping[0][0], "n_9999" if field == "net_map" else "mdl_9999"),) + mapping[1:]})
            elif suffix == "provenance":
                base = replace(base, provenance=replace(base.provenance, mapping_sha256="a" * 64))
            elif suffix == "blocked":
                issue = ir.ExportIssue("EXPORT_APPROVAL_MISSING", ir.IssueSeverity.ERROR, (), None, "Test blocked preview.")
                base = ir.ExportResult(status=ir.ExportStatus.BLOCKED, spice_text=None, issues=(issue,),
                                       provenance=None, element_map=(), net_map=(), model_map=())
            data["export_result"] = base
        elif scenario.startswith(("ac_", "tran_", "dc_")):
            fields = {"ac_start": ("start_frequency", "11"), "ac_stop": ("stop_frequency", "2000000"), "ac_points": ("points", 101),
                      "ac_sweep": ("sweep", ir.ACSweep.OCTAVE), "tran_stop": ("stop_time", "0.02"), "tran_start": ("start_saving_time", "0.001"),
                      "tran_step": ("maximum_timestep", "0.00002"), "dc_start": ("start_value", "-1"), "dc_stop": ("stop_value", "6"),
                      "dc_step": ("step_value", "0.25"), "dc_source": ("sweep_source", "V2")}
            field, value = fields[scenario]
            data["request"] = replace(req, condition=replace(req.condition, **{field: value}))
        elif scenario in ("target", "reference", "comparison", "measurement", "requested_point"):
            field, value = {"target": ("target_net", "vin"), "reference": ("reference_net", None), "comparison": ("comparison_net", None),
                            "measurement": ("measurements", ("Gain",)), "requested_point": ("requested_point", "3.6")}[scenario]
            data["request"] = replace(req, **{field: value})
        else:
            if scenario in ("circuit_scope", "representation_scope"):
                key = scenario.split("_", 1)[0] + "_approval"
                data[key] = data["representation_approval" if key == "circuit_approval" else "circuit_approval"]
                return
            if scenario == "adapter_version":
                key, field, value = "execution_approval", "adapter_contract", "future"
            else:
                prefix, suffix = scenario.split("_", 1)
                key = prefix + "_approval"
                field, value = {"scope": ("scope", ir.ApprovalScope.REPRESENTATION if prefix == "circuit" else ir.ApprovalScope.CIRCUIT_EXPORT),
                                "version": ("contract_version", "future"), "declined": ("approved", False),
                                "parent": ("representation_approval_sha256" if prefix == "execution" else "parent_approval_sha256", "a" * 64),
                                "missing": (None, None), "wrong_type": (None, data["circuit_approval"])}[suffix]
            data[key] = value if field is None else replace(data[key], **{field: value})

    def test_catalog_integrity(self):
        self.assertEqual(len(CASES), len({c["case_id"] for c in CASES}))
        for case in CASES:
            with self.subTest(case=case["case_id"]):
                for key in ("fixture", "golden", "expectation", "request"):
                    if key in case:
                        path = ROOT / case[key]
                        self.assertTrue(path.is_file(), case[key])
                        self.assertTrue(path.resolve().is_relative_to(ROOT))
                self.assertTrue(case["ci_safe"])
                self.assertTrue(case["expected"]); self.assertTrue(case["rationale"])

    def test_no_implicit_downstream_review(self):
        data = reviewed(load("tests/fixtures/spice_export/resistor_divider/circuit.json"))
        # Verification/composition must not create new review decisions.
        with patch("circuit_ir.approval.make_representation_approval", side_effect=AssertionError("automatic review")), \
             patch("circuit_ir.execution.make_execution_approval", side_effect=AssertionError("automatic review")):
            self.assertIsNotNone(ir.compose_execution_netlist(**data).artifact)

    def test_sanitized_evidence_inventory_integrity(self):
        # CI checks the published inventory structure, not absent local RAW files
        # or simulator physics. The separate local inspection checks those files.
        path = ROOT / "docs/v0.2/m2/real-run-evidence.json"
        text = path.read_text(encoding="utf8")
        inventory = json.loads(text)
        self.assertEqual(len(inventory["runs"]), 34)
        self.assertEqual(len({r["case_id"] for r in inventory["runs"]}), 34)
        self.assertEqual(inventory["counts"]["m2g_new_simulator_runs"], 0)
        self.assertNotIn("C:\\\\Users", text)
        for row in inventory["runs"]:
            self.assertEqual(row["status"], "PASS")
            self.assertEqual(set(row["evidence"]), {"raw", "log"})
            for evidence in row["evidence"].values():
                self.assertFalse(Path(evidence["path"]).is_absolute())
                self.assertNotIn("..", Path(evidence["path"]).parts)
                self.assertGreater(evidence["bytes"], 0)
                self.assertRegex(evidence["sha256"], r"^[a-f0-9]{64}$")
        json.dumps(inventory, allow_nan=False)


def catalog_test(case):
    def test(self):
        self.exercise(case)
    test.__doc__ = case["rationale"]
    return test


# A stable unittest name per independently authored catalog row gives visible
# failures and exact scenario counts in ordinary CI discovery.
for _case in CASES:
    setattr(M2AcceptanceTests, "test_" + _case["case_id"], catalog_test(_case))


if __name__ == "__main__":
    unittest.main()
