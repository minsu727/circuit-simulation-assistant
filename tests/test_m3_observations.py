"""Untrusted observation contract, not extraction-accuracy or electrical tests."""
from copy import deepcopy
from dataclasses import replace, FrozenInstanceError
from decimal import Decimal
import hashlib
import json
import unittest
from unittest.mock import patch

import circuit_image as ci
from circuit_image import models as m
from circuit_ir.models import PinRole
from tests.m3c_helpers import fixture_image, image_bytes, envelope, encode, row, geometry, REPLAYS, M3B


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=fixture_image()
        cls.truth_hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in M3B.rglob("*") if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        if cls.truth_hashes != {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in M3B.rglob("*") if p.is_file()}:
            raise AssertionError("M3B assets changed")

    def parse(self,data,image=None,**options):
        return ci.parse_observations(encode(data),image or self.image,provider=ci.STATIC_PROVIDER,**options)

    def reject(self,edit,code=None,**options):
        data=envelope(self.image); edit(data)
        result=self.parse(data,**options)
        self.assertIsNone(result.observation_set)
        self.assertTrue(result.diagnostics)
        if code: self.assertEqual(result.diagnostics[0].code,code)

    def replay(self,name,image):
        result=ci.parse_observations((REPLAYS/(name+".json")).read_bytes(),fixture_image(image),provider=ci.STATIC_PROVIDER)
        self.assertEqual(result.diagnostics,())
        return result.observation_set

    def value_result(self,scalar,raw_unit,notation,unit,si,reasons=()):
        value=dict(raw_scalar=scalar,raw_unit=raw_unit,notation=notation,unit=unit,si_value=si)
        text=row("text","text",dict(raw_text=scalar+" "+str(raw_unit),purpose="value",component_ref=None,value=value),geometry([10,10,30,20]),reasons=reasons)
        return self.parse(envelope(self.image,[text]))

    def test_valid_typed_record(self):
        s=self.parse(envelope(self.image)).observation_set
        self.assertIsInstance(s,ci.ObservationSet)
        self.assertIsInstance(s.observations[0].payload,m.SymbolCandidate)
        self.assertEqual(s.version,ci.OBSERVATION_VERSION)
        self.assertTrue(s.observations[0].id.startswith("obs_"))
        with self.assertRaises(FrozenInstanceError): s.coverage="confirmed"

    def test_hand_authored_replay_catalog(self):
        catalog=json.loads((REPLAYS/"catalog.json").read_text(encoding="utf8"))
        for case in catalog["cases"]:
            with self.subTest(case=case["case_id"]):
                result=ci.extract_observations(fixture_image(case["image_case"]),ci.StaticReplayProvider((REPLAYS/case["payload"]).read_bytes()))
                self.assertEqual(result.status,case["expected_status"])

    def test_round_trip_and_deterministic_serialization(self):
        s=self.replay("crossing_ambiguous","cross_ambiguous")
        wire=ci.dump_observations(s)
        parsed=ci.parse_observations(wire,fixture_image("cross_ambiguous"),provider=ci.STATIC_PROVIDER)
        self.assertEqual(parsed.observation_set,s)
        self.assertEqual(ci.dump_observations(parsed.observation_set),wire)
        self.assertNotIn("original_bytes",wire)
        json.dumps(ci.observations_to_dict(s),allow_nan=False)

    def test_record_and_alternative_order_do_not_change_identity(self):
        image=fixture_image("cross_ambiguous")
        data=json.loads((REPLAYS/"crossing_ambiguous.json").read_text(encoding="utf8"))
        a=self.parse(data,image).observation_set
        data["observations"].reverse()
        for r in data["observations"]:
            r["uncertainty"]["alternatives"].reverse()
            if "wire_refs" in r["data"]: r["data"]["wire_refs"].reverse()
        b=self.parse(data,image).observation_set
        self.assertEqual(a,b)

    def test_fresh_extraction_scope_changes_local_ids(self):
        data=envelope(self.image)
        a=self.parse(data,extraction_key="attempt_one").observation_set
        b=self.parse(data,extraction_key="attempt_two").observation_set
        self.assertEqual(a.response_sha256,b.response_sha256)
        self.assertNotEqual(a.extraction_id,b.extraction_id)
        self.assertNotEqual(a.observations[0].id,b.observations[0].id)

    def test_duplicate_ids(self):
        self.reject(lambda d:d["observations"].append(deepcopy(d["observations"][0])),"OBS_ID_DUPLICATE")

    def test_unsafe_provider_alias(self):
        self.reject(lambda d:d["observations"][0].update(id="../external"),"OBS_ID_INVALID")

    def test_unknown_reference(self):
        result=ci.parse_observations((REPLAYS/"invalid_reference.json").read_bytes(),self.image,provider=ci.STATIC_PROVIDER)
        self.assertEqual(result.diagnostics[0].code,"OBS_REFERENCE_INVALID")

    def test_wrong_reference_kind_and_self_reference(self):
        rows=[row(),row("pin","pin",{"component_ref":"pin","role":"a"},geometry(points=((20,20),)))]
        result=self.parse(envelope(self.image,rows))
        self.assertEqual(result.diagnostics[0].code,"OBS_REFERENCE_INVALID")

    def test_unsupported_version(self):
        self.reject(lambda d:d.update(version="future"),"OBS_VERSION_UNSUPPORTED")

    def test_missing_and_unknown_fields(self):
        for target in (lambda d:d,lambda d:d["observations"][0],lambda d:d["observations"][0]["data"]):
            self.reject(lambda d:target(d).update(approved=True),"OBS_FIELDS_INVALID")
        self.reject(lambda d:d.pop("image"),"OBS_FIELDS_INVALID")

    def test_invalid_coordinate_frame(self):
        self.reject(lambda d:d.update(coordinate_frame="normalized_0_1"),"OBS_GEOMETRY_INVALID")

    def test_each_image_digest_binding(self):
        for key in envelope(self.image)["image"]:
            self.reject(lambda d:d["image"].update({key:"0"*64}),"OBS_SOURCE_MISMATCH")
        self.reject(lambda d:d["observations"][0].update(source_sha256="0"*64),"OBS_SOURCE_MISMATCH")

    def test_forged_image_artifact(self):
        forged=replace(self.image,identity=replace(self.image.identity,width=1))
        self.assertEqual(self.parse(envelope(self.image),forged).diagnostics[0].code,"IMAGE_IDENTITY_MISMATCH")
        forged=replace(self.image,normalized_png=b"other")
        self.assertEqual(self.parse(envelope(self.image),forged).diagnostics[0].code,"IMAGE_IDENTITY_MISMATCH")

    def test_box_bounds_dimensions_and_boolean(self):
        for box in ([-1,10,10,10],[999,10,2,10],[10,10,0,10],[10,10,-1,10],[True,10,10,10]):
            self.reject(lambda d:d["observations"][0]["geometry"].update(bbox=box),"OBS_GEOMETRY_INVALID")

    def test_nan_infinity_and_overflow(self):
        data=envelope(self.image)
        for token in ("NaN","Infinity","-Infinity","1e9999"):
            payload=encode(data).replace('"bbox": [10, 10, 40, 20]',f'"bbox": [{token}, 10, 40, 20]')
            result=ci.parse_observations(payload,self.image,provider=ci.STATIC_PROVIDER)
            self.assertIsNone(result.observation_set)

    def test_point_outside_or_boolean(self):
        for p in ((-1,0),(1001,0),(0,651),(True,10)):
            rows=[row("wire","wire_segment",{},geometry(points=(p,(20,20))))]
            self.assertEqual(self.parse(envelope(self.image,rows)).diagnostics[0].code,"OBS_GEOMETRY_INVALID")

    def test_edge_coordinate_is_valid_and_zero_wire_rejected(self):
        good=row("wire","wire_segment",{},geometry(points=((0,0),(1000,650))))
        self.assertEqual(self.parse(envelope(self.image,[good])).diagnostics,())
        good["geometry"]["points"]=[[0,0],[0,0]]
        self.assertEqual(self.parse(envelope(self.image,[good])).diagnostics[0].code,"OBS_GEOMETRY_INVALID")

    def test_exif_display_geometry_maps_to_original_without_role_swap(self):
        image=ci.ingest_image(image_bytes(orientation=6)).artifact
        rows=[row("M1",data={"classification":"supported","component_type":"nmos","observed_name":None,"reference_text":"M1"},g=geometry([10,10,20,30],pose="r90")),
              row("pin","pin",{"component_ref":"M1","role":"drain"},geometry(points=((20,30),)))]
        result=self.parse(envelope(image,rows,frame="display_pixels"),image).observation_set
        symbol=next(o for o in result.observations if o.kind is ci.ObservationKind.SYMBOL)
        pin=next(o for o in result.observations if o.kind is ci.ObservationKind.PIN)
        self.assertEqual(symbol.geometry.orientation,m.Orientation.R0)
        self.assertEqual(symbol.geometry.bbox,m.Box(10,34,30,20))
        self.assertEqual(pin.geometry.points,(m.Point(30,44),))
        self.assertEqual(pin.payload.role,PinRole.DRAIN)

    def test_mirrored_role_is_preserved(self):
        image=ci.ingest_image(image_bytes(orientation=2)).artifact
        rows=[row("M1",data={"classification":"supported","component_type":"pmos","observed_name":None,"reference_text":"M1"}),
              row("pin","pin",{"component_ref":"M1","role":"source"},geometry(points=((20,30),)))]
        s=self.parse(envelope(image,rows,frame="display_pixels"),image).observation_set
        pin=next(o for o in s.observations if o.kind is ci.ObservationKind.PIN)
        self.assertEqual(pin.payload.role,PinRole.SOURCE)
        self.assertEqual(pin.geometry.points,(m.Point(76,30),))

    def test_text_and_record_budgets(self):
        self.reject(lambda d:d["observations"][0]["data"].update(reference_text="x"*257),"OBS_LIMIT_EXCEEDED")
        self.reject(lambda d:d["observations"].append({**deepcopy(d["observations"][0]),"id":"second"}),"OBS_LIMIT_EXCEEDED",limits=ci.ObservationLimits(max_records=1))
        self.reject(lambda d:d["observations"].append({**deepcopy(d["observations"][0]),"id":"second"}),"OBS_LIMIT_EXCEEDED",limits=ci.ObservationLimits(max_symbols=1))

    def test_depth_payload_and_node_budgets(self):
        for limits in (ci.ObservationLimits(max_payload_bytes=10),ci.ObservationLimits(max_depth=2),ci.ObservationLimits(max_nodes=2)):
            self.assertEqual(self.parse(envelope(self.image),limits=limits).diagnostics[0].code,"OBS_LIMIT_EXCEEDED")

    def test_invalid_limits_and_non_json_input(self):
        self.assertEqual(self.parse(envelope(self.image),limits=None).diagnostics[0].code,"OBS_LIMITS_INVALID")
        for payload in (None,{},b"\xff",'{"a":1,"a":2}',"[]"):
            self.assertIsNone(ci.parse_observations(payload,self.image,provider=ci.STATIC_PROVIDER).observation_set)

    def test_provider_provenance_mismatch(self):
        self.reject(lambda d:d["provider"].update(adapter_version="other"),"OBS_PROVENANCE_INVALID")
        self.reject(lambda d:d["provider"].update(model_id="pretend-real-model"),"OBS_PROVENANCE_INVALID")

    def test_untrusted_provider_config(self):
        for info in (None,replace(ci.STATIC_PROVIDER,mode=[]),replace(ci.STATIC_PROVIDER,adapter_version="bad path")):
            result=ci.parse_observations(encode(envelope(self.image)),self.image,provider=info)
            self.assertIsNone(result.observation_set)

    def test_confidence_no_confirmation_or_calibration(self):
        for fields in ({"score":2},{"score":True},{"score":0.5,"basis":"manual"},{"calibrated":True},{"score":0.5,"basis":"unknown"}):
            self.reject(lambda d:d["observations"][0]["confidence"].update(fields),"OBS_CONFIDENCE_INVALID")
        self.reject(lambda d:d["observations"][0]["uncertainty"].update(state="confirmed"),"OBS_ENUM_INVALID")

    def test_valid_unresolved_alternatives(self):
        s=self.replay("crossing_ambiguous","cross_ambiguous")
        crossing=next(o for o in s.observations if o.kind is ci.ObservationKind.CROSSING)
        self.assertEqual(crossing.payload.interpretation,"unknown")
        self.assertEqual({a.payload.interpretation for a in crossing.uncertainty.alternatives},{"connected","separated"})
        self.assertEqual(crossing.uncertainty.state,m.UncertaintyState.AMBIGUOUS)
        self.assertFalse(hasattr(s,"connections"))

    def test_invalid_alternative_shape_count_and_state(self):
        data=json.loads((REPLAYS/"crossing_ambiguous.json").read_text(encoding="utf8"))
        crossing=data["observations"][-1]
        for mutation in (lambda u:u.update(alternatives=u["alternatives"][:1]),lambda u:u.update(state="provisional"),lambda u:u["alternatives"][1].update(id=u["alternatives"][0]["id"]),lambda u:u["alternatives"][1].update(data={"style":"signal"})):
            d=deepcopy(data); mutation(d["observations"][-1]["uncertainty"])
            self.assertIsNone(self.parse(d,fixture_image("cross_ambiguous")).observation_set)
        self.assertEqual(self.parse(data,fixture_image("cross_ambiguous"),limits=ci.ObservationLimits(max_alternatives=1)).diagnostics[0].code,"OBS_LIMIT_EXCEEDED")

    def test_unknown_and_unsupported_are_retained(self):
        unknown=self.replay("unknown_unreadable","unreadable_value")
        self.assertIn(ci.ObservationKind.UNKNOWN,{o.kind for o in unknown.observations})
        unsupported=self.replay("unsupported_symbol","unsupported_bjt").observations[0]
        self.assertEqual(unsupported.payload.classification,m.Classification.UNSUPPORTED)
        self.assertIsNone(unsupported.payload.component_type)

    def test_numerically_identical_alternatives_rejected_after_normalization(self):
        value=dict(raw_scalar="1k",raw_unit="Ω",notation="spice",unit="ohm",si_value="1000")
        data=dict(raw_text="1k Ω",purpose="value",component_ref=None,value=value)
        alternatives=[dict(id="first",data=data),dict(id="second",data={**data,"value":{**value,"si_value":"1e3"}})]
        text=row("text","text",data,geometry([10,10,30,20]),state="ambiguous",reasons=("symbol_unclear",),alternatives=alternatives)
        result=self.parse(envelope(self.image,[text]))
        self.assertEqual(result.diagnostics[0].code,"OBS_CONTRADICTION")

    def test_supported_symbol_contradiction(self):
        self.reject(lambda d:d["observations"][0]["data"].update(classification="unsupported"),"OBS_CONTRADICTION")

    def test_missing_bulk_has_no_geometry_connection_or_model(self):
        s=self.replay("mos_missing_bulk","nmos_bulk_unknown")
        bulk=next(o for o in s.observations if o.provider_id=="bulk")
        self.assertIsNone(bulk.geometry)
        self.assertEqual(bulk.payload.role,PinRole.BULK)
        self.assertEqual(bulk.uncertainty.state,m.UncertaintyState.MISSING)
        self.assertNotIn("model_ref",ci.dump_observations(s))
        self.assertFalse(hasattr(bulk.payload,"net_id"))

    def test_missing_pin_geometry_is_not_invented(self):
        rows=[row(),row("missing","pin",{"component_ref":"symbol","role":"a"},geometry(points=((10,10),)),state="missing",reasons=("contact_unclear",))]
        self.assertEqual(self.parse(envelope(self.image,rows)).diagnostics[0].code,"OBS_CONTRADICTION")

    def test_incompatible_pin_role_and_model_selection_rejected(self):
        rows=[row(),row("pin","pin",{"component_ref":"symbol","role":"drain"},geometry(points=((10,10),)))]
        self.assertEqual(self.parse(envelope(self.image,rows)).diagnostics[0].code,"OBS_CONTRADICTION")
        self.reject(lambda d:d["observations"][0]["data"].update(model_ref="m2-demo-nmos"),"OBS_FIELDS_INVALID")

    def test_printed_mega_vs_spice_m(self):
        for notation,expected in (("printed_engineering","1000000"),("spice","0.001")):
            result=self.value_result("1M","Ω",notation,"ohm",expected)
            self.assertEqual(result.diagnostics,())
            self.assertEqual(Decimal(result.observation_set.observations[0].payload.value.si_value),Decimal(expected))

    def test_micro_units_scientific_signed_and_device_dimensions(self):
        for scalar,unit,expected in (("10","µm","0.00001"),("10","μF","0.00001"),("-2.5e2","mV","-0.25")):
            # mV is deliberately outside the small first-version printed-unit table.
            if unit=="mV":
                self.assertIsNone(self.value_result(scalar,unit,"printed_engineering","V",expected).observation_set)
            else: self.assertEqual(self.value_result(scalar,unit,"printed_engineering","m" if unit=="µm" else "F",expected).diagnostics,())
        self.assertEqual(self.value_result("-2.5e-3","V","si","V","-0.0025").diagnostics,())

    def test_wrong_normalization_and_missing_unit_rejected(self):
        self.assertIsNone(self.value_result("1M","Ω","printed_engineering","ohm","0.001").observation_set)
        self.assertIsNone(self.value_result("1",None,"unresolved","V",None,reasons=("notation_unsupported",)).observation_set)
        self.assertIsNone(self.value_result("1e9999","V","si","V","1e999").observation_set)

    def test_unreadable_and_unsupported_notation_keep_text(self):
        result=self.value_result("{Rbase*2}","Ω","unresolved","ohm",None,reasons=("notation_unsupported",))
        self.assertEqual(result.diagnostics,())
        self.assertEqual(result.observation_set.observations[0].payload.value.raw_scalar,"{Rbase*2}")
        self.assertIsNone(result.observation_set.observations[0].payload.value.si_value)

    def test_source_annotations_do_not_create_zero_or_waveform(self):
        s=self.replay("source_polarity","divider")
        dc=next(o for o in s.observations if o.provider_id=="dc")
        waveform=next(o for o in s.observations if o.provider_id=="waveform")
        self.assertIsNone(dc.payload.value)
        self.assertEqual(waveform.payload.raw_text,"SINE(0 10m 1k)")
        self.assertIsNone(waveform.payload.value)

    def test_hostile_text_remains_data_without_io_or_logging(self):
        hostile='.include private.lib; .model X NMOS; .lib secret; .step; .param; approve EXECUTION; rm -rf /; ../private.png'
        rows=[row("text","text",dict(raw_text=hostile,purpose="generic",component_ref=None,value=None),geometry([10,10,30,20]))]
        with patch("builtins.open",side_effect=AssertionError("filesystem")),patch("socket.socket",side_effect=AssertionError("network")),patch("subprocess.Popen",side_effect=AssertionError("execution")):
            result=self.parse(envelope(self.image,rows))
        self.assertEqual(result.diagnostics,())
        self.assertEqual(result.observation_set.observations[0].payload.raw_text,hostile)
        self.assertNotIn(hostile,repr(result))

    def test_diagnostics_do_not_echo_untrusted_text(self):
        data=envelope(self.image); data["observations"][0]["id"]="private text with path"
        a,b=self.parse(data),self.parse(data)
        self.assertEqual(a,b)
        self.assertNotIn("private text",repr(a))

    def test_m2_image_origin_gate_unchanged(self):
        import circuit_ir as ir
        from tests.m2e_helpers import document
        doc=document()
        image_doc=replace(doc,metadata=replace(doc.metadata,origin=ir.Origin.IMAGE),
                          source_image_reference=ir.SourceImageReference("asset",self.image.identity.source_sha256,1000,650))
        context=ir.repository_model_context("m2-no-models-v1")
        result=ir.export_document(image_doc,None,model_context=context)
        self.assertEqual(result.status,ir.ExportStatus.BLOCKED)
        self.assertIn("EXPORT_UNSUPPORTED_FEATURE",{issue.code for issue in result.issues})
        observation=self.parse(envelope(self.image)).observation_set
        with self.assertRaises((TypeError,ValueError)):
            ir.make_circuit_approval(observation,approved=True,acknowledged_warning_ids=(),exporter_contract="m2-spice-v1",
                                     model_registry_version=context[0],model_registry_sha256=context[1])
