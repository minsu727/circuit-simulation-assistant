# M2G acceptance matrix

Verified locally on 2026-10-09. The [catalog](../../../tests/fixtures/m2_acceptance/catalog.json)
contains 97 independently selected scenarios. The
[acceptance module](../../../tests/test_m2_acceptance.py) runs them through public
APIs, with three additional integrity/authority checks. Existing unit coverage is
referenced below instead of copied wholesale.

## Controlled path and separate authorities

Circuit JSON → strict schema/typed load → fresh deterministic M1 validation →
explicit **CIRCUIT_EXPORT** decision → restricted base export preview → explicit
**REPRESENTATION** decision → typed AnalysisRequest → explicit **EXECUTION**
decision → verified composition → generated-copy runner → contained nonempty
RAW/LOG → approved mode/axis/traces → existing deterministic analysis.

Loading, validation, export, digest verification and composition are deterministic.
The three approval factories require deliberate decisions; fixtures grant these
only inside a test controller. There is no live v0.2 review interface. Technical
VALID is local contract validity, not human approval, model physical accuracy or
simulator compatibility. Export SUCCESS is a preview, not execution permission.
Exit 0 and nonempty files are necessary but do not establish readable/mapped RAW
or successful analysis. Simulator-dependent stages need separately installed
LTspice and remain explicit opt-in.

## Contract coverage

| Area / rule | CI-safe tests and fixtures | Real evidence | Current status |
| --- | --- | --- | --- |
| Strict load / M1 prerequisites | [M1 acceptance](../../../tests/test_circuit_ir_acceptance.py), M1 catalog; M2G circuit gates | All 25 primary runs loaded reviewed JSON snapshots | PASS |
| Circuit approval | M2G `circuit_*`, `decision_circuit`, snapshot/report/context/scope/version stale rows; [approval unit tests](../../../tests/test_circuit_ir_approval.py) | Explicit fixture decisions recorded by M2F harness | PASS; no UI/authentication claim |
| Representation approval | M2G `decision_representation`, `stale_representation_*`, `stale_base_*`; approval unit tests | 25 primary + 6 reference artifact digests/copies | PASS |
| Execution approval | M2G `decision_execution`, `stale_execution_*`, `stale_adapter_version`, AC/TRAN/DC and selection edits; [execution unit tests](../../../tests/test_circuit_ir_execution.py) | Recorded directives and actual RAW modes | PASS |
| All stale/preflight gates | 45 stale + 3 non-VALID + 2 model rows: no artifact, no files, zero injected runner calls; real-entry backend also unreachable | No new fault injection into live simulator | PASS (CI-safe) |
| Restricted exporter / source syntax | 12 existing M2C/D goldens; [exporter unit tests](../../../tests/test_circuit_ir_exporter.py) | Divider, RC, I load, RLC, V/I SINE/PULSE | PASS |
| Sealed MOS profiles | Shared/mixed/NMOS/PMOS goldens, unknown/polarity rejection; [profile tests](../../../tests/test_circuit_ir_model_profiles.py) | NMOS/PMOS DC/AC/TRAN + 6 reference runs | PASS; Level-1 demo only |
| Injection / unsupported input | 9 command/path rows; exporter tests for labels as data, ID/value/model injections and unsupported features | No external model/library runs | PASS (fail closed); external libraries NOT RUN/unsupported |
| Exact bytes / deterministic maps | 12 base + 5 execution goldens; repeated export/composition; existing hash-seed/cwd tests | Base/source/execution digests and preserved copy bytes rechecked | PASS; goldens unchanged |
| Generated-copy orchestration | 5 execution rows, exactly one fake call; [runner tests](../../../tests/test_netlist_runner.py) for containment/collisions/tampering | 25 primary + 6 reference contained outputs | PASS |
| Launch/discovery/timeout/fatal LOG | [M2F tests](../../../tests/test_netlist_ltspice.py): invalid executable, copy gate, timeout, nonzero, absent/outside files, fatal LOG | Recorded exit 0/version + actual model advisories | PASS; faults are mock tests, not live timeout trials |
| RAW / mapped result handoff | M2G 7 fault + 3 analysis rows; M2F ASCII/binary lazy-axis, domain/shape/stepped/ambiguous/missing-trace tests | 34 retained RAW/LOG pairs actually re-read | PASS; initial axis failure retained |
| AC / TRAN / DC algorithms | M2G synthetic mapped samples with non-unit reference and selected DC point; unchanged v0.1 tests | 25 primary M2 runs + 3 ASC modes | PASS; no new numerical algorithm |
| Current sign / mapping | M2F exact R/C/L/V/I mapping guard, signed synthetic V current, unsupported MOS current rejection | Signed V-source/I-source observations; MOS load uses I(R), not guessed Id | PASS within documented probe subset |
| Source preservation | Acceptance fixture-byte snapshot; fake source/base files retained; existing success/failure hash tests | 25 source/base/execution copies, committed JSON hashes, public ASC source hash rechecked | PASS |
| v0.1 regression | Entire existing suite; existing ASC/analysis/Summary/launcher tests unchanged | Three public ASC AC/TRAN/DC smoke outputs re-read | PASS; ASC path not rewritten |
| Dependency / public scope | Existing requirements/CI unchanged; `pip check` | Windows-only existing library environment | PASS locally; broader portability not certified |

