"""Read a local ASC and exercise reference review; never run LTspice or an API.

Pass --asc <file> or use the existing local-only test_ltspice.py ASC_FILE config.
The config is parsed with AST, never imported/executed. No result files are written.
"""
import argparse
import ast
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ac_reference import suggest_ac_references
from streamlit.testing.v1 import AppTest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asc', type=Path)
    parser.add_argument('--expected', help='Expected candidate, for example V(vin)')
    args = parser.parse_args()
    source = args.asc
    if source is None:
        tree = ast.parse((PROJECT / 'test_ltspice.py').read_text(encoding='utf-8'))
        source = Path(next(ast.literal_eval(n.value) for n in tree.body
                           if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ASC_FILE' for t in n.targets)))
    original = source.read_bytes()
    hints = suggest_ac_references(original)
    assert hints.candidates, 'No supported candidate; manual reference entry is required.'
    if args.expected:
        assert args.expected in hints.candidates, hints
    before = {str(p) for folder in ('simulation_input', 'simulation_output') for p in (PROJECT / folder).rglob('*')}
    with patch('simulation_runner.run_ltspice') as runner, \
            patch('parameter_sweep_execution.run_parameter_sweep') as sweep, \
            patch('llm_client.interpret_analysis') as api:
        app = AppTest.from_file(str(PROJECT / 'app.py'), default_timeout=45).run()
        app.file_uploader[0].set_value(('local_validation.asc', original, 'text/plain')).run()
        app.text_area[0].set_value('V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘.').run()
        next(b for b in app.button if b.label == 'Analyze Request').click().run()
        assert not app.exception
        assert app.text_input(key='review_reference').value == ''
        assert next(b for b in app.button if b.label == 'Run Simulation').disabled
        candidate = args.expected or hints.candidates[0]
        # Explicit test-user action, never an app default.
        next(b for b in app.button if b.label == f'Use suggestion: {candidate}').click().run()
        assert app.text_input(key='review_reference').value == candidate
        assert not app.checkbox(key='execution_approved').value
        assert next(b for b in app.button if b.label == 'Run Simulation').disabled
        assert not app.exception
        runner.assert_not_called()
        sweep.assert_not_called()
        api.assert_not_called()
    assert source.read_bytes() == original
    assert before == {str(p) for folder in ('simulation_input', 'simulation_output') for p in (PROJECT / folder).rglob('*')}
    print('PASS: actual ASC sources=' + ', '.join(hints.sources) + '; candidates=' + ', '.join(hints.candidates))
    print('PASS: first-request preview, explicit selection, renewed approval, original bytes preserved')
    print('PASS: no simulator/API calls and no simulation input/output files created')


if __name__ == '__main__':
    main()
