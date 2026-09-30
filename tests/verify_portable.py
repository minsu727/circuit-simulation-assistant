"""Opt-in Windows executable smoke check (requires optional Playwright/Edge).

python tests/verify_portable.py [--simulate] [--open-browser] [--missing-ltspice]
No API calls; --simulate explicitly runs the public resistor fixture through UI.
Only the process started here is stopped. No screenshots are saved.
"""
import argparse
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

PROJECT = Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright, expect
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=PROJECT / 'dist/CircuitSimulationAssistant/CircuitSimulationAssistant.exe')
    parser.add_argument('--simulate', action='store_true')
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--missing-ltspice', action='store_true')
    parser.add_argument('--shutdown-timeout', type=int, choices=(15, 45), default=15,
                        help='Grace period for the owned launcher; report forced fallback honestly.')
    args = parser.parse_args()
    assert args.exe.is_file(), 'Build the portable executable first.'
    assert not (args.missing_ltspice and args.simulate)
    output = PROJECT / 'simulation_output'
    output.mkdir(exist_ok=True)
    fixture = PROJECT / 'tests/fixtures/dc_divider.asc'
    before = hashlib.sha256(fixture.read_bytes()).hexdigest()
    data = fixture.read_bytes().replace(b'SYMATTR Value 0', b'SYMATTR Value 0\nSYMATTR Value2 AC 1')
    report = {'simulation_run': args.simulate, 'missing_ltspice_case': args.missing_ltspice}
    runtime_data = Path(os.environ['LOCALAPPDATA']) / 'CircuitSimulationAssistant'
    prior_runs = set((runtime_data / 'simulation_output').glob('*'))
    with tempfile.TemporaryDirectory(prefix='portable-cwd-') as cwd:
        env = os.environ.copy()
        for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'OPENAI_API_KEY'):
            env.pop(name, None)
        env['PATH'] = str(Path(os.environ['SYSTEMROOT']) / 'System32')
        if args.missing_ltspice:
            env['LTSPICE_EXECUTABLE'] = str(Path(cwd) / 'not-installed.exe')
        transcript = output / 'prompt_014a_exe_console.log'
        with transcript.open('wb') as console:
            proc = subprocess.Popen([str(args.exe.resolve())] + ([] if args.open_browser else ['--no-browser']),
                                    cwd=cwd, env=env, stdout=console, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            try:
                url = None
                for _ in range(240):
                    if proc.poll() is not None:
                        raise RuntimeError('Executable stopped during startup. Inspect local console log.')
                    match = re.search(r'Ready: (http://127\.0\.0\.1:\d+)', transcript.read_text(encoding='utf-8', errors='replace'))
                    if match:
                        url = match[1]
                        break
                    time.sleep(.25)
                assert url, 'Readiness not reached; inspect local console log.'
                with urllib.request.urlopen(url + '/_stcore/health', timeout=3) as response:
                    assert response.status == 200
                report.update(readiness=True, source_cwd_independent=True, development_path_removed=True)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel='msedge', headless=True)
                    try:
                        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
                        page.goto(url)
                        page.get_by_role('heading', name='Circuit Simulation Assistant', exact=True).wait_for(timeout=45000)
                        page.locator('input[type=file]').wait_for(state='attached')
                        assert page.locator('[data-testid=stException]').count() == 0
                        assert not re.search(r'[A-Z]:[\\/]|site-packages|\.venv', page.locator('body').inner_text())
                        report['initial_ui'] = True
                        if args.missing_ltspice:
                            page.get_by_text('LTspice was not found on this computer.', exact=False).wait_for()
                            report['missing_ltspice_message'] = True
                        else:
                            assert page.get_by_text('LTspice was not found on this computer.', exact=False).count() == 0
                            report['ltspice_detected'] = True
                        page.locator('input[type=file]').set_input_files({'name': 'portable_divider.asc', 'mimeType': 'text/plain', 'buffer': data})
                        page.get_by_text('Schematic loaded', exact=True).wait_for()
                        page.get_by_label('Describe what simulation you want to run', exact=True).fill('AC V(out) V(in) 10 Hz to 1 MHz gain and -3 dB bandwidth')
                        page.get_by_role('button', name='Analyze Request', exact=True).click()
                        run = page.get_by_role('button', name='Run Simulation', exact=True)
                        expect(run).to_be_disabled()
                        expect(page.get_by_label('Start Frequency', exact=True)).to_have_value('10 Hz')
                        expect(page.get_by_label('Stop Frequency', exact=True)).to_have_value('1 MHz')
                        report['review_and_approval_gate'] = True
                        if args.missing_ltspice:
                            checkbox = page.get_by_role('checkbox', name='I reviewed', exact=False)
                            checkbox.focus()
                            checkbox.press('Space')
                            expect(run).to_be_enabled()
                            run.click()
                            page.get_by_text('Technical details', exact=True).wait_for()
                            assert page.locator('[data-testid=stException]').count() == 0
                            assert set((runtime_data / 'simulation_output').glob('*')) == prior_runs
                            report['missing_dependency_run_blocked_without_crash'] = True
                        if args.simulate:
                            checkbox = page.get_by_role('checkbox', name='I reviewed', exact=False)
                            checkbox.focus()
                            checkbox.press('Space')
                            expect(run).to_be_enabled()
                            run.click()
                            page.get_by_text('Simulation completed', exact=True).wait_for(timeout=90000)
                            page.get_by_role('heading', name='Analysis Summary', exact=True).wait_for(timeout=45000)
                            assert page.locator('[data-testid=stException]').count() == 0
                            page.wait_for_function('Array.from(document.querySelectorAll("[data-testid=stImage] img")).some(i=>i.complete&&i.naturalWidth>0)')
                            metrics = page.locator('[data-testid=stMetric]').all_text_contents()
                            assert any('-6.021 dB' in value for value in metrics), metrics
                            page.get_by_text('View structured summary', exact=True).click()
                            # Summary data is the same structured evidence used in the app.
                            json_text = page.locator('[data-testid=stJson]').inner_text()
                            report['ac_gain_display'] = '-6.021 dB'
                            report['graph_rendered'] = True
                            report['raw_log_summary_visible'] = 'raw_file' in json_text and 'log_file' in json_text
                            assert report['raw_log_summary_visible']
                            report['actual_ac_run'] = True
                            generated = set((runtime_data / 'simulation_output').glob('*')) - prior_runs
                            assert len(generated) == 1, 'Expected one isolated simulation run'
                            run_folder = generated.pop()
                            raw = [p for p in run_folder.glob('*.raw') if not p.name.lower().endswith('.op.raw')]
                            log = list(run_folder.glob('*.log'))
                            assert raw and log and all(p.stat().st_size > 0 for p in raw + log)
                            from PyLTSpice import RawRead
                            import numpy as np
                            result = RawRead(str(raw[0]), verbose=False)
                            # RawRead loads binary traces lazily, as in read_ac_result.
                            frequency = result.get_trace('frequency').get_wave().real
                            gain = 20 * np.log10(np.abs(result.get_trace('V(out)').get_wave() / result.get_trace('V(in)').get_wave()))
                            assert np.isclose(frequency[0], 10) and np.isclose(frequency[-1], 1e6)
                            assert np.allclose(gain, 20 * np.log10(.5), atol=1e-5)
                            copy = runtime_data / 'simulation_input' / run_folder.name / 'portable_divider.asc'
                            assert '.ac dec 100 10 1Meg' in copy.read_text(encoding='utf-8')
                            report.update(raw_and_log_nonempty=True, raw_frequency_hz=[float(frequency[0]), float(frequency[-1])],
                                          raw_gain_db=float(np.median(gain)), applied_directive='.ac dec 100 10 1Meg')
                    finally:
                        browser.close()
                assert hashlib.sha256(fixture.read_bytes()).hexdigest() == before
                report['source_fixture_preserved'] = True
            finally:
                if proc.poll() is None:
                    try:
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                        proc.wait(timeout=args.shutdown_timeout)
                        report['shutdown'] = 'CTRL_BREAK'
                    except (OSError, subprocess.TimeoutExpired):
                        proc.terminate()
                        proc.wait(timeout=10)
                        report['shutdown'] = 'terminate'
                report['exe_exit_code'] = proc.returncode
            try:
                urllib.request.urlopen(url + '/_stcore/health', timeout=1)
            except OSError:
                report['server_stopped'] = True
            else:
                raise AssertionError('Server remained reachable after launcher exit')
    name = 'missing' if args.missing_ltspice else 'smoke'
    (output / f'prompt_014a_{name}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
