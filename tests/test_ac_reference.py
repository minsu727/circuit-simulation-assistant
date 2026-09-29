import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from ac_reference import suggest_ac_references
from ui_helpers import review_defaults

PROJECT = Path(__file__).resolve().parents[1]
REQUEST = 'V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘.'
PREVIOUS = dict(target='V(vout)', reference='V(previous)', start_frequency='10 Hz',
                stop_frequency='1 MHz', points=100, sweep_type='Decade')


def source(name='V1', x=0, label='Vin', excitation='AC 1', symbol='voltage', orientation='R0'):
    flags = f'FLAG {x} 96 0\n' + (f'FLAG {x} 16 {label}\n' if label else '')
    return (flags + f'SYMBOL {symbol} {x} 0 {orientation}\n'
            f'SYMATTR InstName {name}\nSYMATTR Value SINE(0 1 1000)\n'
            + (f'SYMATTR Value2 {excitation}\n' if excitation else ''))


def asc(records):
    return ('Version 4\nSHEET 1 880 680\n' + records).encode()


def circuit():
    return ((PROJECT / 'tests/fixtures/dc_divider.asc').read_bytes()
            .replace(b' in', b' vin').replace(b' out', b' vout')
            .replace(b'SYMATTR Value 0', b'SYMATTR Value 0\nSYMATTR Value2 AC 1'))


class ACReferenceTests(unittest.TestCase):
    def test_single_numeric_ac_source_and_label(self):
        data = asc(source())
        before = bytes(data)
        hints = suggest_ac_references(data)
        self.assertEqual(hints.candidates, ('V(vin)',))
        self.assertEqual(hints.sources, ('V1',))
        self.assertFalse(hints.ambiguous)
        self.assertEqual(data, before)

    def test_dc_sine_only_and_comment_do_not_count(self):
        for excitation in ('', '; AC 1', 'AC 0', 'AC 0m'):
            with self.subTest(excitation=excitation):
                hints = suggest_ac_references(asc(source(excitation=excitation) + 'TEXT 0 200 Left 2 ;AC 1\n'))
                self.assertFalse(hints.candidates)
                self.assertFalse(hints.sources)

    def test_nonzero_spice_literals_and_phase(self):
        for value in ('AC 2 90', 'AC 1m', 'ac .5Meg', 'AC -1', 'AC 1e-3'):
            with self.subTest(value=value):
                self.assertEqual(suggest_ac_references(asc(source(excitation=value))).candidates, ('V(vin)',))

    def test_unconnected_label_is_not_invented(self):
        hints = suggest_ac_references(asc(source(label='') + 'FLAG 999 999 Vin\n'))
        self.assertFalse(hints.candidates)
        self.assertTrue(hints.ambiguous)
        self.assertIn('no unambiguous labeled input node', hints.notices[0])

    def test_two_ac_sources_preserve_all_candidates(self):
        hints = suggest_ac_references(asc(source(label='Vin1') + source('V2', 200, 'Vin2')))
        self.assertEqual(hints.candidates, ('V(vin1)', 'V(vin2)'))
        self.assertTrue(hints.ambiguous)

    def test_case_and_encoding_normalization(self):
        for label in ('Vin', 'VIN', 'vin'):
            for encoding in ('utf-8-sig', 'utf-16', 'latin-1'):
                data = asc(source(label=label)).decode().encode(encoding)
                self.assertEqual(suggest_ac_references(data).candidates, ('V(vin)',))

    def test_wire_chain_t_junction_and_label_on_segment(self):
        records = ('WIRE 0 16 100 16\nWIRE 50 16 50 -64\n'
                   'FLAG 50 -32 Vin\n' + source(label=''))
        self.assertEqual(suggest_ac_references(asc(records)).candidates, ('V(vin)',))

    def test_multiple_labels_require_choice(self):
        hints = suggest_ac_references(asc('WIRE 0 16 100 16\nFLAG 100 16 Second\n' + source()))
        self.assertEqual(hints.candidates, ('V(second)', 'V(vin)'))
        self.assertTrue(hints.ambiguous)

    def test_interior_crossing_and_diagonal_abstain(self):
        for wires in ('WIRE 0 16 100 16\nWIRE 50 -50 50 50\n',
                      'WIRE 0 16 100 116\n'):
            hints = suggest_ac_references(asc(wires + source()))
            self.assertFalse(hints.candidates)
            self.assertTrue(hints.ambiguous)

    def test_grounded_positive_or_floating_negative_abstain(self):
        for records in (source(label='0'), source().replace('FLAG 0 96 0', 'FLAG 0 96 Other')):
            hints = suggest_ac_references(asc(records))
            self.assertFalse(hints.candidates)
            self.assertTrue(hints.ambiguous)

    def test_unknown_magnitude_rotation_current_and_custom_abstain(self):
        records = [source(excitation='AC {amplitude}'), source(excitation='AC'),
                   source(orientation='R90'), source(orientation='M0'),
                   source('I1', symbol='current'), source(symbol='custom_voltage')]
        for record in records:
            with self.subTest(record=record):
                hints = suggest_ac_references(asc(record))
                self.assertFalse(hints.candidates)
                self.assertTrue(hints.ambiguous)
                self.assertTrue(hints.notices)

    def test_supported_plus_unresolved_excitation_stays_ambiguous(self):
        hints = suggest_ac_references(asc(source() + source('V2', 200, 'other', 'AC {amp}')))
        self.assertEqual(hints.candidates, ('V(vin)',))
        self.assertEqual(hints.sources, ('V1', 'V2'))
        self.assertTrue(hints.ambiguous)

    def test_malformed_and_duplicate_records_are_manual(self):
        for data in (b'invalid', asc('WIRE bad coordinates\n' + source()),
                     asc(source() + 'SYMATTR Value2 AC 2\n')):
            hints = suggest_ac_references(data)
            self.assertFalse(hints.candidates)
            self.assertTrue(hints.ambiguous)

    def test_existing_parser_priority_remains_unchanged(self):
        values, _ = review_defaults(REQUEST, 'AC', PREVIOUS)
        self.assertEqual(values['reference'], 'V(previous)')
        values, _ = review_defaults(REQUEST + ' Reference=V(explicit)', 'AC', PREVIOUS)
        self.assertEqual(values['reference'], 'V(explicit)')


