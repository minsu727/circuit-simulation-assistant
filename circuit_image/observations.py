"""Strict bounded untrusted JSON -> typed original-frame observations only."""
from dataclasses import dataclass, replace
from decimal import Decimal
from hashlib import sha256
import json
import math
import re

from . import models as m
from .intake import ImageLimits, canonical_json, content_digest, validate_artifact
from .serialization import observations_to_dict, provider_to_dict, payload_to_dict
from .value_candidates import proposed_normalization, observed_unit


@dataclass(frozen=True, slots=True)
class ObservationLimits:
    max_payload_bytes: int = 2 * 1024 * 1024
    max_records: int = 4096
    max_symbols: int = 128
    max_texts: int = 1024
    max_pins: int = 512
    max_wires: int = 2048
    max_junctions: int = 512
    max_contacts: int = 512
    max_text_length: int = 256
    max_alternatives: int = 8
    max_depth: int = 16
    max_nodes: int = 100_000

    def __post_init__(self):
        for value in (self.max_payload_bytes,self.max_records,self.max_symbols,self.max_texts,
                      self.max_pins,self.max_wires,self.max_junctions,self.max_contacts,
                      self.max_text_length,self.max_alternatives,self.max_depth,self.max_nodes):
            if type(value) is not int or value <= 0:
                raise ValueError("Observation limits must be positive integers.")


class _Invalid(Exception):
    def __init__(self,code,field): self.code,self.field = code,field


def _check(ok,code="OBS_FIELDS_INVALID",field="payload"):
    if not ok: raise _Invalid(code,field)


def _keys(obj,names,field):
    _check(type(obj) is dict and set(obj)==set(names.split()),field=field)


def _enum(cls,value,field):
    _check(type(value) is str,field=field)
    try: return cls(value)
    except ValueError: raise _Invalid("OBS_ENUM_INVALID",field) from None


def _text(value,maximum,field,nullable=False):
    if value is None and nullable: return value
    _check(type(value) is str,field=field)
    _check(len(value)<=maximum,"OBS_LIMIT_EXCEEDED",field)
    return value


def _id(value,field):
    _check(type(value) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}",value),"OBS_ID_INVALID",field)
    return value


def _refs(values,field):
    _check(type(values) is list and len(values)<=16,"OBS_REFERENCE_INVALID",field)
    result = tuple(_id(v,field) for v in values)
    _check(len(set(result))==len(result),"OBS_REFERENCE_INVALID",field)
    return tuple(sorted(result))


def validate_provider_info(info):
    """Typed provider configuration is checked too; it is not provider authority."""
    try:
        _check(type(info) is m.ProviderInfo,"OBS_PROVENANCE_INVALID","provider")
        _provider(provider_to_dict(info))
    except _Invalid as error:
        return m.diagnostic(error.code,error.field)
    except (TypeError,ValueError):
        return m.diagnostic("OBS_PROVENANCE_INVALID","provider")
    return None


