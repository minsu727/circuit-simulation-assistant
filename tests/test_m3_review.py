import json
import unittest
from dataclasses import replace
from pathlib import Path
from hashlib import sha256
from circuit_ir import models as ir
from circuit_image import review_models as r
from circuit_image.review import validate_review, load_review
from circuit_image.review_serialization import dump_review, correction_from_dict, correction_to_dict
from tests.m3e_helpers import ReviewCase, CASES, quantity


class ReviewTests(unittest.TestCase):
    def synthetic(self, rows):
        from tests.m3d_helpers import build
        result,observations,image=build(rows)
        return ReviewCase(source=(result.hypothesis,observations,image))

    def test_ambiguous_pin_contact_explicit_option(self):
        from tests.m3d_helpers import component,pin,wire,junction
        c=self.synthetic([component(),pin('p','R1','a',(50,50)),
            wire('h',(0,50),(100,50)),wire('v',(50,0),(50,100)),
            junction('mark',('h','v'),(50,50),'separated')])
        self.assertIsNone(c.net('p'))
        a=next(a for a in c.h.ambiguities if a.kind=='PIN_CONTACT_UNCLEAR')
        option=next(o for o in a.options if o.meaning=='attached' and c.ids['h'] in o.subjects)
        c.edit(r.ChooseTopology(a.id,option.id));self.assertEqual(c.net('p'),c.net('h'))
        self.assertNotEqual(c.net('p'),c.net('v'))

    def test_ambiguous_ground_explicit_attachment(self):
        from tests.m3d_helpers import wire,ground
        c=self.synthetic([wire('w',(0,100),(100,100)),ground(state='ambiguous',reasons=('ground_unclear',))])
        self.assertIsNone(c.net('g'));c.edit(r.SetGround(c.ids['g'],c.net('w')))
        self.assertNotIn('GROUND_ATTACHMENT_UNRESOLVED',{i.code for i in c.session.current.issues})

    def test_terminal_ownership_not_resolved_by_role(self):
        from tests.m3d_helpers import component,pin,wire
        p=pin('p','R1','a',(10,10),state='ambiguous',reasons=('mos_role_unclear',),
              alternatives=(dict(id='original',data=dict(component_ref='R1',role='a')),
                            dict(id='owner',data=dict(component_ref='R2',role='a'))))
        c=self.synthetic([component(),component('R2',box=(100,20,40,20)),p,wire('w',(0,10),(50,10))])
        c.edit(r.SetTerminalRole(c.ids['p'],ir.PinRole.A))
        self.assertIn('TERMINAL_OWNER_REQUIRED',{i.code for i in c.session.current.issues})
        c.edit(r.SetTerminalOwner(c.ids['p'],c.ids['R2']))
        self.assertNotIn('TERMINAL_OWNER_REQUIRED',{i.code for i in c.session.current.issues})

    def test_changed_partition_cannot_keep_conflicting_review_choice(self):
        c=ReviewCase('cross_ambiguous');c.choose('separated')
        c.edit(r.MergeNets((c.net('horizontal0'),c.net('vertical0'))))
        self.assertIn('TOPOLOGY_RESOLUTION_CONFLICT',{i.code for i in c.session.current.issues})
        self.assertIsNone(c.confirm_result().session);c.choose('connected');c.confirm()

    def test_label_equivalence_explicit(self):
        c=ReviewCase('shared_labels');labels=tuple(i for i,_ in c.session.current.snapshot.labels)
        from circuit_image.topology import label_identity
        pairs={}
        for i,text in c.session.current.snapshot.labels:pairs.setdefault(label_identity(text),[]).append(i)
        pair=next(tuple(p) for p in pairs.values() if len(p)>=2)
        c.edit(r.LabelEquivalence(pair,True));c.confirm()

    def test_all_prepared_cases_start_and_preserve_sources(self):
        root=Path(__file__).parent/'fixtures'
        before={str(p):sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        for name in CASES:
            with self.subTest(name=name):
                c=ReviewCase(name)
                self.assertEqual(validate_review(c.session,**c.bindings),())
                self.assertIsNone(c.session.confirmation)
                self.assertEqual(c.session.initial_topology,c.h)
        self.assertEqual(before,{str(p):sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()})

    def test_initial_revision_reproducible(self):
        self.assertEqual(dump_review(ReviewCase().session),dump_review(ReviewCase().session))

    def test_crossing_requires_decision(self):
        c=ReviewCase('cross_ambiguous')
        self.assertIsNone(c.confirm_result().session)
        c.choose('connected');self.assertFalse(c.session.current.issues);c.confirm()

    def test_ambiguous_crossing_separated(self):
        c=ReviewCase('cross_ambiguous');c.choose('separated');c.confirm()
        self.assertNotEqual(c.net('horizontal0'),c.net('vertical0'))

    def test_non_junction_remains_separate(self):
        c=ReviewCase('cross_open');c.edit(r.ConfirmContact(c.ids['mark'],False));c.confirm()
        self.assertNotEqual(c.net('horizontal0'),c.net('vertical0'))

    def test_explicit_junction(self):
        c=ReviewCase('cross_dot');c.edit(r.ConfirmContact(c.ids['mark'],True));c.confirm()
        self.assertEqual(c.net('horizontal0'),c.net('vertical0'))

    def test_gap_never_auto_connected(self):
        c=ReviewCase('near_gap');self.assertNotEqual(c.net('lower0'),c.net('upper0'))
        c.choose('separated');self.assertNotEqual(c.net('lower0'),c.net('upper0'))
        self.assertIsNone(c.confirm_result().session)  # still unresolved label

    def test_gap_explicitly_connected(self):
        c=ReviewCase('near_gap');c.choose('touching')
        c.edit(r.SetLabel(c.ids['vout'],'vout',c.net('upper0')));c.confirm()
        self.assertEqual(c.net('lower0'),c.net('upper0'))

    def test_wrong_pin_association_corrected(self):
        c=ReviewCase();pin=c.ids['R1.a'];original=c.net('R1.a');other=c.net('R1.b')
        c.edit(r.ConnectPin(pin,other));self.assertEqual(c.net('R1.a'),other)
        c.edit(r.ConnectPin(pin,original));self.assertEqual(c.net('R1.a'),original)

    def test_disconnect_requires_new_assignment(self):
        c=ReviewCase();c.edit(r.ConnectPin(c.ids['R1.a'],None))
        self.assertIsNone(c.confirm_result().session)

    def test_value_change_keeps_observations(self):
        c=ReviewCase();old=c.o;c.edit(r.SetValue(c.ids['R1'],quantity('2k')))
        self.assertEqual(c.o,old)
        component=next(v for v in c.session.current.snapshot.components if v.id==c.ids['R1'])
        self.assertEqual(component.value.literal,'2k')
        self.assertEqual(component.value.si_value,'2000')

    def test_missing_value_manual(self):
        c=ReviewCase('missing_value');self.assertIsNone(c.confirm_result().session)
        c.edit(r.SetValue(c.ids['C1'],quantity('10n','F')));c.confirm()

    def test_unreadable_value_manual(self):
        c=ReviewCase('unreadable_value');c.edit(r.SetValue(c.ids['C1'],quantity('10n','F')));c.confirm()

    def test_source_polarity_atomic_swap(self):
        c=ReviewCase('rotated_sources');pins=[p for p in c.session.current.snapshot.pins if p.component_id==c.ids['V1']]
        c.edit(*(r.SetTerminalRole(p.id,ir.PinRole.NEGATIVE if p.role is ir.PinRole.POSITIVE else ir.PinRole.POSITIVE) for p in pins))
        self.assertFalse(c.session.current.issues);c.confirm()

    def test_source_configuration_explicit(self):
        c=ReviewCase();source=ir.SourceConfiguration(quantity('5','V'),ir.ACConfiguration(quantity('1','V'),quantity('0','deg')),ir.Waveform(ir.WaveformKind.NONE,()))
        c.edit(r.SetSource(c.ids['V1'],source));c.confirm()

    def test_source_expression_rejected(self):
        c=ReviewCase();bad=ir.Quantity('.param X=1','1','V',ir.ValueGrammar.SPICE)
        source=ir.SourceConfiguration(bad,None,ir.Waveform(ir.WaveformKind.NONE,()))
        self.assertIsNone(c.apply(r.SetSource(c.ids['V1'],source)).session)

    def test_mos_model_not_guessed(self):
        c=ReviewCase('nmos');self.assertIsNone(c.confirm_result().session);c.mos();c.confirm()

    def test_pmos_requires_matching_profile(self):
        c=ReviewCase('pmos');self.assertIsNone(c.apply(r.SetMOSModel(c.ids['M1'],'repository_demo_nmos',quantity('10u','m'),quantity('1u','m'))).session)
        c.mos('repository_demo_pmos');c.confirm()

    def test_mos_role_correction_explicit(self):
        c=ReviewCase('nmos');c.mos()
        c.edit(r.SetTerminalRole(c.ids['M1.drain'],ir.PinRole.SOURCE),r.SetTerminalRole(c.ids['M1.source'],ir.PinRole.DRAIN));c.confirm()

    def test_missing_bulk_not_tied_automatically(self):
        c=ReviewCase('nmos_bulk_unknown');c.mos();self.assertIsNone(c.net('M1.bulk'))
        self.assertIsNone(c.confirm_result().session)
        c.edit(r.ConnectPin(c.ids['M1.bulk'],c.net('M1.source')));c.confirm()

    def test_unsupported_acknowledgement_is_not_full_confirmation(self):
        c=ReviewCase('unsupported_bjt');c.edit(r.MarkUnsupported(c.ids['Q1']))
        self.assertIsNone(c.confirm_result().session)
        self.assertIsNone(c.promote().document)

    def test_unsupported_cannot_be_fake_supported(self):
        c=ReviewCase('unsupported_bjt')
        self.assertIsNone(c.apply(r.SetComponentType(c.ids['Q1'],ir.ComponentType.NMOS)).session)

    def test_supply_definition_never_invented(self):
        c=ReviewCase('supply_unknown');self.assertIsNone(c.confirm_result().session)
        self.assertFalse(c.session.current.snapshot.ground_ids)

    def test_retaining_issue_does_not_waive_it(self):
        c=ReviewCase('missing_value');c.edit(r.RetainIssue(c.session.current.issues[0].id))
        self.assertTrue(c.session.current.snapshot.retained_issues)
        self.assertIsNone(c.confirm_result().session)

    def test_duplicate_writes_atomic_rejection(self):
        c=ReviewCase();old=c.session
        result=c.apply(r.SetReference(c.ids['R1'],'R3'),r.SetReference(c.ids['R1'],'R4'))
        self.assertIsNone(result.session);self.assertEqual(result.diagnostics[0].code,'REVIEW_CORRECTION_CONFLICT');self.assertEqual(c.session,old)

    def test_type_and_unsupported_contradiction(self):
        c=ReviewCase();result=c.apply(r.SetComponentType(c.ids['R1'],ir.ComponentType.RESISTOR),r.MarkUnsupported(c.ids['R1']))
        self.assertEqual(result.diagnostics[0].code,'REVIEW_CORRECTION_CONFLICT')

    def test_wrong_reference_rejected(self):
        c=ReviewCase();self.assertIsNone(c.apply(r.ConnectPin('missing',c.net('R1.a'))).session)

    def test_stale_revision_rejected(self):
        c=ReviewCase();base=c.session.current.digest;c.edit(r.SetValue(c.ids['R1'],quantity('2k')))
        self.assertEqual(c.apply(r.SetValue(c.ids['R1'],quantity('3k')),base=base).diagnostics[0].code,'REVIEW_STALE_REVISION')

    def test_correction_invalidates_confirmation_even_noop(self):
        c=ReviewCase();c.confirm();old=c.session.confirmation;c.edit(r.SetReference(c.ids['R1'],'R1'))
        self.assertIsNone(c.session.confirmation);self.assertNotEqual(c.session.current.digest,old.revision_sha256)

    def test_copied_confirmation_rejected(self):
        c=ReviewCase();c.confirm();old=c.session.confirmation;c.edit(r.SetValue(c.ids['R1'],quantity('2k')))
        fake=replace(c.session,confirmation=old)
        self.assertEqual(validate_review(fake,**c.bindings)[0].code,'REVIEW_CONFIRMATION_STALE')

    def test_all_claims_explicitly_reviewed(self):
        c=ReviewCase();self.assertIsNone(c.confirm_result(reviewed_claim_ids=()).session)
        self.assertIsNone(c.confirm_result(decision=True).session)

    def test_archive_never_restores_confirmation(self):
        c=ReviewCase();c.confirm();result=load_review(dump_review(c.session),**c.bindings)
        self.assertFalse(result.diagnostics);self.assertIsNone(result.session.confirmation)

    def test_archive_unknown_fields_and_versions_rejected(self):
        c=ReviewCase();base=json.loads(dump_review(c.session))
        for data in (dict(base,approved=True),dict(base,version='future'),dict(base,current=dict(base['current'],approved=True))):
            self.assertIsNone(load_review(json.dumps(data),**c.bindings).session)

    def test_archive_nonfinite_and_duplicate_keys_rejected(self):
        c=ReviewCase()
        for text in ('{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}'):
            self.assertIsNone(load_review(text,**c.bindings).session)

    def test_archive_bool_is_not_revision_number(self):
        c=ReviewCase();data=json.loads(dump_review(c.session));data['current']['number']=False
        self.assertIsNone(load_review(json.dumps(data),**c.bindings).session)

    def test_corrections_strict_roundtrip(self):
        c=ReviewCase();op=r.SetValue(c.ids['R1'],quantity('2k'))
        self.assertEqual(correction_from_dict(correction_to_dict(op)),op)
        with self.assertRaises(ValueError):correction_from_dict(dict(correction_to_dict(op),approved=True))
        with self.assertRaises(ValueError):correction_from_dict(dict(kind='reference',component_id='../x',reference='R1'))

    def test_injection_literals_inert(self):
        c=ReviewCase()
        for value in ('.include','.lib','.model','.tran','.ac','.dc','.step','.param',r'C:\some\path'):
            self.assertIsNone(c.apply(r.SetReference(c.ids['R1'],value)).session)
            q=ir.Quantity(value,'1','ohm',ir.ValueGrammar.SPICE)
            self.assertIsNone(c.apply(r.SetValue(c.ids['R1'],q)).session)

    def test_reordered_independent_operations_identical(self):
        a=ReviewCase();b=ReviewCase();ops=(r.SetValue(a.ids['R1'],quantity('2k')),r.SetValue(a.ids['R2'],quantity('3k')))
        a.edit(*ops);b.edit(*reversed(ops));self.assertEqual(a.session,b.session)

    def test_ground_removal_blocks_confirmation(self):
        c=ReviewCase();g=c.session.current.snapshot.ground_ids[0];c.edit(r.SetGround(g,None))
        self.assertIsNone(c.confirm_result().session)
        c.edit(r.SetGround(g,c.net('V1.negative')));c.confirm()

    def test_merge_and_split_exact_partition(self):
        c=ReviewCase('cross_open');a=c.net('horizontal0');b=c.net('vertical0')
        original=dict(c.session.current.snapshot.memberships)
        partitions=tuple(tuple(k for k,v in original.items() if v==n) for n in (a,b))
        c.edit(r.MergeNets((a,b)));merged=c.net('horizontal0')
        self.assertEqual(merged,c.net('vertical0'))
        self.assertIsNone(c.apply(r.SplitNet(merged,(partitions[0],))).session)
        c.edit(r.SplitNet(merged,partitions));self.assertNotEqual(c.net('horizontal0'),c.net('vertical0'))

    def test_explicit_terminal_addition_requires_connection_and_role_review(self):
        c=ReviewCase();c.edit(r.AddTerminal(c.ids['R1'],'manual',ir.PinRole.A))
        self.assertIsNone(c.confirm_result().session)

    def test_component_type_change_does_not_keep_old_value(self):
        c=ReviewCase();c.edit(r.SetComponentType(c.ids['R1'],ir.ComponentType.CAPACITOR))
        comp=next(v for v in c.session.current.snapshot.components if v.id==c.ids['R1'])
        self.assertIsNone(comp.value);self.assertIsNone(c.confirm_result().session)