class ACReferenceUITests(unittest.TestCase):
    def setUp(self):
        self.runner = patch('simulation_runner.run_ltspice').start()
        self.sweep = patch('parameter_sweep_execution.run_parameter_sweep').start()
        self.api = patch('llm_client.interpret_analysis').start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.runner.assert_not_called()
        self.sweep.assert_not_called()
        self.api.assert_not_called()

    def button(self, app, label):
        return next(button for button in app.button if button.label == label)

    def prepare(self, request=REQUEST, data=None, previous=None):
        data = circuit() if data is None else data
        app = AppTest.from_file(str(PROJECT / 'app.py'), default_timeout=45).run()
        if previous:
            digest = hashlib.sha256(data).hexdigest()
            app.session_state['successful_review_conditions'] = {digest: {'AC': dict(previous)}}
        app.file_uploader[0].set_value(('reference_test.asc', data, 'text/plain')).run()
        app.text_area[0].set_value(request).run()
        self.button(app, 'Analyze Request').click().run()
        self.assertFalse(app.exception)
        return app

    def test_candidate_click_target_suggestion_and_manual_change(self):
        before = {str(p) for folder in ('simulation_input', 'simulation_output') for p in (PROJECT / folder).rglob('*')}
        app = self.prepare()
        self.assertEqual(app.text_input(key='review_reference').value, '')
        self.assertTrue(self.button(app, 'Run Simulation').disabled)
        self.assertTrue(any('Did you mean V(vout)?' in w.value for w in app.warning))
        # Stale approval must be cleared even if injected before the callback.
        app.session_state['execution_approved'] = True
        self.button(app, 'Use suggestion: V(vin)').click().run()
        self.assertEqual(app.text_input(key='review_reference').value, 'V(vin)')
        self.assertFalse(app.checkbox(key='execution_approved').value)
        self.button(app, 'Use V(vout) for Target').click().run()
        app.checkbox(key='execution_approved').check().run()
        app.text_input(key='review_reference').set_value('V(manual)').run()
        self.assertFalse(app.checkbox(key='execution_approved').value)
        self.assertEqual(app.text_input(key='review_reference').value, 'V(manual)')
        self.assertFalse(any(b.label.startswith('Use suggestion:') for b in app.button))
        self.assertFalse(app.exception)
        self.assertEqual(before, {str(p) for folder in ('simulation_input', 'simulation_output') for p in (PROJECT / folder).rglob('*')})

    def test_explicit_reference_beats_history_and_schematic(self):
        app = self.prepare(REQUEST + ' Reference=V(explicit)', previous=PREVIOUS)
        self.assertEqual(app.text_input(key='review_reference').value, 'V(explicit)')
        self.assertFalse(any(b.label.startswith('Use suggestion:') for b in app.button))

    def test_previous_ac_reference_beats_schematic_in_parameter_review(self):
        app = self.prepare('R1을 1k, 2k로 바꿔가며 AC gain 비교', previous=PREVIOUS)
        self.assertEqual(app.text_input(key='review_reference').value, 'V(previous)')
        self.assertEqual(app.number_input(key='review_points').value, 100)
        self.assertFalse(any(b.label.startswith('Use suggestion:') for b in app.button))
        self.assertTrue(self.button(app, 'Run Parameter Sweep').disabled)

    def test_multiple_sources_have_buttons_but_no_selection(self):
        app = self.prepare(data=asc(source(label='Vin1') + source('V2', 200, 'Vin2')))
        self.assertEqual(app.text_input(key='review_reference').value, '')
        self.assertTrue(any('Possible AC references' in c.value for c in app.caption))
        self.button(app, 'Use suggestion: V(vin2)').click().run()
        self.assertEqual(app.text_input(key='review_reference').value, 'V(vin2)')
        self.assertFalse(app.checkbox(key='execution_approved').value)

    def test_missing_label_and_no_ac_keep_manual_entry(self):
        for data, notice in ((asc(source(label='')), True), (asc(source(excitation='')), False)):
            app = self.prepare(data=data)
            self.assertEqual(app.text_input(key='review_reference').value, '')
            self.assertFalse(any(b.label.startswith('Use suggestion:') for b in app.button))
            self.assertEqual(any('AC excitation source' in c.value for c in app.caption), notice)

    def test_upload_and_analysis_change_do_not_reuse_suggestion(self):
        app = self.prepare()
        self.button(app, 'Use suggestion: V(vin)').click().run()
        app.file_uploader[0].set_value(('other.asc', asc(source(excitation='')), 'text/plain')).run()
        self.button(app, 'Analyze Request').click().run()
        self.assertEqual(app.text_input(key='review_reference').value, '')
        app.text_area[0].set_value('Transient voltage gain').run()
        self.button(app, 'Analyze Request').click().run()
        self.assertFalse(any(b.label.startswith('Use suggestion:') for b in app.button))
        self.assertEqual(app.text_input(key='review_reference').value, '')

    def test_parameter_suggestion_also_invalidates_approval(self):
        app = self.prepare('R1을 1k, 2k로 바꿔가며 AC 10 Hz to 1 MHz gain 비교')
        app.session_state['parameter_approved'] = True
        self.button(app, 'Use suggestion: V(vin)').click().run()
        self.assertFalse(app.checkbox(key='parameter_approved').value)
        self.assertTrue(self.button(app, 'Run Parameter Sweep').disabled)


if __name__ == '__main__':
    unittest.main()
