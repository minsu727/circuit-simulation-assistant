"""Opt-in real install/launch/uninstall/reinstall validation on Windows.

Requires the built Setup.exe, optional Playwright/Edge, and an unused current-user
installation/shortcut identity. Default mode does not run LTspice; optional
--release-checks runs one real AC fixture and isolated missing-dependency checks.
No API calls. Reports/logs stay in ignored installer_output. Never removes a
pre-existing installation. This developer-host check does not certify a clean VM.
Run: python tests/verify_installer.py [--icon-checks] [--release-checks] [--install-dir PATH]
"""
import ctypes
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import winreg

import psutil

from shutdown_checks import assert_graceful, stop_launcher

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
            return {name: winreg.QueryValueEx(key, name)[0] for name in ('DisplayName', 'DisplayVersion', 'InstallLocation', 'UninstallString', 'DisplayIcon')}
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


def shortcut_icon(path):
    env = os.environ.copy()
    env['CSA_VERIFY_SHORTCUT'] = str(path)
    command = '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:CSA_VERIFY_SHORTCUT); Write-Output $s.IconLocation'
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], env=env,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def assert_icon_location(location, executable):
    filename, index = location.rsplit(',', 1) if ',' in location else (location, '0')
    assert Path(filename.strip('"')).resolve() == executable.resolve(), 'Icon points to a different file'
    assert int(index.strip()) == 0, 'Icon must use the default executable group'


