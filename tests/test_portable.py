"""Launcher/discovery tests without real browser, server or simulator launches."""
import io
import asyncio
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import launcher
import runtime_paths as paths


class PortableTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows launcher loop')
    def test_server_loop_policy_is_scoped_and_restored_on_error(self):
        previous = asyncio.get_event_loop_policy()
        with self.assertRaisesRegex(RuntimeError, 'startup failure'):
            with launcher.server_event_loop():
                loop = asyncio.new_event_loop()
                try:
                    self.assertIsInstance(loop, asyncio.SelectorEventLoop)
                finally:
                    loop.close()
                raise RuntimeError('startup failure')
        self.assertIs(asyncio.get_event_loop_policy(), previous)

    def test_non_windows_policy_is_unchanged(self):
        previous = asyncio.get_event_loop_policy()
        with patch('launcher.os.name', 'posix'), launcher.server_event_loop():
            self.assertIs(asyncio.get_event_loop_policy(), previous)

    def test_port_falls_back_when_preferred_is_busy(self):
        with socket.socket() as busy:
            busy.bind(('127.0.0.1', 0))
            busy.listen()
            self.assertNotEqual(launcher.select_port(busy.getsockname()[1]), busy.getsockname()[1])

    def test_local_url_rejects_untrusted_values(self):
        self.assertEqual(launcher.local_url(8502), 'http://127.0.0.1:8502')
        for value in ('8501; command', 0, 65536, True):
            with self.assertRaises(ValueError):
                launcher.local_url(value)

    def test_unpacked_resource_is_cwd_independent(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(paths.locate_app_resource(), Path(paths.__file__).resolve().parent / 'app.py')

    def test_packaged_resource_and_writable_root_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'app.py').touch()
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', folder, create=True), patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'data')}):
                self.assertEqual(paths.locate_app_resource(), root / 'app.py')
                self.assertEqual(paths.simulation_data_root(), root / 'data/CircuitSimulationAssistant')

    def test_resource_traversal_or_missing_is_rejected(self):
        for name in ('../app.py', 'absent-resource.txt'):
            with self.assertRaises(FileNotFoundError):
                paths.locate_app_resource(name)

    def test_ltspice_local_common_install(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'Programs/ADI/LTspice/LTspice.exe'
            exe.parent.mkdir(parents=True)
            exe.touch()
            with patch.dict(os.environ, {'LOCALAPPDATA': folder, 'LTSPICE_EXECUTABLE': ''}), patch('runtime_paths.shutil.which', return_value=None):
                self.assertEqual(paths.locate_ltspice(), exe)

    def test_ltspice_program_files(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'ADI/LTspice/LTspice.exe'
            exe.parent.mkdir(parents=True)
            exe.touch()
            with patch.dict(os.environ, {'LOCALAPPDATA': str(Path(folder)/'local'), 'ProgramFiles': folder, 'LTSPICE_EXECUTABLE': ''}), patch('runtime_paths.shutil.which', return_value=None):
                self.assertEqual(paths.locate_ltspice(), exe)

    def test_explicit_invalid_path_does_not_fall_back(self):
        with patch.dict(os.environ, {'LTSPICE_EXECUTABLE': 'missing.exe; arbitrary-command'}), patch('runtime_paths.shutil.which') as lookup:
            self.assertIsNone(paths.locate_ltspice())
            lookup.assert_not_called()

    def test_configured_path_passed_as_path_not_shell_string(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'a & b.exe'
            exe.touch()
            with patch.dict(os.environ, {'LTSPICE_EXECUTABLE': str(exe)}), patch('PyLTSpice.LTspice.create_from') as create:
                paths.configure_ltspice()
                create.assert_called_once_with(exe)

    def test_missing_ltspice_is_specific_error(self):
        with patch('runtime_paths.locate_ltspice', return_value=None):
            with self.assertRaisesRegex(paths.LTspiceNotFoundError, 'Install LTspice separately'):
                paths.configure_ltspice()

    def test_approval_precedes_dependency_lookup(self):
        from simulation_runner import run_ltspice
        with patch('simulation_runner.configure_ltspice') as configure, patch('simulation_runner.is_packaged', return_value=True):
            with self.assertRaisesRegex(ValueError, 'approve'):
                run_ltspice(None, approved=False)
            configure.assert_not_called()

    def test_readiness_success_and_no_proxy(self):
        response = Mock(status=200)
        response.read.return_value = b'ok'
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch('launcher.urllib.request.build_opener', return_value=opener):
            self.assertTrue(launcher.wait_until_ready('http://127.0.0.1:8501', threading.Event()))
            opener.open.assert_called_once_with('http://127.0.0.1:8501/_stcore/health', timeout=1)

    def test_readiness_timeout_never_opens_browser(self):
        with patch('launcher.wait_until_ready', return_value=False), patch('launcher.webbrowser.open') as browser, patch('launcher._thread.interrupt_main') as stop, patch('sys.stdout', new_callable=io.StringIO):
            launcher.open_when_ready('http://127.0.0.1:8501', threading.Event(), timeout=0)
            browser.assert_not_called()
            stop.assert_called_once()
        self.assertFalse(launcher.wait_until_ready('http://127.0.0.1:8501', threading.Event(), timeout=0))

    def test_browser_failure_keeps_server_available(self):
        with patch('launcher.wait_until_ready', return_value=True), patch('launcher.webbrowser.open', side_effect=OSError), patch('launcher._thread.interrupt_main') as stop, patch('sys.stdout', new_callable=io.StringIO) as output:
            launcher.open_when_ready('http://127.0.0.1:8501', threading.Event())
            self.assertIn('Open this address manually', output.getvalue())
            stop.assert_not_called()

    def test_shutdown_cancels_browser_open(self):
        stopped = threading.Event()
        stopped.set()
        with patch('launcher.webbrowser.open') as browser, patch('launcher._thread.interrupt_main') as stop:
            launcher.open_when_ready('http://127.0.0.1:8501', stopped)
            browser.assert_not_called()
            stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
