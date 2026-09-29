import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from analysis_summary import build_analysis_summary, build_sweep_summary
from ui_presentation import workflow_labels
from ui_helpers import style_graph
from ac_result_analysis import gain_figure
from ui_polish_fixtures import display_results

PROJECT = Path(__file__).resolve().parents[1]
AC_REQUEST = 'AC V(out) 10 Hz to 1 MHz gain and -3 dB bandwidth'


class FinalUIPolishTests(unittest.TestCase):
    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def prepare(self, request=AC_REQUEST):
        app = AppTest.from_file(str(PROJECT / 'app.py'), default_timeout=45).run()
        data = ((PROJECT / 'tests/fixtures/dc_divider.asc').read_bytes()
                .replace(b' in', b' vin').replace(b' out', b' vout')
                .replace(b'SYMATTR Value 0', b'SYMATTR Value 0\nSYMATTR Value2 AC 1'))
        app.file_uploader[0].set_value(('review.asc', data, 'text/plain')).run()
        app.text_area[0].set_value(request).run()
        self.button(app, 'Analyze Request').click().run()
        self.assertFalse(app.exception)
        return app

    def test_initial_empty_states_are_truthful(self):
        app = AppTest.from_file(str(PROJECT / 'app.py')).run()
        self.assertFalse(app.exception)
        captions = '\n'.join(c.value for c in app.caption)
        self.assertIn('Upload needed', captions)
        self.assertIn('Results will appear here', captions)
        self.assertNotIn('Measured', captions)
        self.assertFalse(app.metric)

    def test_uploaded_file_info_and_request_step(self):
        app = self.prepare()
        self.assertTrue(any(t.value == 'review.asc' for t in app.text))
        self.assertTrue(any('KB · ASC' in c.value for c in app.caption))
        self.assertTrue(any('Request — Parsed' in c.value for c in app.caption))
        self.assertTrue(self.button(app, 'Run Simulation').disabled)

    def test_suggestions_review_and_approval_change_message(self):
        with patch('simulation_runner.run_ltspice') as runner:
            app = self.prepare()
            self.button(app, 'Use suggestion: V(vin)').click().run()
            self.button(app, 'Use V(vout) for Target').click().run()
            app.checkbox(key='execution_approved').check().run()
            self.assertFalse(self.button(app, 'Run Simulation').disabled)
            app.text_input(key='review_stop_frequency').set_value('2 MHz').run()
            self.assertFalse(app.checkbox(key='execution_approved').value)
            self.assertTrue(any('Settings changed.' in c.value for c in app.caption))
            self.assertTrue(self.button(app, 'Run Simulation').disabled)
            runner.assert_not_called()

    def test_result_metrics_and_evidence_expanders(self):
        ac, transient, dc, _ = display_results()
        cases = [(AC_REQUEST + ' Reference=V(vin)', 'ac_result_analysis.read_ac_result', ac, '.ac dec 100 10 1Meg', 'Low-Frequency Gain'),
                 ('Transient V(vout) V(vin) 1 ms voltage gain output swing', 'transient_result_analysis.read_transient_result', transient, '.tran 1m', 'Input Vpp'),
                 ('V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 V(vout). 3.55 V에서 V(vout)', 'dc_result_analysis.read_dc_result', dc, '.dc V2 3.4 3.7 10m', 'Value at V2 = 3.55 V')]
        for request, reader, result, directive, metric in cases:
            with self.subTest(metric=metric), tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'fixture.raw'
                with patch('simulation_runner.run_ltspice', return_value=(raw, raw.with_suffix('.log'), directive)), patch(reader, return_value=result):
                    app = self.prepare(request)
                    app.checkbox(key='execution_approved').check().run()
                    self.button(app, 'Run Simulation').click().run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any(m.label == metric for m in app.metric))
                    evidence = next(e for e in app.expander if e.label == 'Simulation Files / Evidence')
                    self.assertFalse(evidence.proto.expanded)
                    self.assertTrue(any(str(raw) in t.value for t in evidence.text))
                    self.assertFalse(next(e for e in app.expander if e.label == 'View structured summary').proto.expanded)
                    before = copy.deepcopy(app.session_state['completed_analysis_summary'])
                    app.run()
                    self.assertTrue(any(m.label == metric for m in app.metric))
                    self.assertTrue(app.get('image'))
                    self.assertEqual(app.session_state['completed_analysis_summary'], before)

    def test_summary_precision_and_failed_status_are_preserved(self):
        ac, _, _, _ = display_results()
        summary = build_analysis_summary('AC', ac)
        original = copy.deepcopy(summary)
        app = AppTest.from_file(str(PROJECT / 'app.py')).run()
        app.session_state['completed_analysis_summary'] = summary
        app.run()
        self.assertEqual(app.session_state['completed_analysis_summary'], original)
        rendered = json.loads(app.json[0].value)
        self.assertEqual(rendered, original)
        self.assertTrue(any('Confirmed Measurements' in m.value for m in app.markdown))
        failed = build_analysis_summary('AC', error=RuntimeError('failure'), status='Simulation Failed')
        self.assertIn('4 · Results — Simulation failed', workflow_labels(True, 'AC', True, True, failed))

    def test_parameter_comparison_and_evidence_remain_accessible(self):
        _, _, _, points = display_results()
        with tempfile.TemporaryDirectory() as directory:
            points[0].raw = str(Path(directory) / 'fixture.raw')
            points[0].log = str(Path(directory) / 'fixture.log')
            summary = build_sweep_summary(points, 'R1', 'AC')
            app = AppTest.from_file(str(PROJECT / 'app.py')).run()
            app.session_state['completed_analysis_summary'] = summary
            app.run()
            self.assertFalse(app.exception)
            self.assertGreater(len(app.dataframe), 0)
            for table in app.dataframe:
                self.assertNotIn('RAW', table.value.columns)
                self.assertNotIn('LOG', table.value.columns)
            evidence = next(e for e in app.expander if e.label == 'Point Details / Evidence')
            self.assertFalse(evidence.proto.expanded)
            self.assertTrue(any(points[0].raw in t.value for t in evidence.text))

    def test_no_key_explains_optional_ai_and_makes_no_call(self):
        ac, _, _, _ = display_results()
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai', 'OPENAI_API_KEY': ''}), patch('llm_client.interpret_analysis') as api:
            app = AppTest.from_file(str(PROJECT / 'app.py')).run()
            app.session_state['completed_analysis_summary'] = build_analysis_summary('AC', ac)
            app.run()
            self.button(app, 'Prepare AI Interpretation').click().run()
            self.assertTrue(self.button(app, 'Run AI Interpretation').disabled)
            self.assertTrue(any('Deterministic simulation analysis is fully available' in c.value for c in app.caption))
            self.assertFalse(next(e for e in app.expander if e.label == 'AI settings / Advanced').proto.expanded)
            api.assert_not_called()

    def test_failure_details_do_not_replace_friendly_error(self):
        with patch('simulation_runner.run_ltspice', side_effect=RuntimeError('Technical detail sentinel')):
            app = self.prepare(AC_REQUEST + ' Reference=V(vin)')
            app.checkbox(key='execution_approved').check().run()
            self.button(app, 'Run Simulation').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.error[0].value, 'LTspice simulation failed.')
            details = next(e for e in app.expander if e.label == 'Technical details')
            self.assertFalse(details.proto.expanded)
            self.assertIn('Technical detail sentinel', details.error[0].value)

    def test_long_legend_wraps_without_changing_curve_or_aspect(self):
        ac, _, _, _ = display_results()
        ac.target_name = 'V(' + 'long_signal_name_' * 8 + ')'
        figure = gain_figure(ac)
        before = figure.axes[0].lines[0].get_ydata().copy()
        aspect = figure.get_figheight() / figure.get_figwidth()
        style_graph(figure)
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(figure).draw()
        self.assertAlmostEqual(figure.get_figheight() / figure.get_figwidth(), aspect)
        self.assertTrue((before == figure.axes[0].lines[0].get_ydata()).all())
        labels = figure.axes[0].get_legend().get_texts()
        self.assertIn('\n', labels[0].get_text())
        for label in labels:
            box = label.get_window_extent(figure.canvas.get_renderer())
            self.assertGreaterEqual(box.x0, 0)
            self.assertLessEqual(box.x1, figure.bbox.x1)


if __name__ == '__main__':
    unittest.main()
