"""Optional Edge browser validation. No screenshots or actual simulation/API.

Reuses the production app via a synthetic-result harness. Writes geometry JSON
under ignored simulation_output, and stops only its own Streamlit server.
Run from the repository root: python tests/verify_ui_polish.py
Requires optional Playwright and installed Microsoft Edge (not core dependencies).
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright, expect
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'tests/ui_polish_preview.py',
                               '--server.headless=true', '--server.address=127.0.0.1', f'--server.port={port}',
                               '--browser.gatherUsageStats=false'], cwd=PROJECT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    data = ((PROJECT / 'tests/fixtures/dc_divider.asc').read_bytes().replace(b' in', b' vin').replace(b' out', b' vout')
            .replace(b'SYMATTR Value 0', b'SYMATTR Value 0\nSYMATTR Value2 AC 1'))
    records = []
    try:
        url = f'http://127.0.0.1:{port}'
        for _ in range(80):
            try:
                with urllib.request.urlopen(url + '/_stcore/health', timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                time.sleep(.25)
        else:
            raise RuntimeError('Streamlit startup timed out')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for width in (1280, 390):
                    for case, request in [
                        ('AC', 'AC V(out) 10 Hz to 1 MHz gain and -3 dB bandwidth'),
                        ('Transient', 'Transient V(vout) V(vin) 1 ms voltage gain output swing'),
                        ('DC', 'V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 V(vout). 3.55 V에서 V(vout)'),
                        ('Parameter', 'R1을 1k, 2k로 바꿔가며 AC V(vout) V(vin) 10 Hz to 1 MHz gain 비교')]:
                        page = browser.new_page(viewport={'width': width, 'height': 1000})
                        page.goto(url)
                        page.get_by_text('UI validation fixture · Synthetic results · LTspice and API calls blocked', exact=True).wait_for(timeout=45000)
                        if case == 'AC':
                            inspect(page, width, 'Initial', records)
                        page.locator('input[type=file]').set_input_files({'name': 'display.asc', 'mimeType': 'text/plain', 'buffer': data})
                        page.get_by_text('Schematic loaded', exact=True).wait_for()
                        page.get_by_label('Describe what simulation you want to run', exact=True).fill(request)
                        page.get_by_role('button', name='Analyze Request', exact=True).click()
                        run = page.get_by_role('button', name='Run Parameter Sweep' if case == 'Parameter' else 'Run Simulation', exact=True)
                        run.wait_for()
                        assert run.is_disabled()
                        if case == 'AC':
                            page.get_by_role('button', name='Use suggestion: V(vin)', exact=True).wait_for()
                            inspect(page, width, 'AC review / suggestions', records)
                            page.get_by_role('button', name='Use suggestion: V(vin)', exact=True).click()
                            expect(page.get_by_label('Reference / Input Signal', exact=True)).to_have_value('V(vin)')
                            page.get_by_role('button', name='Use V(vout) for Target', exact=True).click()
                            expect(page.get_by_label('Target Signal', exact=True)).to_have_value('V(vout)')
                            assert run.is_disabled()
                        checkbox = page.get_by_role('checkbox', name='I reviewed', exact=False)
                        expect(checkbox).to_be_enabled(timeout=10000)
                        # Streamlit's styled label covers its native checkbox.
                        # Exercise its accessible keyboard action, not a forced DOM click.
                        checkbox.focus()
                        checkbox.press('Space')
                        expect(checkbox).to_be_checked()
                        page.wait_for_function('Array.from(document.querySelectorAll("button")).some(b=>b.innerText.trim().startsWith("Run ")&&!b.disabled)')
                        run.click()
                        page.get_by_role('heading', name='Analysis Summary', exact=True).wait_for(timeout=45000)
                        page.wait_for_function('Array.from(document.querySelectorAll("[data-testid=stImage] img")).some(i=>i.complete&&i.naturalWidth>0)')
                        inspect(page, width, case + ' result', records)
                        assert not page.get_by_text('RAW:', exact=False).first.is_visible()
                        page.get_by_text('View structured summary', exact=True).wait_for()
                        assert not any(element.is_visible() for element in page.locator('[data-testid=stJson]').all())
                        assert 'schema_version' not in page.locator('body').inner_text()
                        if case == 'AC':
                            page.get_by_role('button', name='Prepare AI Interpretation', exact=True).click()
                            page.get_by_text('API key not configured', exact=True).wait_for()
                            assert page.get_by_role('button', name='Run AI Interpretation', exact=True).is_disabled()
                            page.wait_for_function('Array.from(document.querySelectorAll("[data-testid=stImage] img")).some(i=>i.complete&&i.naturalWidth>0)')
                            inspect(page, width, 'No API key', records)
                        page.close()
            finally:
                browser.close()
        output = PROJECT / 'simulation_output/prompt_013_browser_geometry.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(records, indent=2), encoding='utf-8')
        print(f'PASS: {len(records)} browser states; 1280/390px; graphs, hidden paths, approval and no-key checks; no screenshots saved')
    finally:
        server.terminate()
        server.wait(timeout=10)


def inspect(page, width, name, records):
    assert page.locator('[data-testid=stException]').count() == 0, name
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, width)
    geometry = page.locator('[data-testid=stImage] img').evaluate_all('''images=>images.map(i=>{
        const r=i.getBoundingClientRect(), row=i.closest('[data-testid="stHorizontalBlock"]').getBoundingClientRect();
        return {x:r.x,right:r.right,width:r.width,ratio:r.width/row.width,
                center:Math.abs(r.x+r.width/2-row.x-row.width/2),aspect:r.width/r.height,natural:i.naturalWidth/i.naturalHeight};})''')
    for image in geometry:
        assert image['x'] >= 0 and image['right'] <= width + 1, (name, image)
        assert image['center'] < 2 and abs(image['aspect'] - image['natural']) < .01, (name, image)
        if width == 1280:
            assert .80 <= image['ratio'] <= .85, (name, image)
    buttons = page.locator('[data-testid=stMain] button').evaluate_all('''buttons=>buttons.filter(b=>b.checkVisibility()).map(b=>{
        const r=b.getBoundingClientRect();return {name:b.innerText,x:r.x,right:r.right};})''')
    for button in buttons:
        assert button['x'] >= 0 and button['right'] <= width + 1, (name, button)
    assert buttons, (name, 'No visible buttons were inspected')
    metrics = page.locator('[data-testid=stMetric]').evaluate_all('''items=>items.map(i=>{
        const r=i.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,right:r.right};})''')
    if width == 390 and metrics:
        assert max(m['x'] for m in metrics) - min(m['x'] for m in metrics) < 2, (name, metrics)
    for metric in metrics:
        assert metric['x'] >= 0 and metric['right'] <= width + 1, (name, metric)
    visible = page.locator('body').inner_text()
    assert 'circuit-ui-preview-' not in visible, name
    records.append({'state': name, 'viewport': width, 'graphs': geometry, 'metrics': metrics, 'visible_buttons': len(buttons)})


if __name__ == '__main__':
    main()