def _provider(data):
    _keys(data,"provider_id provider_version model_id model_version adapter_version catalog_version prompt_version mode","provider")
    _id(data["provider_id"],"provider.provider_id")
    for key in ("provider_version","model_id","model_version","adapter_version","catalog_version","prompt_version"):
        _text(data[key],64,"provider."+key,key not in {"adapter_version","catalog_version"})
        _check(data[key] is None or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",data[key]),"OBS_PROVENANCE_INVALID","provider."+key)
    _check(data["mode"] in {"replay","local","remote"},"OBS_PROVENANCE_INVALID","provider.mode")
    if data["mode"] == "replay":
        _check(data["provider_id"]=="static-replay" and data["model_id"] is None and data["model_version"] is None and data["prompt_version"] is None,
               "OBS_PROVENANCE_INVALID","provider")
    return m.ProviderInfo(**data)


def _value(data,limits):
    if data is None: return None
    _keys(data,"raw_scalar raw_unit notation unit si_value","value")
    raw = _text(data["raw_scalar"],128,"value.raw_scalar")
    raw_unit = _text(data["raw_unit"],32,"value.raw_unit",True)
    notation = _enum(m.Notation,data["notation"],"value.notation")
    _check(data["unit"] in {None,"ohm","F","H","V","A","Hz","s","deg","m"},"OBS_VALUE_INVALID","value.unit")
    _check(data["unit"] is None or observed_unit(raw_unit,notation)==data["unit"],"OBS_VALUE_INVALID","value.unit")
    si = _text(data["si_value"],128,"value.si_value",True)
    if si is not None:
        _check(re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?",si,flags=re.ASCII),"OBS_VALUE_INVALID","value.si_value")
        normalized = proposed_normalization(raw,raw_unit,notation)
        _check(normalized is not None and normalized[0]==data["unit"] and Decimal(normalized[1])==Decimal(si),"OBS_VALUE_INVALID","value")
        si = normalized[1]
    else:
        _check(notation is m.Notation.UNRESOLVED or proposed_normalization(raw,raw_unit,notation) is None,
               "OBS_CONTRADICTION","value")
    return m.ValueCandidate(raw,raw_unit,notation,data["unit"],si)


def _payload(kind,data,limits):
    if kind is m.ObservationKind.SYMBOL:
        _keys(data,"classification component_type observed_name reference_text","data.symbol")
        category = _enum(m.Classification,data["classification"],"data.classification")
        component = _enum(m.ComponentType,data["component_type"],"data.component_type") if data["component_type"] is not None else None
        _check((category is m.Classification.SUPPORTED and component not in (None,m.ComponentType.UNKNOWN)) or
               (category is not m.Classification.SUPPORTED and component is None),"OBS_CONTRADICTION","data.symbol")
        return m.SymbolCandidate(category,component,_text(data["observed_name"],limits.max_text_length,"data.observed_name",True),
                                 _text(data["reference_text"],limits.max_text_length,"data.reference_text",True))
    if kind is m.ObservationKind.TEXT:
        _keys(data,"raw_text purpose component_ref value","data.text")
        ref = _id(data["component_ref"],"data.component_ref") if data["component_ref"] is not None else None
        return m.TextCandidate(_text(data["raw_text"],limits.max_text_length,"data.raw_text"),
                               _enum(m.TextPurpose,data["purpose"],"data.purpose"),ref,_value(data["value"],limits))
    if kind in {m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL}:
        _keys(data,"raw_text attachment_ref","data.label")
        ref = _id(data["attachment_ref"],"data.attachment_ref") if data["attachment_ref"] is not None else None
        return m.LabelCandidate(_text(data["raw_text"],limits.max_text_length,"data.raw_text"),ref)
    if kind is m.ObservationKind.PIN:
        _keys(data,"component_ref role","data.pin")
        return m.PinCandidate(_id(data["component_ref"],"data.component_ref"),_enum(m.PinRole,data["role"],"data.role"))
    if kind is m.ObservationKind.WIRE:
        _keys(data,"","data.wire")
        return m.WireCandidate()
    if kind in {m.ObservationKind.JUNCTION,m.ObservationKind.CROSSING}:
        _keys(data,"wire_refs interpretation","data.junction")
        refs = _refs(data["wire_refs"],"data.wire_refs")
        _check(len(refs)>=2 and data["interpretation"] in {"connected","separated","unknown"},"OBS_CONTRADICTION","data.junction")
        return m.JunctionCandidate(refs,data["interpretation"])
    if kind is m.ObservationKind.GROUND:
        _keys(data,"style","data.ground")
        _check(data["style"] in {"signal","earth","chassis","unknown"},"OBS_ENUM_INVALID","data.style")
        return m.GroundCandidate(data["style"])
    if kind is m.ObservationKind.UNKNOWN:
        _keys(data,"observed_name","data.unknown")
        return m.UnknownCandidate(_text(data["observed_name"],limits.max_text_length,"data.observed_name",True))
    _keys(data,"refs interpretation","data.contact")
    refs = _refs(data["refs"],"data.refs")
    _check(len(refs)==2 and data["interpretation"] in {"touching","separated","equivalent","unknown"},"OBS_CONTRADICTION","data.contact")
    return m.ContactCandidate(refs,data["interpretation"])


_POSE = {m.Orientation.R0:(1,0,0,1),m.Orientation.R90:(0,-1,1,0),
         m.Orientation.R180:(-1,0,0,-1),m.Orientation.R270:(0,1,-1,0),
         m.Orientation.R0_MIRROR:(-1,0,0,1),m.Orientation.R90_MIRROR:(0,-1,-1,0),
         m.Orientation.R180_MIRROR:(1,0,0,-1),m.Orientation.R270_MIRROR:(0,1,1,0)}


def _geometry(data,identity,frame):
    if data is None: return None
    _keys(data,"bbox points orientation","geometry")
    w,h = (identity.width,identity.height) if frame=="original_pixels" else (identity.display_width,identity.display_height)
    def point(values):
        _check(type(values) is list and len(values)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in values),"OBS_GEOMETRY_INVALID","geometry.point")
        x,y = values
        _check(0<=x<=w and 0<=y<=h,"OBS_GEOMETRY_INVALID","geometry.point")
        if frame=="display_pixels": x,y = identity.transform.to_original(x,y)
        return m.Point(float(x),float(y))
    b = data["bbox"]
    bbox = None
    if b is not None:
        _check(type(b) is list and len(b)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in b),"OBS_GEOMETRY_INVALID","geometry.bbox")
        x,y,bw,bh = b
        _check(bw>0 and bh>0,"OBS_GEOMETRY_INVALID","geometry.bbox")
        corners = [point(p) for p in ([x,y],[x+bw,y],[x,y+bh],[x+bw,y+bh])]
        x0,y0 = min(p.x for p in corners),min(p.y for p in corners)
        bbox = m.Box(x0,y0,max(p.x for p in corners)-x0,max(p.y for p in corners)-y0)
    _check(type(data["points"]) is list and len(data["points"])<=2,"OBS_GEOMETRY_INVALID","geometry.points")
    points = tuple(point(p) for p in data["points"])
    pose = _enum(m.Orientation,data["orientation"],"geometry.orientation")
    if frame=="display_pixels" and pose is not m.Orientation.UNKNOWN:
        a,b,_,d,e,_ = identity.transform.inverse
        pa,pb,pd,pe = _POSE[pose]
        matrix = (a*pa+b*pd,a*pb+b*pe,d*pa+e*pd,d*pb+e*pe)
        pose = next(k for k,v in _POSE.items() if v==matrix)
    return m.Geometry(bbox,points,pose)


