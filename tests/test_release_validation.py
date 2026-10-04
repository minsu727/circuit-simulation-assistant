"""Artifact/preflight checks only; do not pretend to test a clean VM or AV."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]


def powershell_environment():
    # A pwsh -> Python -> powershell.exe chain otherwise inherits PS7 modules.
    # Let Windows PowerShell construct its own compatible default module paths.
    return {key: value for key, value in os.environ.items() if key.upper() != 'PSMODULEPATH'}


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell release helper')
class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='csa-release-check-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.setup = self.root / 'Setup.exe'
        self.report = self.root / 'report.json'
        self.powershell = Path(os.environ['SYSTEMROOT']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        # Hash fixture only: these bytes must never be executed.
        self.setup.write_bytes(b'artifact-integrity-fixture')

    def run_check(self, *args):
        result = subprocess.run([
            str(self.powershell),
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(PROJECT / 'scripts/verify_release.ps1'),
            '-Setup', str(self.setup), '-Report', str(self.report), *map(str, args),
        ], env=powershell_environment(), capture_output=True, timeout=30)
        self.output = self.diagnostics(result)
        return result.returncode, json.loads(self.report.read_text(encoding='utf-8-sig'))

    def diagnostics(self, result):
        return (f'executable: {self.powershell}\n'
                f'stdout:\n{result.stdout.decode(errors="replace")}\n'
                f'stderr:\n{result.stderr.decode(errors="replace")}')

    def test_artifact_hash_without_execution_or_clean_machine_claim(self):
        code, report = self.run_check()
        self.assertEqual(code, 0, self.output)
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
            str(self.powershell),
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(helper), '-Setup', str(self.setup),
        ], cwd=self.root, env=powershell_environment(), capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, self.diagnostics(result))
        report = self.root / 'installer_output/release-validation/release-smoke.json'
        self.assertEqual(json.loads(report.read_text(encoding='utf-8-sig'))['status'], 'passed')

    def test_ps7_module_path_cannot_break_windows_powershell_helper(self):
        # Reproduce a shared module name resolving to an incompatible PS7 module.
        modules = self.root / 'ps7-only-modules'
        shadow = modules / 'Microsoft.PowerShell.Utility'
        shadow.mkdir(parents=True)
        (shadow / 'Microsoft.PowerShell.Utility.psm1').write_text('', encoding='utf-8')
        (shadow / 'Microsoft.PowerShell.Utility.psd1').write_text(
            "@{ModuleVersion='7.0.0'; PowerShellVersion='7.0'; "
            "RootModule='Microsoft.PowerShell.Utility.psm1'; "
            "FunctionsToExport=@('Get-FileHash'); CmdletsToExport=@(); AliasesToExport=@()}",
            encoding='utf-8')
        inherited = str(modules) + os.pathsep + str(self.powershell.parent / 'Modules')
        with patch.dict(os.environ, {'PSModulePath': inherited}):
            # Confirm the trap is real before checking the corrected harness.
            broken = subprocess.run([
                str(self.powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(PROJECT / 'scripts/verify_release.ps1'),
                '-Setup', str(self.setup), '-Report', str(self.report),
            ], env=os.environ.copy(), capture_output=True, timeout=30)
            self.assertEqual(broken.returncode, 1, self.diagnostics(broken))
            failure = json.loads(self.report.read_text(encoding='utf-8-sig'))
            self.assertEqual(failure['error_type'], 'CommandNotFoundException')
            code, report = self.run_check()
        self.assertEqual(code, 0, self.output)
        self.assertEqual(report['installer']['sha256'], hashlib.sha256(self.setup.read_bytes()).hexdigest())
        self.assertFalse(report['simulation_run'])
        self.assertFalse(report['clean_vm_verified'])


if __name__ == '__main__':
    unittest.main()
