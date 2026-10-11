"""Explicit M3D projection. It is not SPICE/Circuit JSON or an admission gate."""
from .intake import canonical_json, content_digest
from . import models as m
from .topology_models import TopologyHypothesis


def limits_to_dict(limits):
    return dict(max_claims=limits.max_claims,max_ambiguities=limits.max_ambiguities,
                max_alternatives=limits.max_alternatives,max_hypotheses=limits.max_hypotheses,
                max_pair_checks=limits.max_pair_checks,max_evidence_refs=limits.max_evidence_refs,ambiguity_depth=limits.ambiguity_depth,
                near_distance_px=float(limits.near_distance_px))


def topology_to_dict(hypothesis, *, include_digest=True):
    if type(hypothesis) is not TopologyHypothesis: raise TypeError("Expected TopologyHypothesis.")
    h=hypothesis
    components=[]
    for c in sorted(h.components,key=lambda c:c.observation_id):
        p=c.payload
        components.append(dict(observation_id=c.observation_id,
            classification=p.classification.value if isinstance(p,m.SymbolCandidate) else "unknown",
            component_type=p.component_type.value if isinstance(p,m.SymbolCandidate) and p.component_type else None,
            observed_name=p.observed_name,
            reference_text=p.reference_text if isinstance(p,m.SymbolCandidate) else None,
            text_observation_ids=sorted(c.text_observation_ids)))
    data=dict(version=h.version,source_identity_sha256=h.source_identity_sha256,source_sha256=h.source_sha256,
        observation_response_sha256=h.observation_response_sha256,extraction_id=h.extraction_id,
        limits=limits_to_dict(h.limits),topology_state=h.topology_state.value,conversion_state=h.conversion_state.value,
        candidate_state=h.candidate_state,review_required=h.review_required,admission_state=h.admission_state,
        hypothesis_count=h.hypothesis_count,components=components,
        terminals=[dict(observation_id=p.observation_id,component_observation_id=p.component_observation_id,
                        role=p.role.value,role_alternatives=sorted(r.value for r in p.role_alternatives))
                   for p in sorted(h.terminals,key=lambda p:p.observation_id)],
        nets=[dict(id=n.id,wire_observation_ids=sorted(n.wire_observation_ids),ground_observation_ids=sorted(n.ground_observation_ids),
                   label_observation_ids=sorted(n.label_observation_ids)) for n in sorted(h.nets,key=lambda n:n.id)],
        claims=[dict(id=c.id,kind=c.kind,subjects=sorted(c.subjects),evidence=sorted(c.evidence),decision=c.decision,
                     net_id=c.net_id,role=c.role.value if c.role else None) for c in sorted(h.claims,key=lambda c:c.id)],
        ambiguities=[dict(id=a.id,kind=a.kind,subjects=sorted(a.subjects),evidence=sorted(a.evidence),
                         options=[dict(id=o.id,meaning=o.meaning,subjects=sorted(o.subjects),evidence=sorted(o.evidence),
                                       source_alternative_id=o.source_alternative_id) for o in sorted(a.options,key=lambda o:o.id)])
                     for a in sorted(h.ambiguities,key=lambda a:a.id)],
        issues=[dict(code=i.code,scope=i.scope,observation_ids=sorted(i.observation_ids),requires_review=i.requires_review,missing=i.missing)
                for i in sorted(h.issues,key=lambda i:(i.scope,i.code,i.observation_ids))])
    if include_digest: data["digest"]=h.digest
    return data


def topology_digest(hypothesis):
    return content_digest(topology_to_dict(hypothesis,include_digest=False))


def dump_topology(hypothesis):
    return canonical_json(topology_to_dict(hypothesis))+"\n"
