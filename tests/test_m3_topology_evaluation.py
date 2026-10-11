"""CI-safe prepared-observation reconstruction and independent truth comparison."""
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch
import circuit_image as ci
from circuit_image import models as m
from circuit_image.topology_evaluation import (evaluate_topology, TopologyReference,
    ReferenceReview, ReferenceComponent, ReferencePin, _matching)
from tests.m3d_helpers import replay, reference, REPLAYS, build, component, pin, wire
from tests.m3c_helpers import fixture_image, encode

ELIGIBLE=('divider','rc','missing_value','unreadable_value','rlc','nmos','pmos',
          'cross_open','cross_dot','shared_labels','rotated_sources','supply_unknown')
CASES=(*ELIGIBLE,'cross_ambiguous','near_gap','nmos_bulk_unknown','unsupported_bjt')


class TopologyEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared={n:replay(n) for n in CASES}
        # Input predictions are already constructed before opening any truth.
        cls.targets={n:reference(n) for n in CASES}

    def metric(self,name):
        h,s,image=self.prepared[name]
        result=evaluate_topology(h,s,image,self.targets[name])
        self.assertEqual(result.diagnostics,())
        return result.metrics

    def changed(self,name,edit):
        data=json.loads((REPLAYS/(name+'.json')).read_text(encoding='utf-8'))
        edit(data['observations'])
        image=fixture_image(name)
        parsed=ci.parse_observations(encode(data),image,provider=ci.STATIC_PROVIDER)
        self.assertIsNotNone(parsed.observation_set,parsed.diagnostics)
        result=ci.reconstruct_topology(parsed.observation_set,image)
        self.assertIsNotNone(result.hypothesis,result.diagnostics)
        return evaluate_topology(result.hypothesis,parsed.observation_set,image,self.targets[name]).metrics

    def test_twelve_unique_supported_topologies_match(self):
        for name in ELIGIBLE:
            with self.subTest(case=name):
                metric=self.metric(name)
                self.assertTrue(metric['exact_topology_match'],metric)
                self.assertEqual(metric['pin_assignment_correct'],metric['pin_assignment_total'])

    def test_all_cases_have_no_false_primary_joins(self):
        for name in CASES:
            with self.subTest(case=name):
                metric=self.metric(name)
                self.assertEqual(metric['false_added_connections'],[])
                self.assertEqual(metric['false_confident_junctions'],[])
                self.assertEqual(metric['unresolved_truth_join_claims'],[])

    def test_all_authored_required_reviews_surface_on_correct_target(self):
        for name in CASES:
            with self.subTest(case=name):
                metric=self.metric(name)
                self.assertEqual(metric['required_review_correct'],metric['required_review_total'],metric)

    def test_ambiguous_crossing_abstains_with_both_options(self):
        metric=self.metric('cross_ambiguous')
        self.assertIsNone(metric['exact_topology_match'])
        self.assertEqual(metric['appropriate_abstentions'],['jx'])
        h,_,_=self.prepared['cross_ambiguous']
        self.assertEqual({o.meaning for a in h.ambiguities for o in a.options},{'connected','separated'})

    def test_gap_manual_repair_is_not_primary_connection(self):
        metric=self.metric('near_gap')
        self.assertEqual(metric['appropriate_abstentions'],['gap'])
        self.assertIsNone(metric['exact_topology_match'])
        h,_,_=self.prepared['near_gap']
        self.assertEqual({o.meaning for a in h.ambiguities for o in a.options},{'touching','separated'})

    def test_missing_bulk_is_excluded_from_localization_not_review(self):
        metric=self.metric('nmos_bulk_unknown')
        self.assertEqual(metric['terminal_matches'],9)
        self.assertEqual(metric['required_review_correct'],2)
        self.assertIsNone(metric['exact_topology_match'])

    def test_unsupported_is_retained_without_supported_exact_denominator(self):
        h,_,_=self.prepared['unsupported_bjt']
        self.assertEqual(h.topology_state,ci.TopologyState.UNSUPPORTED)
        self.assertEqual(len(h.components),1)
        self.assertEqual(len(h.terminals),3)
        self.assertIsNone(self.metric('unsupported_bjt')['exact_topology_match'])

    def test_missing_quantities_do_not_prevent_topology_evaluation(self):
        for n in ('missing_value','unreadable_value','nmos','pmos'):
            h,_,_=self.prepared[n]
            self.assertEqual(h.topology_state,ci.TopologyState.RESOLVED)
            self.assertEqual(h.conversion_state,ci.TopologyState.INCOMPLETE)
            self.assertTrue(self.metric(n)['exact_topology_match'])

    def test_wrong_connected_crossing_reports_false_joins_and_merge(self):
        def edit(rows):
            next(o for o in rows if o['id']=='mark')['data']['interpretation']='connected'
        metric=self.changed('cross_open',edit)
        self.assertFalse(metric['exact_topology_match'])
        self.assertEqual(len(metric['false_added_connections']),4)
        self.assertEqual(metric['net_merge_errors'],1)
        self.assertEqual(metric['junction_errors'],['jx'])
        self.assertLess(metric['pin_assignment_correct'],metric['pin_assignment_total'])

    def test_wrong_separated_dot_reports_missing_joins_and_split(self):
        def edit(rows):
            next(o for o in rows if o['id']=='mark')['data']['interpretation']='separated'
        metric=self.changed('cross_dot',edit)
        self.assertEqual(len(metric['missing_connections']),4)
        self.assertEqual(metric['net_split_errors'],1)
        self.assertFalse(metric['exact_topology_match'])

    def test_false_confidence_is_distinct_from_correct_abstention(self):
        def edit(rows):
            mark=next(o for o in rows if o['id']=='mark')
            mark['data']['interpretation']='connected'
            mark['uncertainty']=dict(state='provisional',reasons=[],related_refs=[],alternatives=[])
        metric=self.changed('cross_ambiguous',edit)
        self.assertEqual(metric['false_confident_junctions'],['jx'])
        self.assertEqual(len(metric['unresolved_truth_join_claims']),4)
        self.assertEqual(metric['appropriate_abstentions'],[])
        self.assertEqual(metric['required_review_correct'],0)

    def test_mos_swap_cannot_be_hidden_by_net_renaming(self):
        def edit(rows):
            for o in rows:
                if o['id'] in ('M1.drain','M1.source'):
                    o['data']['role']={'drain':'source','source':'drain'}[o['data']['role']]
        metric=self.changed('nmos',edit)
        self.assertEqual(metric['terminal_role_errors'],['M1.drain','M1.source'])
        self.assertFalse(metric['exact_topology_match'])

    def test_source_polarity_is_judged_after_geometry(self):
        def edit(rows):
            for o in rows:
                if o['id'].startswith('V1.'):
                    o['data']['role']={'positive':'negative','negative':'positive'}[o['data']['role']]
        metric=self.changed('rotated_sources',edit)
        self.assertEqual(metric['terminal_role_errors'],['V1.negative','V1.positive'])
        self.assertFalse(metric['exact_topology_match'])

    def test_missing_pin_is_a_miss_not_denominator_reduction(self):
        metric=self.changed('rlc',lambda rows:rows.remove(next(o for o in rows if o['id']=='R1.b')))
        self.assertEqual(metric['pin_assignment_total'],8)
        self.assertEqual(metric['terminal_matches'],7)
        self.assertFalse(metric['exact_topology_match'])
        self.assertGreater(metric['net_split_errors'],0)

    def test_duplicate_component_is_unmatched_false_positive(self):
        def edit(rows):
            extra=json.loads(json.dumps(next(o for o in rows if o['id']=='R1')))
            extra['id']='duplicate';rows.append(extra)
        self.assertFalse(self.changed('rlc',edit)['exact_topology_match'])

    def test_duplicate_connected_pin_adds_spurious_pair_errors(self):
        def edit(rows):
            extra=json.loads(json.dumps(next(o for o in rows if o['id']=='R1.b')))
            extra['id']='duplicate_pin';rows.append(extra)
        metric=self.changed('rlc',edit)
        self.assertGreater(metric['spurious_connected_pairs'],0)
        self.assertFalse(metric['exact_topology_match'])

    def test_wrong_type_does_not_change_geometry_correspondence(self):
        def edit(rows):
            next(o for o in rows if o['id']=='R1')['data']['component_type']='inductor'
        metric=self.changed('rlc',edit)
        self.assertEqual(metric['component_matches'],4)
        self.assertEqual(metric['component_errors'],['R1'])

    def test_wrong_label_attachment_fails_anchor_compatible_net_match(self):
        def edit(rows): next(o for o in rows if o['id']=='vout')['data']['attachment_ref']='return1'
        metric=self.changed('rc',edit)
        self.assertFalse(metric['exact_topology_match'])
        self.assertIn('l_out',metric['label_errors'])

    def test_added_ground_does_not_get_ignored(self):
        def edit(rows):
            g=json.loads(json.dumps(next(o for o in rows if o['id']=='earth')))
            g['id']='extra_ground';g['geometry']['points']=[[180,280]];g['geometry']['bbox']=[158,280,44,40];rows.append(g)
        metric=self.changed('rc',edit)
        self.assertFalse(metric['exact_topology_match'])
        self.assertEqual(len(metric['extra_anchors']),1)

    def test_reference_identity_mismatch_rejected(self):
        h,s,image=self.prepared['rc']
        result=evaluate_topology(h,s,image,replace(self.targets['rc'],source_sha256='0'*64))
        self.assertIsNone(result.metrics)

    def test_unknown_reference_pin_and_duplicate_assignment_rejected(self):
        h,s,image=self.prepared['rc'];r=self.targets['rc']
        for con in ((('absent','vin'),),r.connections+(r.connections[0],)):
            self.assertIsNone(evaluate_topology(h,s,image,replace(r,connections=con)).metrics)

    def test_stale_prediction_and_unknown_claim_evidence_rejected(self):
        h,s,image=self.prepared['rc']
        for invalid in (replace(h,digest='0'*64),replace(h,claims=(replace(h.claims[0],evidence=('absent',)),))):
            self.assertIsNone(evaluate_topology(invalid,s,image,self.targets['rc']).metrics)

    def test_wrong_review_target_is_not_credited(self):
        h,s,image=self.prepared['nmos'];r=self.targets['nmos']
        metric=evaluate_topology(h,s,image,replace(r,reviews=(ReferenceReview('model_selection_required',('R1',)),))).metrics
        self.assertEqual(metric['required_review_correct'],0)

    def test_zero_denominators_are_null_not_perfect_accuracy(self):
        result,s,image=build([wire('w',(0,10),(100,10))])
        r=TopologyReference(s.source_sha256,(),(),(),(),(),(),(),(),False,True)
        metric=evaluate_topology(result.hypothesis,s,image,r).metrics
        self.assertIsNone(metric['pin_assignment_ratio'])
        self.assertIsNone(metric['exact_topology_match'])

    def test_matching_maximizes_cardinality_before_weight(self):
        result=_matching(('a','b'),('x','y'),{('a','x'):10,('a','y'):1,('b','x'):1})
        self.assertEqual(result,{'a':'y','b':'x'})

    def test_matching_maximizes_total_weight_then_lexicographic_tie(self):
        pairs={(a,b):1 for a in ('a','b') for b in ('x','y')}
        self.assertEqual(_matching(('b','a'),('y','x'),pairs),{'a':'x','b':'y'})
        pairs['a','y']=2
        self.assertEqual(_matching(('a','b'),('x','y'),pairs),{'a':'y','b':'x'})

    def test_reordered_reference_has_identical_metrics(self):
        h,s,image=self.prepared['pmos'];r=self.targets['pmos']
        reordered=replace(r,components=tuple(reversed(r.components)),pins=tuple(reversed(r.pins)),nets=tuple(reversed(r.nets)),connections=tuple(reversed(r.connections)),anchors=tuple(reversed(r.anchors)))
        self.assertEqual(evaluate_topology(h,s,image,r),evaluate_topology(h,s,image,reordered))

    def test_comparison_does_not_perform_file_network_or_process_io(self):
        h,s,image=self.prepared['rc'];r=self.targets['rc']
        with patch('builtins.open',side_effect=AssertionError('I/O')),patch('socket.socket',side_effect=AssertionError('network')),patch('subprocess.Popen',side_effect=AssertionError('process')):
            result=evaluate_topology(h,s,image,r)
        self.assertEqual(result.diagnostics,())
        json.dumps(result.metrics,allow_nan=False)

    def test_replay_catalog_hashes_and_separate_provenance(self):
        catalog=json.loads((REPLAYS/'catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['lane'],'prepared-observations')
        self.assertEqual(set(c['case_id'] for c in catalog['cases']),set(CASES))
        for c in catalog['cases']:
            self.assertEqual(hashlib.sha256((REPLAYS/c['file']).read_bytes()).hexdigest(),c['sha256'])
            self.assertEqual(c['truth_used_as_input'],False)
            self.assertTrue(self.metric(c['case_id']))
