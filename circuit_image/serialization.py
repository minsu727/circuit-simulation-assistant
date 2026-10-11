"""Explicit, deterministic observation wire projection; never Circuit JSON."""
from . import models as m
from .intake import canonical_json


def payload_to_dict(p, refs):
    if isinstance(p,m.SymbolCandidate):
        return {"classification":p.classification.value,"component_type":p.component_type.value if p.component_type else None,
                "observed_name":p.observed_name,"reference_text":p.reference_text}
    if isinstance(p,m.TextCandidate):
        v = p.value
        return {"raw_text":p.raw_text,"purpose":p.purpose.value,"component_ref":refs[p.component_ref] if p.component_ref else None,
                "value":None if v is None else {"raw_scalar":v.raw_scalar,"raw_unit":v.raw_unit,"notation":v.notation.value,"unit":v.unit,"si_value":v.si_value}}
    if isinstance(p,m.LabelCandidate):
        return {"raw_text":p.raw_text,"attachment_ref":refs[p.attachment_ref] if p.attachment_ref else None}
    if isinstance(p,m.PinCandidate):
        return {"component_ref":refs[p.component_ref],"role":p.role.value}
    if isinstance(p,m.WireCandidate):
        return {}
    if isinstance(p,m.JunctionCandidate):
        return {"wire_refs":sorted(refs[r] for r in p.wire_refs),"interpretation":p.interpretation}
    if isinstance(p,m.GroundCandidate):
        return {"style":p.style}
    if isinstance(p,m.UnknownCandidate):
        return {"observed_name":p.observed_name}
    if isinstance(p,m.ContactCandidate):
        return {"refs":sorted(refs[r] for r in p.refs),"interpretation":p.interpretation}
    raise ValueError("Unsupported typed observation payload.")


def geometry_to_dict(g):
    if g is None: return None
    b = g.bbox
    return {"bbox":None if b is None else [b.x,b.y,b.width,b.height],
            "points":[[p.x,p.y] for p in g.points],"orientation":g.orientation.value}


def provider_to_dict(p):
    return {"provider_id":p.provider_id,"provider_version":p.provider_version,
            "model_id":p.model_id,"model_version":p.model_version,"adapter_version":p.adapter_version,
            "catalog_version":p.catalog_version,"prompt_version":p.prompt_version,"mode":p.mode}


def observations_to_dict(observation_set):
    """Canonical wire data uses provider aliases; locally remapped IDs stay internal.

    Observations, reasons, related refs and alternatives are unordered and sorted.
    Wire endpoint order remains meaningful. No reflection or numpy conversion.
    """
    if type(observation_set) is not m.ObservationSet or type(observation_set.observations) is not tuple:
        raise ValueError("Expected a parsed immutable ObservationSet.")
    s = observation_set
    refs = {o.id:o.provider_id for o in s.observations}
    rows = []
    for o in sorted(s.observations,key=lambda o:o.provider_id):
        u,c = o.uncertainty,o.confidence
        rows.append({"id":o.provider_id,"kind":o.kind.value,"source_sha256":o.source_sha256,
                     "geometry":geometry_to_dict(o.geometry),"data":payload_to_dict(o.payload,refs),
                     "confidence":{"score":c.score,"basis":c.basis,"calibrated":c.calibrated},
                     "uncertainty":{"state":u.state.value,"reasons":sorted(r.value for r in u.reasons),
                                    "related_refs":sorted(refs[r] for r in u.related_refs),
                                    "alternatives":[{"id":a.id,"data":payload_to_dict(a.payload,refs)}
                                                    for a in sorted(u.alternatives,key=lambda a:a.id)]}})
    return {"version":s.version,"image":{"source_identity_sha256":s.source_identity_sha256,
             "source_sha256":s.source_sha256,"normalized_sha256":s.normalized_sha256,
             "transform_sha256":s.transform_sha256},"coordinate_frame":"original_pixels",
            "provider":provider_to_dict(s.provider),"coverage":s.coverage,"observations":rows}


def dump_observations(observation_set):
    """Serialize parsed records without source pixels, paths, approvals or topology."""
    return canonical_json(observations_to_dict(observation_set)) + "\n"
