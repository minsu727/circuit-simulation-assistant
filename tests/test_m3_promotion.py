import json
import unittest
from dataclasses import replace
from circuit_ir import models as ir
from circuit_ir.serialization import dump_document, document_to_dict
from circuit_ir.schema import load_document
from circuit_image import review_models as r
from circuit_image.promotion import promote_review, verify_promotion, dump_promotion, load_promotion
from circuit_image.admission import issue_image_admission
from tests.m3e_helpers import ReviewCase, quantity


class PromotionTests(unittest.TestCase):
    def test_divider_full_review_to_existing_schema(self):
        c=ReviewCase();c.confirm();p=c.promote()
        self.assertFalse(p.diagnostics);self.assertEqual(p.validation.technical_state,ir.TechnicalState.VALID)
        self.assertEqual(load_document(dump_document(p.document)).document,p.document)

    def test_unconfirmed_blocked(self):
        self.assertIsNone(ReviewCase().promote().document)

    def test_incomplete_blocked(self):
        c=ReviewCase('missing_value');self.assertIsNone(c.promote().document)

    def test_unsupported_blocked_without_drop(self):
        c=ReviewCase('unsupported_bjt');self.assertIsNone(c.promote().document)
        self.assertTrue(any(x.unsupported for x in c.session.current.snapshot.components))

    def test_confirmed_invalid_stays_invalid(self):
        c=ReviewCase();c.edit(r.SetValue(c.ids['R1'],quantity('-1k')));c.confirm();p=c.promote()
        self.assertIsNotNone(p.document);self.assertEqual(p.validation.technical_state,ir.TechnicalState.INVALID)
        self.assertIsNone(issue_image_admission(p,c.session,**c.bindings).admission)

    def test_m1_float_and_island_rules_unchanged(self):
        for name in ('cross_open','shared_labels'):
            c=ReviewCase(name);c.confirm();p=c.promote()
            self.assertEqual(p.validation.technical_state,ir.TechnicalState.INVALID)

    def test_corrected_missing_value_promotes(self):
        c=ReviewCase('missing_value');c.edit(r.SetValue(c.ids['C1'],quantity('10n','F')));c.confirm()
        self.assertIsNotNone(c.promote().document)

    def test_corrected_unreadable_value_promotes(self):
        c=ReviewCase('unreadable_value');c.edit(r.SetValue(c.ids['C1'],quantity('10n','F')));c.confirm()
        self.assertIsNotNone(c.promote().document)

    def test_nmos_explicit_profile_and_dimensions(self):
        c=ReviewCase('nmos');c.mos();c.confirm();p=c.promote()
        self.assertFalse(p.diagnostics)
        device=next(v for v in p.document.components if v.type is ir.ComponentType.NMOS)
        self.assertEqual(device.model_ref,'repository_demo_nmos');self.assertEqual(set(dict(device.parameters)),{'width','length'})

    def test_pmos_explicit_profile_and_dimensions(self):
        c=ReviewCase('pmos');c.mos('repository_demo_pmos');c.confirm()
        self.assertIsNotNone(c.promote().document)

    def test_rotated_sources_preserve_roles(self):
        c=ReviewCase('rotated_sources');c.confirm();p=c.promote();pinmap=dict(p.record.pin_map)
        self.assertEqual({v.id:v.role for v in p.document.pins}[pinmap[c.ids['V1.positive']]],ir.PinRole.POSITIVE)

    def test_no_auto_bulk_repair(self):
        c=ReviewCase('nmos_bulk_unknown');c.mos();self.assertIsNone(c.promote().document)
        c.edit(r.ConnectPin(c.ids['M1.bulk'],c.net('M1.source')));c.confirm()
        self.assertIsNotNone(c.promote().document)

    def test_stale_confirmation_cannot_promote(self):
        c=ReviewCase();c.confirm();old=c.session.confirmation;c.edit(r.SetValue(c.ids['R1'],quantity('2k')))
        p=promote_review(replace(c.session,confirmation=old),**c.bindings)
        self.assertIsNone(p.document)

    def test_wrong_image_and_topology_bindings(self):
        c=ReviewCase();c.confirm();other=ReviewCase('rc')
        self.assertIsNone(promote_review(c.session,hypothesis=other.h,observations=other.o,image=other.image).document)
        self.assertIsNone(promote_review(c.session,hypothesis=c.h,observations=c.o,image=other.image).document)

    def test_deterministic_mapping_and_repeated_bytes(self):
        c=ReviewCase();c.confirm();a=c.promote();b=c.promote()
        self.assertEqual(a,b);self.assertEqual(dump_document(a.document),dump_document(b.document))
        self.assertTrue(all(len(v)<=64 for mapping in (a.record.component_map,a.record.pin_map,a.record.net_map) for _,v in mapping))
        self.assertEqual(dict(a.record.component_map)[c.ids['R1']],'R1')

    def test_reordered_nonsemantic_operations_same_projection(self):
        a=ReviewCase();b=ReviewCase();ops=(r.SetValue(a.ids['R1'],quantity('2k')),r.SetValue(a.ids['R2'],quantity('3k')))
        a.edit(*ops);b.edit(*reversed(ops));a.confirm();b.confirm()
        self.assertEqual(dump_document(a.promote().document),dump_document(b.promote().document))

    def test_connection_is_only_canonical_membership(self):
        c=ReviewCase();c.confirm();p=c.promote();data=document_to_dict(p.document)
        self.assertEqual(len(data['connections']),len(data['pins']))
        self.assertTrue(all('net_id' not in x for x in data['pins']))
        self.assertTrue(all('net_id' not in x for x in data['components']))
        self.assertTrue(all(set(x)=={'id','is_ground'} for x in data['nets']))

    def test_original_provenance_and_sidecar(self):
        c=ReviewCase();c.edit(r.SetReference(c.ids['R1'],'R3'));c.confirm();p=c.promote()
        self.assertEqual(p.document.metadata.origin,ir.Origin.IMAGE)
        self.assertEqual(p.document.metadata.catalog_version,c.o.provider.catalog_version)
        self.assertEqual(p.document.source_image_reference.sha256,c.image.identity.source_sha256)
        self.assertEqual(p.document.source_image_reference.width_px,c.image.identity.width)
        self.assertEqual(p.record.review_sha256,c.session.digest)
        self.assertEqual(p.record.confirmation_sha256,c.session.confirmation.digest)
        self.assertEqual(p.document.confidence.basis,ir.ConfidenceBasis.MANUAL)
        self.assertIsNone(p.document.confidence.score);self.assertEqual(p.document.visual.entities,())

    def test_record_roundtrip_requires_current_live_review(self):
        c=ReviewCase();c.confirm();p=c.promote()
        self.assertEqual(load_promotion(dump_promotion(p.record),c.session,**c.bindings),p)
        c.edit(r.SetReference(c.ids['R1'],'R1'))
        self.assertIsNone(load_promotion(dump_promotion(p.record),c.session,**c.bindings).document)

    def test_record_unknown_fields_and_version_rejected(self):
        c=ReviewCase();c.confirm();p=c.promote();data=json.loads(dump_promotion(p.record))
        for payload in (dict(data,approved=True),dict(data,version='future'),dict(data,pin_map=[['fake','fake']])):
            self.assertIsNone(load_promotion(json.dumps(payload),c.session,**c.bindings).document)

    def test_changed_document_or_report_not_accepted(self):
        c=ReviewCase();c.confirm();p=c.promote()
        changed=replace(p.document,metadata=replace(p.document.metadata,revision=8))
        self.assertTrue(verify_promotion(replace(p,document=changed),c.session,**c.bindings))
        self.assertTrue(verify_promotion(replace(p,validation=replace(p.validation,ruleset_version='future')),c.session,**c.bindings))

    def test_revision_changes_even_electrically_identical(self):
        c=ReviewCase();c.confirm();first=c.promote();c.edit(r.SetReference(c.ids['R1'],'R1'));c.confirm();second=c.promote()
        self.assertEqual(second.document.metadata.revision,first.document.metadata.revision+1)
        self.assertNotEqual(first.record.document_sha256,second.record.document_sha256)
