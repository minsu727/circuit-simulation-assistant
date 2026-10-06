# M2A–M2G Handoff Prompts — Planned / Not Executed

Read [Architecture](architecture.md), [Exporter Contract](exporter-contract.md), [Approval Contract](approval-contract.md), [Format](netlist-format.md), [Validation Boundary](validation-boundary.md) and [Test Plan](test-plan.md) before each slice. Preserve unrelated working-tree edits; inspect actual current APIs, check latest CI, and stop before implementation if CI is not green. No automatic commit/push/tag/release; each implementation is separately reviewable. This file does not authorize any future slice.

## M2A — Restricted Exporter Architecture (Prompt 035)

**Goal:** Design the narrow M2 contract before production work.

**Allowed:** This focused `docs/v0.2/m2/` set; genuine architecture decisions only, without rewriting old ADRs.

**Acceptance:** Link/API/terminology/security audit, explicit existing ASC assumptions, precise technical/approval/artifact separation and no executable changes. Record M1 baseline CI and documentation verification.

**Do not:** Implement exporter/approval/adapter, add dependencies/tests, run LTspice or advertise proposed work as complete.

## M2B — Snapshot/Electrical/Report Digests and Circuit Approval

**Goal:** Introduce the immutable circuit-review binding without exporting anything.

**Allowed future changes:** `circuit_ir/approval.py`, focused approval tests and independently authored digest vectors in the separate M2 fixture root; minimal public exports after review.

**Acceptance:** Reuse dump_document, exact electrical projection/report hashing, correct null/enum/tuple fields, explicit trusted decision/warning acknowledgement, same-revision edits reject, imported reviewed states never authorize. Stable under irrelevant parameter map insertion order; provenance/order changes conservatively invalidate. Targeted + full regressions pass.

**Do not:** Add APPROVED to TechnicalState, modify Circuit JSON schema/M1 validation, implement text export, model lookup, execution or UI. An envelope is a stale-review token, not authentication or can_execute.

## M2C — Restricted R/C/L/V/I Text Export

**Goal:** Pure complete base `.cir` generation from eligible, circuit-approved input.

**Allowed future changes:** `circuit_ir/exporter.py`, exporter tests, static authored M2 goldens; minimal reviewed exports.

**Acceptance:** Ordinal names/collision checks, explicit roles/connections, exact SI/source syntax and waveform/DC restriction, fixed ideal-inductor option, current warning/approval gates, determinism/purity/input preservation, fail-closed result with no partial text. No new dependency. Full ASC/M1 tests unchanged.

**Do not:** Support MOS until M2D, models/paths/directives/raw SPICE, file writing, GUI or simulator. Do not generate expected files from exporter output.

## M2D — MOS and Sealed Demo Model Profiles

**Goal:** Conditional explicit NMOS/PMOS export with known repository-owned Level-1 model data.

**Allowed future changes:** `model_profiles.py`, minimal exporter/model-context integration and tests/goldens.

**Acceptance:** D/G/S/B independent of visual/pin list ordering, exact positive W/L, safe generated model tokens, exact model_ref lookup/polarity/typed coefficient allowlist, no undeclared external model dependency, registry digest invalidates old approval. A conditional-reference warning still blocks. NMOS/PMOS fixtures use proven resistive reference paths.

**Do not:** Resolve arbitrary files/libraries, trust raw `.model`, substitute unknown models, solve device physics, weaken M1 warnings or add a generic plugin framework.

## M2E — Approved Netlist Execution Adapter

**Goal:** Separate artifact/condition gates and copy-only netlist adapter using existing low-level runner/readers.

**Allowed future changes:** `netlist_runner.py`, representation/ExecutionApproval verification and focused mocked adapter tests; small integration seam only if justified. Do not rewrite the ASC path.

**Acceptance:** Recheck exact source/report/parent approval/base/map/registry/condition hashes before side effects; map DC/target/reference IDs explicitly; reuse current directive builders on one execution copy; verify saved circuit semantics, nonempty RAW/LOG and error handling; full regressions with no fake success. Evidence distinguishes base and execution bytes. Test controller approvals are explicit actions.

**Do not:** Treat an unbound approved=True as authorization, feed `.cir` into AscEditor, silently substitute traces, add parameter sweep for IR, alter numerical algorithms, build production review UI or claim real LTspice from mocks.

## M2F — Real Repository-Owned LTspice Verification

**Goal:** Prove supported generated text/source/model/trace behavior locally.

**Allowed future changes:** Separate public M2 source fixtures/docs and opt-in `verify_netlist_integration.py`; minimal compatibility fixes only with demonstrated cause/tests.

**Acceptance:** Planned divider/RC/I/RLC/NMOS/PMOS and source-mode runs, explicit approvals/mappings/conditions, real simulator return/RAW/LOG/metrics, declared tolerances before comparison, source/base hashes unchanged, existing actual ASC integration where supported. Record versions/limitations/failures honestly; generated outputs ignored.

**Do not:** Modify private coursework/public v0.1 example, hardcode demo metrics into production, add external model/API/network/CI simulator dependencies, conflate simulation with physical or clean-machine validation.

## M2G — Acceptance Catalog and M2 Closure

**Goal:** Complete independently authored export/approval/adapter acceptance and regression evidence.

**Allowed future changes:** M2 catalog/matrix/tests and scoped status docs; minimal proven defect fixes only.

**Acceptance:** Unique inventory, static exact-byte goldens/failure contracts, all planned gates/scopes/security cases, repeat/hash-seed/round-trip/source preservation, full test count/errors/skips/exit, actual M2F evidence and model/format limits. Do not invent a M2 ratio or count copied from M1.

**Do not:** Add Vision/OCR/LLM/M3 extraction, expand supported subset or grant simulator-ready from TechnicalState.VALID. Missing real evidence leaves that gate incomplete rather than being waived by acceptance tests.

## Every Slice's Completion Report

List actual touched files, supported/excluded boundaries, tests/count/failure/skip/exit, source preservation, injection/privacy/diff review and unresolved assumptions. Never count a planned scenario as a passing test or use fake approvals to claim user validation. Do not stage or publish generated input/output, secrets, paths, binaries or model-library files. Follow separately provided Git permissions, not these future templates.
