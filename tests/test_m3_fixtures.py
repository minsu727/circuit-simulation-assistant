"""Owned-image integrity only. No Vision/OCR, network, simulator or approval."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import re
import unittest
import xml.etree.ElementTree as ET

from PIL import Image
from tests.m3_fixture_contract import read_json, safe_path, validate_annotation, validate_catalog

ROOT = Path(__file__).resolve().parent / "fixtures/schematic_images"
CATALOG = read_json(ROOT / "catalog.json")
CASES = {case["case_id"]: case for case in CATALOG["cases"]}


def truth(name):
    return read_json(ROOT / CASES[name]["expected"])


def memberships(data):
    return {c["pin_id"]: c["net_id"] for c in data["expected"]["connections"]}


class M3FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {p.relative_to(ROOT): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in ROOT.rglob("*") if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        current = {p.relative_to(ROOT): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in ROOT.rglob("*") if p.is_file()}
        if current != cls.original:
            raise AssertionError("Fixture assets changed during read-only integrity tests")

    def reject(self, name, edit):
        data = deepcopy(truth(name))
        edit(data)
        with self.assertRaises(ValueError):
            validate_annotation(data, CASES[name])

    def test_catalog_contract(self):
        validate_catalog(CATALOG, ROOT)
        self.assertEqual(set(CASES), {p.name for p in (ROOT / "cases").iterdir() if p.is_dir()})

    def test_category_coverage(self):
        covered = set().union(*(set(c["categories"]) for c in CASES.values()))
        self.assertEqual(covered, set("ABCDEFGHIJKLMN") | {"ordinary_wire", "near_gap", "bulk_unresolved", "numeric_mega"})

    def test_png_decoding_dimensions_and_digests(self):
        for case in CASES.values():
            with self.subTest(case=case["case_id"]):
                p = safe_path(ROOT, case["image"])
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), case["sha256"])
                with Image.open(p) as image:
                    self.assertEqual(image.format, "PNG")
                    image.verify()
                with Image.open(p) as image:
                    image.load()
                    self.assertEqual(image.size, (case["width_px"], case["height_px"]))
                    self.assertEqual(image.mode, "L")
                    self.assertLess(p.stat().st_size, 150_000)

    def test_svg_originals_are_bounded_static_sources(self):
        allowed = {"svg", "rect", "polyline", "text", "circle"}
        for case in CASES.values():
            with self.subTest(case=case["case_id"]):
                tree = ET.parse(safe_path(ROOT, case["source"]))
                root = tree.getroot()
                self.assertEqual(root.attrib["viewBox"], f'0 0 {case["width_px"]} {case["height_px"]}')
                for element in root.iter():
                    self.assertIn(element.tag.split("}")[-1], allowed)
                    self.assertFalse(any("href" in key or key.startswith("on") for key in element.attrib))

    def test_annotations_resolve_without_production_inference(self):
        for case in CASES.values():
            with self.subTest(case=case["case_id"]):
                validate_annotation(read_json(ROOT / case["expected"]), case)

    def test_owned_provenance_and_independent_review_notes(self):
        for case in CASES.values():
            text = safe_path(ROOT, case["provenance"]).read_text(encoding="utf8")
            for phrase in ("Original drawing created", "Independent electrical review",
                           "written separately", "Deliberately unresolved", "authoring agent"):
                self.assertIn(phrase, text)
            self.assertEqual(case["evaluation_split"], "development")

    def test_no_personal_paths_or_credentials(self):
        patterns = (r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", r"\\\\[^\s\\]+\\", r"/Users/", r"/home/",
                    r"sk-[A-Za-z0-9_-]{20,}", r"gh[pousr]_[A-Za-z0-9]{20,}",
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for p in ROOT.rglob("*"):
            if p.suffix not in {".json", ".svg", ".md"}: continue
            text = p.read_text(encoding="utf8")
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, text), f"private material in {p.relative_to(ROOT)}")

    def test_no_unlisted_case_outputs(self):
        for case in CASES.values():
            self.assertEqual({p.name for p in (ROOT / "cases" / case["case_id"]).iterdir()},
                             {"schematic.png", "source.svg", "expected.json", "provenance.md"})

    def test_catalog_duplicate_id_rejected(self):
        catalog = deepcopy(CATALOG)
        catalog["cases"].append(deepcopy(catalog["cases"][0]))
        with self.assertRaises(ValueError): validate_catalog(catalog, ROOT)

    def test_catalog_unknown_field_rejected(self):
        catalog = deepcopy(CATALOG)
        catalog["approval"] = True
        with self.assertRaises(ValueError): validate_catalog(catalog, ROOT)

    def test_catalog_missing_field_rejected(self):
        catalog = deepcopy(CATALOG)
        del catalog["cases"][0]["sha256"]
        with self.assertRaises(ValueError): validate_catalog(catalog, ROOT)

    def test_absolute_and_traversing_paths_rejected(self):
        for path in ("../catalog.json", "C:/private/file.png", "/private/file.png", "cases\\bad.png"):
            with self.subTest(path=path), self.assertRaises(ValueError): safe_path(ROOT, path)

    def test_duplicate_json_keys_rejected(self):
        with TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text('{"id":1,"id":2}', encoding="utf8")
            with self.assertRaises(ValueError): read_json(p)

    def test_nonfinite_json_rejected(self):
        with TemporaryDirectory() as temp:
            p = Path(temp) / "bad.json"
            p.write_text('{"value":NaN}', encoding="utf8")
            with self.assertRaises(ValueError): read_json(p)

    def test_duplicate_component_rejected(self):
        self.reject("divider", lambda d: d["expected"]["components"].append(deepcopy(d["expected"]["components"][0])))

    def test_duplicate_connection_rejected(self):
        self.reject("divider", lambda d: d["expected"]["connections"].append(deepcopy(d["expected"]["connections"][0])))

    def test_contradictory_connection_rejected(self):
        def edit(d):
            row = deepcopy(d["expected"]["connections"][0]); row["net_id"] = "gnd"
            d["expected"]["connections"].append(row)
        self.reject("divider", edit)

    def test_unknown_pin_net_and_evidence_rejected(self):
        for field, value in (("pin_id", "unknown.pin"), ("net_id", "unknown_net"), ("evidence_refs", ["unknown_evidence"])):
            with self.subTest(field=field):
                self.reject("divider", lambda d: d["expected"]["connections"][0].__setitem__(field, value))

    def test_pin_ownership_and_role_rejected(self):
        for field,value in (("component_id", "unknown"), ("role", "drain")):
            self.reject("divider", lambda d: d["expected"]["pins"][0].__setitem__(field,value))

    def test_unknown_annotation_field_rejected(self):
        self.reject("divider", lambda d: d.__setitem__("approval", True))

    def test_missing_membership_cannot_claim_complete(self):
        self.reject("divider", lambda d: d["expected"]["connections"].pop())

    def test_out_of_bounds_evidence_rejected(self):
        self.reject("divider", lambda d: d["observations"]["regions"][0].__setitem__("bbox", [950,600,100,100]))

    def test_filled_dot_cannot_be_separated(self):
        self.reject("cross_dot", lambda d: d["expected"]["junction_decisions"][0].__setitem__("meaning", "separated"))

    def test_no_dot_crossing_cannot_be_connected(self):
        self.reject("cross_open", lambda d: d["expected"]["junction_decisions"][0].__setitem__("meaning", "connected"))

    def test_crossing_goldens_distinguish_intersection_and_connectivity(self):
        separated, joined = memberships(truth("cross_open")), memberships(truth("cross_dot"))
        self.assertEqual(separated["R1.b"], separated["R2.a"])
        self.assertEqual(separated["R3.b"], separated["R4.a"])
        self.assertNotEqual(separated["R1.b"], separated["R3.b"])
        self.assertEqual(len({joined[p] for p in ("R1.b", "R2.a", "R3.b", "R4.a")}), 1)

    def test_ambiguous_crossing_has_no_selected_inner_memberships(self):
        data = truth("cross_ambiguous")
        self.assertEqual(data["interpretation_state"], "NEEDS_REVIEW")
        self.assertFalse({"R1.b", "R2.a", "R3.b", "R4.a"} & set(memberships(data)))
        self.assertEqual({a["id"] for a in data["expected"]["alternatives"]}, {"joined", "separated"})

    def test_near_gap_is_unresolved_not_proximity_joined(self):
        data = truth("near_gap")
        self.assertNotIn("R1.b", memberships(data)); self.assertNotIn("R2.a", memberships(data))
        self.assertEqual(data["expected"]["junction_decisions"][0]["meaning"], "unresolved")
        self.assertEqual(data["expected"]["labels"][1]["net_id"], None)

    def test_nmos_and_pmos_terminal_role_goldens(self):
        n, p = memberships(truth("nmos")), memberships(truth("pmos"))
        self.assertEqual([n["M1."+r] for r in ("drain", "gate", "source", "bulk")], ["vout", "vin", "gnd", "gnd"])
        self.assertEqual([p["M1."+r] for r in ("drain", "gate", "source", "bulk")], ["vout", "vin", "vdd", "vdd"])
        self.assertEqual(truth("pmos")["expected"]["model_choices"][0]["profile"], None)

    def test_absent_bulk_is_not_tied_to_source(self):
        data = truth("nmos_bulk_unknown")
        self.assertNotIn("M1.bulk", memberships(data))
        self.assertIsNone(next(p for p in data["expected"]["pins"] if p["role"] == "bulk")["position"])

    def test_missing_and_unreadable_values_have_no_numeric_answer(self):
        for name, state in (("missing_value", "missing"), ("unreadable_value", "unreadable")):
            value = next(c for c in truth(name)["expected"]["components"] if c["id"] == "C1")["value"]
            self.assertEqual(value["state"], state); self.assertIsNone(value["si_value"])
        self.assertIsNone(truth("missing_value")["expected"]["components"][2]["value"]["unit"])

    def test_unresolved_numeric_value_cannot_be_invented(self):
        self.reject("unreadable_value", lambda d: d["expected"]["components"][2]["value"].__setitem__("si_value", "0.0000001"))

    def test_known_numeric_answer_requires_explicit_unit_evidence(self):
        self.reject("rc", lambda d: d["expected"]["components"][2]["value"].__setitem__("unit_text", None))

    def test_engineering_literals_preserve_exact_normalizations(self):
        values = {c["value"]["raw_text"]: c["value"] for case in CASES for c in truth(case)["expected"]["components"] if c["value"] and c["value"]["state"] == "known"}
        for raw, expected in {"1k":"1000", "10k":"10000", "1M":"1000000", "100n":"0.0000001", "10u":"0.00001", "1p":"0.000000000001"}.items():
            self.assertEqual(Decimal(values[raw]["si_value"]), Decimal(expected))
            self.assertEqual(values[raw]["notation"], "printed-engineering")
        self.assertEqual(values["1M"]["unit_text"], "Ω")

    def test_voltage_polarity_and_current_direction_are_explicit(self):
        data = truth("rotated_sources"); member = memberships(data)
        pins = {p["id"]: p for p in data["expected"]["pins"]}
        self.assertGreater(pins["V1.positive"]["position"][0], pins["V1.negative"]["position"][0])
        self.assertEqual(member["I1.positive"], "vout"); self.assertEqual(member["I1.negative"], "gnd")

    def test_shared_labels_join_disconnected_drawing_segments(self):
        data = truth("shared_labels")
        self.assertEqual(memberships(data)["R1.b"], memberships(data)["C1.a"])
        self.assertEqual([l["text"] for l in data["expected"]["labels"]][1:], ["VOUT", "vout"])

    def test_supply_label_creates_neither_source_nor_ground(self):
        expected = truth("supply_unknown")["expected"]
        self.assertFalse(any(c["type"] == "voltage_source" for c in expected["components"]))
        self.assertIsNone(expected["ground_net_id"])
        self.assertFalse(any(n["is_ground"] for n in expected["nets"]))

    def test_unsupported_bjt_retained_without_mos_substitution(self):
        data = truth("unsupported_bjt")
        self.assertEqual(data["interpretation_state"], "UNSUPPORTED")
        self.assertEqual(data["expected"]["components"][0]["type"], "unsupported_bjt")

    def test_required_review_cannot_be_removed(self):
        self.reject("missing_value", lambda d: d["expected"].__setitem__("issues", []))

    def test_alternative_cannot_contradict_settled_membership(self):
        self.reject("cross_ambiguous", lambda d: d["expected"]["alternatives"][0]["connections"][0].__setitem__("net_id", "right"))

    def test_unsupported_outcome_cannot_be_downgraded(self):
        self.reject("unsupported_bjt", lambda d: d["expected"]["issues"][0].__setitem__("kind", "missing_value"))

    def test_wrong_quantity_dimension_rejected(self):
        self.reject("rc", lambda d: d["expected"]["components"][2]["value"].__setitem__("unit", "ohm"))

    def test_duplicate_label_attachment_rejected(self):
        self.reject("shared_labels", lambda d: d["expected"]["labels"].append(deepcopy(d["expected"]["labels"][0])))

    def test_ground_reference_disagreement_rejected(self):
        self.reject("divider", lambda d: d["expected"].__setitem__("ground_net_id", "vin"))

    def test_duplicate_alternative_truth_rejected(self):
        self.reject("cross_ambiguous", lambda d: d["expected"]["alternatives"][1].__setitem__("connections", deepcopy(d["expected"]["alternatives"][0]["connections"])))

    def test_unknown_issue_target_rejected(self):
        self.reject("missing_value", lambda d: d["expected"]["issues"][0].__setitem__("targets", ["unknown_target"]))


if __name__ == "__main__":
    unittest.main()