def _bounded_json(payload,limits):
    _check(type(payload) in (str,bytes),"OBS_JSON_INVALID","payload")
    if type(payload) is str:
        _check(len(payload)<=limits.max_payload_bytes,"OBS_LIMIT_EXCEEDED","payload")
        encoded = payload.encode("utf8")
    else: encoded = payload
    _check(len(encoded)<=limits.max_payload_bytes,"OBS_LIMIT_EXCEEDED","payload")
    text = encoded.decode("utf8")
    depth,in_string,escape = 0,False,False
    for char in text:
        if in_string:
            if escape: escape=False
            elif char=="\\": escape=True
            elif char=='"': in_string=False
        elif char=='"': in_string=True
        elif char in "[{":
            depth+=1
            _check(depth<=limits.max_depth,"OBS_LIMIT_EXCEEDED","payload.depth")
        elif char in "]}": depth-=1
    def pairs(items):
        result={}
        for key,value in items:
            _check(key not in result,"OBS_JSON_INVALID","payload")
            result[key]=value
        return result
    def constant(value): raise _Invalid("OBS_JSON_INVALID","payload")
    data = json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
    nodes,stack = 0,[data]
    while stack:
        item = stack.pop(); nodes+=1
        _check(nodes<=limits.max_nodes,"OBS_LIMIT_EXCEEDED","payload.nodes")
        if type(item) is dict: stack.extend(item.values())
        elif type(item) is list: stack.extend(item)
    return data


