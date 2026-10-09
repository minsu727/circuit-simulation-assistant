# M2F — Real LTspice Validation

This documents local simulator evidence, separate from CI mocks and exact-byte
export goldens. It adds no Streamlit workflow, image extraction or new analysis
algorithm. The M2E committed baseline was `23952ab`; its preceding CI was green.

## Reproduce

Use Windows, separately installed LTspice, Python and the existing manifests:

```powershell
python -m pip install -r requirements-test.txt
python -X utf8 -m unittest discover -s tests -p "test_*.py"
python -m pip check
git diff --check
python -X utf8 tests/verify_netlist_integration.py --real-ltspice
```

The actual local command used `.venv\Scripts\python.exe` instead of `python`.
Without `--real-ltspice`, the verification script exits without executing a
simulator. Default unittest discovery does not run this script. No API key,
network access, private schematic, external PDK or downloaded model is needed.

Discovery reuses `runtime_paths.locate_ltspice`: trusted `LTSPICE_EXECUTABLE`
environment configuration, normal Windows installation directories, then PATH.
An explicitly invalid configured path does not silently fall back. Circuit JSON
cannot select an executable. Missing LTspice produces a failure diagnostic.

Evidence is retained under ignored `simulation_output/m2f-validation/<run-id>`.
The verification workspace includes spaces. Each M2 run gets the M2E unique
`simulation_input/<id>/m2` and `simulation_output/<id>` directories. `report.json`
contains source/base/execution hashes, conditions, actual mappings/traces,
simulator status/version, RAW/LOG references, comparisons and preservation
results. Local absolute paths stay in ignored evidence, not this document.
The three v0.1 ASC outputs use its existing ignored project runtime directories.

## Execution and analysis boundaries

`netlist_runner.run_ltspice_netlist` requires the document, ExportResult,
circuit/representation approvals, typed AnalysisRequest and ExecutionApproval.
It has no raw `.cir` path or unbound `approved=True` shortcut. It composes and
verifies the complete chain before I/O, then delegates to the M2E copy adapter.
Production never creates or renews approvals. The verification controller makes
explicit decisions only for repository-owned fixtures; this is not a user study
or authentication system.

The private real backend uses public `SimRunner.run_now(Path, ...)`, with a
per-run LTspice subclass configured from a Path. SimRunner copies text bytes;
feeding an editor would reserialize with platform newline handling. The subclass
checks the output execution copy's exact bytes/SHA-256 immediately before the
library invokes LTspice with `-Run -b`, an argument list and no shell. It does not
modify the shared v0.1 LTspice class. The selected executable/version is retained.

Success requires completed task, exit 0, `okSim == 1`, exact copied bytes,
expected contained nonempty RAW/LOG, a readable LOG, the approved RAW mode,
valid axis/samples and actual selected traces. Process/file success is retained
separately from analysis success; a corrupt RAW, missing trace or wrong mode
returns overall FAILED. The public result's `status` is the final status.
Timeout uses the library's owned `subprocess.run` timeout; no broad process kill,
system setting change or user-directory cleanup is performed.

`netlist_result_analysis` translates exact reviewed net IDs through the verified
artifact trace map and delegates to existing `analyze_ac`, `analyze_transient`
and `analyze_dc`. It checks transient saving Offset and binary RAW lazy loading.
No analysis equations or tolerances were added to production calculations.

Current observations resolve exact component IDs through the approved element
map. Only two-terminal R/C/L/V/I probes are admitted. Voltage-source current is
into the positive terminal; independent current-source positive current flows
positive to negative. Values are returned without negation. Unknown/absent traces
report the actual inventory; no labels or similar names substitute for them.
An omitted `V(0)` is reported missing, not replaced with synthetic zero samples.
MOS Id/Is/Ig conventions remain unsupported; MOS load current uses mapped `I(R)`.

## Actual environment and results

Verified 2026-10-09 (Asia/Seoul): Windows 11 build 26200, Python 3.13.5,
LTspice 26.0.1, PyLTSpice 6.0.1, spicelib 1.6.3, NumPy 2.5.3.
The existing requirements already pin these library versions; the older M2A
inspection's statement that they were unpinned is historical, not current.

All 25 primary M2 cases below passed actual execution, RAW/LOG reading and
declared comparisons. Six additional NMOS/PMOS DC/AC/Transient reference runs
also passed, as did three actual v0.1 public ASC runs: 34 successful simulator
runs in the final smoke sequence. The reference uses independently authored M2D
model/device golden rows with only explicit gate stimulus/snapshot-header edits;
it receives representation and execution decisions and the same production
verification gates. Sample comparison tolerance is `rtol=1e-6, atol=1e-8`;
observed maximum difference was zero. This is text/model equivalence and local
repeatability, not independent simulator or hardware validation.

