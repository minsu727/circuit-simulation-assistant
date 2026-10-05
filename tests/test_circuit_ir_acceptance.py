"""M1G: static, independently authored acceptance contracts; no update mode.

Only public Circuit IR APIs are exercised. Load rejection is a separate outcome,
not a fabricated ValidationResult. No simulator, asset lookup or network access.
"""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import unittest
from unittest.mock import patch

import circuit_ir as ir


REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / 'tests' / 'fixtures' / 'circuit_ir'
CATALOG = FIXTURES / 'catalog.json'
DISTRIBUTION = {'VALID': 8, 'INVALID': 20, 'AMBIGUOUS': 10}


def read_json(path):
    return ir.decode_json(path.read_text(encoding='utf-8'))


def project_issue(issue, expected):
    # Prose is deliberately not frozen. Select only authored stable fields.
    values = {'code': issue.code, 'severity': issue.severity.value,
              'target_refs': list(issue.target_refs), 'field': issue.field}
    return {key: values[key] for key in expected}


def exercise(text):
    """Public pipeline, stopping before graph/validation when typed loading fails."""
    primitive = ir.decode_json(text)
    schema_issues = ir.validate_schema(primitive)
    loaded = ir.load_document(text)
    if loaded.document is None:
        return primitive, schema_issues, loaded, None, None
    graph = ir.build_graph(loaded.document)
    result = ir.validate_document(loaded.document)
    return primitive, schema_issues, loaded, graph, result