def _references(payload):
    if isinstance(payload,(m.TextCandidate,m.PinCandidate)):
        return ((payload.component_ref,{m.ObservationKind.SYMBOL}),) if payload.component_ref else ()
    if isinstance(payload,m.LabelCandidate):
        return ((payload.attachment_ref,{m.ObservationKind.WIRE}),) if payload.attachment_ref else ()
    if isinstance(payload,m.JunctionCandidate):
        return tuple((ref,{m.ObservationKind.WIRE}) for ref in payload.wire_refs)
    if isinstance(payload,m.ContactCandidate):
        return tuple((ref,{m.ObservationKind.WIRE,m.ObservationKind.PIN,m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL}) for ref in payload.refs)
    return ()


def _remap(payload,refs):
    if isinstance(payload,(m.TextCandidate,m.PinCandidate)):
        return replace(payload,component_ref=refs[payload.component_ref] if payload.component_ref else None)
    if isinstance(payload,m.LabelCandidate):
        return replace(payload,attachment_ref=refs[payload.attachment_ref] if payload.attachment_ref else None)
    if isinstance(payload,m.JunctionCandidate): return replace(payload,wire_refs=tuple(refs[r] for r in payload.wire_refs))
    if isinstance(payload,m.ContactCandidate): return replace(payload,refs=tuple(refs[r] for r in payload.refs))
    return payload


