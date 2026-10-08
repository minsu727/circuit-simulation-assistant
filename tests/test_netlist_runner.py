"""Mock-only orchestration; opaque evidence sentinels are not LTspice RAW data."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import json
import unittest
from unittest.mock import patch

import circuit_ir as ir
import netlist_runner as nr
from tests.m2e_helpers import ROOT, BASES, chain, make_request


class FakeRunner:
    def __init__(self, mode="success", external=None):
        self.calls = []
        self.mode, self.external = mode, external

    def run(self, path, output):
        self.calls.append((path, output, path.read_bytes()))
        if self.mode == "exception":
            raise RuntimeError("Test-only runner failure")
        if self.mode == "wrong_result":
            return None
        raw, log = output / "mock.raw", output / "mock.log"
        if self.mode not in ("absent", "none"):
            raw.write_bytes(b"" if self.mode == "empty_raw" else b"opaque test sentinel; not simulator RAW")
            log.write_bytes(b"" if self.mode == "empty_log" else b"test-only runner evidence")
        if self.mode == "tamper":
            path.write_bytes(path.read_bytes().replace(b"1000", b"1001"))
        if self.mode == "external":
            raw = self.external
        if self.mode == "same_file":
            log = raw
        return nr.RunnerResult(self.mode != "failure", 1 if self.mode in ("failure", "exit1") else 0,
                               None if self.mode == "none" else raw, log, "Mock process result")


class NetlistRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = chain()

    def run_case(self, root, runner, **changes):
        return nr.run_generated_netlist(**dict(self.data, **changes), workspace_root=root, runner=runner)

    def test_success_exact_working_copy_layout_and_portable_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runner = FakeRunner()
            result = self.run_case(root, runner)
            self.assertEqual(result.status, nr.RunStatus.SUCCESS)
            self.assertEqual(len(runner.calls), 1)
            working, output, content = runner.calls[0]
            self.assertEqual(working, result.working_file)
            self.assertEqual(working.name, "execution.cir")
            self.assertEqual(content, result.artifact.netlist_bytes)
            self.assertEqual(working.parent.name, "m2")
            self.assertEqual(working.parent.parent.name, output.name)
            self.assertEqual((working.parent / "base.cir").read_bytes(), self.data["export_result"].spice_text.encode("utf-8"))
            self.assertEqual((working.parent / "source.circuit.json").read_bytes(), ir.dump_document(self.data["document"]).encode("utf-8"))
            evidence_text = (working.parent / "export-evidence.json").read_text(encoding="utf-8")
            evidence = json.loads(evidence_text)
            self.assertNotIn(temp, evidence_text)
            self.assertNotIn(output.name, evidence_text)
            self.assertEqual(evidence["execution_netlist_sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(result.raw_file, output / "mock.raw")
            self.assertEqual(result.log_file, output / "mock.log")

    def test_source_fixture_existing_json_asc_and_base_files_preserved(self):
        fixture = BASES / "resistor_divider/circuit.json"
        before = fixture.read_bytes()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            existing = {root / "user.asc": b"user-owned schematic", root / "reviewed.json": before,
                        root / "approved.cir": self.data["export_result"].spice_text.encode("utf-8")}
            for path, content in existing.items():
                path.write_bytes(content)
            snapshot = ir.dump_document(self.data["document"])
            self.assertEqual(self.run_case(root, FakeRunner()).status, nr.RunStatus.SUCCESS)
            for path, content in existing.items():
                self.assertEqual(path.read_bytes(), content)
            self.assertEqual(ir.dump_document(self.data["document"]), snapshot)
        self.assertEqual(fixture.read_bytes(), before)

    def test_all_five_analysis_goldens_through_mock_adapter(self):
        folders = ROOT / "tests/fixtures/netlist_execution"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in sorted(p for p in folders.iterdir() if p.is_dir()):
                manifest = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                data = chain(manifest["base_fixture"], make_request(manifest))
                runner = FakeRunner()
                with self.subTest(case=folder.name):
                    result = nr.run_generated_netlist(**data, workspace_root=root, runner=runner)
                    self.assertEqual(result.status, nr.RunStatus.SUCCESS)
                    self.assertEqual(len(runner.calls), 1)
                    self.assertEqual(result.working_file.read_bytes(), (folder / "expected.cir").read_bytes())

    def test_invalid_chain_zero_file_and_runner_calls(self):
        base, rep, execution = (self.data[k] for k in ("export_result", "representation_approval", "execution_approval"))
        cases = ({"circuit_approval": None}, {"representation_approval": None}, {"execution_approval": None},
                 {"representation_approval": self.data["circuit_approval"]}, {"circuit_approval": rep},
                 {"export_result": replace(base, spice_text=base.spice_text[:-1])},
                 {"representation_approval": replace(rep, parent_approval_sha256="a" * 64)},
                 {"execution_approval": replace(execution, request_sha256="a" * 64)},
                 {"execution_approval": replace(execution, adapter_contract="future")},
                 {"request": replace(self.data["request"], condition=replace(self.data["request"].condition, stop_frequency="2000000"))})
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for changes in cases:
                runner = FakeRunner()
                with self.subTest(changes=tuple(changes)), patch("pathlib.Path.mkdir", side_effect=AssertionError("premature mkdir")), \
                        patch("pathlib.Path.open", side_effect=AssertionError("premature file")):
                    result = self.run_case(root, runner, **changes)
                self.assertEqual(result.status, nr.RunStatus.BLOCKED)
                self.assertIsNone(result.artifact)
                self.assertIsNone(result.working_file)
                self.assertFalse(runner.calls)
            self.assertEqual(list(root.iterdir()), [])

    def test_false_approvals_never_execute(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for field in ("circuit_approval", "representation_approval", "execution_approval"):
                runner = FakeRunner()
                result = self.run_case(root, runner, **{field: replace(self.data[field], approved=False)})
                self.assertEqual(result.status, nr.RunStatus.BLOCKED)
                self.assertFalse(runner.calls)
            self.assertEqual(list(root.iterdir()), [])

    def test_different_workspaces_and_run_ids_preserve_artifact_identity(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            a, b = self.run_case(Path(first), FakeRunner()), self.run_case(Path(second), FakeRunner())
            self.assertEqual(a.artifact, b.artifact)
            self.assertNotEqual(a.working_file, b.working_file)
            self.assertEqual(a.working_file.read_bytes(), b.working_file.read_bytes())

    def test_same_workspace_new_run_does_not_overwrite_old_run(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.run_case(root, FakeRunner())
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            second = self.run_case(root, FakeRunner())
            self.assertNotEqual(first.working_file, second.working_file)
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_runner_failure_exit_code_exception_and_wrong_result(self):
        for mode in ("failure", "exit1", "exception", "wrong_result"):
            with self.subTest(mode=mode), TemporaryDirectory() as temp:
                runner = FakeRunner(mode)
                result = self.run_case(Path(temp), runner)
                self.assertEqual(result.status, nr.RunStatus.FAILED)
                self.assertEqual(len(runner.calls), 1)
                self.assertTrue(result.issues)
                self.assertIsNone(result.raw_file)

    def test_nonempty_raw_log_required_not_path_existence_only(self):
        for mode in ("none", "absent", "empty_raw", "empty_log", "same_file"):
            with self.subTest(mode=mode), TemporaryDirectory() as temp:
                result = self.run_case(Path(temp), FakeRunner(mode))
                self.assertEqual(result.status, nr.RunStatus.FAILED)
                self.assertTrue(result.working_file.exists())

    def test_evidence_outside_output_root_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            external = root / "unrelated.raw"
            external.write_bytes(b"user-owned evidence")
            result = self.run_case(root, FakeRunner("external", external))
            self.assertEqual(result.status, nr.RunStatus.FAILED)
            self.assertEqual(external.read_bytes(), b"user-owned evidence")

    def test_runner_input_tampering_detected_after_return(self):
        with TemporaryDirectory() as temp:
            result = self.run_case(Path(temp), FakeRunner("tamper"))
            self.assertEqual(result.status, nr.RunStatus.FAILED)
            self.assertIn("changed", result.issues[0].message)

    def test_saved_copy_rewrite_detected_before_runner(self):
        original = nr._write_new
        def write(root, path, content):
            original(root, path, content)
            if path.name == "execution.cir":
                path.write_bytes(content.replace(b"\n", b"\r\n"))
        with TemporaryDirectory() as temp, patch("netlist_runner._write_new", side_effect=write):
            runner = FakeRunner()
            result = self.run_case(Path(temp), runner)
            self.assertEqual(result.status, nr.RunStatus.FAILED)
            self.assertFalse(runner.calls)

    def test_invalid_or_missing_workspace_never_created(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for path in (str(root), Path("relative"), root / ".." / "escape", root / "missing"):
                runner = FakeRunner()
                result = self.run_case(path, runner)
                self.assertEqual(result.status, nr.RunStatus.BLOCKED)
                self.assertFalse(runner.calls)
            self.assertEqual(list(root.iterdir()), [])

    def test_symlink_and_junction_guard_portable_no_privileged_link_creation(self):
        # Deliberate filesystem seam: Windows CI cannot assume symlink privilege.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runner = FakeRunner()
            for method in ("is_symlink", "is_junction"):
                with self.subTest(method=method), patch.object(Path, method, autospec=True,
                        side_effect=lambda path: path == root / "simulation_input", create=method == "is_junction"):
                    result = self.run_case(root, runner)
                self.assertEqual(result.status, nr.RunStatus.BLOCKED)
                self.assertFalse(runner.calls)
            self.assertEqual(list(root.iterdir()), [])

    def test_resolved_escape_guard_no_write(self):
        with TemporaryDirectory() as temp, TemporaryDirectory() as outside:
            root, external = Path(temp), Path(outside)
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                if "simulation_input" in path.parts:
                    return external / "escape"
                return original(path, *args, **kwargs)
            runner = FakeRunner()
            with patch.object(Path, "resolve", autospec=True, side_effect=resolve):
                result = self.run_case(root, runner)
            self.assertEqual(result.status, nr.RunStatus.BLOCKED)
            self.assertFalse(runner.calls)
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(list(external.iterdir()), [])

    def test_collision_preserves_existing_data(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "simulation_input" / ("a" * 32)
            path.mkdir(parents=True)
            marker = path / "preserve.txt"
            marker.write_bytes(b"existing")
            runner = FakeRunner()
            with patch("netlist_runner.uuid4", return_value=SimpleNamespace(hex="a" * 32)):
                result = self.run_case(root, runner)
            self.assertEqual(result.status, nr.RunStatus.BLOCKED)
            self.assertFalse(runner.calls)
            self.assertEqual(marker.read_bytes(), b"existing")

    def test_write_error_preserves_failure_evidence_and_never_calls_runner(self):
        with TemporaryDirectory() as temp, patch("netlist_runner._write_new", side_effect=OSError("test write failure")):
            runner = FakeRunner()
            result = self.run_case(Path(temp), runner)
            self.assertEqual(result.status, nr.RunStatus.FAILED)
            self.assertFalse(runner.calls)
            self.assertTrue(list((Path(temp) / "simulation_input").iterdir()))

    def test_unicode_and_space_workspace_names(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "workspace with spaces 회로"
            root.mkdir()
            result = self.run_case(root, FakeRunner())
            self.assertEqual(result.status, nr.RunStatus.SUCCESS)

    def test_no_real_runner_imports_or_asc_wrapper_calls(self):
        with TemporaryDirectory() as temp, patch("subprocess.Popen", side_effect=AssertionError("simulator")), \
                patch("simulation_runner.run_ltspice", side_effect=AssertionError("ASC wrapper")):
            self.assertEqual(self.run_case(Path(temp), FakeRunner()).status, nr.RunStatus.SUCCESS)

    def test_runner_result_local_shape_and_status_invariants(self):
        for kwargs in ({"success": 1}, {"return_code": True}, {"raw_file": "fake.raw"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                nr.RunnerResult(**dict(dict(success=True, return_code=0, raw_file=None, log_file=None), **kwargs))


if __name__ == "__main__":
    unittest.main()
