"""Test-only integrity checks for hand-authored M3 image truth.

This is neither a CandidateCircuit loader nor a topology/recognition evaluator.
It checks supplied records; it never infers a connection from pixels/geometry.
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath, PureWindowsPath
import json
import math
import re

VERSION = "m3-fixture-1"
OUTCOMES = {"RESOLVABLE", "NEEDS_REVIEW", "UNSUPPORTED", "INCOMPLETE"}
CATEGORIES = set("ABCDEFGHIJKLMN") | {"ordinary_wire", "near_gap", "bulk_unresolved", "numeric_mega"}
ROLES = {
    "resistor": {"a", "b"}, "capacitor": {"a", "b"}, "inductor": {"a", "b"},
    "voltage_source": {"positive", "negative"}, "current_source": {"positive", "negative"},
    "nmos": {"drain", "gate", "source", "bulk"}, "pmos": {"drain", "gate", "source", "bulk"},
    "unsupported_bjt": {"base", "collector", "emitter"},
}
ISSUES = {"missing_value", "unreadable_value", "model_selection_required", "bulk_unresolved",
          "junction_unclear", "wire_gap", "label_attachment_unresolved", "unsupported_component",
          "supply_definition_missing", "ground_missing"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, names):
    require(type(obj) is dict and set(obj) == set(names.split()), "unexpected/missing fields")


def unique(rows):
    require(type(rows) is list, "records must be lists")
    ids = [row["id"] for row in rows]
    require(all(type(i) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", i) for i in ids), "unsafe ID")
    require(len(ids) == len(set(ids)), "duplicate ID")
    return {row["id"]: row for row in rows}


def read_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON object key")
            out[key] = value
        return out
    def bad_constant(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(Path(path).read_text(encoding="utf8"), object_pairs_hook=pairs, parse_constant=bad_constant)


def safe_path(root, value):
    require(type(value) is str and value and "\\" not in value, "path must be relative POSIX")
    p = PurePosixPath(value)
    require(not p.is_absolute() and not PureWindowsPath(value).drive and ".." not in p.parts,
            "absolute/traversing path")
    result = (Path(root) / value).resolve()
    require(result.is_relative_to(Path(root).resolve()) and result.is_file(), "missing/outside fixture file")
    return result


def validate_catalog(data, root):
    keys(data, "catalog_version annotation_version coordinate_space style cases")
    require(data["catalog_version"] == "m3-images-1" and data["annotation_version"] == VERSION, "catalog version")
    require(data["coordinate_space"] == "original_pixels" and data["style"] == "printed-dot-crossing-v1", "catalog style/frame")
    require(type(data["cases"]) is list and data["cases"], "empty catalog")
    ids, paths = set(), set()
    for case in data["cases"]:
        keys(case, "case_id categories interpretation_state rationale image source expected provenance sha256 width_px height_px source_format media_type ownership annotation_version evaluation_split")
        i = case["case_id"]
        require(type(i) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", i) and i not in ids, "duplicate/unsafe case ID")
        ids.add(i)
        require(case["interpretation_state"] in OUTCOMES, "outcome")
        require(type(case["categories"]) is list and case["categories"] and len(case["categories"]) == len(set(case["categories"])) and set(case["categories"]) <= CATEGORIES, "categories")
        require(type(case["rationale"]) is str and case["rationale"].strip(), "rationale")
        require(case["annotation_version"] == VERSION and case["ownership"] == "repository-original", "ownership/version")
        require(case["source_format"] == "svg" and case["media_type"] == "image/png", "formats")
        require(case["evaluation_split"] == "development", "split")
        require(type(case["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", case["sha256"]), "hash syntax")
        require(all(type(case[k]) is int and 1 <= case[k] <= 4096 for k in ("width_px", "height_px")), "dimensions")
        for kind, filename in (("image", "schematic.png"), ("source", "source.svg"), ("expected", "expected.json"), ("provenance", "provenance.md")):
            value = case[kind]
            require(value == f"cases/{i}/{filename}" and value not in paths, "fixture path association")
            safe_path(root, value)
            paths.add(value)


def validate_annotation(data, case):
    keys(data, "annotation_version case_id coordinate_space interpretation_state topology_complete observations expected")
    require(data["annotation_version"] == VERSION and data["case_id"] == case["case_id"], "annotation identity")
    require(data["interpretation_state"] == case["interpretation_state"] and data["coordinate_space"] == "original_pixels", "annotation outcome/frame")
    require(type(data["topology_complete"]) is bool, "topology completeness")
    w, h = case["width_px"], case["height_px"]
    def point(p):
        require(type(p) is list and len(p) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in p), "point shape/finite")
        require(0 <= p[0] < w and 0 <= p[1] < h, "point outside raster")
    obs = data["observations"]
    keys(obs, "regions wires junctions")
    regions, wires, junctions = (unique(obs[k]) for k in ("regions", "wires", "junctions"))
    evidence = set(regions) | set(wires) | set(junctions)
    require(len(evidence) == len(regions)+len(wires)+len(junctions), "duplicate evidence IDs")
    for r in regions.values():
        keys(r, "id kind bbox text")
        require(r["kind"] in {"symbol", "text", "label", "ground"}, "region kind")
        b = r["bbox"]
        require(type(b) is list and len(b) == 4, "bbox shape")
        point(b[:2])
        require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in b[2:]) and b[0]+b[2] <= w and b[1]+b[3] <= h, "bbox outside raster")
        require(r["text"] is None or type(r["text"]) is str, "text type")
    for r in wires.values():
        keys(r, "id points")
        require(type(r["points"]) is list and len(r["points"]) >= 2, "wire points")
        for p in r["points"]: point(p)
    for r in junctions.values():
        keys(r, "id position wire_ids appearance")
        point(r["position"])
        require(type(r["wire_ids"]) is list and r["wire_ids"] and len(set(r["wire_ids"])) == len(r["wire_ids"]) and set(r["wire_ids"]) <= set(wires), "junction wires")
        require(r["appearance"] in {"filled_dot", "no_dot", "unclear_mark", "endpoint_gap"}, "appearance")
    expected = data["expected"]
    keys(expected, "components pins nets connections labels ground_net_id junction_decisions issues alternatives model_choices")
    components, pins, nets, issues, alternatives = (unique(expected[k]) for k in ("components", "pins", "nets", "issues", "alternatives"))
    entities = set(components) | set(pins) | set(nets) | evidence
    require(len(entities) == len(components)+len(pins)+len(nets)+len(evidence), "duplicate entity IDs")
    def refs(values, allowed):
        require(type(values) is list and values and len(set(values)) == len(values) and set(values) <= set(allowed), "unresolved/duplicate references")
    def quantity(q):
        if q is None: return
        keys(q, "raw_text unit_text notation si_value unit state")
        require(q["state"] in {"known", "missing", "unreadable", "ambiguous"}, "value state")
        require(q["unit"] in {None, "ohm", "F", "H", "V", "A", "m", "Hz", "s", "deg"}, "value unit")
        require(q["raw_text"] is None or type(q["raw_text"]) is str, "raw value text")
        require(q["unit_text"] is None or type(q["unit_text"]) is str, "unit text")
        if q["state"] == "known":
            require(q["raw_text"] and q["unit_text"] and q["unit"] and q["notation"] == "printed-engineering", "known value without explicit text/unit")
            require(type(q["si_value"]) is str and len(q["si_value"]) <= 128 and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?", q["si_value"]), "SI scalar syntax")
            try: require(Decimal(q["si_value"]).is_finite(), "non-finite SI")
            except InvalidOperation as exc: raise ValueError("invalid SI scalar") from exc
        else:
            require(q["si_value"] is None and q["notation"] == "unresolved", "invented unresolved value")
            if q["state"] == "missing": require(q["raw_text"] is None and q["unit_text"] is None and q["unit"] is None, "missing text/unit invented")
    for c in components.values():
        keys(c, "id type reference evidence_ref label_ref value source_dc")
        require(c["type"] in ROLES and c["reference"] == c["id"], "component type/reference")
        require(c["evidence_ref"] in regions and regions[c["evidence_ref"]]["kind"] == "symbol", "symbol evidence")
        require(c["label_ref"] in regions and regions[c["label_ref"]]["kind"] == "text", "label evidence")
        quantity(c["value"]); quantity(c["source_dc"])
        if c["type"] in {"voltage_source", "current_source"}:
            require(c["value"] is None and c["source_dc"] is not None, "source field boundary")
            require(c["source_dc"]["unit"] == ("V" if c["type"] == "voltage_source" else "A"), "source dimension")
        elif c["type"] in {"resistor", "capacitor", "inductor"}:
            require(c["value"] is not None and c["source_dc"] is None, "passive field boundary")
            require(c["value"]["unit"] == {"resistor":"ohm", "capacitor":"F", "inductor":"H"}[c["type"]] or c["value"]["state"] == "missing" and c["value"]["unit"] is None, "passive dimension")
        else: require(c["value"] is None and c["source_dc"] is None, "MOS/unsupported scalar invented")
    for p in pins.values():
        keys(p, "id component_id role position evidence_ref")
        require(p["component_id"] in components and p["evidence_ref"] in regions, "pin ownership/evidence")
        require(p["role"] in ROLES[components[p["component_id"]]["type"]], "pin role")
        if p["position"] is not None: point(p["position"])
    for c in components.values():
        roles = [p["role"] for p in pins.values() if p["component_id"] == c["id"]]
        require(len(roles) == len(set(roles)) and set(roles) == ROLES[c["type"]], "missing/duplicate terminal roles")
    for n in nets.values():
        keys(n, "id is_ground")
        require(type(n["is_ground"]) is bool, "ground bool")
    def ground(g):
        require(g is None or g in nets and nets[g]["is_ground"], "ground reference")
    ground(expected["ground_net_id"])
    require({n["id"] for n in nets.values() if n["is_ground"]} == ({expected["ground_net_id"]} if expected["ground_net_id"] else set()), "ground disagreement")
    def connections(rows, complete):
        require(type(rows) is list, "connections list")
        assignment = {}
        for row in rows:
            keys(row, "pin_id net_id evidence_refs")
            p, n = row["pin_id"], row["net_id"]
            require(p in pins and n in nets, "connection reference")
            require(p not in assignment, "duplicate/contradictory connection")
            require(pins[p]["position"] is not None, "connection for unseen terminal")
            refs(row["evidence_refs"], evidence)
            assignment[p] = n
        if complete: require(set(assignment) == set(pins), "incomplete topology marked complete")
        return assignment
    base = connections(expected["connections"], data["topology_complete"])
    require(type(expected["labels"]) is list and len({l["evidence_ref"] for l in expected["labels"]}) == len(expected["labels"]), "duplicate label attachment")
    for label in expected["labels"]:
        keys(label, "evidence_ref text net_id scope")
        require(label["evidence_ref"] in regions and regions[label["evidence_ref"]]["kind"] == "label" and regions[label["evidence_ref"]]["text"] == label["text"], "label evidence")
        require(label["scope"] == "flat" and (label["net_id"] is None or label["net_id"] in nets), "label scope/net")
    seen_labels = {}
    for label in expected["labels"]:
        key = label["text"].strip().lower()
        if label["net_id"] is not None:
            require(key not in seen_labels or seen_labels[key] == label["net_id"], "contradictory shared label")
            seen_labels[key] = label["net_id"]
    decisions = expected["junction_decisions"]
    require(type(decisions) is list and len({d["observation_id"] for d in decisions}) == len(decisions), "duplicate junction decision")
    require({d["observation_id"] for d in decisions} == set(junctions), "unaccounted junction")
    for d in decisions:
        keys(d, "observation_id meaning net_ids reason")
        j = junctions[d["observation_id"]]
        require(d["meaning"] in {"continuous", "connected", "separated", "unresolved"} and type(d["reason"]) is str and d["reason"].strip(), "junction meaning/reason")
        require(type(d["net_ids"]) is list and set(d["net_ids"]) <= set(nets) and len(set(d["net_ids"])) == len(d["net_ids"]), "junction nets")
        require(d["meaning"] != "connected" or len(d["net_ids"]) == 1, "connected junction group")
        require(d["meaning"] != "separated" or len(d["net_ids"]) >= 2, "separated junction groups")
        if d["meaning"] == "unresolved": require(not d["net_ids"] and not data["topology_complete"] and any(d["observation_id"] in i["targets"] for i in issues.values()), "unresolved junction selected")
        if j["appearance"] == "filled_dot": require(d["meaning"] == "connected", "contradictory filled dot")
        if j["appearance"] == "no_dot": require(d["meaning"] == "separated", "contradictory no-dot crossing")
    for i in issues.values():
        keys(i, "id kind targets evidence_refs required_review message alternative_ids")
        require(i["kind"] in ISSUES and i["required_review"] is True and type(i["message"]) is str and i["message"].strip(), "issue kind/review")
        refs(i["targets"], entities); refs(i["evidence_refs"], evidence)
        require(type(i["alternative_ids"]) is list and len(set(i["alternative_ids"])) == len(i["alternative_ids"]) and set(i["alternative_ids"]) <= set(alternatives), "issue alternatives")
    for c in components.values():
        if c["value"] and c["value"]["state"] in {"missing", "unreadable"}:
            required_kind = c["value"]["state"] + "_value"
            require(any(i["kind"] == required_kind and c["id"] in i["targets"] for i in issues.values()), "missing value review")
    for label in expected["labels"]:
        if label["net_id"] is None:
            require(any(i["kind"] == "label_attachment_unresolved" and label["evidence_ref"] in i["targets"] for i in issues.values()), "unresolved label review")
    for a in alternatives.values():
        keys(a, "id issue_id description connections ground_net_id")
        require(a["issue_id"] in issues and a["id"] in issues[a["issue_id"]]["alternative_ids"], "alternative owner")
        require(type(a["description"]) is str and a["description"].strip(), "alternative description")
        assignment = connections(a["connections"], True)
        require(all(assignment.get(p) == n for p,n in base.items()), "alternative contradicts settled truth")
        ground(a["ground_net_id"])
    partitions = [tuple(sorted((r["pin_id"], r["net_id"]) for r in a["connections"])) for a in alternatives.values()]
    require(len(set(partitions)) == len(partitions), "duplicate alternative truth")
    state = data["interpretation_state"]
    require((state == "RESOLVABLE") == (not issues), "resolvable/review mismatch")
    if state == "RESOLVABLE": require(data["topology_complete"] and not alternatives, "resolvable topology")
    if state == "NEEDS_REVIEW": require(alternatives and not data["topology_complete"], "review alternatives")
    require((state == "UNSUPPORTED") == any(i["kind"] == "unsupported_component" for i in issues.values()), "unsupported outcome mismatch")
    if state == "INCOMPLETE": require(not alternatives, "incomplete topology alternatives")
    choices = expected["model_choices"]
    require(type(choices) is list and len({c["component_id"] for c in choices}) == len(choices), "model choices")
    require({c["component_id"] for c in choices} == {c["id"] for c in components.values() if c["type"] in {"nmos", "pmos"}}, "MOS model accounting")
    for c in choices:
        keys(c, "component_id profile required_parameters")
        require(c["profile"] is None and c["required_parameters"] == ["width", "length"], "invented model/geometry")
        require(any(i["kind"] == "model_selection_required" and c["component_id"] in i["targets"] for i in issues.values()), "MOS required review")
    for p in pins.values():
        if p["position"] is None:
            require(p["id"] not in base and any(i["kind"] == "bulk_unresolved" and p["id"] in i["targets"] for i in issues.values()), "unseen terminal review")
