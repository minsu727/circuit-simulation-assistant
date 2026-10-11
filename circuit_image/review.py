"""Atomic, bounded human corrections; no observation mutation or M2 approval."""
from dataclasses import replace
import re
from circuit_ir import models as ir
from circuit_ir.value_parser import parse_quantity
from circuit_ir.model_profiles import repository_model_context, repository_model_profiles
from . import models as m
from .intake import canonical_json, content_digest
from .topology import validate_topology, label_identity
from . import review_models as r
from .review_serialization import (correction_to_dict, correction_from_dict, snapshot_to_dict,
    revision_to_dict, review_to_dict, confirmation_to_dict, decode_archive, _keys)

MAX_EVENTS=256
MAX_OPERATIONS=64
MAX_ENTITIES=1024
_PASSIVES={ir.ComponentType.RESISTOR:'ohm',ir.ComponentType.CAPACITOR:'F',ir.ComponentType.INDUCTOR:'H'}
_SOURCES={ir.ComponentType.VOLTAGE_SOURCE:'V',ir.ComponentType.CURRENT_SOURCE:'A'}
_ROLES={**{t:{ir.PinRole.A,ir.PinRole.B} for t in _PASSIVES},
        **{t:{ir.PinRole.POSITIVE,ir.PinRole.NEGATIVE} for t in _SOURCES},
        **{t:{ir.PinRole.DRAIN,ir.PinRole.GATE,ir.PinRole.SOURCE,ir.PinRole.BULK} for t in (ir.ComponentType.NMOS,ir.ComponentType.PMOS)}}


class ReviewError(ValueError):
    def __init__(self,code,field='review'):
        self.code,self.field=code,field
        super().__init__('Review does not satisfy '+code+'.')


def _need(condition,code='REVIEW_CORRECTION_INVALID',field='correction'):
    if not condition: raise ReviewError(code,field)


def _safe(value):
    return type(value) is str and len(value)<=64 and re.fullmatch('[A-Za-z][A-Za-z0-9_.-]*',value) is not None


def _quantity(q,unit):
    _need(type(q) is ir.Quantity and q.unit==unit and q.grammar is not ir.ValueGrammar.UNRESOLVED and type(q.literal) is str,'REVIEW_VALUE_INVALID')
    parsed=parse_quantity(q.literal,unit,q.grammar)
    _need(parsed.quantity is not None and parsed.quantity.si_value==q.si_value,'REVIEW_VALUE_INVALID')
    return parsed.quantity


def _observed_quantity(value):
    if value is None or value.si_value is None or value.unit is None:return None
    return parse_quantity(value.si_value,value.unit,ir.ValueGrammar.SI).quantity


def _issue(code,targets):
    targets=tuple(sorted(set(targets)))
    return r.ReviewIssue('review_issue_'+content_digest(dict(code=code,targets=targets)),code,targets)


