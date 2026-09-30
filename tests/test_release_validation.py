"""Artifact/preflight checks only; do not pretend to test a clean VM or AV."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell release helper')
class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='csa-release-check-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.setup = self.root / 'Setup.exe'
        self.report = self.root / 'report.json'
        # Hash fixture only: these bytes must never be executed.
        self.setup.write_bytes(b'artifact-integrity-fixture')

    def run_check(self, *args):
        result = subprocess.run([
            str(Path(os.environ['SYSTEMROOT']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(PROJECT / 'scripts/verify_release.ps1'),
            '-Setup', str(self.setup), '-Report', str(self.report), *map(str, args),
        ], capture_output=True, timeout=30)
        return result.returncode, json.loads(self.report.read_text(encoding='utf-8-sig'))

    def test_artifact_hash_without_execution_or_clean_machine_claim(self):
        code, report = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(report['installer']['sha256'], hashlib.sha256(self.setup.read_bytes()).hexdigest())
        self.assertEqual(report['installer']['bytes'], self.setup.stat().st_size)
        self.assertFalse(report['clean_vm_verified'])
        self.assertFalse(report['python_absence_verified'])
        self.assertFalse(report['simulation_run'])
        self.assertNotIn('localhost_health', report)

    def test_missing_setup_fails_without_leaking_local_path(self):
        self.setup.unlink()
        code, report = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_missing_installed_exe_is_not_a_successful_smoke(self):
        code, report = self.run_check('-InstalledExe', self.root / 'CircuitSimulationAssistant.exe')
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('localhost_health', report)

    def test_standalone_default_report_from_unrelated_directory(self):
        scripts = self.root / 'scripts'
        scripts.mkdir()
        helper = scripts / 'verify_release.ps1'
        helper.write_bytes((PROJECT / 'scripts/verify_release.ps1').read_bytes())
        result = subprocess.run([
            str(Path(os.environ['SYSTEMROOT']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(helper), '-Setup', str(self.setup),
        ], cwd=self.root, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        report = self.root / 'installer_output/release-validation/release-smoke.json'
        self.assertEqual(json.loads(report.read_text(encoding='utf-8-sig'))['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
