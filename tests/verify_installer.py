"""Opt-in real install/launch/uninstall/reinstall validation on Windows.

Requires the built Setup.exe, optional Playwright/Edge, and an unused current-user
installation/shortcut identity. Does not run LTspice or call any API. Reports and
logs stay in ignored installer_output. Never removes a pre-existing installation.
Run: python tests/verify_installer.py
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import winreg

import psutil

PROJECT = Path(__file__).resolve().parents[1]
NAME = 'Circuit Simulation Assistant'
APP_EXE = 'CircuitSimulationAssistant.exe'
UNINSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B6C44674-7140-4DA4-94A0-DF276A147F8B}_is1'


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folder_hashes(path):
    return {str(p.relative_to(path)): hash_file(p) for p in path.rglob('*') if p.is_file()}


def known_folder(csidl):
    buffer = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) != 0:
        raise RuntimeError('Windows shell folder lookup failed')
    return Path(buffer.value)


def registration():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return {name: winreg.QueryValueEx(key, name)[0] for name in ('DisplayName', 'DisplayVersion', 'InstallLocation', 'UninstallString')}
    except FileNotFoundError:
        return None


def running_exe(path):
    found = []
    for proc in psutil.process_iter(['pid', 'exe']):
        try:
            if proc.info['exe'] and Path(proc.info['exe']).resolve() == path.resolve():
                found.append(proc.pid)
        except (psutil.Error, OSError):
            pass
    return found


def shortcut_target(path):
    env = os.environ.copy()
    env['CSA_VERIFY_SHORTCUT'] = str(path)
    command = '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:CSA_VERIFY_SHORTCUT); Write-Output $s.TargetPath'
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], env=env,
                            capture_output=True, text=True, check=True)
    return Path(result.stdout.strip())


def stop_owned_process(proc):
    if proc.poll() is None:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            proc.terminate()
            proc.wait(timeout=10)


def main():
    output = PROJECT / 'installer_output'
    setup = output / 'CircuitSimulationAssistant-Setup.exe'
    portable = PROJECT / 'dist/CircuitSimulationAssistant'
    target = Path(os.environ['LOCALAPPDATA']) / 'Programs' / NAME
    executable = target / APP_EXE
    uninstaller = target / 'unins000.exe'
    group = known_folder(2) / NAME
    menu_link = group / (NAME + '.lnk')
    desktop_link = known_folder(0x10) / (NAME + '.lnk')
    assert setup.is_file() and (portable / APP_EXE).is_file(), 'Build portable and installer first.'
    assert not target.exists() and not group.exists() and not desktop_link.exists() and registration() is None, 'Existing installation or shortcuts found. Refusing to overwrite/uninstall user state.'
    assert target.resolve().is_relative_to((Path(os.environ['LOCALAPPDATA']) / 'Programs').resolve())
    baseline = folder_hashes(portable)
    user_data = Path(os.environ['LOCALAPPDATA']) / 'CircuitSimulationAssistant'
    data_before = {name: folder_hashes(user_data / name) for name in ('simulation_input', 'simulation_output')}
    sys.path.insert(0, str(PROJECT))
    from runtime_paths import locate_ltspice
    ltspice = locate_ltspice()
    assert ltspice is not None, 'Installed-app LTspice detection check needs an installed LTspice.'
    ltspice_hash = hash_file(ltspice)
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=PROJECT, text=True).splitlines()
    repo_before = {p: hash_file(PROJECT / p) for p in tracked if (PROJECT / p).is_file()}
    report = {'installer_mode': 'current user; default user Program Files location', 'simulation_run': False}
    owns_install = False
    with tempfile.TemporaryDirectory(prefix='csa-installer-check-') as cwd:
        def install(desktop, cycle):
            nonlocal owns_install
            owns_install = True
            args = [str(setup), '/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                    '/TASKS=desktopicon' if desktop else '/TASKS=', f'/LOG={output / (cycle + "-install.log")}']
            code = subprocess.run(args, cwd=cwd, creationflags=subprocess.CREATE_NO_WINDOW, timeout=180).returncode
            assert code == 0, ('Setup failed', code)
            assert executable.is_file() and uninstaller.is_file()
            assert registration()['DisplayVersion'] == '0.1.0'
            assert Path(registration()['InstallLocation']).resolve() == target.resolve()
            assert all(hash_file(target / name) == digest for name, digest in baseline.items())
            assert menu_link.is_file() and shortcut_target(menu_link).resolve() == executable.resolve()
            assert desktop_link.exists() == desktop
            if desktop:
                assert shortcut_target(desktop_link).resolve() == executable.resolve()
            assert not running_exe(executable), 'Silent setup must not launch the application.'
            report[cycle + '_install_exit'] = code
            report[cycle + '_payload_files_verified'] = len(baseline)
            report[cycle + '_desktop_shortcut'] = desktop
            report[cycle + '_start_menu_shortcut'] = True
            report[cycle + '_silent_no_launch'] = True

        def uninstall(cycle):
            code = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                                   f'/LOG={output / (cycle + "-uninstall.log")}'], cwd=cwd,
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=180).returncode
            assert code == 0, ('Uninstall failed', code)
            # Inno's self-deletion helper can outlive the initial process briefly.
            for _ in range(100):
                if not target.exists() and not group.exists() and not desktop_link.exists():
                    break
                time.sleep(.1)
            assert not target.exists() and not group.exists() and not desktop_link.exists()
            assert registration() is None
            report[cycle + '_uninstall_exit'] = code
            report[cycle + '_folder_and_shortcuts_removed'] = True

        try:
            install(False, 'first')
            # Reuse the proven executable UI check against the installed path.
            with (output / 'installed-ui.log').open('wb') as log:
                smoke = subprocess.run([sys.executable, '-X', 'utf8', str(PROJECT / 'tests/verify_portable.py'),
                                        '--exe', str(executable), '--open-browser'], cwd=cwd,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=180)
            assert smoke.returncode == 0, 'Installed UI smoke failed; inspect installed-ui.log'
            report['installed_app'] = json.loads((PROJECT / 'simulation_output/prompt_014a_smoke.json').read_text())

            # Check the real running-file guard without forcibly killing apps.
            with (output / 'running-launcher.log').open('wb') as log:
                proc = subprocess.Popen([str(executable), '--no-browser'], cwd=cwd, stdout=log,
                                        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                try:
                    url = None
                    for _ in range(240):
                        text = (output / 'running-launcher.log').read_text(encoding='utf-8', errors='replace')
                        match = re.search(r'Ready: (http://127\.0\.0\.1:\d+)', text)
                        if match:
                            url = match[1]
                            break
                        assert proc.poll() is None
                        time.sleep(.25)
                    assert url, 'Running guard test server did not become ready'
                    code = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                                           f'/LOG={output / "running-uninstall.log"}'], cwd=cwd,
                                          creationflags=subprocess.CREATE_NO_WINDOW, timeout=30).returncode
                    assert code != 0 and executable.is_file() and proc.poll() is None
                    assert 'Close Circuit Simulation Assistant' in (output / 'running-uninstall.log').read_text(errors='replace')
                    report['running_uninstall_blocked_exit'] = code
                finally:
                    stop_owned_process(proc)
                assert proc.returncode == 0
                try:
                    urllib.request.urlopen(url + '/_stcore/health', timeout=1)
                except OSError:
                    pass
                else:
                    raise AssertionError('Owned server remained after shutdown')
            uninstall('first')
            install(True, 'reinstall')
            uninstall('reinstall')
        finally:
            # Only the installation created after the preflight belongs to us.
            if owns_install and uninstaller.exists() and not running_exe(executable):
                try:
                    subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                                   cwd=cwd, creationflags=subprocess.CREATE_NO_WINDOW, timeout=180)
                except FileNotFoundError:
                    pass  # An already-finishing Inno self-deletion is not retried.
    assert folder_hashes(portable) == baseline
    assert all(hash_file(PROJECT / p) == digest for p, digest in repo_before.items())
    assert hash_file(ltspice) == ltspice_hash
    assert all(folder_hashes(user_data / name) == before for name, before in data_before.items())
    report.update(portable_unchanged=True, repository_unchanged=True, ltspice_unchanged=True, user_simulation_data_retained=True)
    (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
