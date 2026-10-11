"""Evidence-linked conservative reconstruction, never human acceptance/promotion."""
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
import re
from . import models as m
from .intake import content_digest, ImageLimits
from .observations import parse_observations, ObservationLimits
from .serialization import dump_observations
from .topology_models import (TOPOLOGY_VERSION, TopologyLimits, TopologyState,
    CandidateComponent, CandidateTerminal, CandidateNet, TopologyClaim,
    TopologyOption, TopologyAmbiguity, TopologyIssue, TopologyHypothesis, TopologyResult)
from .topology_serialization import topology_digest


class _Limit(Exception):
    pass


def _xy(p): return Fraction(p.x),Fraction(p.y)


def _cross(a,b,c):
    ax,ay=_xy(a); bx,by=_xy(b); cx,cy=_xy(c)
    return (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)


def _on(p,a,b):
    return _cross(a,b,p)==0 and min(a.x,b.x)<=p.x<=max(a.x,b.x) and min(a.y,b.y)<=p.y<=max(a.y,b.y)


def _distance2(p,a,b):
    px,py=_xy(p); ax,ay=_xy(a); bx,by=_xy(b)
    dx,dy=bx-ax,by-ay
    t=max(Fraction(0),min(Fraction(1),((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return (px-ax-t*dx)**2+(py-ay-t*dy)**2


def _intersects(a,b,c,d):
    x,y,u,v=_cross(a,b,c),_cross(a,b,d),_cross(c,d,a),_cross(c,d,b)
    return x*y<0 and u*v<0 or any((_on(c,a,b),_on(d,a,b),_on(a,c,d),_on(b,c,d)))


def _certain(o):
    return o.uncertainty.state is m.UncertaintyState.PROVISIONAL and not o.uncertainty.reasons and not o.uncertainty.alternatives


def label_identity(text):
    """Flat-scope ASCII identity only, never fuzzy matching or directive parsing."""
    value=text.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}",value): return None
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"))


class _Groups:
    def __init__(self,ids): self.parent={i:i for i in ids}
    def find(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]]; i=self.parent[i]
        return i
    def join(self,a,b):
        a,b=sorted((self.find(a),self.find(b)))
        self.parent[b]=a


def _checked_set(observations,image):
    """Dataclass replacement is not authority: reparse and compare exact identity."""
    if type(observations) is not m.ObservationSet or type(observations.observations) is not tuple:
        return None,m.diagnostic("TOPOLOGY_INPUT_INVALID","observations")
    if len(observations.observations)>ObservationLimits().max_records:
        return None,m.diagnostic("TOPOLOGY_LIMIT_EXCEEDED","observations")
    try:
        result=parse_observations(dump_observations(observations),image,provider=observations.provider,
                                  extraction_key=observations.extraction_key)
        if result.observation_set is None: return None,result.diagnostics[0]
        ordered=replace(observations,observations=tuple(sorted(observations.observations,key=lambda o:o.provider_id)))
        if ordered!=result.observation_set:
            return None,m.diagnostic("TOPOLOGY_STALE_OBSERVATIONS","observations")
        return result.observation_set,None
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError,RecursionError):
        return None,m.diagnostic("TOPOLOGY_INPUT_INVALID","observations")


class _Builder:
    def __init__(self,s,limits):
        self.s,self.limits=s,limits
        self.by={o.id:o for o in s.observations}
        self.claims={}; self.ambiguities={}; self.issues=set(); self.edges=[]; self.separations=[]
        self.hypotheses=1; self.evidence_count=0

    def issue(self,code,subjects,scope="topology",missing=False):
        self.issues.add(TopologyIssue(code,scope,tuple(sorted(set(subjects))),True,missing))

    def claim(self,kind,subjects,evidence,decision,net=None,role=None):
        subjects,evidence=tuple(sorted(set(subjects))),tuple(sorted(set(evidence)))
        if not evidence or any(i not in self.by for i in (*subjects,*evidence)): raise ValueError("Invalid claim reference")
        key="claim_"+content_digest(dict(kind=kind,subjects=subjects,evidence=evidence,decision=decision,net=net,role=role.value if role else None))
        if key not in self.claims:
            self.evidence_count+=len(evidence)
            if len(self.claims)>=self.limits.max_claims or self.evidence_count>self.limits.max_evidence_refs: raise _Limit()
            self.claims[key]=TopologyClaim(key,kind,subjects,evidence,decision,net,role)
        return key

    def ambiguity(self,kind,subjects,evidence,choices=None,scope="topology"):
        subjects,evidence=tuple(sorted(set(subjects))),tuple(sorted(set(evidence)))
        key="ambiguity_"+content_digest(dict(kind=kind,subjects=subjects,evidence=evidence))
        if key in self.ambiguities: return
        choices=choices or [("connected",subjects,None),("separated",subjects,None)]
        if not 2<=len(choices)<=self.limits.max_alternatives: raise _Limit()
        options=[]
        for meaning,refs,alias in choices:
            refs=tuple(sorted(set(refs)))
            if any(i not in self.by for i in (*refs,*evidence)): raise ValueError("Invalid alternative reference")
            oid="option_"+content_digest(dict(ambiguity=key,meaning=meaning,subjects=refs,alias=alias))
            options.append(TopologyOption(oid,meaning,refs,evidence,alias))
        if len({o.id for o in options})!=len(options): raise ValueError("Duplicate alternative")
        self.hypotheses*=len(options)
        self.evidence_count+=len(evidence)*len(options)
        if len(self.ambiguities)>=self.limits.max_ambiguities or self.hypotheses>self.limits.max_hypotheses or self.evidence_count>self.limits.max_evidence_refs: raise _Limit()
        self.ambiguities[key]=TopologyAmbiguity(key,kind,subjects,evidence,tuple(sorted(options,key=lambda o:o.id)))
        self.issue(kind,(*subjects,*evidence),scope)
        self.claim(kind,subjects,evidence,"unresolved")

    def edge(self,kind,a,b,evidence):
        cid=self.claim(kind,(a,b),evidence,"connected")
        self.edges.append((a,b,tuple(sorted(set(evidence))),cid))

    def groups(self,actors):
        # Contradictions quarantine the whole positive group, not an order-chosen edge.
        proposed=_Groups(actors)
        for a,b,_,_ in self.edges: proposed.join(a,b)
        bad={proposed.find(a) for a,b,_ in self.separations if proposed.find(a)==proposed.find(b)}
        for a,b,evidence in self.separations:
            if proposed.find(a) in bad and proposed.find(a)==proposed.find(b):
                self.issue("CONTRADICTORY_CONTACT",(*evidence,a,b))
        groups=_Groups(actors)
        for a,b,evidence,cid in self.edges:
            if proposed.find(a) in bad:
                self.claims[cid]=replace(self.claims[cid],decision="unresolved")
            else: groups.join(a,b)
        return groups

    def run(self):
        rows=self.s.observations
        wires=[o for o in rows if o.kind is m.ObservationKind.WIRE]
        pins=[o for o in rows if o.kind is m.ObservationKind.PIN]
        grounds=[o for o in rows if o.kind is m.ObservationKind.GROUND]
        labels=[o for o in rows if o.kind in {m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL}]
        symbols=[o for o in rows if o.kind in {m.ObservationKind.SYMBOL,m.ObservationKind.UNKNOWN}]
        checks=len(wires)*(len(wires)-1)//2+len(pins)*len(wires)+len(grounds)*(len(wires)+len(pins))
        if checks>self.limits.max_pair_checks: raise _Limit()
        actors={o.id for o in (*wires,*pins,*grounds,*labels)}
        wire_ids={o.id for o in wires}; covered=set()
        components=[]; terminals=[]
        for o in symbols:
            texts=[t for t in rows if isinstance(t.payload,m.TextCandidate) and t.payload.component_ref==o.id]
            components.append(CandidateComponent(o.id,o.payload,tuple(t.id for t in texts)))
            if isinstance(o.payload,m.UnknownCandidate) or o.payload.classification is m.Classification.UNKNOWN:
                self.issue("SYMBOL_UNCLEAR",(o.id,))
            elif o.payload.classification is m.Classification.UNSUPPORTED:
                self.issue("UNSUPPORTED_COMPONENT",(o.id,))
            if not _certain(o): self.issue("SYMBOL_UNCLEAR",(o.id,))
            owned=[p for p in pins if p.payload.component_ref==o.id]
            roles=[p.payload.role for p in owned if p.uncertainty.state is not m.UncertaintyState.MISSING]
            if len(set(roles)-{m.PinRole.UNKNOWN})!=len([r for r in roles if r is not m.PinRole.UNKNOWN]):
                self.issue("CONFLICTING_TERMINAL_ROLE",(o.id,*(p.id for p in owned)))
            if isinstance(o.payload,m.SymbolCandidate) and o.payload.component_type:
                expected={m.ComponentType.RESISTOR:{m.PinRole.A,m.PinRole.B},m.ComponentType.CAPACITOR:{m.PinRole.A,m.PinRole.B},m.ComponentType.INDUCTOR:{m.PinRole.A,m.PinRole.B},
                          m.ComponentType.VOLTAGE_SOURCE:{m.PinRole.POSITIVE,m.PinRole.NEGATIVE},m.ComponentType.CURRENT_SOURCE:{m.PinRole.POSITIVE,m.PinRole.NEGATIVE},
                          m.ComponentType.NMOS:{m.PinRole.DRAIN,m.PinRole.GATE,m.PinRole.SOURCE,m.PinRole.BULK},m.ComponentType.PMOS:{m.PinRole.DRAIN,m.PinRole.GATE,m.PinRole.SOURCE,m.PinRole.BULK}}[o.payload.component_type]
                for role in sorted(expected-set(roles),key=lambda r:r.value):
                    self.issue("BULK_UNRESOLVED" if role is m.PinRole.BULK else "PIN_MISSING",(o.id,),missing=True)
                if o.payload.component_type in {m.ComponentType.RESISTOR,m.ComponentType.CAPACITOR,m.ComponentType.INDUCTOR}:
                    values=[t for t in texts if t.payload.purpose is m.TextPurpose.VALUE and t.payload.value and t.payload.value.si_value is not None and _certain(t)]
                    if not values:
                        unreadable=any(t.uncertainty.state is m.UncertaintyState.UNREADABLE for t in texts)
                        self.issue("VALUE_UNREADABLE" if unreadable else "VALUE_MISSING",(o.id,*(t.id for t in texts)),"conversion",True)
                    elif len(values)>1: self.issue("VALUE_CONFLICT",(o.id,*(t.id for t in values)),"conversion")
                if o.payload.component_type in {m.ComponentType.VOLTAGE_SOURCE,m.ComponentType.CURRENT_SOURCE}:
                    if not any(t.payload.purpose is m.TextPurpose.SOURCE_DC and t.payload.value and t.payload.value.si_value is not None and _certain(t) for t in texts):
                        self.issue("SOURCE_DEFINITION_MISSING",(o.id,),"conversion",True)
                if o.payload.component_type in {m.ComponentType.NMOS,m.ComponentType.PMOS}:
                    self.issue("MODEL_SELECTION_REQUIRED",(o.id,),"conversion",True)
                    for purpose in (m.TextPurpose.DEVICE_WIDTH,m.TextPurpose.DEVICE_LENGTH):
                        if not any(t.payload.purpose is purpose and t.payload.value and t.payload.value.si_value is not None and _certain(t) for t in texts):
                            self.issue("DEVICE_DIMENSION_MISSING",(o.id,),"conversion",True)
        for o in rows:
            if o.uncertainty.alternatives and o.kind not in {m.ObservationKind.JUNCTION,m.ObservationKind.CROSSING,m.ObservationKind.CONTACT}:
                choices=[("observation_choice",(o.id,),a.id) for a in o.uncertainty.alternatives]
                scope="conversion" if o.kind is m.ObservationKind.TEXT else "topology"
                self.ambiguity("OBSERVATION_ALTERNATIVES",(o.id,),(o.id,),choices,scope)
            if o.kind is m.ObservationKind.WIRE and not _certain(o): self.issue("WIRE_INCOMPLETE",(o.id,),missing=True)
        for p in pins:
            terminals.append(CandidateTerminal(p.id,p.payload.component_ref,p.payload.role,
                tuple(sorted({a.payload.role for a in p.uncertainty.alternatives if isinstance(a.payload,m.PinCandidate)},key=lambda r:r.value))))
            if p.uncertainty.state is m.UncertaintyState.MISSING:
                self.issue("PIN_MISSING",(p.id,p.payload.component_ref),missing=True)
            elif p.payload.role is m.PinRole.UNKNOWN or not _certain(p): self.issue("TERMINAL_ROLE_UNCLEAR",(p.id,p.payload.component_ref))
            self.claim("terminal_role",(p.id,p.payload.component_ref),(p.id,p.payload.component_ref),"role" if _certain(p) else "unresolved",role=p.payload.role)

        # Explicit junction/separation evidence is processed before any geometry.
        for o in rows:
            if not isinstance(o.payload,m.JunctionCandidate): continue
            refs=o.payload.wire_refs; point=o.geometry.points[0]
            valid=all(_on(point,*self.by[r].geometry.points) and _certain(self.by[r]) for r in refs)
            if not _certain(o):
                all_refs=tuple(sorted(set(refs)|{r for a in o.uncertainty.alternatives for r in a.payload.wire_refs}))
                covered.update(frozenset(pair) for pair in combinations(all_refs,2))
                choices=[(a.payload.interpretation,a.payload.wire_refs,a.id) for a in o.uncertainty.alternatives] or None
                self.ambiguity("JUNCTION_UNCLEAR",all_refs,(o.id,*all_refs),choices)
                if not valid: self.issue("JUNCTION_POSITION_CONFLICT",(o.id,*refs))
                continue
            for a,b in combinations(refs,2):
                covered.add(frozenset((a,b)))
                if valid and _certain(o) and o.payload.interpretation=="connected": self.edge("junction",a,b,(o.id,a,b))
                elif valid and _certain(o) and o.payload.interpretation=="separated":
                    self.separations.append((a,b,(o.id,a,b)))
                    self.claim("junction",(a,b),(o.id,a,b),"separated")
                else:
                    self.ambiguity("JUNCTION_UNCLEAR",(a,b),(o.id,a,b))
            if not valid: self.issue("JUNCTION_POSITION_CONFLICT",(o.id,*refs))

        # Contacts never silently close a gap, even if the provider says touching.
        blocked_pins=set()
        for o in rows:
            if not isinstance(o.payload,m.ContactCandidate): continue
            a,b=o.payload.refs; covered.add(frozenset((a,b)))
            if a not in actors or b not in actors: raise ValueError("Impossible contact")
            if _certain(o) and o.payload.interpretation=="separated":
                self.separations.append((a,b,(o.id,a,b))); self.claim("contact",(a,b),(o.id,a,b),"separated")
            else:
                pa,pb=self.by[a],self.by[b]
                exact=False
                if pa.kind is m.ObservationKind.WIRE and pb.kind is m.ObservationKind.WIRE:
                    exact=bool(set(pa.geometry.points)&set(pb.geometry.points))
                elif pa.kind is m.ObservationKind.PIN and pb.kind is m.ObservationKind.WIRE and pa.geometry:
                    exact=_on(pa.geometry.points[0],*pb.geometry.points)
                elif pb.kind is m.ObservationKind.PIN and pa.kind is m.ObservationKind.WIRE and pb.geometry:
                    exact=_on(pb.geometry.points[0],*pa.geometry.points)
                if exact and _certain(o) and _certain(pa) and _certain(pb) and o.payload.interpretation=="touching": self.edge("contact",a,b,(o.id,a,b))
                else:
                    choices=[(alt.payload.interpretation,alt.payload.refs,alt.id) for alt in o.uncertainty.alternatives] or None
                    self.ambiguity("CONTACT_UNCLEAR",(a,b),(o.id,a,b),choices)
                    blocked_pins.update(i for i in (a,b) if self.by[i].kind is m.ObservationKind.PIN)
                    for alt in o.uncertainty.alternatives:
                        covered.add(frozenset(alt.payload.refs))
                        blocked_pins.update(i for i in alt.payload.refs if self.by[i].kind is m.ObservationKind.PIN)
        for a,b in combinations(wires,2):
            pair=frozenset((a.id,b.id))
            if pair in covered: continue
            ap,bp=a.geometry.points,b.geometry.points
            if not _certain(a) or not _certain(b): continue
            shared=bool(set(ap)&set(bp))
            collinear=_cross(*ap,bp[0])==0 and _cross(*ap,bp[1])==0
            intersect=_intersects(*ap,*bp)
            if shared or collinear and intersect: self.edge("wire_continuity",a.id,b.id,(a.id,b.id))
            elif intersect: self.ambiguity("JUNCTION_UNCLEAR",(a.id,b.id),(a.id,b.id))
            elif min(*(_distance2(p,*bp) for p in ap),*(_distance2(p,*ap) for p in bp))<=Fraction(self.limits.near_distance_px)**2:
                self.ambiguity("WIRE_GAP",(a.id,b.id),(a.id,b.id))

        # Label attachment is explicit; bbox proximity does not attach labels.
        attached={}
        for o in labels:
            name=label_identity(o.payload.raw_text)
            if _certain(o) and name and o.payload.attachment_ref and _certain(self.by[o.payload.attachment_ref]):
                wire=o.payload.attachment_ref
                self.edge("label_attachment",o.id,wire,(o.id,wire)); attached[o.id]=(name,wire)
            else: self.issue("LABEL_ATTACHMENT_UNRESOLVED",(o.id,))
        physical=self.groups(actors)
        names_by_group={}
        for lid,(name,wire) in attached.items(): names_by_group.setdefault(physical.find(wire),set()).add(name)
        conflicting={root for root,names in names_by_group.items() if len(names)>1}
        if conflicting:
            self.issue("NET_LABEL_CONFLICT",tuple(lid for lid,(_,wire) in attached.items() if physical.find(wire) in conflicting))
        by_name={}
        for lid,(name,wire) in attached.items():
            if physical.find(wire) not in conflicting: by_name.setdefault(name,[]).append((lid,wire))
        for matches in by_name.values():
            # A spanning chain is sufficient; no quadratic label clique.
            matches=sorted(matches)
            for (la,wa),(lb,wb) in zip(matches,matches[1:]):
                self.edge("label_equivalence",wa,wb,(la,lb,wa,wb))
        groups=self.groups(actors)

        for p in pins:
            if p.geometry is None or p.id in blocked_pins: continue
            if not _certain(p):
                self.issue("PIN_CONTACT_UNRESOLVED",(p.id,)); continue
            point=p.geometry.points[0]
            matches=[w for w in wires if _certain(w) and _on(point,*w.geometry.points) and frozenset((p.id,w.id)) not in covered]
            roots={groups.find(w.id) for w in matches}
            if len(roots)==1:
                for w in matches: self.edge("pin_contact",p.id,w.id,(p.id,w.id))
            elif len(roots)>1:
                self.ambiguity("PIN_CONTACT_UNCLEAR",(p.id,*(w.id for w in matches)),(p.id,*(w.id for w in matches)),
                    [("attached",(p.id,w.id),None) for w in matches]+[("unassigned",(p.id,),None)])
            else:
                near=[w for w in wires if _certain(w) and frozenset((p.id,w.id)) not in covered and _distance2(point,*w.geometry.points)<=Fraction(self.limits.near_distance_px)**2]
                if near: self.ambiguity("PIN_CONTACT_GAP",(p.id,*(w.id for w in near)),(p.id,*(w.id for w in near)))
        groups=self.groups(actors)
        for g in grounds:
            if not _certain(g) or g.payload.style!="signal" or not g.geometry or len(g.geometry.points)!=1:
                self.issue("GROUND_ATTACHMENT_UNRESOLVED",(g.id,)); continue
            point=g.geometry.points[0]
            matches=[w.id for w in wires if _certain(w) and _on(point,*w.geometry.points)]
            matches += [p.id for p in pins if _certain(p) and p.geometry and p.geometry.points[0]==point]
            roots={groups.find(i) for i in matches}
            if len(roots)==1:
                for actor in matches: self.edge("ground_attachment",g.id,actor,(g.id,actor))
            else: self.issue("GROUND_ATTACHMENT_UNRESOLVED",(g.id,))
        groups=self.groups(actors)

        members={}
        for actor in sorted(actors): members.setdefault(groups.find(actor),[]).append(actor)
        nets=[]; net_for={}
        for group in members.values():
            ws=tuple(i for i in group if i in wire_ids)
            gs=tuple(i for i in group if self.by[i].kind is m.ObservationKind.GROUND and len(group)>1)
            ls=tuple(i for i in group if i in attached)
            if not ws and not gs: continue
            nid="net_"+content_digest(dict(version=TOPOLOGY_VERSION,members=group))
            nets.append(CandidateNet(nid,ws,gs,ls))
            for i in group: net_for[i]=nid
            names={attached[i][0] for i in ls}
            if len(names)>1: self.issue("NET_LABEL_CONFLICT",ls)
        for w in wires: self.claim("wire_membership",(w.id,),(w.id,),"attached",net_for[w.id])
        for p in pins:
            nid=net_for.get(p.id)
            if nid is None:
                self.claim("pin_to_net",(p.id,),(p.id,),"unresolved")
                self.issue("PIN_UNCONNECTED",(p.id,),missing=True)
            else:
                root=groups.find(p.id)
                proof={p.id}
                for a,b,evidence,cid in self.edges:
                    if groups.find(a)==root and self.claims[cid].decision=="connected": proof.update(evidence)
                self.claim("pin_to_net",(p.id,),proof,"attached",nid)
        for g in grounds:
            self.claim("ground",(g.id,),(g.id,),"attached" if g.id in net_for else "unresolved",net_for.get(g.id))
        if not any(n.ground_observation_ids for n in nets): self.issue("GROUND_MISSING",tuple(o.id for o in (*grounds,*labels)),"conversion",True)
        if sum(bool(n.ground_observation_ids) for n in nets)>1: self.issue("GROUND_GROUP_UNRESOLVED",tuple(g.id for g in grounds),"conversion")
        if not any(isinstance(o.payload,m.SymbolCandidate) and o.payload.component_type in {m.ComponentType.VOLTAGE_SOURCE,m.ComponentType.CURRENT_SOURCE} for o in symbols):
            self.issue("SUPPLY_DEFINITION_MISSING",tuple(o.id for o in labels if o.kind is m.ObservationKind.SUPPLY_LABEL),"conversion",True)
        if self.s.coverage=="partial" or not rows: self.issue("OBSERVATIONS_INCOMPLETE",(),missing=True)
        def state(scopes):
            selected=[i for i in self.issues if i.scope in scopes]
            if any(i.code=="UNSUPPORTED_COMPONENT" for i in selected): return TopologyState.UNSUPPORTED
            if any(i.requires_review and not i.missing for i in selected): return TopologyState.NEEDS_REVIEW
            if any(i.missing for i in selected): return TopologyState.INCOMPLETE
            return TopologyState.RESOLVED
        topology_state,conversion_state=state({"topology"}),state({"topology","conversion"})
        h=TopologyHypothesis(TOPOLOGY_VERSION,self.s.source_identity_sha256,self.s.source_sha256,self.s.response_sha256,
            self.s.extraction_id,self.limits,topology_state,conversion_state,"NEEDS_REVIEW" if self.issues else "DRAFT",True,
            "BLOCKED_M3E",self.hypotheses,tuple(components),tuple(terminals),tuple(sorted(nets,key=lambda n:n.id)),
            tuple(sorted(self.claims.values(),key=lambda c:c.id)),tuple(sorted(self.ambiguities.values(),key=lambda a:a.id)),
            tuple(sorted(self.issues,key=lambda i:(i.scope,i.code,i.observation_ids))),"")
        return replace(h,digest=topology_digest(h))


def reconstruct_topology(observations, image, *, limits=TopologyLimits()) -> TopologyResult:
    """Recheck M3C identity, build only unapproved evidence-linked hypotheses."""
    if type(limits) is not TopologyLimits: return TopologyResult(None,(m.diagnostic("TOPOLOGY_LIMITS_INVALID","limits"),))
    checked,issue=_checked_set(observations,image)
    if issue: return TopologyResult(None,(issue,))
    try: return TopologyResult(_Builder(checked,limits).run(),())
    except _Limit: return TopologyResult(None,(m.diagnostic("TOPOLOGY_LIMIT_EXCEEDED","topology"),))
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError):
        return TopologyResult(None,(m.diagnostic("TOPOLOGY_INPUT_INVALID","topology"),))


def validate_topology(hypothesis, observations, image):
    """Reconstruction equality detects forged/stale evidence; grants no approval."""
    if type(hypothesis) is not TopologyHypothesis: return (m.diagnostic("TOPOLOGY_INPUT_INVALID","hypothesis"),)
    result=reconstruct_topology(observations,image,limits=hypothesis.limits)
    if result.hypothesis is None: return result.diagnostics
    if hypothesis!=result.hypothesis: return (m.diagnostic("TOPOLOGY_STALE_HYPOTHESIS","hypothesis"),)
    return ()