def _issues(s,h,observations):
    issues=[];components={c.id:c for c in s.components};members=dict(s.memberships);corrected=set(s.corrected_entities)
    for c in s.components:
        if c.unsupported: issues.append(_issue('UNSUPPORTED_COMPONENT',(c.id,)));continue
        if c.component_type not in _ROLES:issues.append(_issue('COMPONENT_TYPE_REQUIRED',(c.id,)));continue
        if not _safe(c.reference):issues.append(_issue('COMPONENT_REFERENCE_REQUIRED',(c.id,)))
        owned=[p for p in s.pins if p.component_id==c.id]
        roles=[p.role for p in owned]
        if set(roles)!=_ROLES[c.component_type] or len(roles)!=len(set(roles)):issues.append(_issue('TERMINAL_ROLES_REQUIRED',(c.id,)))
        if c.component_type in _PASSIVES and c.value is None:issues.append(_issue('VALUE_REQUIRED',(c.id,)))
        if c.component_type in _SOURCES and (c.source is None or c.source.dc is None):issues.append(_issue('SOURCE_REQUIRED',(c.id,)))
        if c.component_type in (ir.ComponentType.NMOS,ir.ComponentType.PMOS) and (c.model_ref is None or set(dict(c.parameters))!={'width','length'}):issues.append(_issue('MOS_MODEL_DIMENSIONS_REQUIRED',(c.id,)))
    refs=[c.reference for c in s.components if c.reference]
    if len(set(refs))!=len(refs):issues.append(_issue('REFERENCE_CONFLICT',tuple(c.id for c in s.components)))
    for p in s.pins:
        if p.component_id not in components:issues.append(_issue('TERMINAL_OWNER_REQUIRED',(p.id,)))
        if members.get(p.id) is None:issues.append(_issue('PIN_CONNECTION_REQUIRED',(p.id,)))
    grounds={members.get(i) for i in s.ground_ids if members.get(i) is not None}
    if len(grounds)!=1:issues.append(_issue('GROUND_REQUIRED',s.ground_ids))
    names={}
    for lid,text in s.labels:
        if members.get(lid) is None and 'label:'+lid not in corrected:issues.append(_issue('LABEL_ATTACHMENT_REQUIRED',(lid,)))
        if members.get(lid) is not None:
            if label_identity(text) is None:issues.append(_issue('LABEL_TEXT_REQUIRED',(lid,)))
            names.setdefault(members[lid],set()).add(label_identity(text))
    if any(len(v)>1 for v in names.values()):issues.append(_issue('LABEL_CONFLICT',tuple(l for l,_ in s.labels)))
    resolved=dict(s.resolutions);by={o.id:o for o in observations.observations}
    for a in h.ambiguities:
        if a.id in resolved:
            choice=next((o for o in a.options if o.id==resolved[a.id]),None)
            meaning=choice.meaning if choice is not None else resolved[a.id]
            if choice is not None or meaning in ('manual_connected','manual_separated'):
                groups=[members.get(i) for i in (choice.subjects if choice is not None else a.subjects)]
                if meaning in ('connected','touching','equivalent','attached','manual_connected'):
                    consistent=bool(groups) and None not in groups and len(set(groups))==1
                elif meaning=='unassigned':
                    consistent=all(v is None for v in groups)
                else:
                    consistent=None not in groups and len(set(groups))==len(groups)
                if not consistent:issues.append(_issue('TOPOLOGY_RESOLUTION_CONFLICT',(a.id,)))
            continue
        typed=True
        for oid in a.subjects:
            o=by[oid]
            key=None
            if isinstance(o.payload,m.PinCandidate):key='role:'+oid
            elif isinstance(o.payload,m.SymbolCandidate):key='class:'+oid
            elif isinstance(o.payload,m.TextCandidate):key='value:'+str(o.payload.component_ref)
            elif isinstance(o.payload,m.LabelCandidate):key='label:'+oid
            if key is None or key not in corrected:typed=False
        if a.kind!='OBSERVATION_ALTERNATIVES' or not typed:issues.append(_issue('TOPOLOGY_CHOICE_REQUIRED',(a.id,)))
    for i in h.issues:
        if i.scope=='conversion' or i.code in {'UNSUPPORTED_COMPONENT','PIN_MISSING','PIN_UNCONNECTED','BULK_UNRESOLVED','CONFLICTING_TERMINAL_ROLE','NET_LABEL_CONFLICT'}:continue
        if any(set(i.observation_ids)&set(a.evidence) for a in h.ambiguities):continue
        prefix={'SYMBOL_UNCLEAR':'class:','TERMINAL_ROLE_UNCLEAR':'role:','LABEL_ATTACHMENT_UNRESOLVED':'label:',
                'GROUND_ATTACHMENT_UNRESOLVED':'ground:','PIN_CONTACT_UNRESOLVED':'connection:'}.get(i.code,'topology:')
        relevant=[t for t in i.observation_ids if t in by and (prefix!='role:' or by[t].kind is m.ObservationKind.PIN)]
        if not relevant or not all(prefix+t in corrected for t in relevant):issues.append(_issue(i.code,i.observation_ids))
    # Ownership alternatives cannot be settled by role alone.
    for o in observations.observations:
        if isinstance(o.payload,m.PinCandidate) and any(a.payload.component_ref!=o.payload.component_ref for a in o.uncertainty.alternatives) and 'owner:'+o.id not in corrected:
            issues.append(_issue('TERMINAL_OWNER_REQUIRED',(o.id,)))
    return tuple(sorted(set(issues),key=lambda i:i.id))


