"""Browser-only production UI harness with synthetic results and blocked execution.

streamlit run tests/ui_polish_preview.py
No real LTspice/API calls. Generated graph evidence is temporary, not screenshots.
"""
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'tests'))
import streamlit as st
from llm_client import LLMConfig
from ui_polish_fixtures import display_results

ac, transient, dc, points = display_results()


def fake_run(upload, ac_conditions=None, *, transient_conditions=None, dc_conditions=None, approved=False):
    assert approved, 'The display fixture still requires approval.'
    directive = '.ac dec 100 10 1Meg' if ac_conditions is not None else '.tran 1m' if transient_conditions is not None else '.dc V2 3.4 3.7 10m'
    return evidence / 'fixture.raw', evidence / 'fixture.log', directive


def fake_sweep(*args, **kwargs):
    assert kwargs.get('approved')
    for i, point in enumerate(points):
        point.raw = str(evidence / f'point_{i}.raw')
        point.log = str(evidence / f'point_{i}.log')
        point.directive = '.ac dec 100 10 1Meg'
    return points


if 'ui_preview_evidence' not in st.session_state:
    st.session_state['ui_preview_evidence'] = tempfile.TemporaryDirectory(prefix='circuit-ui-preview-')
evidence = Path(st.session_state['ui_preview_evidence'].name)
with patch('simulation_runner.run_ltspice', side_effect=fake_run), \
        patch('parameter_sweep_execution.run_parameter_sweep', side_effect=fake_sweep), \
        patch('ac_result_analysis.read_ac_result', return_value=ac), \
        patch('transient_result_analysis.read_transient_result', return_value=transient), \
        patch('dc_result_analysis.read_dc_result', return_value=dc), \
        patch('llm_client.load_config', return_value=LLMConfig(provider='openai', api_key='')), \
        patch('llm_client.interpret_analysis', side_effect=AssertionError('API calls are disabled in this fixture')):
    runpy.run_path(str(PROJECT / 'app.py'), run_name='__main__')
st.caption('UI validation fixture · Synthetic results · LTspice and API calls blocked')
