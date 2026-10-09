"""Level B: explicit local real LTspice verification of repository-owned M2 IR.

python -X utf8 tests/verify_netlist_integration.py --real-ltspice
No default discovery, no user approval automation, no external model/network.
Source variants are reviewed test-controller snapshots and retained in ignored
run evidence; committed M1/M2 inputs and exact-byte goldens are never changed.
"""
import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import circuit_ir as ir
from netlist_runner import run_ltspice_netlist, RunStatus, _read_log
from netlist_result_analysis import read_generated_current
from tests.m2e_helpers import BASES, document, chain


def q(value,unit):
    value=ir.parse_quantity(str(value),unit,ir.ValueGrammar.SI)
    assert value.quantity is not None,value.issues
    return value.quantity


def driven(name,*,sine=False):
    """Explicit test fixture edit, followed by all three separate decisions."""
    doc=document(name)
    source=next(c for c in doc.components if c.id=="V1")
    waveform=source.source.waveform
    if sine:
        waveform=ir.Waveform(ir.WaveformKind.SINE,(("offset",source.source.dc),
                            ("amplitude",q("0.01","V")),("frequency",q("1000","Hz"))))
    source=replace(source,source=replace(source.source,
            ac=ir.ACConfiguration(q("2","V"),q("-45" if name=="rc_low_pass" else "0","deg")),waveform=waveform))
    return replace(doc,metadata=replace(doc.metadata,revision=doc.metadata.revision+1),
                   components=tuple(source if c.id==source.id else c for c in doc.components))


def ac(target="vout",reference="vin"):
    return ir.AnalysisRequest(ir.ACCondition(ir.ACSweep.DECADE,100,"10","1000000"),target,reference,
                             measurements=("Gain","-3 dB Bandwidth"))


def tran(target="vin",reference="vin"):
    return ir.AnalysisRequest(ir.TransientCondition("0.01",maximum_timestep="0.000001"),target,reference,
                             measurements=("Voltage Gain","Output Swing"))


def dc(source="V1",target="vout",point="3"):
    return ir.AnalysisRequest(ir.DCCondition(source,"0","5","0.1"),target,requested_point=point,
                             measurements=("Minimum","Maximum","Value at Sweep Point"))


def cases():
    yield "divider_dc","resistor_divider",dc(),None
    yield "divider_ac","resistor_divider",ac(),None
    yield "rc_ac","rc_low_pass",ac(),driven("rc_low_pass")
    yield "rc_transient","rc_low_pass",tran("vout"),driven("rc_low_pass",sine=True)
    yield "current_dc","current_source_load",ir.AnalysisRequest(ir.DCCondition("I1","-0.001","0.001","0.0001"),"vin",requested_point="0.001",measurements=("Value at Sweep Point",)),None
    yield "rlc_dc","rlc_network",dc(point="1"),None
    yield "rlc_transient","rlc_network",tran("vout"),driven("rlc_network",sine=True)
    for name in ("sine_voltage","sine_current","pulse_voltage","pulse_current"):
        yield name+"_ac",name,ac("vin","vin"),None
        yield name+"_transient",name,tran(),None
        source="I1" if name.endswith("current") else "V1"
        request=(ir.AnalysisRequest(ir.DCCondition(source,"-0.001","0.001","0.0001"),"vin",requested_point="0.001",measurements=("Value at Sweep Point",))
                 if source=="I1" else dc(target="vin",point="1"))
        yield name+"_dc",name,request,None
    for name,bias in (("nmos_common_source","2"),("pmos_resistive_load","3")):
        yield name+"_dc",name,dc(point=bias),None
        yield name+"_ac",name,ac(),driven(name,sine=True)
        yield name+"_transient",name,tran("vout"),driven(name,sine=True)


def number(doc,identity):
    return float(next(c for c in doc.components if c.id==identity).value.si_value)