def contract(loaded, result, expected):
    if result is None:
        return {'outcome': 'load_rejected', 'issues': [project_issue(i, e)
                for i, e in zip(loaded.issues, expected['issues'])]}
    return {'profile': result.profile, 'technical_state': result.technical_state.value,
            'issues': [project_issue(i, e) for i, e in zip(result.issues, expected['issues'])],
            'completed_stages': list(result.completed_stages),
            'skipped_stages': dict(result.skipped_stages),
            'deferred_checks': list(result.deferred_checks)}


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read_json(CATALOG)
        cls.cases = cls.catalog['cases']

    def case_path(self, entry):
        path = PurePosixPath(entry['fixture_path'])
        self.assertFalse(path.is_absolute())
        self.assertNotIn('..', path.parts)
        self.assertNotIn('\\', str(path))
        self.assertNotIn(':', str(path))
        self.assertEqual(len(path.parts), 2)
        resolved = (FIXTURES / str(path)).resolve()
        self.assertTrue(resolved.is_relative_to(FIXTURES.resolve()))
        return resolved

    def assert_case(self, entry):
        path = self.case_path(entry)
        text = (path / 'circuit.json').read_text(encoding='utf-8')
        expected = read_json(path / 'expected.json')
        primitive, schema_issues, loaded, graph, result = exercise(text)
        issues = loaded.issues if result is None else result.issues
        # Length check prevents zip from hiding missing/additional findings.
        self.assertEqual(len(issues), len(expected['issues']))
        self.assertEqual(contract(loaded, result, expected), expected)
        self.assertEqual([i.issue_id for i in issues],
                         [f'issue_{i+1:04d}' for i in range(len(issues))])
        if entry.get('boundary') == 'typed_load':
            self.assertIsNone(loaded.document)
            self.assertIsNone(graph)
            self.assertIsNone(result)
            self.assertTrue(schema_issues)
            self.assertEqual(expected['outcome'], 'load_rejected')
            self.assertNotIn('technical_state', expected)
        else:
            self.assertFalse(schema_issues)
            self.assertFalse(loaded.issues)
            self.assertEqual(ir.document_to_dict(loaded.document), primitive)
            if 'expected_technical_state' in entry:
                self.assertEqual(result.technical_state.value, entry['expected_technical_state'])
            self.assertEqual(result.document_revision, loaded.document.metadata.revision)
        return primitive, loaded, graph, result

    def test_catalog_identity_and_paths(self):
        self.assertEqual(self.catalog['schema_version'], ir.SCHEMA_VERSION)
        self.assertEqual(self.catalog['profile'], 'm1-local-v1')
        ids = [c['case_id'] for c in self.cases]
        paths = [c['fixture_path'] for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(set(ids), {f'{prefix}{i:02d}' for prefix, count in
                                    [('V', 8), ('I', 20), ('A', 10)] for i in range(1, count+1)})
        for entry in self.cases:
            with self.subTest(case=entry['case_id']):
                path = self.case_path(entry)
                self.assertTrue((path / 'circuit.json').is_file())
                self.assertTrue((path / 'expected.json').is_file())
                self.assertTrue(entry['rationale'].strip())
                self.assertTrue(entry['stage'])
                self.assertTrue(entry['rules'])
                self.assertEqual(path.parts[-2], entry['category'])
                self.assertEqual(entry['category'].upper(), entry['expected_technical_state'])
                self.assertIn(entry['boundary'], ('validation', 'typed_load'))

    def test_planned_distribution_and_supplemental_inventory(self):
        self.assertEqual(len(self.cases), 38)
        self.assertEqual(self.catalog['planned_distribution'], DISTRIBUTION)
        self.assertEqual(dict(Counter(c['expected_technical_state'] for c in self.cases)), DISTRIBUTION)
        paths = [c['fixture_path'] for c in self.cases]
        supplemental = self.catalog['supplemental_fixtures']
        self.assertEqual([s['fixture_path'] for s in supplemental], ['valid/simple_source_resistor'])
        for entry in supplemental:
            self.assertTrue(entry['rationale'].strip())
            self.case_path(entry)
            paths.append(entry['fixture_path'])
        self.assertEqual(len(paths), len(set(paths)))
        circuits = {p.parent.relative_to(FIXTURES).as_posix() for p in FIXTURES.glob('*/*/circuit.json')}
        expectations = {p.parent.relative_to(FIXTURES).as_posix() for p in FIXTURES.glob('*/*/expected.json')}
        self.assertEqual(circuits, set(paths))
        self.assertEqual(expectations, set(paths))

    def test_independent_expected_states_and_primary_codes(self):
        for entry in self.cases:
            with self.subTest(case=entry['case_id']):
                expected = read_json(self.case_path(entry) / 'expected.json')
                codes = [i['code'] for i in expected['issues']]
                self.assertTrue(set(entry['primary_issue_codes']).issubset(codes))
                self.assertEqual(len(entry['primary_issue_codes']), len(set(entry['primary_issue_codes'])))
                if entry['boundary'] == 'typed_load':
                    self.assertEqual(expected['outcome'], 'load_rejected')
                    self.assertNotIn('completed_stages', expected)
                    self.assertNotIn('technical_state', expected)
                else:
                    self.assertEqual(expected['profile'], self.catalog['profile'])
                    self.assertEqual(expected['technical_state'], entry['expected_technical_state'])
                severities = {i['severity'] for i in expected['issues']}
                state = entry['expected_technical_state']
                if state == 'VALID':
                    self.assertTrue(severities.issubset({'WARNING', 'CONFIRMED'}))
                elif state == 'INVALID':
                    self.assertIn('ERROR', severities)
                else:
                    self.assertIn('AMBIGUOUS', severities)
                    self.assertNotIn('ERROR', severities)

    def test_all_38_public_pipeline_contracts(self):
        for entry in self.cases:
            with self.subTest(case=entry['case_id']):
                self.assert_case(entry)

    def test_preserved_supplemental_fixture(self):
        for entry in self.catalog['supplemental_fixtures']:
            self.assert_case(entry)

    def test_schema_rejection_never_calls_graph_or_validation(self):
        entry = next(c for c in self.cases if c['case_id'] == 'I19')
        with patch.object(ir, 'build_graph', side_effect=AssertionError('graph after rejection')), \
             patch.object(ir, 'validate_document', side_effect=AssertionError('validation after rejection')):
            self.assert_case(entry)

    def test_graph_gates_have_no_partial_topology_or_dependent_conclusions(self):
        ids = {'I01', 'I02', 'I06', 'I07', 'I08', 'I20'}
        for entry in self.cases:
            if entry['case_id'] not in ids:
                continue
            with self.subTest(case=entry['case_id']):
                _, _, graph, result = self.assert_case(entry)
                self.assertIsNone(graph.graph)
                self.assertEqual(graph.issues, result.issues)
                self.assertNotIn('component_value_source', result.completed_stages)
                self.assertNotIn('graph_dc', result.completed_stages)
                self.assertIn('component_value_source', dict(result.skipped_stages))

    def test_repeat_reports_include_stable_ids_order_and_stage_metadata(self):
        for entry in self.cases:
            with self.subTest(case=entry['case_id']):
                text = (self.case_path(entry) / 'circuit.json').read_text(encoding='utf-8')
                first = exercise(text)
                second = exercise(text)
                self.assertEqual(first[2], second[2])
                self.assertEqual(first[4], second[4])
                if first[3] is not None and first[3].graph is not None:
                    self.assertEqual(dict(first[3].graph.adjacency), dict(second[3].graph.adjacency))

    def test_typed_roundtrip_preserves_source_and_fresh_report(self):
        for entry in self.cases:
            if entry['boundary'] == 'typed_load':
                continue
            with self.subTest(case=entry['case_id']):
                primitive, loaded, _, result = self.assert_case(entry)
                before = ir.dump_document(loaded.document)
                reloaded = ir.load_document(before)
                self.assertEqual(reloaded.document, loaded.document)
                self.assertFalse(reloaded.issues)
                self.assertEqual(ir.validate_document(reloaded.document), result)
                self.assertEqual(ir.document_to_dict(loaded.document), primitive)
                self.assertEqual(ir.dump_document(loaded.document), before)

    def test_array_order_and_visual_geometry_cannot_change_canonical_topology(self):
        for entry in self.cases:
            if entry['boundary'] == 'typed_load':
                continue
            with self.subTest(case=entry['case_id']):
                primitive, _, graph, result = self.assert_case(entry)
                reordered = deepcopy(primitive)
                for key in ('components', 'pins', 'nets', 'connections', 'labels', 'ambiguities'):
                    reordered[key].reverse()
                # A06's authored junction position is evidence, never an edge.
                for visual in reordered['visual']['entities']:
                    visual['position'] = [17, 29]
                loaded = ir.load_document(json.dumps(reordered))
                self.assertIsNotNone(loaded.document)
                self.assertEqual(ir.validate_document(loaded.document), result)
                rebuilt = ir.build_graph(loaded.document)
                if graph.graph is None:
                    self.assertIsNone(rebuilt.graph)
                else:
                    self.assertEqual(dict(rebuilt.graph.adjacency), dict(graph.graph.adjacency))
                    for row in loaded.document.connections:
                        self.assertEqual(rebuilt.graph.net_for_pin(row.pin_id), row.net_id)

    def test_hash_seed_independence_in_separate_interpreters(self):
        script = '''import json, sys
sys.path.insert(0, 'tests')
from test_circuit_ir_acceptance import FIXTURES, read_json, exercise, contract
catalog = read_json(FIXTURES / 'catalog.json')
outputs = []
for entry in catalog['cases']:
    if entry['case_id'] not in ('V07', 'I18', 'A06'):
        continue
    path = FIXTURES / entry['fixture_path']
    expected = read_json(path / 'expected.json')
    _, _, loaded, _, result = exercise((path / 'circuit.json').read_text(encoding='utf-8'))
    outputs.append([contract(loaded, result, expected), [i.issue_id for i in result.issues]])
print(json.dumps(outputs, sort_keys=True))
'''
        outputs = []
        for seed in ('1', '731'):
            child = subprocess.run([sys.executable, '-X', 'utf8', '-c', script], cwd=REPO,
                                   env={**os.environ, 'PYTHONHASHSEED': seed}, capture_output=True,
                                   text=True, encoding='utf-8', timeout=30)
            self.assertEqual(child.returncode, 0, child.stderr)
            outputs.append(child.stdout)
        self.assertEqual(outputs[0], outputs[1])

    def test_static_fixtures_remain_read_only_without_snapshot_regeneration(self):
        files = sorted(FIXTURES.rglob('*.json'))
        def hashes():
            return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        before = hashes()
        import builtins
        import io
        real_open, real_io_open = builtins.open, io.open
        def guard(delegate):
            def checked(file, mode='r', *args, **kwargs):
                if any(c in mode for c in 'wax+'):
                    raise AssertionError('Acceptance tests cannot write or bless fixtures')
                return delegate(file, mode, *args, **kwargs)
            return checked
        with ExitStack() as stack:
            stack.enter_context(patch('builtins.open', side_effect=guard(real_open)))
            stack.enter_context(patch('io.open', side_effect=guard(real_io_open)))
            for name in ('write_text', 'write_bytes', 'touch', 'unlink', 'rename', 'replace'):
                stack.enter_context(patch.object(Path, name, side_effect=AssertionError('No fixture updates')))
            with self.assertRaises(AssertionError):
                CATALOG.write_text('not allowed', encoding='utf-8')
            for entry in self.cases:
                with self.subTest(case=entry['case_id']):
                    self.assert_case(entry)
        self.assertEqual(before, hashes())

    def test_local_valid_state_never_means_model_resolution_or_approval(self):
        for entry in self.cases:
            if entry['category'] != 'valid':
                continue
            with self.subTest(case=entry['case_id']):
                _, loaded, _, result = self.assert_case(entry)
                self.assertIn('model_catalog_resolution', result.deferred_checks)
                self.assertIn('human_approval', result.deferred_checks)
                self.assertIn('full_export_readiness', result.deferred_checks)
                self.assertEqual(loaded.document.validation_state.status.value, 'draft')
                self.assertFalse(hasattr(result, 'approved'))


if __name__ == '__main__':
    unittest.main()
