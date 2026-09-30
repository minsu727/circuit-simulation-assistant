"""Real build-script rejection paths; no mocked Inno compiler or installation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell build script')
class InstallerBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='csa-build-check-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.portable = self.root / 'portable'
        (self.portable / '_internal').mkdir(parents=True)
        # Preflight-only fixture: every test must reject before any compile.
        for name in ('CircuitSimulationAssistant.exe', '_internal/app.py', '_internal/python313.dll'):
            (self.portable / name).touch()
        self.powershell = Path(os.environ['SYSTEMROOT']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'

    def check_rejection(self, args, message, env=None):
        result = subprocess.run([str(self.powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(PROJECT / 'scripts/build_installer.ps1'), *args], cwd=self.root,
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(message, result.stdout)
        self.assertFalse((self.root / 'installer_output').exists())

    def test_missing_portable_explains_build_step(self):
        self.check_rejection(['-PortableDir', str(self.root / 'missing')], 'Run scripts/build_windows.ps1 first')

    def test_invalid_compiler_does_not_silently_fall_back(self):
        self.check_rejection(['-PortableDir', str(self.portable), '-ISCC', str(self.root / 'missing.exe')],
                             'Configured ISCC.exe was not found')

    def test_no_compiler_explains_installation(self):
        env = os.environ.copy()
        env.update(PATH=str(self.root), ISCC_EXE='', PROGRAMFILES=str(self.root),
                   LOCALAPPDATA=str(self.root))
        env['PROGRAMFILES(X86)'] = str(self.root)
        self.check_rejection(['-PortableDir', str(self.portable)], 'Install it from https://jrsoftware.org/isdl.php', env)

    def test_private_file_rejected_before_compiler(self):
        (self.portable / '.env').write_text('')
        self.check_rejection(['-PortableDir', str(self.portable), '-ISCC', str(self.root / 'missing.exe')],
                             'contains private or external simulation files')


if __name__ == '__main__':
    unittest.main()