def _revision(number,parent,snapshot,h,observations):
    v=r.ReviewRevision(number,parent,snapshot,_issues(snapshot,h,observations),'')
    return replace(v,digest=content_digest(revision_to_dict(v,False)))


def _seal(session):return replace(session,digest=content_digest(review_to_dict(session,False)))


def _initial(h,s):
    by={o.id:o for o in s.observations};components=[]
    for c in h.components:
        p=c.payload;kind=p.component_type if isinstance(p,m.SymbolCandidate) else None
        quantities=[by[t].payload for t in c.text_observation_ids
                    if by[t].uncertainty.state is m.UncertaintyState.PROVISIONAL and not by[t].uncertainty.reasons
                    and not by[t].uncertainty.alternatives]
        values=[_observed_quantity(t.value) for t in quantities if t.purpose is m.TextPurpose.VALUE]
        dc=[_observed_quantity(t.value) for t in quantities if t.purpose is m.TextPurpose.SOURCE_DC]
        source=ir.SourceConfiguration(dc[0],None,ir.Waveform(ir.WaveformKind.NONE,())) if len(dc)==1 and dc[0] is not None else None
        components.append(r.ReviewedComponent(c.observation_id,kind,p.reference_text if isinstance(p,m.SymbolCandidate) else None,
            values[0] if len(values)==1 else None,source,None,(),isinstance(p,m.SymbolCandidate) and p.classification is m.Classification.UNSUPPORTED))
    members={o.id:None for o in s.observations if o.kind in {m.ObservationKind.WIRE,m.ObservationKind.PIN,m.ObservationKind.GROUND,m.ObservationKind.LABEL,m.ObservationKind.SUPPLY_LABEL}}
    for n in h.nets:
        for oid in (*n.wire_observation_ids,*n.ground_observation_ids,*n.label_observation_ids):members[oid]=n.id
    for c in h.claims:
        if c.kind=='pin_to_net':members[c.subjects[0]]=c.net_id if c.decision=='attached' else None
    snapshot=r.ReviewSnapshot(tuple(sorted(components,key=lambda c:c.id)),tuple(r.ReviewedPin(p.observation_id,p.component_observation_id,p.role) for p in sorted(h.terminals,key=lambda p:p.observation_id)),
        tuple(sorted(members.items())),tuple(sorted((o.id,o.payload.raw_text) for o in s.observations if isinstance(o.payload,m.LabelCandidate))),
        tuple(sorted(o.id for o in s.observations if o.kind is m.ObservationKind.GROUND)),(),(),())
    _need(len(members)+len(components)<=MAX_ENTITIES,'REVIEW_LIMIT_EXCEEDED')
    return _seal(r.ReviewSession(r.REVIEW_VERSION,h.source_identity_sha256,h.observation_response_sha256,h.digest,h,(),_revision(0,None,snapshot,h,s),None,''))


def start_review(hypothesis,observations,image):
    diagnostics=validate_topology(hypothesis,observations,image)
    if diagnostics:return r.ReviewResult(None,diagnostics)
    try:return r.ReviewResult(_initial(hypothesis,observations),())
    except (TypeError,ValueError,KeyError,AttributeError):return r.ReviewResult(None,(m.diagnostic('REVIEW_INPUT_INVALID','review'),))


def _batch(operations):
    _need(type(operations) is tuple and 1<=len(operations)<=MAX_OPERATIONS,'REVIEW_LIMIT_EXCEEDED')
    normalized=[];writes=set();global_write=False
    for op in operations:
        data=correction_to_dict(op);parsed=correction_from_dict(data)
        _need(parsed==op,'REVIEW_CORRECTION_INVALID')
        if type(op) in (r.MergeNets,r.SplitNet,r.ChooseTopology,r.ConfirmContact,r.LabelEquivalence):
            _need(not global_write,'REVIEW_CORRECTION_CONFLICT');global_write=True
        key=(data['kind'],data.get('component_id',data.get('pin_id',data.get('observation_id',data.get('issue_id','global')))))
        _need(key not in writes,'REVIEW_CORRECTION_CONFLICT');writes.add(key)
        normalized.append(op)
    classes={o.component_id for o in normalized if type(o) is r.SetComponentType}
    unsupported={o.component_id for o in normalized if type(o) is r.MarkUnsupported}
    _need(not classes.intersection(unsupported),'REVIEW_CORRECTION_CONFLICT')
    if global_write:
        _need(sum(type(o) in (r.MergeNets,r.SplitNet,r.ChooseTopology,r.ConfirmContact,r.LabelEquivalence,r.ConnectPin,r.SetGround,r.SetLabel) for o in normalized)==1,'REVIEW_CORRECTION_CONFLICT')
    return tuple(sorted(normalized,key=lambda o:canonical_json(correction_to_dict(o))))


