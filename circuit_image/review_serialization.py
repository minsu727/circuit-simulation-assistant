"""Explicit canonical M3E projections; archives never restore live authority."""
import json
import re
from circuit_ir import models as ir
from .intake import canonical_json, content_digest
from . import review_models as r


def quantity_dict(q):
    if q is None: return None
    if type(q) is not ir.Quantity: raise TypeError('Quantity required')
    return dict(literal=q.literal,si_value=q.si_value,unit=q.unit,grammar=q.grammar.value)


def source_dict(s):
    if s is None: return None
    if type(s) is not ir.SourceConfiguration: raise TypeError('SourceConfiguration required')
    return dict(dc=quantity_dict(s.dc),ac=None if s.ac is None else dict(magnitude=quantity_dict(s.ac.magnitude),phase=quantity_dict(s.ac.phase)),
                waveform=dict(kind=s.waveform.kind.value,parameters={k:quantity_dict(v) for k,v in s.waveform.parameters}))


def correction_to_dict(op):
    t=type(op)
    if t is r.SetComponentType: return dict(kind='component_type',component_id=op.component_id,component_type=op.component_type.value)
    if t is r.SetReference: return dict(kind='reference',component_id=op.component_id,reference=op.reference)
    if t is r.SetValue: return dict(kind='value',component_id=op.component_id,value=quantity_dict(op.value))
    if t is r.SetSource: return dict(kind='source',component_id=op.component_id,source=source_dict(op.source))
    if t is r.SetMOSModel: return dict(kind='mos_model',component_id=op.component_id,profile_id=op.profile_id,width=quantity_dict(op.width),length=quantity_dict(op.length))
    if t is r.SetTerminalRole: return dict(kind='terminal_role',pin_id=op.pin_id,role=op.role.value)
    if t is r.SetTerminalOwner: return dict(kind='terminal_owner',pin_id=op.pin_id,component_id=op.component_id)
    if t is r.AddTerminal: return dict(kind='add_terminal',component_id=op.component_id,key=op.key,role=op.role.value)
    if t is r.ConnectPin: return dict(kind='pin_connection',pin_id=op.pin_id,net_id=op.net_id)
    if t is r.ChooseTopology: return dict(kind='topology_choice',ambiguity_id=op.ambiguity_id,option_id=op.option_id)
    if t is r.ConfirmContact: return dict(kind='contact',observation_id=op.observation_id,connected=op.connected)
    if t is r.MergeNets: return dict(kind='merge',net_ids=list(op.net_ids))
    if t is r.SplitNet: return dict(kind='split',net_id=op.net_id,partitions=[list(p) for p in op.partitions])
    if t is r.SetLabel: return dict(kind='label',observation_id=op.observation_id,text=op.text,net_id=op.net_id)
    if t is r.LabelEquivalence: return dict(kind='label_equivalence',observation_ids=list(op.observation_ids),equivalent=op.equivalent)
    if t is r.SetGround: return dict(kind='ground',observation_id=op.observation_id,net_id=op.net_id)
    if t is r.MarkUnsupported: return dict(kind='unsupported',component_id=op.component_id)
    if t is r.RetainIssue: return dict(kind='retain_issue',issue_id=op.issue_id)
    raise TypeError('Unsupported correction')


def _keys(d,names):
    if type(d) is not dict or set(d)!=set(names.split()): raise ValueError('Unexpected fields')


def _quantity(d):
    _keys(d,'literal si_value unit grammar')
    return ir.Quantity(d['literal'],d['si_value'],d['unit'],ir.ValueGrammar(d['grammar']))


def _source(d):
    _keys(d,'dc ac waveform');w=d['waveform'];_keys(w,'kind parameters')
    if type(w['parameters']) is not dict or len(w['parameters'])>7: raise ValueError('Waveform')
    ac=d['ac']
    if ac is not None: _keys(ac,'magnitude phase')
    return ir.SourceConfiguration(None if d['dc'] is None else _quantity(d['dc']),
        None if ac is None else ir.ACConfiguration(_quantity(ac['magnitude']),_quantity(ac['phase'])),
        ir.Waveform(ir.WaveformKind(w['kind']),tuple((k,_quantity(v)) for k,v in sorted(w['parameters'].items()))))