| Fixture | Actual modes | Representative measurement | Comparison / tolerance |
| --- | --- | --- | --- |
| Resistor divider, 1 kΩ / 2 kΩ | DC, AC | Output at 3 V: 2.000000 V; AC gain -3.521825 dB | Ratio 2/3; 0.5% relative |
| RC, 1 kΩ / 1 µF | AC, Transient | Gain -0.021048 dB; BW 159.540182 Hz; 1 kHz transient gain 0.157285 V/V | AC transfer `1/(1+j2πfRC)`, max error 3.38e-16 (limit 1e-5); bandwidth 1%; transient 2% |
| Current source / 1 kΩ | DC | +1 mA source gives -1.000000 V; observed source current +1.000000 mA | `V=-IR`; 0.5% |
| RLC, 1 mH / 100 Ω / 1 µF | DC, Transient | DC output at 1 V: 1 V; 1 kHz gain 0.871254 V/V | Ideal inductor DC short; `1/abs(1-ω²LC+jωRC)` = 0.871251; 2% |
| SINE voltage, 10 mV peak / 1 kHz | AC, Transient, DC | AC magnitude 2 V; transient Vpp 19.999962 mV; same-node voltage gain 1; DC point 1 V | Complex AC error ≤1e-6; waveform error ≤max(1e-6, Vpp×0.001); Vpp 1% |
| SINE current, 10 mA peak / 1 kHz / 1 kΩ | AC, Transient, DC | AC node -2000 V; transient Vpp 19.999962 V; DC point -1 V | Same source conventions and declared tolerances |
| PULSE voltage, -1 to +1 V | AC, Transient, DC | AC magnitude 2 V; transient Vpp 2 V; initial -1 V; DC point 1 V | Vpp 1%; initial absolute 1e-6; AC/DC as above |
| PULSE current, -1 to +1 A / 1 kΩ | AC, Transient, DC | AC node -2000 V; transient Vpp 2000 V; initial +1000 V; DC point -1 V | Ideal mathematical load; source sign/initial level checked |
| NMOS common source | DC, AC, Transient | Gate 2 V: output 4.455446 V, load 0.544554 mA; AC gain 0.654999 dB; transient 1.078321 V/V | Level-1/resistor bias equation, 1%; finite inverted AC; reference run |
| PMOS resistive load | DC, AC, Transient | Gate 3 V: output 0.544554 V, load 0.544554 mA; AC gain 0.654999 dB; transient 1.078324 V/V | Polarity-consistent mirrored bias equation, 1%; reference run |

The RC source fixture originally has AC magnitude zero. The test controller
creates a new reviewed snapshot with AC magnitude 2 and phase -45°, retaining
the original JSON. RC/RLC/MOS transient snapshots explicitly add a 10 mV,
1 kHz gate/source sine with offset equal to existing DC. No existing fixture,
golden or exporter restriction is changed. V/I SINE/PULSE fixtures are unchanged.
All AC runs use `.ac dec 100 10 1Meg`; M2 transient uses `.tran 0 10m 0 1u`.
Voltage DC is 0–5 V in 0.1 V steps; current DC is -1–+1 mA in 0.1 mA steps.

RC half-power corner is 159.154943 Hz. The existing algorithm uses the first-ten
sample median and baseline minus exactly 3.000 dB, not exact half power. Its
zero-baseline theoretical crossing is 158.777482 Hz; the finite-frequency
baseline explains the small difference to 159.540182 Hz, within declared 1%.
No algorithm was changed. Transient gain uses stable recent cycles, not the
startup-inclusive Output Swing Vpp. PULSE gain was correctly unavailable for
these narrow low-duty intervals under the conservative existing cycle criteria;
Vpp/initial levels passed and the reason is preserved. No gain is fabricated.

NMOS/PMOS `.model LEVEL=1`, D/G/S/B order, W/L and generated underscore names
were accepted. Both LOGs advise `Length shorter than recommended for a level 1
MOSFET`; this is retained as a warning even without a `Warning:` prefix.
No bandwidth crossing was found for the capacitance-free MOS fixtures; the
result remains unavailable. `Rser=0` was accepted in both RLC modes. This does
not validate all RLC dynamics or process-accurate semiconductor behavior.

Existing [public ASC](../../../examples/common_source_amplifier/README.md)
ran through unchanged `simulation_runner.run_ltspice`: AC 12.943483 dB /
8255.964075 Hz; transient Input Vpp 9.999752 mV, Output Vpp 44.057846 mV,
gain 4.405894 V/V; DC output at gate 2 V: 7.692307 V. The source SHA-256 stayed
`5736eb12ba0e4526381c89eb67a99d00150739c13d29954eeba2aa6c6e2338af`.

## Failure history and remaining limits

The first real sequence generated RAW/LOG but all 25 analysis handoffs failed
with `This RAW file does not have an axis.` Binary RAW's axis had not been lazily
loaded before `get_axis()`. Inspecting the actual installed reader and retained
RAW proved the cause. The adapter now explicitly reads `get_trace(0).get_wave()`;
an independent synthetic binary RAW test covers the failure missed by ASCII
and mocks. Original failure evidence remains ignored and preserved. Source
hashes were unchanged on both failed and successful sequences.

Default CI tests cover missing/invalid discovery, stale approvals, source/copy
tampering, launch exception, timeout/nonzero status, missing/outside outputs,
corrupt RAW, wrong mode, missing/ambiguous traces and current mapping/sign. These
are mocked/synthetic cases, not claims of live timeout/error fault injection.
Whole-source hashes and M2C/D/E goldens remain unchanged. No new dependency,
packaging, installer, release, root README, UI or v0.1 algorithm change is needed.

Final Level A verification: 28 M2F tests passed; full repository suite 748 tests,
0 failures/errors/skips, exit 0 (108.569 seconds). Focused M2E adapter/composition
regressions also passed. `pip check` reported no broken requirements and
`git diff --check` passed. These counts exclude the opt-in real simulator runs.

This is one local Windows/simulator version, not clean-Windows-VM validation,
cross-version certification, physical circuit validation or image fidelity.
Unsupported device-current probes, arbitrary models/includes, analysis modes,
IR parameter sweeps and UI remain unavailable. Filesystem link checks do not
guarantee safety against a privileged concurrent filesystem attacker. Model
advisories and measurement-unavailable results are not silently hidden.
M2G still owns the complete acceptance catalog/matrix and formal M2 closure.