def _apply(session,operations,observations):
    snapshot=session.current.snapshot;components={c.id:c for c in snapshot.components};pins={p.id:p for p in snapshot.pins}
    members=dict(snapshot.memberships);labels=dict(snapshot.labels);ground_ids=set(snapshot.ground_ids)
    corrected=set(snapshot.corrected_entities);resolved=dict(snapshot.resolutions);retained=set(snapshot.retained_issues)
    by={o.id:o for o in observations.observations};h=session.initial_topology
    def entity(identity,collection):_need(type(identity) is str and identity in collection,'REVIEW_REFERENCE_INVALID')
    def net(identity):_need(identity is None or type(identity) is str and identity in set(members.values())-{None},'REVIEW_REFERENCE_INVALID')
    def merge(ids):
        _need(type(ids) is tuple and len(ids)>=2 and len(set(ids))==len(ids))
        for i in ids:net(i);_need(i is not None)
        affected=sorted(k for k,n in members.items() if n in ids)
        target='review_net_'+content_digest(affected)
        for k in affected:members[k]=target;corrected.add('topology:'+k)
    def relation(refs,connected):
        _need(type(connected) is bool)
        for i in refs:entity(i,members)
        ids=tuple(sorted({members[i] for i in refs if members[i] is not None}))
        _need(len(ids)>0 and all(members[i] is not None for i in refs),'REVIEW_REFERENCE_INVALID')
        if connected and len(ids)>1:merge(ids)
        if not connected:_need(len(ids)==len(refs),'REVIEW_SPLIT_REQUIRED')
        for i in refs:corrected.add('topology:'+i)
    for op in operations:
        t=type(op)
        if t in (r.SetComponentType,r.SetReference,r.SetValue,r.SetSource,r.SetMOSModel,r.MarkUnsupported,r.AddTerminal):entity(op.component_id,components)
        if t in (r.SetTerminalRole,r.SetTerminalOwner,r.ConnectPin):entity(op.pin_id,pins)
        if t is r.SetComponentType:
            _need(type(op.component_type) is ir.ComponentType and op.component_type in _ROLES)
            _need(not components[op.component_id].unsupported,'REVIEW_UNSUPPORTED_SUBSTITUTION')
            c=components[op.component_id]
            if c.component_type is not op.component_type:
                # An explicit type change withdraws dependent proposals. It
                # never invents replacement values, sources, roles or models.
                c=replace(c,value=None,source=None,model_ref=None,parameters=())
            components[op.component_id]=replace(c,component_type=op.component_type)
            corrected.add('class:'+op.component_id)
        elif t is r.SetReference:
            _need(_safe(op.reference),'REVIEW_REFERENCE_INVALID')
            components[op.component_id]=replace(components[op.component_id],reference=op.reference)
        elif t is r.SetValue:
            c=components[op.component_id];_need(c.component_type in _PASSIVES)
            components[c.id]=replace(c,value=_quantity(op.value,_PASSIVES[c.component_type]));corrected.add('value:'+c.id)
        elif t is r.SetSource:
            c=components[op.component_id];_need(c.component_type in _SOURCES and type(op.source) is ir.SourceConfiguration)
            source=op.source;unit=_SOURCES[c.component_type]
            if source.dc is not None:_quantity(source.dc,unit)
            if source.ac is not None:_quantity(source.ac.magnitude,unit);_quantity(source.ac.phase,'deg')
            specs={ir.WaveformKind.NONE:{},ir.WaveformKind.SINE:{'offset':unit,'amplitude':unit,'frequency':'Hz'},ir.WaveformKind.PULSE:{'level1':unit,'level2':unit,'delay':'s','rise':'s','fall':'s','width':'s','period':'s'}}[source.waveform.kind]
            _need(set(dict(source.waveform.parameters))==set(specs),'REVIEW_SOURCE_INVALID')
            for k,q in source.waveform.parameters:_quantity(q,specs[k])
            components[c.id]=replace(c,source=source);corrected.add('value:'+c.id)
        elif t is r.SetMOSModel:
            c=components[op.component_id]
            profiles=repository_model_profiles(repository_model_context())
            _need(any(p.profile_id==op.profile_id and p.component_type is c.component_type for p in profiles),'REVIEW_MODEL_UNSUPPORTED')
            components[c.id]=replace(c,model_ref=op.profile_id,parameters=(('length',_quantity(op.length,'m')),('width',_quantity(op.width,'m'))))
        elif t is r.SetTerminalRole:
            _need(type(op.role) is ir.PinRole and op.role is not ir.PinRole.UNKNOWN)
            pins[op.pin_id]=replace(pins[op.pin_id],role=op.role);corrected.add('role:'+op.pin_id)
        elif t is r.SetTerminalOwner:
            entity(op.component_id,components);pins[op.pin_id]=replace(pins[op.pin_id],component_id=op.component_id);corrected.add('owner:'+op.pin_id)
        elif t is r.AddTerminal:
            _need(_safe(op.key) and type(op.role) is ir.PinRole and op.role is not ir.PinRole.UNKNOWN)
            identity='review_pin_'+content_digest(dict(component=op.component_id,key=op.key))
            _need(identity not in pins,'REVIEW_CORRECTION_CONFLICT')
            pins[identity]=r.ReviewedPin(identity,op.component_id,op.role);members[identity]=None;corrected.add('role:'+identity)
        elif t is r.ConnectPin:
            net(op.net_id);members[op.pin_id]=op.net_id;corrected.add('connection:'+op.pin_id)
        elif t is r.ChooseTopology:
            a=next((a for a in h.ambiguities if a.id==op.ambiguity_id),None)
            _need(a is not None,'REVIEW_REFERENCE_INVALID')
            choice=next((c for c in a.options if c.id==op.option_id),None)
            _need(choice is not None and a.kind!='OBSERVATION_ALTERNATIVES','REVIEW_REFERENCE_INVALID')
            if choice.meaning in ('attached','unassigned'):
                ps=[i for i in choice.subjects if i in pins];_need(len(ps)==1)
                others=[i for i in choice.subjects if i not in pins];members[ps[0]]=members[others[0]] if others else None;corrected.add('connection:'+ps[0])
            else:relation(choice.subjects,choice.meaning in ('connected','touching','equivalent'))
            resolved[a.id]=choice.id
        elif t is r.ConfirmContact:
            entity(op.observation_id,by);o=by[op.observation_id]
            _need(isinstance(o.payload,(m.JunctionCandidate,m.ContactCandidate)))
            refs=o.payload.wire_refs if isinstance(o.payload,m.JunctionCandidate) else o.payload.refs
            if any(i in pins and members.get(i) is None for i in refs):
                _need(len(refs)==2)
                p=next(i for i in refs if i in pins);other=next(i for i in refs if i!=p)
                _need(type(op.connected) is bool);members[p]=members[other] if op.connected else None;corrected.add('connection:'+p)
            else:relation(refs,op.connected)
            corrected.add('topology:'+o.id)
            for a in h.ambiguities:
                if o.id in a.evidence:resolved[a.id]='manual_connected' if op.connected else 'manual_separated'
        elif t is r.MergeNets:merge(op.net_ids)
        elif t is r.SplitNet:
            net(op.net_id);_need(op.net_id is not None and type(op.partitions) is tuple and 2<=len(op.partitions)<=128)
            _need(all(type(p) is tuple and p and len(p)<=MAX_ENTITIES for p in op.partitions))
            items=[i for p in op.partitions for i in p]
            _need(len(items)==len(set(items)) and set(items)=={k for k,n in members.items() if n==op.net_id},'REVIEW_PARTITION_INVALID')
            for partition in op.partitions:
                nid='review_net_'+content_digest(sorted(partition))
                for i in partition:members[i]=nid;corrected.add('topology:'+i)
        elif t is r.SetLabel:
            entity(op.observation_id,labels);net(op.net_id)
            _need(label_identity(op.text) is not None,'REVIEW_LABEL_INVALID')
            labels[op.observation_id]=op.text;members[op.observation_id]=op.net_id;corrected.add('label:'+op.observation_id)
        elif t is r.LabelEquivalence:
            _need(type(op.equivalent) is bool and type(op.observation_ids) is tuple and len(op.observation_ids)>=2 and len(set(op.observation_ids))==len(op.observation_ids))
            for i in op.observation_ids:entity(i,labels)
            _need(len({label_identity(labels[i]) for i in op.observation_ids})==1,'REVIEW_LABEL_INVALID')
            relation(op.observation_ids,op.equivalent)
            for i in op.observation_ids:corrected.add('label:'+i)
        elif t is r.SetGround:
            entity(op.observation_id,ground_ids);net(op.net_id);members[op.observation_id]=op.net_id;corrected.add('ground:'+op.observation_id)
        elif t is r.MarkUnsupported:components[op.component_id]=replace(components[op.component_id],unsupported=True)
        elif t is r.RetainIssue:
            _need(op.issue_id in {i.id for i in session.current.issues},'REVIEW_REFERENCE_INVALID');retained.add(op.issue_id)
        else:raise ReviewError('REVIEW_CORRECTION_INVALID')
    # Explicit partition corrections can settle local contacts, never role/value alternatives.
    for a in h.ambiguities:
        if a.kind!='OBSERVATION_ALTERNATIVES' and a.id not in resolved and all('topology:'+i in corrected for i in a.subjects):
            resolved[a.id]='manual_partition'
    _need(len(members)+len(components)<=MAX_ENTITIES,'REVIEW_LIMIT_EXCEEDED')
    new=r.ReviewSnapshot(tuple(sorted(components.values(),key=lambda c:c.id)),tuple(sorted(pins.values(),key=lambda p:p.id)),tuple(sorted(members.items())),tuple(sorted(labels.items())),tuple(sorted(ground_ids)),tuple(sorted(resolved.items())),tuple(sorted(corrected)),tuple(sorted(retained)))
    revision=_revision(session.current.number+1,session.current.digest,new,h,observations)
    event=r.ReviewEvent(session.current.digest,operations,revision.digest)
    return _seal(replace(session,events=(*session.events,event),current=revision,confirmation=None))