def parse_observations(payload, artifact, *, provider: m.ProviderInfo,
                       extraction_key="replay", limits=ObservationLimits(), image_limits=ImageLimits()):
    """Validate/normalize one complete wire envelope or return no partial result.

    All classifications, roles, contacts and values remain unaccepted hypotheses.
    """
    issue = validate_artifact(artifact,image_limits)
    if issue: return m.ObservationResult(None,(issue,))
    issue = validate_provider_info(provider)
    if issue: return m.ObservationResult(None,(issue,))
    try:
        _check(isinstance(limits,ObservationLimits),"OBS_LIMITS_INVALID","limits")
        _id(extraction_key,"extraction_key")
        data = _bounded_json(payload,limits)
        _keys(data,"version image coordinate_frame provider coverage observations","payload")
        _check(data["version"]==m.OBSERVATION_VERSION,"OBS_VERSION_UNSUPPORTED","version")
        _keys(data["image"],"source_identity_sha256 source_sha256 normalized_sha256 transform_sha256","image")
        identity = artifact.identity
        expected = {"source_identity_sha256":identity.identity_sha256,"source_sha256":identity.source_sha256,
                    "normalized_sha256":identity.normalized_sha256,"transform_sha256":identity.transform.sha256}
        _check(data["image"]==expected,"OBS_SOURCE_MISMATCH","image")
        _check(_provider(data["provider"])==provider,"OBS_PROVENANCE_INVALID","provider")
        frame = data["coordinate_frame"]
        _check(frame in {"original_pixels","display_pixels"},"OBS_GEOMETRY_INVALID","coordinate_frame")
        _check(data["coverage"] in {"reported_complete","partial"},field="coverage")
        rows = data["observations"]
        _check(type(rows) is list,"OBS_FIELDS_INVALID","observations")
        _check(len(rows)<=limits.max_records,"OBS_LIMIT_EXCEEDED","observations")
        _check(rows or data["coverage"]=="partial","OBS_CONTRADICTION","coverage")
        ids=[]
        for row in rows:
            _keys(row,"id kind source_sha256 geometry data confidence uncertainty","observation")
            ids.append(_id(row["id"],"observation.id"))
        _check(len(ids)==len(set(ids)),"OBS_ID_DUPLICATE","observations")
        observations,counts = [],{}
        for row in sorted(rows,key=lambda row:row["id"]):
            kind = _enum(m.ObservationKind,row["kind"],"observation.kind")
            group = "symbols" if kind in {m.ObservationKind.SYMBOL,m.ObservationKind.UNKNOWN} else "texts" if kind in {m.ObservationKind.TEXT,m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL} else "pins" if kind is m.ObservationKind.PIN else "wires" if kind is m.ObservationKind.WIRE else "contacts" if kind is m.ObservationKind.CONTACT else "junctions"
            counts[group] = counts.get(group,0)+1
            _check(counts[group]<=getattr(limits,"max_"+group),"OBS_LIMIT_EXCEEDED","observations.count")
            _check(row["source_sha256"]==identity.source_sha256,"OBS_SOURCE_MISMATCH","observation.source_sha256")
            g,p = _geometry(row["geometry"],identity,frame),_payload(kind,row["data"],limits)
            c,u = row["confidence"],row["uncertainty"]
            _keys(c,"score basis calibrated","confidence")
            _check(c["score"] is None or type(c["score"]) in (int,float) and math.isfinite(c["score"]) and 0<=c["score"]<=1,"OBS_CONFIDENCE_INVALID","confidence.score")
            _check(c["basis"] in {"unknown","synthetic","provider_score","heuristic"} and c["calibrated"] is False,"OBS_CONFIDENCE_INVALID","confidence")
            _check(c["score"] is None or c["basis"]!="unknown","OBS_CONFIDENCE_INVALID","confidence")
            _keys(u,"state reasons related_refs alternatives","uncertainty")
            state = _enum(m.UncertaintyState,u["state"],"uncertainty.state")
            _check(type(u["reasons"]) is list and len(u["reasons"])<=len(m.Reason),"OBS_LIMIT_EXCEEDED","uncertainty.reasons")
            reasons = tuple(sorted((_enum(m.Reason,r,"uncertainty.reason") for r in u["reasons"]),key=lambda r:r.value))
            _check(len(set(reasons))==len(reasons),"OBS_CONTRADICTION","uncertainty.reasons")
            related = _refs(u["related_refs"],"uncertainty.related_refs")
            _check(type(u["alternatives"]) is list and len(u["alternatives"])<=limits.max_alternatives,"OBS_LIMIT_EXCEEDED","uncertainty.alternatives")
            alternatives=[]
            for a in u["alternatives"]:
                _keys(a,"id data","alternative")
                alternatives.append(m.Alternative(_id(a["id"],"alternative.id"),_payload(kind,a["data"],limits)))
            _check(len({a.id for a in alternatives})==len(alternatives),"OBS_ID_DUPLICATE","alternatives")
            _check(not alternatives or len(alternatives)>=2,"OBS_CONTRADICTION","alternatives")
            choices = {canonical_json(payload_to_dict(a.payload,{ref:ref for ref,_ in _references(a.payload)}))
                       for a in alternatives}
            _check(len(choices)==len(alternatives),"OBS_CONTRADICTION","alternatives")
            _check(not alternatives or state is m.UncertaintyState.AMBIGUOUS,"OBS_CONTRADICTION","uncertainty.state")
            _check(state is m.UncertaintyState.PROVISIONAL or reasons,"OBS_CONTRADICTION","uncertainty.reasons")
            if g is None:
                _check(kind is m.ObservationKind.CONTACT or kind in {m.ObservationKind.PIN,m.ObservationKind.TEXT} and state is m.UncertaintyState.MISSING,"OBS_GEOMETRY_INVALID","geometry")
            elif kind in {m.ObservationKind.PIN,m.ObservationKind.JUNCTION,m.ObservationKind.CROSSING}:
                _check(len(g.points)==1,"OBS_GEOMETRY_INVALID","geometry.points")
            elif kind is m.ObservationKind.WIRE:
                _check(len(g.points)==2 and g.points[0]!=g.points[1],"OBS_GEOMETRY_INVALID","geometry.points")
            elif kind is not m.ObservationKind.CONTACT:
                _check(g.bbox is not None,"OBS_GEOMETRY_INVALID","geometry.bbox")
            _check(not (kind is m.ObservationKind.PIN and state is m.UncertaintyState.MISSING) or g is None,"OBS_CONTRADICTION","geometry")
            if isinstance(p,m.SymbolCandidate) and p.classification is not m.Classification.SUPPORTED:
                _check(reasons,"OBS_CONTRADICTION","uncertainty.reasons")
            if isinstance(p,m.UnknownCandidate): _check(reasons,"OBS_CONTRADICTION","uncertainty.reasons")
            if isinstance(p,m.TextCandidate) and p.value and p.value.si_value is None:
                _check(reasons,"OBS_CONTRADICTION","uncertainty.reasons")
            observations.append(m.Observation(row["id"],row["id"],kind,identity.source_sha256,g,p,
                                m.Confidence(None if c["score"] is None else float(c["score"]),c["basis"],False),
                                m.Uncertainty(state,reasons,related,tuple(sorted(alternatives,key=lambda a:a.id)))))
        by_id = {o.id:o for o in observations}
        for o in observations:
            for ref in o.uncertainty.related_refs:
                _check(ref in by_id and ref!=o.id,"OBS_REFERENCE_INVALID","uncertainty.related_refs")
            for p in (o.payload,*(a.payload for a in o.uncertainty.alternatives)):
                for ref,kinds in _references(p):
                    _check(ref in by_id and ref!=o.id and by_id[ref].kind in kinds,"OBS_REFERENCE_INVALID","observation.references")
                if isinstance(p,m.PinCandidate):
                    owner = by_id[p.component_ref].payload
                    if owner.classification is m.Classification.SUPPORTED:
                        roles = {m.ComponentType.RESISTOR:{m.PinRole.A,m.PinRole.B},m.ComponentType.CAPACITOR:{m.PinRole.A,m.PinRole.B},m.ComponentType.INDUCTOR:{m.PinRole.A,m.PinRole.B},m.ComponentType.VOLTAGE_SOURCE:{m.PinRole.POSITIVE,m.PinRole.NEGATIVE},m.ComponentType.CURRENT_SOURCE:{m.PinRole.POSITIVE,m.PinRole.NEGATIVE},m.ComponentType.NMOS:{m.PinRole.DRAIN,m.PinRole.GATE,m.PinRole.SOURCE,m.PinRole.BULK},m.ComponentType.PMOS:{m.PinRole.DRAIN,m.PinRole.GATE,m.PinRole.SOURCE,m.PinRole.BULK}}[owner.component_type]
                        _check(p.role in roles|{m.PinRole.UNKNOWN},"OBS_CONTRADICTION","data.role")
        provisional = m.ObservationSet(m.OBSERVATION_VERSION,identity.identity_sha256,identity.source_sha256,
                       identity.normalized_sha256,identity.transform.sha256,provider,data["coverage"],extraction_key,"","",tuple(observations))
        digest = content_digest(observations_to_dict(provisional))
        extraction = "extract_"+content_digest({"version":m.OBSERVATION_VERSION,"response":digest,"key":extraction_key})
        refs = {o.id:"obs_"+sha256((extraction+":"+o.id).encode()).hexdigest() for o in observations}
        mapped = tuple(replace(o,id=refs[o.id],payload=_remap(o.payload,refs),uncertainty=replace(o.uncertainty,
                           related_refs=tuple(refs[r] for r in o.uncertainty.related_refs),
                           alternatives=tuple(replace(a,payload=_remap(a.payload,refs)) for a in o.uncertainty.alternatives))) for o in observations)
        return m.ObservationResult(replace(provisional,response_sha256=digest,extraction_id=extraction,observations=mapped),())
    except _Invalid as error:
        return m.ObservationResult(None,(m.diagnostic(error.code,error.field),))
    except (ValueError,TypeError,UnicodeError,RecursionError,OverflowError):
        return m.ObservationResult(None,(m.diagnostic("OBS_JSON_INVALID","payload"),))
