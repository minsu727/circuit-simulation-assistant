"""Prepared-observation comparison against an independent, in-memory target.

This is evaluation, not reconstruction, recognition accuracy or M1 validation.
The engine never receives these reference records. No file/provider/process I/O.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
import math
import re
from . import models as m
from .topology import label_identity, validate_topology
from .topology_models import TopologyState

EVALUATION_VERSION = "m3-evaluation-1"


@dataclass(frozen=True, slots=True)
class ReferenceComponent:
    id: str
    type: str
    bbox: m.Box


@dataclass(frozen=True, slots=True)
class ReferencePin:
    id: str
    component_id: str
    role: str
    position: m.Point | None


@dataclass(frozen=True, slots=True)
class ReferenceAnchor:
    id: str
    kind: str  # label or ground
    bbox: m.Box
    text: str | None
    net_id: str | None


@dataclass(frozen=True, slots=True)
class ReferenceDecision:
    id: str
    position: m.Point
    meaning: str


@dataclass(frozen=True, slots=True)
class ReferenceReview:
    kind: str
    targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TopologyReference:
    source_sha256: str
    components: tuple[ReferenceComponent, ...]
    pins: tuple[ReferencePin, ...]
    nets: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]
    alternative_partitions: tuple[tuple[tuple[str, str], ...], ...]
    anchors: tuple[ReferenceAnchor, ...]
    decisions: tuple[ReferenceDecision, ...]
    reviews: tuple[ReferenceReview, ...]
    topology_complete: bool
    supported: bool


@dataclass(frozen=True, slots=True)
class TopologyEvaluation:
    metrics: dict | None
    diagnostics: tuple[m.Diagnostic, ...]


def _iou(a, b):
    if a is None or b is None: return Fraction(0)
    x=max(Fraction(0),min(Fraction(a.x)+Fraction(a.width),Fraction(b.x)+Fraction(b.width))-max(Fraction(a.x),Fraction(b.x)))
    y=max(Fraction(0),min(Fraction(a.y)+Fraction(a.height),Fraction(b.y)+Fraction(b.height))-max(Fraction(a.y),Fraction(b.y)))
    intersection=x*y
    return intersection/(Fraction(a.width)*Fraction(a.height)+Fraction(b.width)*Fraction(b.height)-intersection)


def _distance(a,b):
    return math.hypot(a.x-b.x,a.y-b.y)


def _matching(left, right, weights):
    """Max cardinality, then max weight, then lexicographic pair-list minimum.

    Bounded min-cost unit-capacity flow. Tuple costs and exact tie bits avoid
    arbitrary epsilon, greedy collisions and factorial matching enumeration.
    Weights are IoU, negative Euclidean distance, or role-correct pin overlap.
    """
    left,right=sorted(left),sorted(right)
    if len(left)>128 or len(right)>128 or len(weights)>4096: raise ValueError("Matching budget")
    pairs=sorted(weights)
    source,sink=("source",),("sink",)
    graph={source:[],sink:[]}
    def edge(a,b,cost):
        graph.setdefault(a,[]);graph.setdefault(b,[])
        graph[a].append([b,1,cost,len(graph[b])])
        graph[b].append([a,0,tuple(-x for x in cost),len(graph[a])-1])
    for a in left: edge(source,("left",a),(Fraction(0),0))
    for b in right: edge(("right",b),sink,(Fraction(0),0))
    handles={}
    for rank,(a,b) in enumerate(pairs):
        handles[a,b]=(("left",a),len(graph[("left",a)]))
        edge(("left",a),("right",b),(-weights[a,b],-(1<<(len(pairs)-rank-1))))
    # Residual reverse edges permit revising earlier choices without losing
    # maximum cardinality. Bellman-Ford supports negative exact tuple costs.
    while True:
        dist={source:(Fraction(0),0)};previous={}
        for _ in range(len(graph)-1):
            changed=False
            for a in sorted(graph):
                if a not in dist: continue
                for index,(b,capacity,cost,_) in enumerate(graph[a]):
                    candidate=tuple(x+y for x,y in zip(dist[a],cost))
                    if capacity and (b not in dist or candidate<dist[b]):
                        dist[b]=candidate;previous[b]=(a,index);changed=True
            if not changed: break
        if sink not in previous: break
        b=sink
        while b!=source:
            a,index=previous[b];e=graph[a][index];e[1]=0;graph[b][e[3]][1]=1;b=a
    return {a:b for (a,b),(node,index) in handles.items() if graph[node][index][1]==0}


def _check_reference(r, source):
    if type(r) is not TopologyReference or r.source_sha256!=source or not re.fullmatch('[0-9a-f]{64}',r.source_sha256): raise ValueError("Identity")
    collections=(r.components,r.pins,r.nets,r.connections,r.alternative_partitions,r.anchors,r.decisions,r.reviews)
    if any(type(c) is not tuple for c in collections): raise ValueError("Tuple contract")
    if len(r.components)>64 or len(r.pins)>128 or len(r.nets)>128 or len(r.anchors)>64 or len(r.decisions)>64 or len(r.reviews)>64 or len(r.alternative_partitions)>8: raise ValueError("Reference budget")
    if type(r.topology_complete) is not bool or type(r.supported) is not bool: raise ValueError("Flags")
    objects=(*r.components,*r.pins,*r.anchors,*r.decisions)
    ids=[o.id for o in objects]
    if any(type(i) is not str or not i or len(i)>256 for i in (*ids,*r.nets)) or len(set(ids))!=len(ids) or len(set(r.nets))!=len(r.nets): raise ValueError("Duplicate/invalid ID")
    if any(type(o) is not t for rows,t in ((r.components,ReferenceComponent),(r.pins,ReferencePin),(r.anchors,ReferenceAnchor),(r.decisions,ReferenceDecision),(r.reviews,ReferenceReview)) for o in rows): raise ValueError("Record type")
    def point(p):
        if type(p) is not m.Point or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=32768 for v in (p.x,p.y)): raise ValueError("Point")
    def box(b):
        if type(b) is not m.Box: raise ValueError("Box")
        point(m.Point(b.x,b.y));point(m.Point(b.width,b.height))
        if min(b.width,b.height)<=0 or max(b.x+b.width,b.y+b.height)>32768: raise ValueError("Box bounds")
    for c in r.components:
        box(c.bbox)
        if type(c.type) is not str or not c.type: raise ValueError("Component type")
    owners={c.id for c in r.components};pins={p.id for p in r.pins}
    for p in r.pins:
        if p.component_id not in owners or type(p.role) is not str or not p.role: raise ValueError("Pin reference")
        if p.position is not None: point(p.position)
    for a in r.anchors:
        box(a.bbox)
        if a.kind not in {'label','ground'} or a.net_id is not None and a.net_id not in r.nets or a.kind=='label' and (type(a.text) is not str or len(a.text)>4096): raise ValueError("Anchor")
    for d in r.decisions:
        point(d.position)
        if d.meaning not in {'connected','separated','unresolved'}: raise ValueError("Decision")
    for q in r.reviews:
        if type(q.kind) is not str or type(q.targets) is not tuple or not q.targets or any(t not in ids for t in q.targets): raise ValueError("Review reference")
    for partition in (r.connections,*r.alternative_partitions):
        if type(partition) is not tuple or len(partition)>128: raise ValueError("Partition")
        if any(type(v) is not tuple or len(v)!=2 or v[0] not in pins or v[1] not in r.nets for v in partition) or len({p for p,n in partition})!=len(partition): raise ValueError("Connection reference")
    if r.topology_complete and r.alternative_partitions: raise ValueError("No unique topology")


def evaluate_topology(hypothesis, observations, image, reference) -> TopologyEvaluation:
    """Validate prediction identity, then compare. No reference reaches engine."""
    diagnostics=validate_topology(hypothesis,observations,image)
    if diagnostics: return TopologyEvaluation(None,diagnostics)
    try:
        _check_reference(reference,hypothesis.source_sha256)
        return TopologyEvaluation(_evaluate(hypothesis,observations,reference),())
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError):
        return TopologyEvaluation(None,(m.diagnostic('TOPOLOGY_REFERENCE_INVALID','reference'),))


def _evaluate(h,s,r):
    by={o.id:o for o in s.observations}
    components={c.observation_id:c for c in h.components}
    component_match=_matching([c.id for c in r.components],components,
        {(t.id,p):_iou(t.bbox,by[p].geometry.bbox) for t in r.components for p in components if _iou(t.bbox,by[p].geometry.bbox)>=Fraction(1,2)})
    correspondence=dict(component_match)
    component_errors=[c.id for c in r.components if c.id not in component_match or
        (components[component_match[c.id]].payload.component_type.value if components[component_match[c.id]].payload.component_type else 'unsupported')!=c.type]
    terminal_match={}
    for c in r.components:
        if c.id not in component_match: continue
        truth=[p for p in r.pins if p.component_id==c.id and p.position is not None]
        pred=[p for p in h.terminals if p.component_observation_id==component_match[c.id] and by[p.observation_id].geometry]
        matches=_matching([p.id for p in truth],[p.observation_id for p in pred],
            {(t.id,p.observation_id):-Fraction(_distance(t.position,by[p.observation_id].geometry.points[0])) for t in truth for p in pred if _distance(t.position,by[p.observation_id].geometry.points[0])<=12})
        terminal_match.update(matches)
        # Null-position missing terminals are review targets only, excluded from
        # localization and assignment denominators. Never repair visible roles.
        for missing in (p for p in r.pins if p.component_id==c.id and p.position is None):
            candidates=[p.observation_id for p in h.terminals if p.component_observation_id==component_match[c.id] and p.role.value==missing.role and by[p.observation_id].geometry is None]
            if len(candidates)==1: correspondence[missing.id]=candidates[0]
    correspondence.update(terminal_match)
    roles={p.observation_id:p.role.value for p in h.terminals}
    visible=[p for p in r.pins if p.position is not None]
    role_errors=[p.id for p in visible if p.id not in terminal_match or roles[terminal_match[p.id]]!=p.role]
    pin_claims={c.subjects[0]:c.net_id for c in h.claims if c.kind=='pin_to_net' and c.decision=='attached'}
    predicted={p.id:pin_claims.get(terminal_match.get(p.id)) for p in visible}
    truth=dict(r.connections)
    anchor_match={}
    for kind in ('label','ground'):
        targets=[a for a in r.anchors if a.kind==kind]
        candidates=[o for o in s.observations if o.kind in ({m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL} if kind=='label' else {m.ObservationKind.GROUND})]
        anchor_match.update(_matching([a.id for a in targets],[o.id for o in candidates],
            {(a.id,o.id):_iou(a.bbox,o.geometry.bbox) for a in targets for o in candidates if _iou(a.bbox,o.geometry.bbox)>=Fraction(1,2)}))
    correspondence.update(anchor_match)
    pred_labels={n.id:{label_identity(by[i].payload.raw_text) for i in n.label_observation_ids} for n in h.nets}
    truth_labels={n:{label_identity(a.text) for a in r.anchors if a.kind=='label' and a.net_id==n} for n in r.nets}
    pred_ground={n.id:bool(n.ground_observation_ids) for n in h.nets}
    truth_ground={n:any(a.kind=='ground' and a.net_id==n for a in r.anchors) for n in r.nets}
    overlap={}
    for pn in pred_ground:
        for tn in r.nets:
            if pred_ground[pn]!=truth_ground[tn] or pred_labels[pn]!=truth_labels[tn]: continue
            score=sum(p.id not in role_errors and predicted.get(p.id)==pn and truth.get(p.id)==tn for p in visible)
            if score: overlap[pn,tn]=Fraction(score)
    net_match=_matching(pred_ground,r.nets,overlap)
    correct=sum(p.id not in role_errors and predicted.get(p.id) is not None and net_match.get(predicted[p.id])==truth.get(p.id) for p in visible if p.id in truth)
    scenarios=[dict(p) for p in r.alternative_partitions] or [truth]
    false_joins=[];missing_joins=[];unknown_joins=[];truth_joined=0;pred_joined=0
    for a,b in combinations(sorted(p.id for p in visible),2):
        dispositions=[None if a not in q or b not in q else q[a]==q[b] for q in scenarios]
        relation=dispositions[0] if all(v==dispositions[0] for v in dispositions) else None
        joined=predicted.get(a) is not None and predicted.get(a)==predicted.get(b)
        pred_joined+=int(joined);truth_joined+=int(relation is True)
        if joined and relation is False: false_joins.append([a,b])
        if not joined and relation is True: missing_joins.append([a,b])
        if joined and relation is None: unknown_joins.append([a,b])
    unmatched_pred=set(pin_claims)-set(terminal_match.values())
    spurious_pairs=sum(a in unmatched_pred or b in unmatched_pred for a,b in combinations(sorted(pin_claims),2) if pin_claims[a]==pin_claims[b])
    merge_errors=sum(len({truth[p] for p in truth if predicted.get(p)==n})>1 for n in pred_ground)
    active_truth=set(truth.values())
    split_errors=sum(any(predicted.get(p) is None for p in truth if truth[p]==n) or len({predicted[p] for p in truth if truth[p]==n and predicted.get(p) is not None})>1 for n in active_truth)
    label_errors=[];ground_errors=[]
    for a in r.anchors:
        observed=by.get(anchor_match.get(a.id))
        net=next((n.id for n in h.nets if observed and observed.id in (n.label_observation_ids if a.kind=='label' else n.ground_observation_ids)),None)
        good=observed is not None and (a.net_id is None and net is None or a.net_id is not None and net_match.get(net)==a.net_id)
        if a.kind=='label': good=good and label_identity(observed.payload.raw_text)==label_identity(a.text) if observed else False
        if not good: (label_errors if a.kind=='label' else ground_errors).append(a.id)
    # Added ground/labels also invalidate exact topology; unmatched geometry
    # cannot be hidden by matching text or a favorable partition renaming.
    anchor_pred={o.id for o in s.observations if o.kind in {m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL,m.ObservationKind.GROUND}}
    extra_anchors=sorted(anchor_pred-set(anchor_match.values()))
    candidates=[o for o in s.observations if isinstance(o.payload,(m.JunctionCandidate,m.ContactCandidate))]
    decision_match=_matching([d.id for d in r.decisions],[o.id for o in candidates],
        {(d.id,o.id):-Fraction(_distance(d.position,o.geometry.points[0])) for d in r.decisions for o in candidates if o.geometry and _distance(d.position,o.geometry.points[0])<=12})
    correspondence.update(decision_match)
    decisions={}
    for d in r.decisions:
        oid=decision_match.get(d.id)
        claims=[c.decision for c in h.claims if oid in c.evidence and c.kind in {'junction','contact','JUNCTION_UNCLEAR','CONTACT_UNCLEAR'}]
        decisions[d.id]=next(iter(set(claims))) if len(set(claims))==1 else 'unresolved'
    junction_errors=[d.id for d in r.decisions if d.id not in decision_match or decisions[d.id]!=d.meaning]
    abstained=[d.id for d in r.decisions if d.meaning=='unresolved' and d.id in decision_match and decisions[d.id]=='unresolved']
    false_confident=[d.id for d in r.decisions if d.meaning=='unresolved' and decisions[d.id]=='connected']
    review_correct=0
    aliases={'wire_gap':{'WIRE_GAP','CONTACT_UNCLEAR'},'bulk_unresolved':{'BULK_UNRESOLVED','PIN_MISSING'},
             'missing_value':{'VALUE_MISSING'},'unreadable_value':{'VALUE_UNREADABLE'}}
    for q in r.reviews:
        targets={correspondence[t] for t in q.targets if t in correspondence}
        codes=aliases.get(q.kind,{q.kind.upper()})
        if len(targets)==len(q.targets) and any(i.requires_review and i.code in codes and targets<=set(i.observation_ids) for i in h.issues): review_correct+=1
    required=[p for p in visible if p.id in truth]
    eligible=r.topology_complete and r.supported
    exact=(bool(visible) and not component_errors and len(component_match)==len(h.components)==len(r.components) and len(terminal_match)==len(h.terminals)==len(visible) and not role_errors and correct==len(required)==len(visible) and not false_joins and not missing_joins and not junction_errors and not label_errors and not ground_errors and not extra_anchors and h.topology_state is TopologyState.RESOLVED) if eligible else None
    return dict(version=EVALUATION_VERSION,lane='prepared-observations',source_sha256=r.source_sha256,hypothesis_digest=h.digest,
        exact_topology_match=exact,component_matches=len(component_match),component_errors=sorted(component_errors),
        terminal_matches=len(terminal_match),terminal_role_errors=sorted(role_errors),pin_assignment_correct=correct,pin_assignment_total=len(required),pin_assignment_ratio=correct/len(required) if required else None,
        false_added_connections=false_joins,missing_connections=missing_joins,spurious_connected_pairs=spurious_pairs,predicted_joined_pairs=pred_joined+spurious_pairs,truth_required_joined_pairs=truth_joined,
        net_merge_errors=merge_errors,net_split_errors=split_errors,junction_errors=sorted(junction_errors),label_errors=sorted(label_errors),ground_errors=sorted(ground_errors),extra_anchors=extra_anchors,
        unresolved_truth_join_claims=unknown_joins,false_confident_junctions=sorted(false_confident),appropriate_abstentions=sorted(abstained),required_review_correct=review_correct,required_review_total=len(r.reviews))