def correction_from_dict(d):
    if type(d) is not dict: raise ValueError('Correction object')
    kind=d.get('kind')
    specs={'component_type':('component_id component_type',r.SetComponentType), 'reference':('component_id reference',r.SetReference),
           'value':('component_id value',r.SetValue),'source':('component_id source',r.SetSource),'mos_model':('component_id profile_id width length',r.SetMOSModel),
           'terminal_role':('pin_id role',r.SetTerminalRole),'terminal_owner':('pin_id component_id',r.SetTerminalOwner),
           'add_terminal':('component_id key role',r.AddTerminal),'pin_connection':('pin_id net_id',r.ConnectPin),
           'topology_choice':('ambiguity_id option_id',r.ChooseTopology),'contact':('observation_id connected',r.ConfirmContact),
           'merge':('net_ids',r.MergeNets),'split':('net_id partitions',r.SplitNet),'label':('observation_id text net_id',r.SetLabel),
           'label_equivalence':('observation_ids equivalent',r.LabelEquivalence),'ground':('observation_id net_id',r.SetGround),
           'unsupported':('component_id',r.MarkUnsupported),'retain_issue':('issue_id',r.RetainIssue)}
    if type(kind) is not str or kind not in specs: raise ValueError('Correction kind')
    fields,cls=specs[kind];_keys(d,'kind '+fields);args={k:d[k] for k in fields.split()}
    for key in ('component_id','pin_id','observation_id','issue_id','ambiguity_id','option_id','net_id'):
        if key in args and not (key=='net_id' and args[key] is None):
            if type(args[key]) is not str or re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}',args[key]) is None:
                raise ValueError('Malformed identifier')
    for k in ('net_ids','observation_ids'):
        if k in args:
            if type(args[k]) is not list or len(args[k])>512: raise ValueError('ID list')
            if any(type(v) is not str or re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}',v) is None for v in args[k]):
                raise ValueError('Malformed identifier')
            args[k]=tuple(args[k])
    if 'partitions' in args:
        if type(args['partitions']) is not list or len(args['partitions'])>128 or any(type(p) is not list or len(p)>512 for p in args['partitions']): raise ValueError('Partitions')
        args['partitions']=tuple(tuple(p) for p in args['partitions'])
    if 'component_type' in args: args['component_type']=ir.ComponentType(args['component_type'])
    if 'role' in args: args['role']=ir.PinRole(args['role'])
    if 'value' in args: args['value']=_quantity(args['value'])
    if 'source' in args: args['source']=_source(args['source'])
    for k in ('width','length'):
        if k in args: args[k]=_quantity(args[k])
    return cls(**args)


def snapshot_to_dict(s):
    return dict(components=[dict(id=c.id,component_type=c.component_type.value if c.component_type else None,reference=c.reference,value=quantity_dict(c.value),source=source_dict(c.source),model_ref=c.model_ref,parameters={k:quantity_dict(v) for k,v in c.parameters},unsupported=c.unsupported) for c in s.components],
        pins=[dict(id=p.id,component_id=p.component_id,role=p.role.value) for p in s.pins],
        memberships=[list(v) for v in s.memberships],labels=[list(v) for v in s.labels],ground_ids=list(s.ground_ids),
        resolutions=[list(v) for v in s.resolutions],corrected_entities=list(s.corrected_entities),retained_issues=list(s.retained_issues))


def revision_to_dict(v,include_digest=True):
    d=dict(number=v.number,parent_digest=v.parent_digest,snapshot=snapshot_to_dict(v.snapshot),issues=[dict(id=i.id,code=i.code,targets=list(i.targets)) for i in v.issues])
    if include_digest:d['digest']=v.digest
    return d


def confirmation_to_dict(c,include_digest=True):
    d=dict(version=c.version,source_identity_sha256=c.source_identity_sha256,observation_sha256=c.observation_sha256,topology_sha256=c.topology_sha256,revision_sha256=c.revision_sha256,decision=c.decision.value,reviewed_claim_ids=list(c.reviewed_claim_ids))
    if include_digest:d['digest']=c.digest
    return d


def review_to_dict(s,include_digest=True):
    d=dict(version=s.version,source_identity_sha256=s.source_identity_sha256,observation_sha256=s.observation_sha256,topology_sha256=s.topology_sha256,
           events=[dict(base_digest=e.base_digest,operations=[correction_to_dict(o) for o in e.operations],revision_digest=e.revision_digest) for e in s.events],
           current=revision_to_dict(s.current),confirmation=None if s.confirmation is None else confirmation_to_dict(s.confirmation))
    if include_digest:d['digest']=s.digest
    return d


def dump_review(s): return canonical_json(review_to_dict(s))+'\n'


def decode_archive(payload):
    if type(payload) is bytes: payload=payload.decode('utf-8')
    if type(payload) is not str or len(payload.encode('utf-8'))>2_097_152: raise ValueError('Archive size')
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d: raise ValueError('Duplicate field')
            d[k]=v
        return d
    def constant(_): raise ValueError('Non-finite')
    return json.loads(payload,object_pairs_hook=pairs,parse_constant=constant)
