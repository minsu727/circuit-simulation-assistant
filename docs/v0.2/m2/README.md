# v0.2 M2 — Restricted SPICE Export Plan

**Prompt 035 / M2A: specification only. No M2 exporter, approval envelope or netlist runner has been implemented.** M1 is implemented; the documents below describe the proposed next boundary, not installed-app functionality or passing M2 tests.

## Baseline and Authority

- [M1 closure](../m1/status.md): 38 planned acceptance cases, 482 repository tests; source commit `aac6b47` (`aac6b47b22e7e4ed5896a3d6445af0df87c25895`).
- Latest CI checked on 2026-10-06 (Asia/Seoul): [Automated tests run 37310055753](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37310055753), `main`, that exact commit, completed/success. This is M1 evidence, not an M2 implementation result.
- Existing authority: [Circuit JSON](../circuit-json-schema.md), [validation rules](../validation-rules.md), [architecture](../architecture.md), [roadmap](../roadmap.md), [ADR-002](../adr/002-simulator-output.md) and [ADR-004](../adr/004-human-approval.md). M1 schema/version/connectivity and the v0.1 branch stay closed.

## Documents

| Document | Decision owned here |
| --- | --- |
| [Architecture](architecture.md) | Review/export/representation/execution flow, current APIs, ownership and adapter seam |
| [Exporter Contract](exporter-contract.md) | Restricted devices, pure API/result, fail-closed findings and injection rules |
| [Approval Contract](approval-contract.md) | Exact snapshot/electrical/report binding, two approval scopes and invalidation |
| [Netlist Format](netlist-format.md) | `.cir`, names, SI tokens, source/MOS syntax, trusted model profiles and exact bytes |
| [Validation Boundary](validation-boundary.md) | What M1 proves, stricter M2 admission and warning/deferral decisions |
| [Test Plan](test-plan.md) | Independently authored goldens, negative/staleness/security cases and later real LTspice checks |
| [Implementation Plan](implementation-plan.md) | Minimal proposed package/API records and M2A–G sequence |
| [Prompt Breakdown](prompt-breakdown.md) | Small future implementation prompts and review gates |

## Controlled Path

Reviewed manual Circuit JSON → strict typed load → fresh deterministic validation + M2 preflight → explicit **circuit-export approval** → restricted base SPICE preview → exact **representation approval** → analysis-condition review/approval → separate netlist adapter → LTspice / existing RAW analysis.

`TechnicalState.VALID` **≠ Human Approved ≠ Simulator Executable**. A hash is a stale-review check, not authentication. Imported `validation_state.status=reviewed` is never permission. Neither approval scope launches LTspice, and representation approval does not choose an analysis.

## Initial Profile / Non-goals

Proposed `m2-spice-v1` admits manual-origin, single flat circuits with explicit R/C/L/V/I and, after M2D, NMOS/PMOS using an exactly selected repository-owned Level-1 demo profile. It emits complete self-contained circuit text, not unresolved external model identifiers. Unsupported or uncertain meaning blocks export; no partial netlist is returned.

No image/OCR/Vision, automatic reconstruction, CAD/ASC exporter, production review UI, generic model resolver, arbitrary SPICE expressions, external libraries, Circuit JSON parameter sweep, new analysis algorithms, LLM/API, packaging or release changes. Image-origin admission needs a later explicit asset/review contract; M3 extraction cannot bypass these gates. M2F will verify actual simulator compatibility; this plan claims none yet.

M2A changes only this documentation directory. The current source, tests, fixtures, requirements, root README, CI and releases remain unchanged. The verification procedure and actual documentation audit are recorded in [Implementation Plan](implementation-plan.md#documentation-verification).
