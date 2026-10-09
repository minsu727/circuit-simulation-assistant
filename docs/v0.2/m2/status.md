# M2 status and closure

**Verdict: CLOSED for the restricted M2 Python/API milestone.**
Acceptance was reviewed on 2026-10-09 (Asia/Seoul). This verdict covers the
implemented contract below, not a v0.2 product release, UI, clean-machine
certification or image-to-circuit capability.

## Implemented boundary

| Stage | Implemented API / evidence |
| --- | --- |
| Circuit JSON load / validation | Existing strict M1 schema/typed loader, Connection-only graph and fresh `validate_document` |
| Circuit review binding | `make_circuit_approval` / `verify_circuit_approval`, exact snapshot, report, warnings, contract and sealed model context |
| Restricted base preview | `export_document` / `check_export_eligibility`; complete R/C/L/V/I/NMOS/PMOS, exact generated names/text/maps; fail closed |
| Representation review binding | `make_representation_approval` / `verify_representation_approval`; exact regenerated base bytes/maps/provenance and parent |
| Conditions / execution review | Typed ACCondition / TransientCondition / DCCondition, AnalysisRequest, separate ExecutionApproval |
| Composition | `compose_execution_netlist`; full fresh chain, one controlled directive immediately before terminal .end |
| Copy / simulator boundary | `run_generated_netlist` with injected runner; `run_ltspice_netlist` for explicit actual simulation |
| Result handoff | `read_netlist_analysis`, exact mapped RAW traces delegated to unchanged v0.1 AC/Transient/DC functions; bounded current observation |

Technical VALID, CIRCUIT_EXPORT, export SUCCESS, REPRESENTATION, EXECUTION,
process/file success and final analysis success remain distinct. Factory decisions
are supplied by a trusted controller; hashes bind freshness, not identity or
authentication. Imported reviewed state grants no permission. Test controllers
make explicit fixture decisions and do not supply a live human-review workflow.

## Verification record

- New [acceptance catalog](../../../tests/fixtures/m2_acceptance/README.md):
  **97 cases / 100 M2G tests**, including three integrity/authority tests.
  Focused verification passed 99 tests plus the subsequently added inventory
  integrity test; all 100 also passed in final full discovery.
- Final local full suite: **848 tests**, failures **0**, errors **0**,
  skips **0**, exit **0**, **409.219 seconds**. This includes the unchanged
  748-test baseline and the 100 new acceptance tests; live simulator runs are not
  counted as unit tests.
- `python -m pip check`: no broken requirements. No dependencies or workflow
  changes. The existing Windows CI installs `requirements-test.txt` and uses
  standard unittest discovery, which discovers the new module.
- Latest relevant hosted CI checked read-only:
  [run 37868116946](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37868116946),
  **completed / success**, main source
  `1c6634ec7be271d334dc4bb6be6645f8dc1357d5`. It is the latest main run and covers
  committed M2F. **The uncommitted M2G tests have not run on hosted CI.**
  No new hosted run was dispatched or represented as passing.
- M2F preserved final evidence: **10 primary fixture families / 25 primary
  cases + 6 MOS reference runs + 3 public ASC regressions = 34 successful
  simulator runs**. M2G inspected all 34 required RAW/LOG pairs, LOG versions,
  exact M2 copies/digests, actual traces and recomputed existing measurements.
  It did **not** execute LTspice again.
- Environment recorded in the inspected evidence: Windows 11 build 26200,
  Python 3.13.5, LTspice **26.0.1 for Windows**, PyLTSpice 6.0.1, spicelib 1.6.3,
  NumPy 2.5.3. Actual metrics/tolerances and run references are in the
  [inventory](real-run-evidence.json) and [matrix](acceptance-matrix.md).
- Original Circuit JSON, public ASC, base/execution golden files, M1
  schema/version/catalog and all pre-existing production/test files were checked
  against the starting SHA-256 baseline and retained byte for byte.
- `git diff --check` passed; new files were also checked for whitespace, links
  and private paths. Local audit logs/helpers and simulator outputs remain ignored.

Final scope audit: of 313 pre-existing tracked files, 312 were byte-identical;
the only intended pre-existing change is this directory's README. All 150
original fixture files are unchanged. All 75 relative link/anchor occurrences
in 13 M2/catalog Markdown documents resolve. No secret, email, personal absolute
path or trailing-whitespace finding was detected in the seven public changed/new
files. No file is staged and no generated output/audit helper is tracked.

The first focused run had four **acceptance-controller construction errors**:
positional ExportResult fields, an incorrect Confidence attribute, and two
scope substitutions violating frozen record shape. The tests were corrected
using the actual public record fields and valid cross-scope records. No production
defect or contract relaxation was found.