## Actual real-run coverage

The [sanitized inventory](real-run-evidence.json) records each run's fixture,
analysis, measured facts, declared expected/theoretical comparisons and
tolerances, RAW/LOG relative references, sizes and SHA-256. M2G re-read files and
recomputed measurements using the existing analyzers without launching LTspice.
Ignored referenced files are local retained evidence, not shipped fixtures.

**10 primary fixture families / 25 primary cases / 6 MOS references / 3 ASC
regressions = 34 successful real simulator runs in the final M2F sequence.**
These are distinct from 100 M2G CI-safe tests and from the 12 exporter goldens.

| Family | Actual primary modes | Representative observed result | Comparison / tolerance |
| --- | --- | --- | --- |
| Divider | DC, AC | 3 V → 2 V; -3.521825 dB | Ratio 2/3, 0.5% |
| RC | AC, TRAN | -0.021048 dB; BW 159.540182 Hz; transient gain 0.157285 V/V | Complex H maximum error 3.38e-16, limit 1e-5; BW 1%; periodic gain 2% |
| Current source / resistor | DC | +1 mA source → -1 V | V=-IR, 0.5% |
| RLC | DC, TRAN | 1 V → 1 V; gain 0.871254 V/V | Ideal DC / analytic 1 kHz transfer, 0.5% / 2% |
| SINE voltage | AC, TRAN, DC | Source AC 2 V; output 19.999962 mVpp; DC point 1 V | Complex error ≤1e-6; Vpp 1%; point 0.5% |
| SINE current | AC, TRAN, DC | AC node -2000 V; 19.999962 Vpp; DC point -1 V | Signed source/load relation; same declared tolerances |
| PULSE voltage | AC, TRAN, DC | 2 Vpp; initial -1 V; DC point 1 V | Vpp 1%; initial absolute 1e-6; AC/DC as above |
| PULSE current | AC, TRAN, DC | 2000 Vpp; initial +1000 V; DC point -1 V | Mathematical ideal load; same tolerances |
| NMOS | DC, AC, TRAN | Output 4.455446 V at gate 2 V; AC 0.654999 dB; transient gain 1.078321 V/V | Bias/load Level-1 equation 1%; finite inverted AC; same-simulator reference |
| PMOS | DC, AC, TRAN | Output 0.544554 V at gate 3 V; AC 0.654999 dB; transient gain 1.078324 V/V | Mirrored Level-1 bias 1%; same-simulator reference |

NMOS/PMOS each have three additional independently authored device/model-body
reference runs; all target samples matched with max difference 0 at
`rtol=1e-6, atol=1e-8`. This checks text/model equivalence on the **same simulator**,
not independent physics/hardware validation. MOS AC/transient checks establish
finite/inverted output and equivalent samples; they do not assert PDK accuracy.

Public ASC evidence: AC 12.943483 dB / 8255.964075 Hz; transient Input Vpp
9.999752 mV, Output Vpp 44.057846 mV, gain 4.405894 V/V; DC output at gate 2 V
7.692307 V. These are finite-result/source-preserving regression smoke checks,
without a new theoretical tolerance claim.

Untested family/mode combinations (such as divider TRAN, RC DC, RLC AC and
current-load AC/TRAN) are **NOT RUN in this M2F sequence**, rather than inferred
PASS from another fixture. Shared/mixed MOS fixtures have CI export coverage,
not live simulation coverage here.

## Numerical and evidence limits

- RC uses the unchanged initial-sample median baseline and -3.000 dB crossing
  algorithm. The harness compares against 158.777482 Hz for -3.000 dB from zero
  baseline, with 1% tolerance; exact half-power corner is 159.154943 Hz. Sweep
  baseline at 10 Hz and interpolation explain why these are distinct references.
- RC transient steady-cycle Output Vpp is 3.145695 mV; whole-record swing is
  4.116416 mV including startup. They are deliberately different measurements.
- Capacitor-free MOS and constant transfer fixtures have no bandwidth crossing.
  PULSE stable-cycle gain is unavailable under existing eligibility rules.
  Neither missing metric is fabricated.
- Voltage-source positive current is into its positive terminal; independent
  current-source positive current is positive-to-negative. Divider supply at
  5 V was -1.666667 mA, current load at +1 mA was +1.000000 mA. No sign inversion
  is applied. Verified observations are source/load probes; no universal MOS
  current-probe convention is claimed.
- First M2F sequence: 25 analysis failures after RAW/LOG creation
  (`This RAW file does not have an axis.`). The binary lazy-axis fix and synthetic
  binary regression preceded final success. A later successful sequence lacked
  structured model-advisory capture; the final report records the actual
  `Length shorter than recommended` advisories. History is in the inventory.
- Environment: Windows 11 build 26200, Python 3.13.5, LTspice 26.0.1,
  PyLTSpice 6.0.1, spicelib 1.6.3, NumPy 2.5.3. No clean-VM or multi-version
  validation. Required returned file pairs were checked individually; auxiliary
  .op RAW and executable logs do not increase the simulation-run count.

See [M2 status](status.md) for closure criteria, exact suite totals, hosted CI
scope and deferred milestones, and [M2F validation](real-ltspice-validation.md)
for the separate opt-in reproduction command.
