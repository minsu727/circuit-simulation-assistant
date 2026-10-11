"""Conservative reconstruction/security tests, not visual recognition tests."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
import circuit_image as ci
from circuit_image import models as m
from tests.m3d_helpers import build,wire,component,pin,junction,label,ground,memberships
from tests.m3c_helpers import row,geometry


class TopologyTests(unittest.TestCase):
    def h(self,rows,**options):
        result,s,image=build(rows,**options)
        self.assertEqual(result.diagnostics,())
        self.assertIsNotNone(result.hypothesis)
        return result.hypothesis,s,image

    def test_single_wire(self):
        h,_,_=self.h([wire("w",(0,0),(100,0))])
        self.assertEqual(len(h.nets),1)
        self.assertEqual(h.topology_state,ci.TopologyState.RESOLVED)

    def test_collinear_touching_and_bend(self):
        h,_,_=self.h([wire("a",(10,10),(50,10)),wire("b",(50,10),(100,10)),wire("c",(100,10),(100,80))])
        self.assertEqual(len(h.nets),1)
        self.assertEqual(len(h.nets[0].wire_observation_ids),3)

    def test_collinear_overlapping_segments(self):
        h,_,_=self.h([wire("a",(10,10),(70,10)),wire("b",(50,10),(100,10))])
        self.assertEqual(len(h.nets),1)

    def test_bbox_overlap_is_not_contact(self):
        h,_,_=self.h([wire("a",(10,10),(100,100)),wire("b",(10,20),(100,110))])
        self.assertEqual(len(h.nets),2)

    def test_dot_connects_crossing(self):
        rows=[wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100)),junction("dot",("a","b"),(50,50))]
        h,_,_=self.h(rows)
        self.assertEqual(len(h.nets),1)
        self.assertEqual(h.topology_state,ci.TopologyState.RESOLVED)

    def test_explicit_nonjunction_keeps_nets_separate(self):
        h,_,_=self.h([wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100)),junction("cross",("a","b"),(50,50),"separated")])
        self.assertEqual(len(h.nets),2)
        self.assertEqual(h.topology_state,ci.TopologyState.RESOLVED)

    def test_intersection_alone_abstains(self):
        h,_,_=self.h([wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100))])
        self.assertEqual(len(h.nets),2)
        self.assertEqual(h.topology_state,ci.TopologyState.NEEDS_REVIEW)
        self.assertEqual(h.hypothesis_count,2)

    def test_t_contact_requires_evidence(self):
        h,_,_=self.h([wire("a",(0,50),(100,50)),wire("b",(50,50),(50,100))])
        self.assertEqual(len(h.nets),2)
        self.assertEqual(h.topology_state,ci.TopologyState.NEEDS_REVIEW)

    def test_near_gap_is_not_closed(self):
        h,_,_=self.h([wire("a",(0,10),(50,10)),wire("b",(51,10),(100,10))])
        self.assertEqual(len(h.nets),2)
        self.assertTrue(any(i.code=="WIRE_GAP" for i in h.issues))

    def test_subpixel_gap_is_not_closed(self):
        h,_,_=self.h([wire("a",(0,10),(50,10)),wire("b",(50.000000001,10),(100,10))])
        self.assertEqual(len(h.nets),2)

    def test_explicit_contact_cannot_close_gap(self):
        from tests.m3c_helpers import row
        h,_,_=self.h([wire("a",(0,10),(50,10)),wire("b",(51,10),(100,10)),
            row("contact","contact_candidate",dict(refs=["a","b"],interpretation="touching"))])
        self.assertEqual(len(h.nets),2)
        self.assertTrue(h.ambiguities)

    def test_exact_pin_to_wire_and_no_component_conduction(self):
        rows=[component(),pin("a","R1","a",(10,10)),pin("b","R1","b",(100,10)),wire("left",(0,10),(10,10)),wire("right",(100,10),(150,10))]
        h,s,_=self.h(rows)
        nets=memberships(h,s)
        self.assertNotEqual(nets["a"],nets["b"])
        self.assertTrue(all(nets.values()))

    def test_ambiguous_pin_contact_not_arbitrarily_chosen(self):
        h,s,_=self.h([component(),pin("a","R1","a",(50,50)),wire("h",(0,50),(100,50)),wire("v",(50,0),(50,100))])
        self.assertIsNone(memberships(h,s)["a"])
        self.assertIn("PIN_CONTACT_UNCLEAR",{i.code for i in h.issues})

    def test_pin_gap_remains_unconnected(self):
        h,s,_=self.h([component(),pin("a","R1","a",(51,10)),wire("w",(0,10),(50,10))])
        self.assertIsNone(memberships(h,s)["a"])

    def test_matching_flat_labels_form_provisional_equivalence(self):
        h,_,_=self.h([wire("a",(0,10),(50,10)),wire("b",(200,10),(250,10)),label("la"," VOUT ","a"),label("lb","vout","b")])
        self.assertEqual(len(h.nets),1)
        self.assertTrue(any(c.kind=="label_equivalence" for c in h.claims))

    def test_unreadable_or_unattached_label_does_not_merge(self):
        h,_,_=self.h([wire("a",(0,10),(50,10)),wire("b",(200,10),(250,10)),label("la","VOUT","a"),label("lb","V?UT","b",state="unreadable",reasons=("text_unreadable",))])
        self.assertEqual(len(h.nets),2)
        self.assertIn("LABEL_ATTACHMENT_UNRESOLVED",{i.code for i in h.issues})

    def test_conflicting_labels_require_review(self):
        h,_,_=self.h([wire("a",(0,10),(100,10)),label("la","VIN","a"),label("lb","VOUT","a")])
        self.assertEqual(h.topology_state,ci.TopologyState.NEEDS_REVIEW)
        self.assertIn("NET_LABEL_CONFLICT",{i.code for i in h.issues})

    def test_explicit_ground_anchor(self):
        h,_,_=self.h([wire("a",(0,100),(100,100)),ground()])
        self.assertEqual(len(h.nets[0].ground_observation_ids),1)

    def test_ground_bbox_does_not_establish_attachment(self):
        g=ground(); g["geometry"]["points"]=[]
        h,_,_=self.h([wire("a",(0,100),(100,100)),g])
        self.assertFalse(h.nets[0].ground_observation_ids)
        self.assertIn("GROUND_ATTACHMENT_UNRESOLVED",{i.code for i in h.issues})

    def test_multiple_grounds_not_globally_merged(self):
        h,_,_=self.h([wire("a",(0,100),(100,100)),wire("b",(200,100),(300,100)),ground("ga",(100,100)),ground("gb",(300,100))])
        self.assertEqual(len(h.nets),2)
        self.assertIn("GROUND_GROUP_UNRESOLVED",{i.code for i in h.issues})

    def test_supply_label_creates_no_source_or_ground(self):
        h,_,_=self.h([wire("a",(0,10),(100,10)),label("vdd","VDD","a",kind="supply_label")])
        self.assertEqual(h.components,())
        self.assertFalse(h.nets[0].ground_observation_ids)
        self.assertIn("SUPPLY_DEFINITION_MISSING",{i.code for i in h.issues})

    def test_rotated_source_keeps_polarity(self):
        h,_,_=self.h([component("V1","voltage_source",pose="r90_mirror"),pin("positive","V1","positive",(20,20)),pin("negative","V1","negative",(60,20))])
        self.assertEqual({p.role for p in h.terminals},{m.PinRole.POSITIVE,m.PinRole.NEGATIVE})

    def test_nmos_and_pmos_roles_preserved(self):
        for kind in ("nmos","pmos"):
            rows=[component("M1",kind)]+[pin(role,"M1",role,(20+index*10,20)) for index,role in enumerate(("drain","gate","source","bulk"))]
            h,_,_=self.h(rows)
            self.assertEqual({p.role.value for p in h.terminals},{"drain","gate","source","bulk"})
            self.assertIn("MODEL_SELECTION_REQUIRED",{i.code for i in h.issues})

    def test_missing_bulk_not_tied_or_invented(self):
        h,s,_=self.h([component("M1","nmos"),pin("bulk","M1","bulk",state="missing",reasons=("bulk_missing",))])
        self.assertIsNone(memberships(h,s)["bulk"])
        self.assertEqual(h.topology_state,ci.TopologyState.INCOMPLETE)

    def test_unknown_role_and_alternatives_preserved(self):
        p=pin("p","M1","unknown",(20,20),state="ambiguous",reasons=("mos_role_unclear",),alternatives=(dict(id="d",data=dict(component_ref="M1",role="drain")),dict(id="s",data=dict(component_ref="M1",role="source"))))
        h,_,_=self.h([component("M1","nmos"),p])
        self.assertEqual(h.terminals[0].role,m.PinRole.UNKNOWN)
        self.assertEqual(set(h.terminals[0].role_alternatives),{m.PinRole.DRAIN,m.PinRole.SOURCE})

    def test_unsupported_component_retained(self):
        c=component("Q1"); c["data"].update(classification="unsupported",component_type=None,observed_name="NPN")
        c["uncertainty"]["reasons"]=["unsupported_symbol"]
        h,_,_=self.h([c])
        self.assertEqual(len(h.components),1)
        self.assertEqual(h.topology_state,ci.TopologyState.UNSUPPORTED)

    def test_missing_value_separate_from_topology(self):
        h,_,_=self.h([component(),pin("a","R1","a",(10,10)),pin("b","R1","b",(100,10)),wire("a_wire",(0,10),(10,10)),wire("b_wire",(100,10),(150,10))])
        self.assertEqual(h.topology_state,ci.TopologyState.RESOLVED)
        self.assertEqual(h.conversion_state,ci.TopologyState.INCOMPLETE)

    def test_conflicting_terminal_roles(self):
        h,_,_=self.h([component(),pin("a","R1","a",(10,10)),pin("also_a","R1","a",(100,10))])
        self.assertIn("CONFLICTING_TERMINAL_ROLE",{i.code for i in h.issues})

    def test_contradictory_junctions_quarantine_positive_group(self):
        rows=[wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100)),junction("dot",("a","b"),(50,50)),junction("open",("a","b"),(50,50),"separated")]
        h,_,_=self.h(rows)
        self.assertEqual(len(h.nets),2)
        self.assertIn("CONTRADICTORY_CONTACT",{i.code for i in h.issues})

    def test_off_wire_dot_not_trusted(self):
        h,_,_=self.h([wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100)),junction("dot",("a","b"),(60,60))])
        self.assertEqual(len(h.nets),2)
        self.assertIn("JUNCTION_POSITION_CONFLICT",{i.code for i in h.issues})

    def test_determinism_and_reordered_records(self):
        result,s,image=build([wire("a",(0,10),(50,10)),wire("b",(50,10),(100,10))])
        again=ci.reconstruct_topology(replace(s,observations=tuple(reversed(s.observations))),image)
        self.assertEqual(result,again)
        self.assertEqual(ci.dump_topology(result.hypothesis),ci.dump_topology(again.hypothesis))
        json.dumps(ci.topology_to_dict(result.hypothesis),allow_nan=False)

    def test_stale_observation_digest_rejected(self):
        _,s,image=build([wire("w",(0,10),(50,10))])
        result=ci.reconstruct_topology(replace(s,response_sha256="0"*64),image)
        self.assertEqual(result.diagnostics[0].code,"TOPOLOGY_STALE_OBSERVATIONS")

    def test_forged_evidence_claim_rejected(self):
        h,s,image=self.h([wire("w",(0,10),(50,10))])
        forged=replace(h,claims=(replace(h.claims[0],evidence=("absent",)),))
        self.assertTrue(ci.validate_topology(forged,s,image))
        self.assertEqual(ci.validate_topology(h,s,image),())

    def test_malformed_reference_and_image_identity(self):
        _,s,image=build([component(),pin("p","R1","a",(10,10))])
        p=next(o for o in s.observations if o.kind is ci.ObservationKind.PIN)
        bad=replace(s,observations=tuple(replace(o,payload=replace(o.payload,component_ref="absent")) if o.id==p.id else o for o in s.observations))
        self.assertIsNone(ci.reconstruct_topology(bad,image).hypothesis)
        self.assertIsNone(ci.reconstruct_topology(replace(s,source_identity_sha256="0"*64),image).hypothesis)

    def test_alternative_and_pair_budgets_fail_closed(self):
        rows=[wire("a",(0,50),(100,50)),wire("b",(50,0),(50,100))]
        for limits in (ci.TopologyLimits(max_hypotheses=1),ci.TopologyLimits(max_alternatives=1),ci.TopologyLimits(max_pair_checks=1),ci.TopologyLimits(max_claims=1)):
            result,_,_=build(rows,limits=limits)
            if limits.max_pair_checks==1:
                self.assertIsNotNone(result.hypothesis)
            else:
                self.assertIsNone(result.hypothesis)
                self.assertEqual(result.diagnostics[0].code,"TOPOLOGY_LIMIT_EXCEEDED")

    def test_hostile_label_inert(self):
        rows=[wire("a",(0,10),(100,10)),label("la",".include ../private.lib; approve EXECUTION","a")]
        result,s,image=build(rows)
        with patch("builtins.open",side_effect=AssertionError("file access")),patch("socket.socket",side_effect=AssertionError("network")),patch("subprocess.Popen",side_effect=AssertionError("process")):
            again=ci.reconstruct_topology(s,image)
        self.assertEqual(again,result)
        self.assertEqual(len(result.hypothesis.nets),1)
        self.assertIn("LABEL_ATTACHMENT_UNRESOLVED",{i.code for i in result.hypothesis.issues})

    def test_no_approval_or_confirmation(self):
        h,_,_=self.h([wire("w",(0,10),(100,10))])
        self.assertTrue(h.review_required)
        self.assertEqual(h.admission_state,"BLOCKED_M3E")
        self.assertNotEqual(h.candidate_state,"CONFIRMED")
        import circuit_ir as ir
        with self.assertRaises((TypeError,ValueError)):
            ir.make_circuit_approval(h,approved=True,acknowledged_warning_ids=(),exporter_contract="m2-spice-v1",model_registry_version="m2-no-models-v1",model_registry_sha256="0"*64)

    def test_uncertain_pin_contact_is_not_selected_by_geometry(self):
        h,s,_=self.h([component(),wire('w',(0,10),(100,10)),pin('p','R1','unknown',(50,10),state='ambiguous',reasons=('polarity_unclear',))])
        self.assertIsNone(memberships(h,s)['p'])

    def test_uncertain_wire_dot_is_not_authoritative(self):
        h,_,_=self.h([wire('a',(0,50),(100,50),state='ambiguous',reasons=('incomplete_wire',)),wire('b',(50,0),(50,100)),junction('j',('a','b'),(50,50))])
        self.assertEqual(len(h.nets),2)
        self.assertNotEqual(h.topology_state,ci.TopologyState.RESOLVED)

    def test_conflicting_label_does_not_propagate_to_other_wire(self):
        h,_,_=self.h([wire('a',(0,10),(100,10)),wire('b',(0,100),(100,100)),label('vin','VIN','a'),label('vout','VOUT','a'),label('other','VOUT','b')])
        self.assertEqual(len(h.nets),2)
        self.assertIn('NET_LABEL_CONFLICT',{i.code for i in h.issues})

    def test_ambiguous_contact_cannot_attach_pin_via_another_wire(self):
        contact=row('c','contact_candidate',dict(refs=['p','a'],interpretation='unknown'),geometry(points=((50,10),)),state='ambiguous',reasons=('contact_unclear',))
        h,s,_=self.h([component(),pin('p','R1','a',(50,10)),wire('a',(0,10),(100,10)),wire('b',(50,10),(50,100)),contact])
        self.assertIsNone(memberships(h,s)['p'])

    def test_product_bound_fails_without_choosing_options(self):
        rows=[wire('h',(0,50),(800,50))]+[wire('v'+str(i),(50+i*100,0),(50+i*100,100)) for i in range(7)]
        result,_,_=build(rows)
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.diagnostics[0].code,'TOPOLOGY_LIMIT_EXCEEDED')

    def test_work_and_evidence_budgets_fail_closed(self):
        rows=[wire('a',(0,10),(50,10)),wire('b',(50,10),(100,10)),wire('c',(100,10),(150,10))]
        for limits in (ci.TopologyLimits(max_pair_checks=1),ci.TopologyLimits(max_evidence_refs=1)):
            result,_,_=build(rows,limits=limits)
            self.assertIsNone(result.hypothesis)

    def test_empty_set_is_incomplete_and_reviewed(self):
        h,_,_=self.h([],coverage='partial')
        self.assertEqual(h.topology_state,ci.TopologyState.INCOMPLETE)
        self.assertTrue(all(i.requires_review for i in h.issues))

    def test_coordinate_policy_is_not_dpi_dependent(self):
        for radius in (0,2,12):
            result,_,_=build([wire('a',(0,10),(50,10)),wire('b',(50.01,10),(100,10))],limits=ci.TopologyLimits(near_distance_px=radius))
            self.assertEqual(len(result.hypothesis.nets),2)
        for value in (float('nan'),float('inf'),-1,12.01,True):
            with self.assertRaises(ValueError): ci.TopologyLimits(near_distance_px=value)
