# M2 Test Plan — Proposed / No M2 Tests Run

The M1 baseline is **482 passing repository tests**, not an M2 test result. M2A creates no executable test or circuit asset. Future implementation uses existing unittest/stdlib plus the already declared IR/PyLTSpice test environment; no network, API key, model-library installation or LTspice requirement for unit tests. Real simulator checks are separate opt-in evidence.

## Fixture Organization and Independence

Proposed distinct root, avoiding M1's complete inventory assertions:

```text
tests/fixtures/spice_export/<case>/
  circuit.json
  expected-export.json
  expected.cir          # success only, static complete base text
  provenance.md        # authored purpose, profile/conditions, optional real-run recipe
```

Do not put M2 pairs under `tests/fixtures/circuit_ir/`: the existing M1 acceptance test treats all its case directories as catalog/supplemental inventory. Preserve every M1 fixture/expected byte. Reuse those fixtures read-only as negative/reference inputs when useful, but create M2-specific edited copies in the new root.

Author Circuit JSON topology, role/name mapping, source/model rows and expected issues independently from exporter results. Static success goldens include title, all rows, allowed model declarations, `.end`, LF and final newline. Independently compute fixed header digests from reviewed source/projection definitions with transparent stdlib hashing; do not run the exporter to bless expected text. Approval fixtures are created only by explicit test review actions against those documents, never imported reviewed flags. Provide no snapshot-update mode; hash source/expected files before/after and prohibit golden writes during tests. Failure expected files contain no `.cir` or partial maps.

No numerical gain/current value is an exporter golden. Formula/RAW metrics belong to M2F and existing deterministic analyzers. Case counts are actual future results, not a target invented from this table.

## Required Scenario Groups

| Area | Minimum planned scenarios / assertions |
| --- | --- |
| Digest snapshot | Match independently computed dump UTF-8/LF SHA; raw JSON whitespace/key order equivalence; literal/provenance/imported finding and same-revision changes invalidate; schema/version/revision remain bound |
| Electrical projection | Explicit schema/catalog/component/pin/net/connection/label fields; sorted arrays; exact SI equality; no geometry/confidence/report influence; electrical equality alone cannot preserve full-snapshot approval |
| Report/envelope | Current VALID report and warning set; exact profile/ruleset/projection; missing/false/wrong-scope/version envelope; stale report or content despite same revision; no approval from archival reviewed status; constructor shape versus consuming gate |
| Positive devices | Explicit resistor/source divider; RC low-pass; resistively loaded I source; RLC with fixed Rser=0; no component omissions and correct a/b or polarity mapping |
| Positive sources | V and I: DC, explicit zero/signed DC, AC magnitude/phase including 0; SINE and PULSE exact field/unit order; matching dc/initial value; exact timing equality; NONE has no waveform fields |
| MOS positive | Separately authored NMOS common-source and PMOS resistively referenced drain; explicit D/G/S/B and W/L; exact trusted model selection; multiple uses share one declaration |
| M1 refusal | INVALID, AMBIGUOUS and UNVALIDATED/incomplete reports; strict shape rejection before graph; no unsupported UNKNOWN/device loss; ERROR not overridden by approved=true |
| M2 restrictions | Image-origin/reference admission denied; extra MOS/passive/source parameters; waveform dc/initial mismatch; selected value/SI inconsistency; unrepresentable numeric token; wrong polarity/unrecognized/missing model registry profile |
| Warning policy | Acknowledged LABEL_ALIAS and resolved unused wire stub may coexist with complete mapping; missing acknowledgements block; conditional nonlinear reference, redundant ideal source, passive bypass and dynamic deferral block; unknown warning/deferral fails closed |
| Injection | Newlines/CR/NUL, braces/semicolon/continuation/directive tokens in token-bearing fields; raw include/lib/model/step/param/path/source text; labels/candidates/visual text stay data and never appear as SPICE comments; malformed IDs/model refs reject, while legal opaque ID punctuation is mapped safely |
| Numbers | M/m vs Meg, exponent/sign/zero, long coefficients under reduced Decimal precision; fixed/scientific cutoffs -3 and 6; exponent ±300 and token 128 bounds; no float conversion/rounding/unit suffix emission |
| Names and roles | Safe case-insensitive unique node/element/model maps; ground only to 0; labels do not rename nets; legal punctuation/case variants do not collide; ordinal >9999 not truncated; mixed NMOS/PMOS M allocation; pin-array order cannot swap terminal roles |
| Determinism | Repeated same snapshot/envelope/profile identical text and provenance; parameter-map insertion order identical; multiple Python hash seeds/working directories; source array permutations preserve generated names/rows/electrical digest but invalidate old approval and change source header |
| Provenance/tampering | Full chain of snapshot/report/circuit approval/base bytes/maps/representation approval; altering any bound model/map/base byte blocks; parent links cannot be forged by artifact equality alone; no circular digest or timestamp/path in deterministic text |
| Purity and preservation | Export performs no user filesystem/network/process/simulator access; immutable typed input and original JSON unchanged; refusal gives no text/provenance/generated maps; no assumed `can_execute` from export success |

