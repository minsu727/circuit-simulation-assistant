"""Prevent smoke verification from passing after forced termination."""
import subprocess
import unittest
from unittest.mock import Mock, patch

from shutdown_checks import assert_graceful, stop_launcher


class ShutdownVerificationTests(unittest.TestCase):
    def run_stop(self, waits, code):
        proc = Mock(pid=123, returncode=code)
        proc.poll.return_value = None
        proc.wait.side_effect = waits
        with patch('shutdown_checks.process_state', return_value={'pid': 123}), patch('shutdown_checks.signal.CTRL_BREAK_EVENT', 1, create=True):
            result = stop_launcher(proc, timeout=45)
        return proc, result

    def test_graceful_exit(self):
        proc, report = self.run_stop([0], 0)
        assert_graceful(report)
        proc.terminate.assert_not_called()
        proc.send_signal.assert_called_once_with(1)
        self.assertIn('shutdown_requested_at', report)

    def test_timeout_cleanup_cannot_pass(self):
        proc, report = self.run_stop([subprocess.TimeoutExpired('app', 45), 1], 1)
        self.assertEqual(report['shutdown_failure'], 'TimeoutExpired')
        self.assertTrue(report['forced_termination'])
        proc.terminate.assert_called_once()
        with self.assertRaises(AssertionError):
            assert_graceful(report)

    def test_signal_delivery_failure_cannot_pass(self):
        proc = Mock(pid=123, returncode=0)
        proc.poll.return_value = None
        proc.send_signal.side_effect = OSError('not attached')
        with patch('shutdown_checks.process_state', return_value={}), patch('shutdown_checks.signal.CTRL_BREAK_EVENT', 1, create=True):
            report = stop_launcher(proc)
        self.assertEqual(report['shutdown_failure'], 'OSError')
        with self.assertRaises(AssertionError):
            assert_graceful(report)

    def test_nonzero_exit_cannot_pass(self):
        _, report = self.run_stop([1], 1)
        with self.assertRaises(AssertionError):
            assert_graceful(report)
