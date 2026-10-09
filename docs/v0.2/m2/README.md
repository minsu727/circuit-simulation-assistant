# v0.2 M2 — Restricted SPICE Export and Execution

**M2B–M2F are implemented.** M2G owns the acceptance catalog, evidence inventory
and closure review. This is an additive Python/IR workflow, not a new installed
app UI or image-recognition feature. See [current status](status.md) and the
[acceptance matrix](acceptance-matrix.md) for the final verification scope.

## Current verification and authority

- [M2G acceptance catalog](../../../tests/fixtures/m2_acceptance/README.md):
  97 independent scenarios; 100 CI-safe tests including integrity checks.
- [Real-run inventory](real-run-evidence.json): preserved M2F evidence for
  25 primary runs, six MOS reference runs and three v0.1 ASC regressions.
  RAW/LOG are ignored local evidence, not files shipped in this repository.
- Latest relevant hosted CI checked on 2026-10-09 (Asia/Seoul):
  [run 37868116946](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37868116946),
  commit `1c6634ec7be271d334dc4bb6be6645f8dc1357d5`, completed/success.
  This hosted run covers committed M2F; the uncommitted M2G additions have local
  validation only. Exact totals and closure criteria are in [status](status.md).
- Existing authority: [Circuit JSON](../circuit-json-schema.md),
  [validation rules](../validation-rules.md), [architecture](../architecture.md),
  [roadmap](../roadmap.md), [ADR-002](../adr/002-simulator-output.md) and
  [ADR-004](../adr/004-human-approval.md). M1 schema/version/connectivity and
  v0.1 behavior remain unchanged.
- Historical M2A baseline: [M1 closure](../m1/status.md), 38 acceptance cases,
  482 tests, commit `aac6b47`; its
  [CI run 37310055753](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37310055753)
  was M1 evidence, not an M2 implementation result.

## Documents

The eight M2A design documents below retain their original proposal-time language
and verification history. Their “proposed” / “not implemented” statements describe
Prompt 035's date, not the present implementation. Current implemented API,
execution evidence and closure authority are recorded in the last three documents.

| Document | Decision owned here |
| --- | --- |
| [Architecture](architecture.md) | Original review/export/representation/execution design and ownership |
| [Exporter Contract](exporter-contract.md) | Restricted devices, pure API/result and fail-closed rules |
| [Approval Contract](approval-contract.md) | Snapshot/electrical/report binding, two IR approval scopes |
| [Netlist Format](netlist-format.md) | Names, SI tokens, source/MOS syntax and exact bytes |
| [Validation Boundary](validation-boundary.md) | M1 proof versus stricter M2 admission |
| [Test Plan](test-plan.md) | Independently authored goldens, negative and real-run coverage |
| [Implementation Plan](implementation-plan.md) | Original M2A–G sequence and baseline documentation audit |
| [Prompt Breakdown](prompt-breakdown.md) | Original implementation stages/review gates |
| [Real LTspice Validation](real-ltspice-validation.md) | M2F actual APIs, reproduction command, failures and local results |
| [Acceptance Matrix](acceptance-matrix.md) | M2G contract → tests/fixtures → observed evidence |
| [Status / Closure](status.md) | Exact totals, hosted CI boundary, closure criteria and limitations |

## Controlled path

Reviewed manual Circuit JSON → strict typed load → fresh deterministic validation
and M2 preflight → explicit **CIRCUIT_EXPORT** decision → restricted base SPICE
preview → explicit **REPRESENTATION** decision → typed AnalysisRequest → separate
explicit **EXECUTION** decision → verified generated copy → LTspice → existing
RAW analysis.

Technical VALID, human approval, export SUCCESS, runner success and analysis
success are separate states. A hash detects stale review; it is not authentication.
Imported `validation_state.status=reviewed` grants no permission. Representation
approval alone does not authorize conditions or launch LTspice.

## Implemented profile and deferred scope

`m2-spice-v1` admits manual-origin, flat circuits with explicit R/C/L/V/I and
NMOS/PMOS selected from sealed repository Level-1 demo profiles. Controlled
AC/TRAN/DC conditions are composed by the adapter after approval. Unsupported or
uncertain meaning blocks the whole artifact; external model/includes and
arbitrary commands are unavailable.

No image/OCR/Vision, automatic reconstruction, CAD/ASC exporter, production v0.2
review UI, generic model resolver, Circuit JSON parameter sweep, new analysis
algorithms, LLM/API, packaging or release changes. Future extraction must produce
untrusted draft IR and pass validation/human correction before the existing M2
approval/export/execution chain.
