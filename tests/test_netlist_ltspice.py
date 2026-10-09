"""Level A only: no live subprocess, simulator, network or external model files."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import unittest
from unittest.mock import patch

import numpy as np
import circuit_ir as ir
import netlist_runner as nr
import netlist_result_analysis as na
from tests.m2e_helpers import chain


class SampleRaw:
    """Explicit synthetic samples, never advertised as real simulator output."""
    def __init__(self, mode="ac", missing=False):
        self.mode, self.flags = mode, "complex" if mode == "ac" else "real"
        self.axis = np.geomspace(10, 1e6, 601) if mode == "ac" else np.linspace(0, .01, 1001) if mode == "tran" else np.linspace(0, 5, 11)
        self.names = [{"ac": "frequency", "tran": "time", "dc": "V(v-sweep)"}[mode], "V(n_0001)", "V(n_0002)", "I(V_0001)"]
        ref = np.full(len(self.axis), 2+0j) if mode == "ac" else .01*np.sin(2*np.pi*1000*self.axis) if mode == "tran" else self.axis
        out = ref/(1+1j*self.axis/159.154943) if mode == "ac" else ref*2 if mode == "tran" else ref*2/3
        self.waves = dict(zip(self.names, (self.axis, ref, out, -self.axis/3000)))
        if missing:
            self.names.remove("V(n_0002)")
    def get_trace_names(self):
        return self.names
    def get_axis(self):
        return self.axis
    def get_raw_property(self, key=None):
        data = {"Plotname": {"ac": "AC Analysis", "tran": "Transient Analysis", "dc": "DC transfer characteristic"}[self.mode], "Flags": self.flags, "Offset": 0}
        return data if key is None else data[key]
    def get_trace(self, name):
        if isinstance(name,int):
            return SimpleNamespace(get_wave=lambda: self.axis)
        return SimpleNamespace(get_wave=lambda: self.waves[name])


def case(mode="ac"):
    request = (ir.AnalysisRequest(ir.ACCondition(ir.ACSweep.DECADE,100,"10","1000000"), "vout", "vin") if mode == "ac"
               else ir.AnalysisRequest(ir.TransientCondition("0.01", maximum_timestep="0.00001"), "vout", "vin", measurements=("Voltage Gain", "Output Swing")) if mode == "tran"
               else ir.AnalysisRequest(ir.DCCondition("V1","0","5","0.5"), "vout", requested_point="3", measurements=("Minimum","Maximum","Value at Sweep Point")))
    data = chain(request=request)
    artifact = ir.compose_execution_netlist(**data).artifact
    return data, artifact


class AnalysisMappingTests(unittest.TestCase):
    def read(self, mode="ac", raw=None):
        data, artifact = case(mode)
        with patch.object(na, "RawRead", return_value=raw or SampleRaw(mode)):
            return na.read_netlist_analysis(Path("test.raw"), artifact, data["request"])
    def test_ac_reuses_transfer_algorithm_nonunit_reference(self):
        value = self.read().result
        self.assertAlmostEqual(value.bandwidth_hz,159.154943,delta=1)
        self.assertEqual(abs(value.reference[0]),2)
    def test_transient_reuses_vpp_gain(self):
        values = self.read("tran").result.measurements["Voltage Gain"].values
        self.assertAlmostEqual(values["Voltage Gain"][0],2,places=6)
        self.assertAlmostEqual(values["Input Vpp"][0],.02,delta=.0001)
    def test_dc_reuses_point_interpolation(self):
        self.assertAlmostEqual(self.read("dc").result.point_value,2)
    def test_missing_trace_has_actual_inventory(self):
        with self.assertRaises(na.MissingTraceError) as caught:
            self.read(raw=SampleRaw(missing=True))
        self.assertEqual(caught.exception.missing,["V(n_0002)"])
        self.assertIn("V(n_0001)",caught.exception.available)
    def test_ground_not_manufactured(self):
        data, art = case()
        art = replace(art, trace_map=(("target_net","n0","V(0)"),)+art.trace_map[1:])
        with patch.object(na,"RawRead",return_value=SampleRaw()), self.assertRaises(na.MissingTraceError):
            na.read_netlist_analysis("test.raw",art,data["request"])
    def test_wrong_mode(self):
        with self.assertRaisesRegex(ValueError,"mode"):
            self.read(raw=SampleRaw("dc"))
    def test_request_mode_mismatch(self):
        data, art = case()
        with self.assertRaisesRegex(ValueError,"modes"):
            na.read_netlist_analysis("unused",art,case("dc")[0]["request"])
    def test_stepped_raw_rejected(self):
        raw = SampleRaw(); raw.flags += " stepped"
        with self.assertRaisesRegex(ValueError,"Stepped"):
            self.read(raw=raw)
    def test_duplicate_trace_names_rejected(self):
        raw=SampleRaw(); raw.names.append("v(N_0001)")
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            self.read(raw=raw)
    def test_nonfinite_nonmonotonic_and_bad_shape(self):
        for variant in ("nan","order","shape"):
            raw=SampleRaw()
            if variant=="nan": raw.waves["V(n_0002)"][0]=np.nan
            elif variant=="order": raw.axis[1]=raw.axis[0]
            else: raw.waves["V(n_0002)"]=np.zeros(3)
            with self.subTest(variant=variant), self.assertRaises(ValueError): self.read(raw=raw)
    def test_axis_name_and_domain(self):
        for variant in ("name","negative","complex"):
            raw=SampleRaw()
            if variant=="name": raw.names[0]="time"
            elif variant=="negative": raw.axis[0]=-1
            else: raw.axis=raw.axis.astype(complex)+1j
            with self.subTest(variant=variant), self.assertRaises(ValueError): self.read(raw=raw)
    def test_transient_offset(self):
        raw=SampleRaw("tran")
        original=raw.get_raw_property
        raw.get_raw_property=lambda key=None: dict(original(),Offset=.02) if key is None else original(key)
        self.assertAlmostEqual(self.read("tran",raw).result.time[0],.02)
    def test_current_signed_and_exact_mapping(self):
        data,art=case("dc")
        with patch.object(na,"RawRead",return_value=SampleRaw("dc")):
            axis,values,name=na.read_generated_current("test.raw",art,data["export_result"],"V1")
        self.assertEqual(name,"I(V_0001)")
        self.assertAlmostEqual(values[-1],-5/3000)
    def test_current_unknown_mos_and_tampered_mapping(self):
        data,art=case("dc")
        for identity,base in (("unknown",data["export_result"]),("V1",replace(data["export_result"],element_map=(("V1","V_9999"),)))):
            with self.subTest(identity=identity), self.assertRaises(ValueError): na.read_generated_current("unused",art,base,identity)
        mos=chain("nmos_common_source",request=ir.AnalysisRequest(ir.DCCondition("V1","0","5","0.1"),"vout"))
        art=ir.compose_execution_netlist(**mos).artifact
        with self.assertRaisesRegex(ValueError,"unsupported"):
            na.read_generated_current("unused",art,mos["export_result"],"M1")
    def test_current_missing_not_guessed(self):
        data,art=case("dc"); raw=SampleRaw("dc"); raw.names.remove("I(V_0001)")
        with patch.object(na,"RawRead",return_value=raw),self.assertRaises(na.MissingTraceError):
            na.read_generated_current("test.raw",art,data["export_result"],"V1")
    def test_actual_rawread_on_synthetic_ascii_temp_data(self):
        data,art=case("dc")
        text=("Title: repository-owned synthetic CI data, not LTspice evidence\nDate: test\nPlotname: DC transfer characteristic\nFlags: real\nNo. Variables: 3\nNo. Points: 3\nOffset: 0\nVariables:\n\t0\tV(v-sweep)\tvoltage\n\t1\tV(n_0001)\tvoltage\n\t2\tV(n_0002)\tvoltage\nValues:\n0\t0\n\t0\n\t0\n1\t3\n\t3\n\t2\n2\t5\n\t5\n\t3.333333333333333\n")
        with TemporaryDirectory() as temp:
            path=Path(temp)/"synthetic.raw"; path.write_text(text,encoding="utf8")
            result=na.read_netlist_analysis(path,art,data["request"])
        self.assertEqual(result.result.point_value,2)
    def test_actual_binary_raw_lazy_axis_regression(self):
        import struct
        data,art=case("dc")
        header=("Title: repository-owned synthetic binary CI data\nDate: test\nPlotname: DC transfer characteristic\nFlags: real\nNo. Variables: 3\nNo. Points: 3\nOffset: 0\nVariables:\n\t0\tV(v-sweep)\tvoltage\n\t1\tV(n_0001)\tvoltage\n\t2\tV(n_0002)\tvoltage\nBinary:\n")
        body=b"".join(struct.pack("<dff",x,x,x*2/3) for x in (0,3,5))
        with TemporaryDirectory() as temp:
            path=Path(temp)/"synthetic.raw"; path.write_bytes(header.encode("utf-16-le")+body)
            result=na.read_netlist_analysis(path,art,data["request"])
        self.assertEqual(result.result.point_value,2)


class RealBoundaryTests(unittest.TestCase):
    def test_all_stale_chain_gates_before_real_backend(self):
        data,_=case()
        variants=[dict(data,circuit_approval=replace(data["circuit_approval"],approved=False)),
            dict(data,representation_approval=replace(data["representation_approval"],base_netlist_sha256="0"*64)),
            dict(data,execution_approval=replace(data["execution_approval"],request_sha256="0"*64)),
            dict(data,export_result=replace(data["export_result"],spice_text=data["export_result"].spice_text+"\n")),
            dict(data,request=replace(data["request"],condition=ir.ACCondition(ir.ACSweep.DECADE,100,"10","2000000")))]
        with patch.object(nr,"_LTspiceRunner") as backend,patch.object(Path,"mkdir") as mkdir:
            for variant in variants:
                with self.subTest(variant=list(variant)), TemporaryDirectory() as temp:
                    result=nr.run_ltspice_netlist(**variant,workspace_root=Path(temp))
                    self.assertEqual(result.status,nr.RunStatus.BLOCKED)
            backend.assert_not_called(); mkdir.assert_not_called()
    def test_missing_and_bad_executable_config(self):
        import os
        data,_=case()
        for setting in (None,"not-an-absolute-executable"):
            with TemporaryDirectory() as temp, patch.dict(os.environ,{"LTSPICE_EXECUTABLE":setting or ""}),patch("runtime_paths.locate_ltspice",return_value=None),patch("PyLTSpice.SimRunner") as sim:
                result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
                self.assertEqual(result.status,nr.RunStatus.FAILED); sim.assert_not_called()
    def test_invalid_timeout_blocks_before_io(self):
        data,_=case()
        for value in (0,-1,float("nan"),True,"60"):
            with patch.object(Path,"mkdir") as mkdir:
                self.assertEqual(nr.run_ltspice_netlist(**data,timeout=value).status,nr.RunStatus.BLOCKED)
                mkdir.assert_not_called()
    def test_input_copy_mismatch_no_simrunner(self):
        _,art=case()
        with TemporaryDirectory() as temp,patch("PyLTSpice.SimRunner") as sim:
            p=Path(temp)/"execution.cir"; p.write_bytes(art.netlist_bytes+b"\n")
            with self.assertRaisesRegex(ValueError,"digest"): nr._LTspiceRunner(art,1).run(p,Path(temp))
            sim.assert_not_called()
    def test_backend_errors_timeout_nonzero_and_missing_outputs(self):
        data,_=case()
        for mode in ("exception","timeout","exit1","raw_missing","log_missing","outside","copy_mismatch","bad_log"):
            with self.subTest(mode=mode),TemporaryDirectory() as temp,patch("runtime_paths.locate_ltspice",return_value=Path(temp)/"LTspice.exe"),patch("PyLTSpice.LTspice.create_from") as create,patch("PyLTSpice.SimRunner") as sim:
                create.return_value=object()
                def run(path,**kwargs):
                    out=Path(sim.call_args.kwargs["output_folder"]); copy=out/"execution.cir"; copy.write_bytes(path.read_bytes())
                    if mode=="exception": raise OSError("launch failed")
                    if mode=="copy_mismatch": copy.write_bytes(b"tampered")
                    raw,log=out/"execution.raw",out/"execution.log"
                    if mode!="raw_missing": raw.write_bytes(b"synthetic sentinel")
                    if mode!="log_missing": log.write_bytes(b"Fatal error: test only" if mode=="bad_log" else b"LTspice test-only\n")
                    if mode=="outside": raw=Path(temp)/"external.raw"
                    return raw,log
                sim.return_value.run_now.side_effect=run
                sim.return_value.completed_tasks=[SimpleNamespace(retcode=1 if mode=="exit1" else -2 if mode=="timeout" else 0,exception_text="TimeoutExpired" if mode=="timeout" else "",is_alive=lambda:False)]
                sim.return_value.okSim=0 if mode in ("exit1","timeout") else 1
                result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
                self.assertEqual(result.status,nr.RunStatus.FAILED)
                self.assertIsNone(result.analysis)
    def test_corrupt_wrong_mode_and_missing_trace_fail_overall(self):
        from tests.test_netlist_runner import FakeRunner
        data,_=case()
        for raw in (None,SampleRaw("dc"),SampleRaw(missing=True)):
            with TemporaryDirectory() as temp,patch.object(nr._LTspiceRunner,"run",new=lambda self,p,o: FakeRunner().run(p,o)):
                if raw is None:
                    result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
                else:
                    with patch.object(na,"RawRead",return_value=raw): result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
                self.assertEqual(result.run.status,nr.RunStatus.SUCCESS)
                self.assertEqual(result.status,nr.RunStatus.FAILED)
                self.assertTrue(result.diagnostics)
    def test_valid_synthetic_result_is_not_claimed_real(self):
        from tests.test_netlist_runner import FakeRunner
        data,_=case()
        with TemporaryDirectory() as temp,patch.object(nr._LTspiceRunner,"run",new=lambda self,p,o: FakeRunner().run(p,o)),patch.object(na,"RawRead",return_value=SampleRaw()):
            result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
            self.assertEqual(result.status,nr.RunStatus.SUCCESS)
            self.assertIsNone(result.executable)
    def test_verified_second_copy_gate_precedes_simulator(self):
        data,_=case()
        attempts=[]
        with TemporaryDirectory() as temp,patch("runtime_paths.locate_ltspice",return_value=Path(temp)/"LTspice.exe"),patch("PyLTSpice.LTspice.create_from",new=classmethod(lambda cls,path:cls)),patch("PyLTSpice.SimRunner") as sim,patch("PyLTSpice.LTspice.run") as launch:
            def run(path,**kwargs):
                out=Path(sim.call_args.kwargs["output_folder"]); copy=out/"execution.cir"; copy.write_bytes(path.read_bytes()+b"\n")
                simulator=sim.call_args.kwargs["simulator"]
                attempts.append(copy)
                simulator.run(copy)
            sim.return_value.run_now.side_effect=run
            result=nr.run_ltspice_netlist(**data,workspace_root=Path(temp))
            self.assertEqual(result.status,nr.RunStatus.FAILED); launch.assert_not_called()
            self.assertEqual(len(attempts),1)
    def test_log_decoding(self):
        with TemporaryDirectory() as temp:
            p=Path(temp)/"result.log"
            for encoding in ("utf8","utf-16","utf-16-le"):
                p.write_bytes("LTspice test\nWarning: test-only\n".encode(encoding))
                self.assertIn("Warning",nr._read_log(p))
    def test_actual_model_advisory_without_warning_prefix(self):
        text='LTspice 26.0.1\nInstance "M_0001": Length shorter than recommended for a level 1 MOSFET.\nTotal elapsed time: 0.1 seconds.\n'
        self.assertEqual(nr._log_warnings(text),(text.splitlines()[1],))
    def test_no_path_or_approval_shortcut_in_high_level_api(self):
        import inspect
        args=inspect.signature(nr.run_ltspice_netlist).parameters
        self.assertNotIn("netlist_path",args); self.assertNotIn("approved",args)


if __name__ == "__main__":
    unittest.main()
