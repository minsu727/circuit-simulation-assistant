"""Shared opt-in Windows smoke diagnostics. Forced cleanup is never a pass."""
from datetime import datetime, timezone
from pathlib import Path
import signal
import subprocess
import time


def process_state(pid):
    import psutil

    try:
        process = psutil.Process(pid)
        return {
            'pid': pid, 'parent_pid': process.ppid(),
            'children': [p.pid for p in process.children(recursive=True)],
            'listener_ports': [c.laddr.port for c in process.net_connections()
                               if c.status == psutil.CONN_LISTEN],
        }
    except psutil.NoSuchProcess:
        return {'pid': pid, 'exited': True}


def app_pids(executable):
    import psutil

    found = []
    for proc in psutil.process_iter(['pid', 'exe']):
        try:
            if proc.info['exe'] and Path(proc.info['exe']).resolve() == Path(executable).resolve():
                found.append(proc.pid)
        except (psutil.Error, OSError):
            pass
    return found


def stop_launcher(proc, timeout=45):
    """Signal only our CREATE_NEW_PROCESS_GROUP process; preserve failure evidence."""
    report = {'launch_pid': proc.pid, 'shutdown_timeout_seconds': timeout,
              'shutdown_requested_at': datetime.now(timezone.utc).isoformat(),
              'process_at_signal': process_state(proc.pid),
              'forced_termination': False, 'shutdown': 'already_exited'}
    started = time.monotonic()
    if proc.poll() is None:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            report['shutdown'] = 'CTRL_BREAK'
            proc.wait(timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            report['shutdown_failure'] = type(error).__name__
            report['process_at_timeout'] = process_state(proc.pid)
            report['forced_termination'] = True
            report['shutdown'] = 'terminate'
            proc.terminate()  # Test cleanup only; never production shutdown.
            proc.wait(timeout=10)
    report['shutdown_elapsed_seconds'] = time.monotonic() - started
    report['exe_exit_code'] = proc.returncode
    return report


def assert_graceful(report):
    assert report['shutdown'] == 'CTRL_BREAK', 'Launcher did not exit after the requested signal'
    assert not report['forced_termination'], 'Forced cleanup is not graceful shutdown'
    assert report['exe_exit_code'] == 0, 'Launcher exited with an error'
    assert report['shutdown_elapsed_seconds'] <= report['shutdown_timeout_seconds'], 'Shutdown deadline exceeded'