def _verify(session,hypothesis,observations,image):
    diagnostics=validate_topology(hypothesis,observations,image)
    if diagnostics:raise ReviewError('REVIEW_SOURCE_STALE')
    _need(type(session) is r.ReviewSession and session.version==r.REVIEW_VERSION,'REVIEW_VERSION_INVALID')
    _need(type(session.events) is tuple and len(session.events)<=MAX_EVENTS,'REVIEW_LIMIT_EXCEEDED')
    current=_initial(hypothesis,observations)
    for e in session.events:
        _need(type(e) is r.ReviewEvent and e.base_digest==current.current.digest,'REVIEW_STALE_REVISION')
        ops=_batch(e.operations);_need(ops==e.operations,'REVIEW_CORRECTION_INVALID')
        current=_apply(current,ops,observations)
        _need(current.current.digest==e.revision_digest,'REVIEW_STALE_REVISION')
    if session.confirmation is not None:
        c=_confirmation(current,session.confirmation.decision,session.confirmation.reviewed_claim_ids)
        _need(c==session.confirmation,'REVIEW_CONFIRMATION_STALE')
        current=_seal(replace(current,confirmation=c))
    _need(current==session and canonical_json(review_to_dict(current))==canonical_json(review_to_dict(session)),
          'REVIEW_STALE_SESSION')


