import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from circuit_ir import models as ir
from circuit_ir.model_profiles import repository_model_context
from circuit_ir.approval import (ApprovalError, ApprovalScope, make_circuit_approval, verify_circuit_approval,
    make_representation_approval, verify_representation_approval, approval_digest)
from circuit_ir.exporter import check_export_eligibility, export_document, ExportStatus
from circuit_ir.execution import (AnalysisRequest, TransientCondition, make_execution_approval,
    compose_execution_netlist)
from circuit_image import review_models as r
from circuit_image.review import load_review
from circuit_image.review_serialization import dump_review
from circuit_image.admission import (issue_image_admission, verify_image_admission, dump_admission,
    load_admission)
from tests.m3e_helpers import ReviewCase, quantity


def circuit_approval(ctx, approved=True):
    version,digest=repository_model_context()
    warnings=tuple(sorted(i.issue_id for i in ctx.promotion.validation.issues if i.severity is ir.IssueSeverity.WARNING))
    return make_circuit_approval(ctx.promotion.document,approved=approved,
        acknowledged_warning_ids=warnings,exporter_contract='m2-spice-v1',
        model_registry_version=version,model_registry_sha256=digest,image_admission=ctx)


class AdmissionTests(unittest.TestCase):
    def case(self):
        c=ReviewCase();c.confirm();return c,c.context()

    def test_full_ci_safe_image_to_admission_path(self):
        c,ctx=self.case()
        self.assertEqual(verify_image_admission(ctx.promotion.document,ctx),())
        self.assertEqual(check_export_eligibility(ctx.promotion.document,model_context=repository_model_context(),image_admission=ctx),())
        self.assertIsNotNone(c.session.confirmation)

    def test_unconfirmed_review_blocked(self):
        c,ctx=self.case();unconfirmed=replace(c.session,confirmation=None)
        self.assertIsNone(issue_image_admission(ctx.promotion,unconfirmed,**c.bindings).admission)

    def test_admission_does_not_create_export_approval(self):
        c,ctx=self.case();result=export_document(ctx.promotion.document,None,model_context=repository_model_context(),image_admission=ctx)
        self.assertEqual(result.status,ExportStatus.BLOCKED)
        self.assertIn('EXPORT_APPROVAL_MISSING',[i.code for i in result.issues]);self.assertIsNone(result.spice_text)

    def test_nonadmitted_image_remains_blocked(self):
        c,ctx=self.case();issues=check_export_eligibility(ctx.promotion.document,model_context=repository_model_context())
        self.assertIn('EXPORT_UNSUPPORTED_FEATURE',[i.code for i in issues])

    def test_boolean_not_admission(self):
        c,ctx=self.case()
        for fake in (True,ctx.admission,c.session.confirmation,dict(approved=True)):
            self.assertTrue(verify_image_admission(ctx.promotion.document,fake))

    def test_review_or_admission_not_m2_approval(self):
        c,ctx=self.case()
        for fake in (ctx.admission,c.session.confirmation):
            with self.assertRaises(TypeError):export_document(ctx.promotion.document,fake,model_context=repository_model_context(),image_admission=ctx)

    def test_changed_document_blocked(self):
        c,ctx=self.case();doc=replace(ctx.promotion.document,warnings=('manual_warning',))
        self.assertTrue(verify_image_admission(doc,ctx))

    def test_changed_validation_report_blocked(self):
        c,ctx=self.case();report=replace(ctx.promotion.validation,document_revision=10)
        self.assertTrue(verify_image_admission(ctx.promotion.document,ctx,validation=report))
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,promotion=replace(ctx.promotion,validation=report))))

    def test_changed_ruleset_blocked(self):
        c,ctx=self.case();report=replace(ctx.promotion.validation,ruleset_version='future')
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,promotion=replace(ctx.promotion,validation=report))))

    def test_fresh_ruleset_change_not_silently_refreshed(self):
        c,ctx=self.case();report=replace(ctx.promotion.validation,ruleset_version='future')
        with patch('circuit_image.promotion.validate_document',return_value=report):
            self.assertTrue(verify_image_admission(ctx.promotion.document,ctx))

    def test_changed_image_bytes_blocked(self):
        c,ctx=self.case();image=replace(ctx.image,original_bytes=ctx.image.original_bytes+b'x')
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,image=image)))

    def test_changed_normalized_image_blocked(self):
        c,ctx=self.case();image=replace(ctx.image,normalized_png=ctx.image.normalized_png+b'x')
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,image=image)))

    def test_changed_observations_blocked(self):
        c,ctx=self.case();obs=replace(ctx.observations,response_sha256='0'*64)
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,observations=obs)))

    def test_changed_topology_blocked(self):
        c,ctx=self.case();h=replace(ctx.hypothesis,digest='0'*64)
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,hypothesis=h)))

    def test_changed_review_blocked(self):
        c,ctx=self.case();c.edit(r.SetValue(c.ids['R1'],quantity('2k')))
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,review=c.session)))

    def test_changed_confirmation_blocked(self):
        c,ctx=self.case();review=replace(c.session,confirmation=replace(c.session.confirmation,digest='0'*64))
        self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,review=review)))

    def test_wrong_versions_and_digest_blocked(self):
        c,ctx=self.case()
        for field in ('version','review_version','promotion_version','digest','promotion_sha256','confirmation_sha256'):
            a=replace(ctx.admission,**{field:'wrong'})
            self.assertTrue(verify_image_admission(ctx.promotion.document,replace(ctx,admission=a)))

    def test_archive_strict_and_current_confirmation_required(self):
        c,ctx=self.case();self.assertEqual(load_admission(dump_admission(ctx.admission),ctx).admission,ctx.admission)
        imported=load_review(dump_review(c.session),**c.bindings).session
        self.assertIsNone(load_admission(dump_admission(ctx.admission),replace(ctx,review=imported)).admission)
        base=json.loads(dump_admission(ctx.admission))
        for data in (dict(base,approved=True),dict(base,version='future'),dict(base,document_sha256='../fake')):
            self.assertIsNone(load_admission(json.dumps(data),ctx).admission)

    def test_invalid_document_never_admitted(self):
        c=ReviewCase();c.edit(r.SetValue(c.ids['R1'],quantity('-1')));c.confirm()
        self.assertIsNone(issue_image_admission(c.promote(),c.session,**c.bindings).admission)

    def test_explicit_circuit_approval_bound_to_admission(self):
        c,ctx=self.case();a=circuit_approval(ctx)
        self.assertEqual(a.scope,ApprovalScope.CIRCUIT_EXPORT);self.assertEqual(a.image_admission_sha256,ctx.admission.digest)
        version,digest=repository_model_context()
        verify_circuit_approval(ctx.promotion.document,a,exporter_contract='m2-spice-v1',model_registry_version=version,model_registry_sha256=digest,image_admission=ctx)
        with self.assertRaises(ApprovalError):verify_circuit_approval(ctx.promotion.document,a,exporter_contract='m2-spice-v1',model_registry_version=version,model_registry_sha256=digest)

    def test_circuit_approval_not_automatically_granted(self):
        c,ctx=self.case()
        with self.assertRaises(ApprovalError):circuit_approval(ctx,False)

    def test_old_unbound_approval_cannot_use_new_admission(self):
        c,ctx=self.case();a=replace(circuit_approval(ctx),image_admission_sha256=None)
        result=export_document(ctx.promotion.document,a,model_context=repository_model_context(),image_admission=ctx)
        self.assertEqual(result.status,ExportStatus.BLOCKED)

    def test_admission_in_approval_digest(self):
        c,ctx=self.case();a=circuit_approval(ctx)
        self.assertNotEqual(approval_digest(a),approval_digest(replace(a,image_admission_sha256='0'*64)))

    def test_all_three_m2_approvals_required_pure_boundary_only(self):
        c,ctx=self.case();doc=ctx.promotion.document;models=repository_model_context();a=circuit_approval(ctx)
        preview=export_document(doc,a,model_context=models,image_admission=ctx)
        self.assertEqual(preview.status,ExportStatus.SUCCESS)
        req=AnalysisRequest(TransientCondition('0.01'))
        with self.assertRaises(TypeError):make_execution_approval(doc,preview,a,None,req,approved=True,model_context=models,image_admission=ctx)
        with self.assertRaises(ApprovalError):make_representation_approval(doc,preview,a,approved=False,model_context=models,image_admission=ctx)
        rep=make_representation_approval(doc,preview,a,approved=True,model_context=models,image_admission=ctx)
        self.assertIsNone(compose_execution_netlist(doc,preview,a,rep,req,None,model_context=models,image_admission=ctx).artifact)
        with self.assertRaises(ApprovalError):make_execution_approval(doc,preview,a,rep,req,approved=False,model_context=models,image_admission=ctx)
        execution=make_execution_approval(doc,preview,a,rep,req,approved=True,model_context=models,image_admission=ctx)
        # Pure object verification only; no runtime runner, filesystem or LTspice.
        from circuit_ir.execution import verify_execution_approval
        verify_execution_approval(doc,preview,a,rep,req,execution,model_context=models,image_admission=ctx)

    def test_stale_admission_invalidates_downstream_approval(self):
        c,ctx=self.case();a=circuit_approval(ctx);models=repository_model_context()
        preview=export_document(ctx.promotion.document,a,model_context=models,image_admission=ctx)
        rep=make_representation_approval(ctx.promotion.document,preview,a,approved=True,model_context=models,image_admission=ctx)
        c.edit(r.SetReference(c.ids['R1'],'R1'));stale=replace(ctx,review=c.session)
        self.assertTrue(check_export_eligibility(ctx.promotion.document,model_context=models,image_admission=stale))
        with self.assertRaises(ApprovalError):verify_representation_approval(ctx.promotion.document,preview,a,rep,model_context=models,image_admission=stale)
