"""Explicit local reviewer actions over prepared replay inputs, never truth."""
from tests.m3d_helpers import replay
from circuit_ir.value_parser import parse_quantity
from circuit_ir.models import ValueGrammar
from circuit_image import review_models as r
from circuit_image.review import start_review, apply_corrections, confirm_review
from circuit_image.promotion import promote_review
from circuit_image.admission import issue_image_admission, ImageAdmissionContext

CASES = ('divider','rc','rlc','nmos','pmos','cross_open','cross_dot','cross_ambiguous',
         'near_gap','shared_labels','rotated_sources','nmos_bulk_unknown','missing_value',
         'unreadable_value','supply_unknown','unsupported_bjt')


def quantity(literal, unit='ohm'):
    result = parse_quantity(literal, unit, ValueGrammar.SPICE)
    if result.quantity is None:
        raise AssertionError(result.issues)
    return result.quantity


class ReviewCase:
    def __init__(self, name='divider', source=None):
        self.h, self.o, self.image = replay(name) if source is None else source
        self.bindings = dict(hypothesis=self.h, observations=self.o, image=self.image)
        self.ids = {o.provider_id:o.id for o in self.o.observations}
        result = start_review(self.h, self.o, self.image)
        if result.session is None:
            raise AssertionError(result.diagnostics)
        self.session = result.session

    def apply(self, *ops, base=None):
        return apply_corrections(self.session, tuple(ops),
            base_revision_digest=base or self.session.current.digest, **self.bindings)

    def edit(self, *ops):
        result = self.apply(*ops)
        if result.session is None:
            raise AssertionError(result.diagnostics)
        self.session = result.session
        return self.session

    def confirm_result(self, **overrides):
        args = dict(decision=r.ReviewDecision.CONFIRM,
            reviewed_claim_ids=tuple(sorted(c.id for c in self.h.claims)),
            base_revision_digest=self.session.current.digest, **self.bindings)
        args.update(overrides)
        return confirm_review(self.session, **args)

    def confirm(self):
        result = self.confirm_result()
        if result.session is None:
            raise AssertionError((result.diagnostics, self.session.current.issues))
        self.session = result.session
        return self.session

    def promote(self):
        return promote_review(self.session, **self.bindings)

    def context(self):
        promotion = self.promote()
        result = issue_image_admission(promotion, self.session, **self.bindings)
        if result.admission is None:
            raise AssertionError(result.diagnostics)
        return ImageAdmissionContext(self.image, self.o, self.h, self.session, promotion, result.admission)

    def net(self, alias):
        return dict(self.session.current.snapshot.memberships)[self.ids[alias]]

    def choose(self, meaning):
        ambiguity = self.h.ambiguities[0]
        option = next(c for c in ambiguity.options if c.meaning == meaning)
        return self.edit(r.ChooseTopology(ambiguity.id, option.id))

    def mos(self, profile='repository_demo_nmos'):
        return self.edit(r.SetMOSModel(self.ids['M1'], profile, quantity('10u','m'), quantity('1u','m')))