def comparisons(key,data,sim):
    """Tolerances chosen here before running LTspice, not fitted to outputs."""
    result=sim.analysis.result; doc=data["document"]; checks=[]; metrics={}
    def near(name,actual,expected,rtol=.005,atol=1e-8):
        value={"measurement":name,"actual":float(actual),"expected":float(expected),"rtol":rtol,"atol":atol,
               "passed":bool(np.isclose(actual,expected,rtol=rtol,atol=atol))}
        checks.append(value); metrics[name]=float(actual)
    if isinstance(data["request"].condition,ir.ACCondition):
        metrics.update(gain_db=result.low_frequency_gain_db,bandwidth_hz=result.bandwidth_hz,bandwidth_status=result.bandwidth_status)
        if key=="rc_ac":
            r,c=number(doc,"R1"),number(doc,"C1")
            # Current algorithm uses -3.000 dB, not exact half-power -3.0103 dB.
            near("bandwidth_hz",result.bandwidth_hz,math.sqrt(10**.3-1)/(2*math.pi*r*c),rtol=.01)
            expected=1/(1+1j*2*np.pi*result.frequency*r*c)
            near("maximum_complex_transfer_error",np.max(np.abs(result.transfer-expected)),0,atol=1e-5)
            near("input_ac_magnitude",abs(result.reference[0]),2)
        elif key=="divider_ac":
            near("linear_gain",abs(result.transfer[0]),number(doc,"R2")/(number(doc,"R1")+number(doc,"R2")))
        elif key.startswith(("sine_","pulse_")):
            source=next(c for c in doc.components if c.source)
            magnitude=float(source.source.ac.magnitude.si_value)
            phase=float(source.source.ac.phase.si_value)
            expected=magnitude*np.exp(1j*np.deg2rad(phase))
            if source.type is ir.ComponentType.CURRENT_SOURCE: expected*=-number(doc,"R1")
            near("source_ac_complex_error",np.max(np.abs(result.target-expected)),0,atol=1e-6)
        else:
            near("finite_gain",float(np.all(np.isfinite(result.gain_db))),1,rtol=0,atol=0)
            checks.append({"measurement":"common_source_inversion","passed":bool(np.real(result.transfer[0])<0)})
    elif isinstance(data["request"].condition,ir.TransientCondition):
        swing=result.measurements["Output Swing"].values
        metrics.update({k:float(v[0]) for k,v in swing.items()})
        gain=result.measurements["Voltage Gain"]
        metrics["gain_measurements"]={k:float(v[0]) for k,v in gain.values.items()}
        metrics["gain_unavailable_reason"]=gain.reason
        if key.startswith(("sine_","pulse_")):
            current=key.startswith(("sine_current","pulse_current"))
            scale=number(doc,"R1") if current else 1
            source=next(c for c in doc.components if c.source); wave=dict(source.source.waveform.parameters)
            expected=(2*abs(float(wave["amplitude"].si_value)) if "amplitude" in wave
                      else abs(float(wave["level2"].si_value)-float(wave["level1"].si_value)))*scale
            near("output_vpp",swing["Peak-to-Peak"][0],expected,rtol=.01)
            initial=float(wave["offset" if "offset" in wave else "level1"].si_value)*scale*(-1 if current else 1)
            near("initial_source_voltage",result.target[0],initial,atol=1e-6)
            # Explicit emitted source expression, including positive->negative I sign.
            if "amplitude" in wave:
                values=(float(wave["offset"].si_value)+float(wave["amplitude"].si_value)*np.sin(2*np.pi*float(wave["frequency"].si_value)*result.time))*scale*(-1 if current else 1)
                near("maximum_source_waveform_error",np.max(np.abs(result.target-values)),0,atol=max(1e-6,expected*.001))
                if not gain.values: raise AssertionError("Stable sine gain was not available: "+gain.reason)
                near("periodic_voltage_gain",gain.values["Voltage Gain"][0],1)
        else:
            # RC startup settles before late-cycle comparison; RLC analytic transfer.
            r=number(doc,"R1"); c=number(doc,"C1") if any(v.id=="C1" for v in doc.components) else None
            if key=="rc_transient": expected=1/abs(1+1j*2*np.pi*1000*r*c)
            elif key=="rlc_transient": expected=1/abs(1-(2*np.pi*1000)**2*number(doc,"L1")*c+1j*2*np.pi*1000*r*c)
            else: expected=None
            if not gain.values: raise AssertionError("Periodic gain unavailable: "+gain.reason)
            if expected is not None: near("periodic_voltage_gain",gain.values["Voltage Gain"][0],expected,rtol=.02)
            else: near("finite_gain",float(np.isfinite(gain.values["Voltage Gain"][0])),1,rtol=0,atol=0)
    else:
        metrics["value_at_point"]=result.point_value
        if key=="divider_dc": near("value_at_point",result.point_value,3*number(doc,"R2")/(number(doc,"R1")+number(doc,"R2")))
        elif key.endswith("_dc") and ("current" in key): near("value_at_point",result.point_value,-.001*number(doc,"R1"))
        elif key in ("rlc_dc","sine_voltage_dc","pulse_voltage_dc"): near("value_at_point",result.point_value,1)
        else:
            # Separately derived Level-1 saturation + resistor equation at Vov=1.
            # R=1000, KP=1e-4, W/L=10, lambda=.02, VDD=5.
            model=next(c for c in doc.components if c.type in (ir.ComponentType.NMOS,ir.ComponentType.PMOS))
            profile=next(p for p in ir.repository_model_profiles(data["model_context"]) if p.profile_id==model.model_ref)
            vdd=float(next(c for c in doc.components if c.id=="V2").source.dc.si_value)
            gate=float(data["request"].requested_point)
            vov=(gate if model.type is ir.ComponentType.NMOS else vdd-gate)-abs(float(profile.vto))
            params=dict(model.parameters); beta=float(profile.kp)*float(params["width"].si_value)/float(params["length"].si_value)
            r=number(doc,"R1"); a=.5*beta*vov*vov; lam=float(profile.lambda_)
            drop=r*a*(1+lam*vdd)/(1+r*a*lam)
            near("value_at_point",result.point_value,vdd-drop if model.type is ir.ComponentType.NMOS else drop,rtol=.01)
            current_axis,current_wave,current_name=read_generated_current(sim.run.raw_file,sim.run.artifact,data["export_result"],"R1")
            current_at_bias=float(np.interp(gate,current_axis,current_wave))
            near("resistor_load_current_at_bias",current_at_bias,drop/r,rtol=.01)
            metrics["load_current_trace"]=current_name
    # Always inspect mapped source current when this fixture's probe is supported.
    source=next(c for c in doc.components if c.source)
    axis,values,name=read_generated_current(sim.run.raw_file,sim.run.artifact,data["export_result"],source.id)
    metrics["current_probe"]={"ir_id":source.id,"raw_trace":name,"first":float(values[0].real),"last":float(values[-1].real)}
    if key=="current_dc": near("source_current_last",values[-1],.001,rtol=.005)
    if key=="divider_dc": near("voltage_source_current_last",values[-1],-5/(number(doc,"R1")+number(doc,"R2")),rtol=.005)
    return metrics,checks