def validate_review(session,hypothesis,observations,image):
    try:_verify(session,hypothesis,observations,image);return ()
    except ReviewError as e:return (m.diagnostic(e.code,e.field),)
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError,RecursionError):return (m.diagnostic('REVIEW_INPUT_INVALID','review'),)


def apply_corrections(session,operations,*,base_revision_digest,hypothesis,observations,image):
    diagnostics=validate_review(session,hypothesis,observations,image)
    if diagnostics:return r.ReviewResult(None,diagnostics)
    try:
        _need(base_revision_digest==session.current.digest,'REVIEW_STALE_REVISION')
        _need(len(session.events)<MAX_EVENTS,'REVIEW_LIMIT_EXCEEDED')
        return r.ReviewResult(_apply(session,_batch(operations),observations),())
    except ReviewError as e:return r.ReviewResult(None,(m.diagnostic(e.code,e.field),))
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError):return r.ReviewResult(None,(m.diagnostic('REVIEW_CORRECTION_INVALID','correction'),))


def _confirmation(session,decision,claims):
    _need(type(decision) is r.ReviewDecision and decision is r.ReviewDecision.CONFIRM,'REVIEW_DECISION_REQUIRED')
    _need(not session.current.issues,'REVIEW_BLOCKING_ISSUES')
    _need(type(claims) is tuple and claims==tuple(sorted(c.id for c in session.initial_topology.claims)),'REVIEW_CLAIMS_NOT_REVIEWED')
    c=r.ReviewConfirmation(r.REVIEW_VERSION,session.source_identity_sha256,session.observation_sha256,session.topology_sha256,session.current.digest,decision,claims,'')
    return replace(c,digest=content_digest(confirmation_to_dict(c,False)))