def stop_owned_process(proc, timeout=15):
    return stop_launcher(proc, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--icon-checks', action='store_true',
                        help='Verify official PE icons, shortcut IconLocation and uninstall DisplayIcon (requires build pefile).')
    parser.add_argument('--release-checks', action='store_true',
                        help='Also run missing-dependency/actual AC UI and PowerShell runtime checks on this host (not a clean VM).')
    parser.add_argument('--install-dir', type=Path,
                        help='Optional unused custom directory under the current user Programs folder.')
    args = parser.parse_args()
    output = PROJECT / 'installer_output'
    setup = output / 'CircuitSimulationAssistant-Setup.exe'
    portable = PROJECT / 'dist/CircuitSimulationAssistant'
    target = args.install_dir or Path(os.environ['LOCALAPPDATA']) / 'Programs' / NAME
    target = target.resolve()
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
    report = {'installer_mode': 'current user; custom location' if args.install_dir else 'current user; default user Program Files location',
              'simulation_run': args.release_checks, 'clean_vm_verified': False}
    if args.icon_checks:
        from verify_icons import verify_executable_icon, verify_shell_icon
        report['setup_icon'] = verify_executable_icon(setup)
        report['portable_icon'] = verify_executable_icon(portable / APP_EXE)
        for label, source in [('portable', portable / APP_EXE), ('setup', setup)]:
            report[label + '_shell_icon'] = verify_shell_icon(source, output / 'icon-validation' / (label + '.png'))
    generated_data = {name: {} for name in data_before}
    owns_install = False
    with tempfile.TemporaryDirectory(prefix='csa-installer-check-') as cwd:
        def install(desktop, cycle):
            nonlocal owns_install
            owns_install = True
            install_args = [str(setup), '/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                    '/TASKS=desktopicon' if desktop else '/TASKS=', f'/LOG={output / (cycle + "-install.log")}']
            if args.install_dir:
                install_args.append('/DIR=' + str(target))
            code = subprocess.run(install_args, cwd=cwd, creationflags=subprocess.CREATE_NO_WINDOW, timeout=180).returncode
            assert code == 0, ('Setup failed', code)
            assert executable.is_file() and uninstaller.is_file()
            expected_version = re.search(r'^AppVersion=(.+)$', (PROJECT / 'installer/CircuitSimulationAssistant.iss').read_text(), re.MULTILINE).group(1).strip()
            assert registration()['DisplayVersion'] == expected_version
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
            if args.icon_checks:
                from verify_icons import verify_executable_icon, verify_shell_icon
                report[cycle + '_installed_icon'] = verify_executable_icon(executable)
                report[cycle + '_uninstaller_icon'] = verify_executable_icon(uninstaller)
                assert_icon_location(shortcut_icon(menu_link), executable)
                if desktop:
                    assert_icon_location(shortcut_icon(desktop_link), executable)
                assert_icon_location(registration()['DisplayIcon'], executable)
                report[cycle + '_version'] = expected_version
                report[cycle + '_start_menu_icon'] = True
                report[cycle + '_desktop_icon'] = desktop
                report[cycle + '_uninstall_display_icon'] = True
                sources = [('installed', executable), ('start-menu', menu_link), ('uninstaller', uninstaller)]
                if desktop:
                    sources.append(('desktop', desktop_link))
                for label, source in sources:
                    report[cycle + '_' + label + '_shell_icon'] = verify_shell_icon(
                        source, output / 'icon-validation' / (cycle + '-' + label + '.png'))

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
                                        '--exe', str(executable), '--open-browser',
                                        *(['--shutdown-timeout', '45'] if args.icon_checks else [])], cwd=cwd,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=180)
            assert smoke.returncode == 0, 'Installed UI smoke failed; inspect installed-ui.log'
            report['installed_app'] = json.loads((PROJECT / 'simulation_output/prompt_014a_smoke.json').read_text())
            if args.icon_checks:
                assert report['installed_app']['shutdown'] == 'CTRL_BREAK' and report['installed_app']['exe_exit_code'] == 0, 'Installed icon smoke did not shut down normally'

            if args.release_checks:
                for label, option in [('missing', '--missing-ltspice'), ('simulation', '--simulate')]:
                    with (output / ('release-' + label + '.log')).open('wb') as log:
                        check = subprocess.run([sys.executable, '-X', 'utf8', str(PROJECT / 'tests/verify_portable.py'),
                                                '--exe', str(executable), option, '--shutdown-timeout', '45'], cwd=cwd,
                                               stdout=log, stderr=subprocess.STDOUT, timeout=240)
                    assert check.returncode == 0, 'Release UI check failed: ' + label
                    source = 'missing' if label == 'missing' else 'smoke'
                    report[label] = json.loads((PROJECT / f'simulation_output/prompt_014a_{source}.json').read_text())
                    assert report[label]['shutdown'] == 'CTRL_BREAK' and report[label]['exe_exit_code'] == 0, 'Graceful shutdown failed: ' + label
                report['missing_dependency_method'] = 'Child-process invalid LTSPICE_EXECUTABLE override; LTspice remains installed on host.'
                generated_data = {name: {p: digest for p, digest in folder_hashes(user_data / name).items()
                                         if p not in data_before[name]} for name in data_before}
                with (output / 'release-runtime.log').open('wb') as log:
                    check = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                            str(PROJECT / 'scripts/verify_release.ps1'), '-Setup', str(setup),
                                            '-InstalledExe', str(executable)], cwd=cwd,
                                           stdout=log, stderr=subprocess.STDOUT, timeout=120)
                assert check.returncode == 0, 'PowerShell runtime smoke failed; inspect release-runtime.log'
                report['runtime'] = json.loads((output / 'release-validation/release-smoke.json').read_text(encoding='utf-8-sig'))

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
                    report['running_guard_shutdown'] = stop_owned_process(proc, timeout=45 if args.icon_checks else 15)
                assert_graceful(report['running_guard_shutdown'])
                assert proc.returncode == 0
                try:
                    urllib.request.urlopen(url + '/_stcore/health', timeout=1)
                except OSError:
                    pass
                else:
                    raise AssertionError('Owned server remained after shutdown')
            uninstall('first')
            install(True, 'reinstall')
            if args.release_checks:
                with (output / 'release-reinstalled-ui.log').open('wb') as log:
                    check = subprocess.run([sys.executable, '-X', 'utf8', str(PROJECT / 'tests/verify_portable.py'),
                                            '--exe', str(executable)], cwd=cwd,
                                           stdout=log, stderr=subprocess.STDOUT, timeout=180)
                assert check.returncode == 0, 'Reinstalled executable smoke failed'
                report['reinstalled_app'] = json.loads((PROJECT / 'simulation_output/prompt_014a_smoke.json').read_text())
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
    assert all(folder_hashes(user_data / name) == {**before, **generated_data[name]} for name, before in data_before.items())
    report.update(portable_unchanged=True, repository_unchanged=True, ltspice_unchanged=True, user_simulation_data_retained=True)
    (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
