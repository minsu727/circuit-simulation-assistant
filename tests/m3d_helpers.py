"""Hand-prepared observations as engine inputs; truth is evaluation-only."""
from pathlib import Path
import json
import circuit_image as ci
from tests.m3c_helpers import fixture_image, envelope, row, geometry, encode

REPLAYS=Path(__file__).resolve().parent/"fixtures/topology_observations"

def wire(name,a,b,**options):
    return row(name,"wire_segment",{},geometry(points=(a,b)),**options)

def component(name="R1",kind="resistor",box=(20,20,40,20),pose="r0",**options):
    return row(name,data=dict(classification="supported",component_type=kind,observed_name=kind,reference_text=name),g=geometry(list(box),pose=pose),**options)

def pin(name,owner,role,point=None,**options):
    return row(name,"pin",dict(component_ref=owner,role=role),None if point is None else geometry(points=(point,)),**options)

def junction(name,refs,point,meaning="connected",**options):
    return row(name,"junction" if meaning=="connected" else "crossing",dict(wire_refs=list(refs),interpretation=meaning),geometry(points=(point,)),**options)

def label(name,text,wire_ref=None,kind="label",**options):
    return row(name,kind,dict(raw_text=text,attachment_ref=wire_ref),geometry([50,50,60,20]),**options)

def ground(name="g",point=(100,100),**options):
    return row(name,"ground",dict(style="signal"),geometry([point[0]-22,point[1],44,40],points=(point,)),**options)

def build(rows,coverage="reported_complete",image=None,**options):
    image=image or fixture_image()
    parsed=ci.parse_observations(encode(envelope(image,rows,coverage)),image,provider=ci.STATIC_PROVIDER)
    if parsed.observation_set is None: raise AssertionError(parsed.diagnostics)
    return ci.reconstruct_topology(parsed.observation_set,image,**options),parsed.observation_set,image

def replay(name):
    image=fixture_image(name)
    parsed=ci.parse_observations((REPLAYS/(name+".json")).read_bytes(),image,provider=ci.STATIC_PROVIDER)
    if parsed.observation_set is None: raise AssertionError(parsed.diagnostics)
    result=ci.reconstruct_topology(parsed.observation_set,image)
    if result.hypothesis is None: raise AssertionError(result.diagnostics)
    return result.hypothesis,parsed.observation_set,image

def memberships(hypothesis,observations):
    aliases={o.id:o.provider_id for o in observations.observations}
    return {aliases[c.subjects[0]]:c.net_id for c in hypothesis.claims if c.kind=="pin_to_net"}


def reference(name):
    """Golden is loaded ONLY by the evaluation test after engine reconstruction.

    Project annotation geometry and canonical connection rows, never invoke
    production inference/union-find to generate truth or replay observations.
    """
    from tests.m3_fixture_contract import read_json, validate_annotation
    from tests.m3c_helpers import M3B
    from circuit_image import models as m
    from circuit_image.topology_evaluation import (TopologyReference,ReferenceComponent,
        ReferencePin,ReferenceAnchor,ReferenceDecision,ReferenceReview)
    catalog=read_json(M3B/'catalog.json')
    case=next(c for c in catalog['cases'] if c['case_id']==name)
    data=read_json(M3B/case['expected']);validate_annotation(data,case)
    e=data['expected'];regions={r['id']:r for r in data['observations']['regions']}
    junctions={j['id']:j for j in data['observations']['junctions']}
    components=tuple(ReferenceComponent(c['id'],c['type'],m.Box(*regions[c['evidence_ref']]['bbox'])) for c in e['components'])
    pins=tuple(ReferencePin(p['id'],p['component_id'],p['role'],m.Point(*p['position']) if p['position'] else None) for p in e['pins'])
    anchors=tuple(ReferenceAnchor(l['evidence_ref'],'label',m.Box(*regions[l['evidence_ref']]['bbox']),l['text'],l['net_id']) for l in e['labels'])
    anchors+=tuple(ReferenceAnchor(g['id'],'ground',m.Box(*g['bbox']),None,e['ground_net_id']) for g in regions.values() if g['kind']=='ground')
    decisions=tuple(ReferenceDecision(d['observation_id'],m.Point(*junctions[d['observation_id']]['position']),d['meaning']) for d in e['junction_decisions'])
    object_ids={o.id for o in (*components,*pins,*anchors,*decisions)}
    # Quantity issues target their component; rail issues target the exact
    # authored label evidence, not a guessed name or an unlocalized net ID.
    reviews=tuple(ReferenceReview(q['kind'],tuple(t for t in q['targets'] if t in object_ids) or
        tuple(t for t in q['evidence_refs'] if t in object_ids)) for q in e['issues'] if q['required_review'])
    return TopologyReference(case['sha256'],components,pins,tuple(n['id'] for n in e['nets']),
        tuple((c['pin_id'],c['net_id']) for c in e['connections']),
        tuple(tuple((c['pin_id'],c['net_id']) for c in a['connections']) for a in e['alternatives']),
        anchors,decisions,reviews,data['topology_complete'],all(c.type in {t.value for t in m.ComponentType if t is not m.ComponentType.UNKNOWN} for c in components))