def confirm_review(session,*,decision,reviewed_claim_ids,base_revision_digest,hypothesis,observations,image):
    diagnostics=validate_review(session,hypothesis,observations,image)
    if diagnostics:return r.ReviewResult(None,diagnostics)
    try:
        _need(base_revision_digest==session.current.digest,'REVIEW_STALE_REVISION')
        return r.ReviewResult(_seal(replace(session,confirmation=_confirmation(session,decision,reviewed_claim_ids))),())
    except ReviewError as e:return r.ReviewResult(None,(m.diagnostic(e.code,e.field),))


def load_review(payload,*,hypothesis,observations,image):
    """Replay checked archive, returning an UNCONFIRMED session for human review."""
    try:
        data=decode_archive(payload);_keys(data,'version source_identity_sha256 observation_sha256 topology_sha256 events current confirmation digest')
        _need(data['version']==r.REVIEW_VERSION,'REVIEW_VERSION_INVALID')
        _need(type(data['events']) is list and len(data['events'])<=MAX_EVENTS,'REVIEW_LIMIT_EXCEEDED')
        result=start_review(hypothesis,observations,image)
        _need(result.session is not None,'REVIEW_SOURCE_STALE');session=result.session
        for e in data['events']:
            _keys(e,'base_digest operations revision_digest')
            _need(type(e['operations']) is list and len(e['operations'])<=MAX_OPERATIONS,'REVIEW_LIMIT_EXCEEDED')
            updated=apply_corrections(session,tuple(correction_from_dict(o) for o in e['operations']),base_revision_digest=e['base_digest'],hypothesis=hypothesis,observations=observations,image=image)
            _need(updated.session is not None,'REVIEW_ARCHIVE_INVALID');session=updated.session
            _need(session.current.digest==e['revision_digest'],'REVIEW_STALE_REVISION')
        unconfirmed=session
        if data['confirmation'] is not None:
            c=data['confirmation'];_keys(c,'version source_identity_sha256 observation_sha256 topology_sha256 revision_sha256 decision reviewed_claim_ids digest')
            _need(type(c['reviewed_claim_ids']) is list,'REVIEW_ARCHIVE_INVALID')
            c2=_confirmation(session,r.ReviewDecision(c['decision']),tuple(c['reviewed_claim_ids']))
            session=_seal(replace(session,confirmation=c2))
        _need(canonical_json(review_to_dict(session))==canonical_json(data),'REVIEW_ARCHIVE_INVALID')
        return r.ReviewResult(unconfirmed,())
    except ReviewError as e:return r.ReviewResult(None,(m.diagnostic(e.code,e.field),))
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError,RecursionError):return r.ReviewResult(None,(m.diagnostic('REVIEW_ARCHIVE_INVALID','archive'),))