An unsupported waveform enum cannot normally be constructed/loaded through M1. Test raw rejected mode at load and valid-mode-but-unsupported configuration at M2 separately; do not mutate frozen internals to invent product reachability. UNVALIDATED currently needs an incomplete-report/guard scenario, because no approved catalog case has that state. Use a controlled public-gate test seam for such a report and verify export refuses it; it is not a newly authored M1 VALID document. Similar preflight branch tests are defensive API tests, not claims that current M1 allows malformed records.

## Adapter Unit / Regression Plan — M2E

- Use mocks for public editor/runner, not a simulator install. Missing/stale circuit, representation or condition approval must result in **zero file/editor/runner calls**.
- Verify element-map lookup before DC directive construction, target/reference/comparison trace mapping and explicit user selection; no silent label/RAW substitute.
- One reviewed analysis only; no arbitrary text/directive input. Every request field binds the ExecutionApproval; edits/reset invalidate it. Parameter sweep for generated IR is rejected, while existing ASC sweeps remain untouched.
- Base text hash/maps/model context verified; condition insertion only on a unique contained copy before `.end`; read back allowed exact circuit tokens and directive. Editor rewriting is recorded as execution-copy hash, not approved base hash.
- Success is simulator success **and** nonempty RAW/LOG, not path existence alone. Failures preserve original/base files, return actionable diagnostics and never look successful.
- Path containment, quoting/spaces, copy collision/cleanup and no traversal/symlink escape. Test with stdlib temporary paths; no private user directories.
- Full 482-test baseline plus new tests must pass. Existing ASC approval block/source preservation/AC/Transient/DC/parameter sweep/Summary/launcher regressions remain authoritative. Do not rewrite v0.1 expectations to accommodate the new branch.

## Later Real LTspice Validation — M2F

Opt-in Windows verification using separately installed LTspice, current public PyLTSpice path, repository-owned JSON and controlled model profiles. No private MOSFET coursework, network/model download or API call. Record simulator/library versions, fixtures/source digests, explicit test-review/approval actions, directive/conditions, emitted terminal/mapping evidence, generated-copy hashes, status, RAW/LOG and measured tolerances. Test approvals establish the gate mechanics; do not present automated fixtures as an actual human usability study.

| Fixture / run | Planned evidence |
| --- | --- |
| Resistor divider, DC and simple transient/AC as appropriate | Generated `.cir` accepted; resistor ratio/selected voltage and source polarity match independently known topology; RAW/LOG exist and original JSON/base hashes unchanged |
| RC low-pass with nonzero explicit AC source | 10 Hz–1 MHz AC example where suitable; transfer function target/reference; gain/BW against the declared R/C formula and matching authored circuit; non-unit AC amplitude proves reference handling; transient response separately measured |
| Current-source resistor load | V/I waveform and DC syntax accepted; measured sign/direction against explicit positive→negative convention; no assumption that current source alone provides reference |
| RLC | Editor/simulator accepts fixed Rser=0 and deterministic terminal mapping; no hidden default resistance/coupling claimed |
| NMOS and PMOS educational circuits | Controlled Level-1 profiles and four roles/W/L preserved; actual AC/Transient, and DC where useful, return meaningful RAW/LOG metrics. PMOS uses a proven resistive drain reference, not a bypass of M1 conditional warning |
| V/I SINE and PULSE configurations | Prove actual DC operating-point, AC amplitude/phase and transient initial/steady source values for supported equality restriction and token order; narrow/block any unproved case rather than silently weaken preservation |

Define nominal component/model/source values, analysis range/timestep/window and tolerances **before** simulator comparison. For RC, use independently calculated corner/gain with declared interpolation tolerance. For MOS, compare a separately authored equivalent approved netlist with identical model/geometry/settings, not private coursework measurements or unrelated v0.1 AC numbers. Report bandwidth-not-found, unavailable metrics, instability or convergence failure as observed; never create expected hardware behavior. Actual simulator acceptance does not validate image fidelity or real-device performance.

Confirm source JSON hash and immutable input unchanged before/after both success and failure; preserve approved base copy; identify mapped RAW traces explicitly. Do not stage generated RAW/LOG/copies. M2G accepts the exporter only after this evidence and v0.1 ASC integration regressions are recorded. Hosted CI keeps deterministic tests only, without LTspice installation/secrets; local opt-in integration has distinct status/limitations.