def verify_asc():
    """Actual v0.1 public ASC regression through its unchanged upload wrapper."""
    from io import BytesIO
    from simulation_runner import run_ltspice
    from runtime_paths import configure_ltspice
    from ac_result_analysis import read_ac_result
    from transient_result_analysis import read_transient_result
    from dc_result_analysis import read_dc_result
    path=ROOT/"examples/common_source_amplifier/common_source_amplifier.asc"
    content=path.read_bytes(); before=hashlib.sha256(content).hexdigest()
    configure_ltspice()
    results=[]
    for mode in ("AC","TRAN","DC"):
        uploaded=BytesIO(content); uploaded.name=path.name
        conditions=({"ac_conditions":{"sweep_type":"Decade","points":100,"start_frequency":"10","stop_frequency":"1000000"}} if mode=="AC"
            else {"transient_conditions":{"stop_time":"0.01","start_saving_time":"0.005","maximum_timestep":"0.000002"}} if mode=="TRAN"
            else {"dc_conditions":{"sweep_source":"V1","start_value":"1.8","stop_value":"2.2","step_value":"0.01"}})
        raw,log,directive=run_ltspice(uploaded,approved=True,**conditions)
        if mode=="AC":
            result=read_ac_result(raw,"V(vout)","V(vin)")
            values={"gain_db":result.low_frequency_gain_db,"bandwidth_hz":result.bandwidth_hz}
            assert np.isfinite(result.low_frequency_gain_db) and result.bandwidth_hz is not None
        elif mode=="TRAN":
            result=read_transient_result(raw,"V(vout)","V(vin)",("Voltage Gain",))
            values={k:float(v[0]) for k,v in result.measurements["Voltage Gain"].values.items()}
            assert values and all(np.isfinite(v) for v in values.values())
        else:
            result=read_dc_result(raw,"V(vout)",measurements=("Value at Sweep Point",),point=2,sweep_source="V1")
            values={"value_at_gate_2V":result.point_value}
            assert np.isfinite(result.point_value)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
        results.append({"analysis":mode,"status":"PASS","directive":directive,"raw":str(raw),"log":str(log),"measurements":values,"source_sha256":before,"source_preserved":True})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-ltspice",action="store_true",help="Explicitly execute separately installed LTspice")
    args=parser.parse_args()
    if not args.real_ltspice: parser.error("Real simulator verification requires --real-ltspice")
    paths=list(BASES.rglob("*"))+list((ROOT/"tests/fixtures/netlist_execution").rglob("*"))
    original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    root=ROOT/"simulation_output"/"m2f-validation"/(uuid4().hex+" smoke workspace")
    root.mkdir(parents=True)
    report={"environment":{"platform":platform.platform(),"python":platform.python_version(),
        "libraries":{n:importlib.metadata.version(n) for n in ("PyLTSpice","spicelib","numpy")}},"runs":[],"source_preserved":False}
    failures=0
    for key,name,request,doc in cases():
        entry={"fixture":name,"case":key,"analysis":type(request.condition).__name__,"status":"NOT RUN"}
        report["runs"].append(entry)
        try:
            data=chain(name,request=request,doc=doc)
            before_json=ir.dump_document(data["document"]); before_base=data["export_result"].spice_text
            entry.update(source_json_sha256=hashlib.sha256(before_json.encode("utf8")).hexdigest(),
                         base_sha256=hashlib.sha256(before_base.encode("utf8")).hexdigest(),
                         committed_fixture_sha256=original[BASES/name/"circuit.json"])
            sim=run_ltspice_netlist(**data,workspace_root=root,timeout=60)
            entry.update(status=sim.status.value,approval_chain_verified=sim.run.artifact is not None,
                simulator_version=sim.simulator_version,executable=str(sim.executable) if sim.executable else None,
                simulator_exit_code=sim.run.runner_result.return_code if sim.run.runner_result else None,
                raw_present=bool(sim.run.raw_file and sim.run.raw_file.is_file()),
                log_present=bool(sim.run.log_file and sim.run.log_file.is_file()),
                diagnostics=list(sim.diagnostics)+[i.message for i in sim.run.issues],warnings=list(sim.warnings))
            if sim.run.artifact:
                art=sim.run.artifact
                entry.update(artifact_sha256=art.provenance.execution_netlist_sha256,directive=art.directive,
                             trace_map=art.trace_map,working_file=str(sim.run.working_file),raw=str(sim.run.raw_file),log=str(sim.run.log_file))
            if sim.status is not RunStatus.SUCCESS: raise AssertionError(entry["diagnostics"])
            entry.update(traces=list(sim.analysis.available_traces),selected_traces=sim.analysis.selected_traces)
            metrics,checks=comparisons(key,data,sim)
            entry.update(measurements=metrics,comparisons=checks)
            assert all(v["passed"] for v in checks),checks
            assert before_json==ir.dump_document(data["document"])
            assert before_base==data["export_result"].spice_text
            input_folder=sim.run.working_file.parent
            assert (input_folder/"base.cir").read_bytes()==before_base.encode("utf8")
            assert (input_folder/"source.circuit.json").read_bytes()==before_json.encode("utf8")
            assert hashlib.sha256(sim.run.working_file.read_bytes()).hexdigest()==entry["artifact_sha256"]
            entry["source_and_artifact_preserved"]=True
            # Base body independently authored M2C/D golden; source variants only
            # change the explicitly declared V1 row and reviewed snapshot hashes.
            golden=(BASES/name/"expected.cir").read_text(encoding="utf8").splitlines()
            actual=before_base.splitlines()
            mapped=dict(data["export_result"].element_map).get("V1")
            filtered=lambda lines:[v for v in lines if not v.startswith(("* source_sha256","* electrical_sha256")) and not (doc is not None and mapped and v.startswith(mapped+" "))]
            assert filtered(golden)==filtered(actual)
            entry["independent_base_body_equivalence"]=True
            if name in ("nmos_common_source","pmos_resistive_load"):
                # Independently authored equivalent model/device body from M2D.
                # Only header snapshot hashes and the declared gate stimulus
                # differ in the transient/AC test-controller variant.
                authored=list(golden)
                authored[2]="* source_sha256 "+ir.document_digest(data["document"])
                authored[3]="* electrical_sha256 "+ir.electrical_digest(data["document"])
                if doc is not None:
                    bias="2" if name=="nmos_common_source" else "3"
                    for index,line in enumerate(authored):
                        if line.startswith("V_0001 "):
                            authored[index]=f"V_0001 n_0002 0 SINE({bias} 0.01 1000 0 0 0) AC 2 0"
                text="\n".join(authored)+"\n"
                assert text==before_base
                reference_base=replace(data["export_result"],spice_text=text)
                # Review the authored representation and conditions separately;
                # production still verifies these bytes through the exporter.
                rep=ir.make_representation_approval(data["document"],reference_base,data["circuit_approval"],approved=True,model_context=data["model_context"])
                exe=ir.make_execution_approval(data["document"],reference_base,data["circuit_approval"],rep,request,approved=True,model_context=data["model_context"])
                reference_data=dict(data,export_result=reference_base,representation_approval=rep,execution_approval=exe)
                reference=run_ltspice_netlist(**reference_data,workspace_root=root,timeout=60)
                assert reference.status is RunStatus.SUCCESS,reference.diagnostics
                left,right=sim.analysis.result,reference.analysis.result
                a=left.target if hasattr(left,"target") else None
                b=right.target if hasattr(right,"target") else None
                assert a is not None and b is not None and a.shape==b.shape
                assert np.allclose(a,b,rtol=1e-6,atol=1e-8)
                entry["authored_reference_run"]={"status":"PASS","artifact_sha256":reference.run.artifact.provenance.execution_netlist_sha256,
                    "raw":str(reference.run.raw_file),"log":str(reference.run.log_file),"maximum_sample_error":float(np.max(np.abs(a-b))),
                    "rtol":1e-6,"atol":1e-8}
            entry["status"]="PASS"
        except Exception as error:
            failures+=1; entry.update(status="FAIL",failure=str(error))
        print(entry["status"],key,entry.get("measurements",entry.get("failure")),flush=True)
        (root/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=True,allow_nan=False)+"\n",encoding="utf8")
    report["source_preserved"]=all(hashlib.sha256(p.read_bytes()).hexdigest()==value for p,value in original.items())
    if not report["source_preserved"]: failures+=1
    try:
        report["v01_asc_regression"]=verify_asc()
        print("PASS v0.1 public ASC AC/TRAN/DC",report["v01_asc_regression"],flush=True)
    except Exception as error:
        failures+=1; report["v01_asc_regression"]={"status":"FAIL","reason":str(error)}
        print("FAIL v0.1 ASC",str(error),flush=True)
    report["failures"]=failures
    (root/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=True,allow_nan=False)+"\n",encoding="utf8")
    print("Evidence:",root,"source_preserved:",report["source_preserved"],flush=True)
    return 1 if failures else 0


if __name__=="__main__":
    raise SystemExit(main())