## Closure criteria

| Required criterion | Result / evidence |
| --- | --- |
| M2B–F public APIs implemented as contracted | PASS; existing code and public-chain acceptance |
| Standard repository tests | PASS; final full local count above |
| Acceptance suite | PASS; 97 catalog scenarios + three checks |
| Latest relevant GitHub Actions green | PASS; exact latest M2F run/source above; new M2G hosted run remains pending |
| Actual LTspice evidence | PASS locally; 34 retained runs re-inspected, not mocks |
| Public approval chain cannot be skipped | PASS within trusted-controller contract; declined/stale/wrong records block before filesystem/backend |
| Deterministic generated text/maps | PASS; 12 base / five execution goldens, repeated and existing hash-seed/cwd tests |
| v0.1 remains intact | PASS; existing full regression, unchanged source, three preserved actual ASC modes |
| Limitations / deferred scope recorded | PASS; below and M2F validation |
| No unresolved blocking acceptance defect | PASS; no production changes needed |

Closure does not claim hosted execution of uncommitted files. After a separately
authorized commit/push, the next normal CI run should confirm the added acceptance
coverage; this task performs neither Git publication nor workflow changes.

## Preserved failure history and quality findings

M2F's initial 25 analysis handoffs failed after RAW/LOG generation because the
binary RAW reader axis had not been loaded. `This RAW file does not have an axis.`
was resolved in M2F by explicitly reading the axis trace. Original failed evidence
is retained; the existing independent synthetic binary test covers it.

A later successful sequence did not capture the MOS length advisory in structured
warnings because LTspice omitted the word “Warning”. M2F corrected that parser;
the final inspected sequence preserves the actual advisory. It is not suppressed
or relabeled as a physical model certification.

The M2 README incorrectly presented the whole milestone as specification-only.
Its current status now points here; original M2A design documents retain historical
proposal-time statements and their original baseline evidence. No API was invented
to match obsolete proposal wording. Expected golden files were not regenerated.

## Limitations

- One local Windows environment and one actual LTspice version. No clean Windows
  VM regression or multi-version certification; unsigned installer / possible
  SmartScreen behavior remain separate and unchanged.
- Level-1 repository MOS profiles are educational, not PDK models. No transistor
  physics, hardware, process accuracy or image fidelity validation. Same-simulator
  authored references demonstrate text/model equivalence only.
- Manual-origin flat circuits only. External .lib/.include, user model-library
  imports, arbitrary expressions/directives/devices and unresolved semantics
  remain unsupported/fail closed. IR parameter sweep is not part of M2.
- Current probes admit exact mapped two-terminal R/C/L/V/I classes; actual evidence
  demonstrates source/load conventions, not all probe classes or MOS Id/Is/Ig.
  Omitted ground voltage is missing, not fabricated.
- AC low-pass median/-3.000 dB and transient stable-cycle eligibility are unchanged.
  No crossing or inapplicable PULSE gain remains unavailable. RC startup swing and
  late-cycle gain use different existing windows. MOS examples have no capacitance
  bandwidth claim.
- Filesystem containment checks do not defend against a privileged concurrent
  filesystem attacker. Approval hashes are not authentication. A caller-owned
  trusted human-decision controller is still required.
- RAW/LOG evidence is ignored and not shipped in fresh clones. Reproduction is
  separately opt-in; ordinary CI uses fake/synthetic evidence and cannot prove
  simulator installation or physical accuracy.
- No image recognition, live user approval interface or new v0.2 Streamlit UI.
  No new LLM/API, actual OpenAI smoke test, installer or release validation here.

## Next milestone boundary

Future work should address image/schematic extraction only after its own reviewed
architecture: image → component/text candidates → candidate pin/net relations →
**untrusted** Circuit JSON → deterministic validation → human correction/review →
existing M2 approval/export/execution gates.

Vision output must not grant approval or provide arbitrary runnable SPICE/model
content. Extraction, asset/provenance admission, correction UI, production model
libraries and broader physical/simulator validation are deferred, not implemented.

## Reproduce the CI-safe checks

```powershell
python -X utf8 -m unittest tests.test_m2_acceptance
python -X utf8 -m unittest discover -s tests -p "test_*.py"
python -m pip check
git diff --check
git status --short
```

Use the existing full test environment. Actual simulation remains a separate
[explicit M2F command](real-ltspice-validation.md#reproduce); it is not needed
merely to refresh a PASS date. No add/commit/push/tag/Release action occurred.
