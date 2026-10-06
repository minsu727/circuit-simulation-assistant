# M2 Implementation Plan — Specification Only

No file/API below exists yet as M2 functionality. The plan consumes the closed M1 contract and preserves the existing ASC execution branch. Future slices require their own authorization/review; Prompt 035 performs none of them.

## Minimal Future Package Layout

```text
circuit_ir/
  approval.py       # M2B: binding projections, scopes/envelope, verification
  exporter.py       # M2C/D: preflight, ordered rows, safe naming/numbers/text/result
  model_profiles.py # M2D only: sealed typed repository demo registry
netlist_runner.py   # M2E only: approved execution-copy adapter, outside pure IR
tests/
  test_circuit_ir_approval.py
  test_spice_exporter.py
  test_netlist_runner.py
  fixtures/spice_export/<case>/...
  verify_netlist_integration.py # M2F opt-in local script
```

Start with two IR modules. Add the registry only when MOS support is reviewed, and the runner outside `circuit_ir` so importing core/exporter does not import simulator/UI code. Do not create `spice/` subpackages, standalone naming/formatting frameworks, a parallel neutral graph, plugin/adapter factories or a new versioning system merely for file organization. Private helper functions/transient device tuples are sufficient initially. Expose only reviewed functions/records at each slice; existing public M1 names retain their behavior. No external dependency is planned.

## Proposed Records and API Ownership

| Slice | New records/API proposal | Boundary |
| --- | --- | --- |
| M2B | ApprovalScope, ApprovalEnvelope, ApprovalError; `document_digest`, `electrical_digest`, `validation_digest`, `approval_digest`, `make_circuit_approval`, `verify_circuit_approval` | Use current M1 projection/report; no export, file or simulator API |
| M2C | ExportStatus, ExportIssue, ExportProvenance, ExportResult; `check_export_eligibility`, `export_document` | R/C/L/V/I only with explicit empty model context and circuit approval; no file writes |
| M2D | TrustedModelProfile and fixed registry/version/digest | Exact known model_ref selection; Level-1 coefficients, polarity and W/L; never raw `.model`/include text |
| M2E | Representation approval verification/creation, ExecutionApproval and `run_generated_netlist` adapter | Exact base/map/parent hash + current typed analysis snapshot; separate run-copy execution and existing RAW return convention |

These are proposed names, not undocumented changes to M1 models.py or __init__.py. `ApprovalError` is a small code/field diagnostic exception for invalid/stale envelope checks; expected export failures are converted to ExportIssue without approval.py depending on exporter.py. Envelope creation computes fresh technical validation and hashes; final exporter always repeats technical/preflight/approval checks. For M2B the creation gate grants only a scoped reviewed snapshot, not absent exporter eligibility.

`make_circuit_approval` accepts the document and an explicit trusted human `approved` decision, acknowledged current WARNING IDs, exporter contract and trusted registry version/digest. `verify_circuit_approval` checks an exact document/current recomputed report/context/envelope, not a caller's asserted success. Details/required fields are in [Approval Contract](approval-contract.md).

When the text/mapping hashes exist, future `make_representation_approval` consumes the verified CIRCUIT_EXPORT envelope plus exact base/mapping digests and a second explicit decision; verify against an actual ExportResult/current source before use. It need not import ExportResult into the approval module: pass validated native hashes through the trusted application boundary, then the runner checks all bindings. Scope constraints prevent an artifact envelope from being used for initial export. There is no blanket `approve_document(...)->can_execute` API.

Future `ExecutionApproval` is adapter-owned (not new Circuit IR state): contract version, representation-approval digest, base-netlist digest, normalized current-request digest and explicit approved bool. The request digest binds analysis type, all reviewed conditions, selected IR target/reference/comparison, requested point/measurements, and the reviewed mapping context. `run_generated_netlist` takes the source document, verified ExportResult, circuit/representation envelopes, current typed request and ExecutionApproval; rechecks all bindings before work. It cannot take arbitrary netlist text/path or an unbound `approved=True` shortcut. Exact request field types will reuse current analysis condition contracts in M2E; they are not a new natural-language parser or changing ASC approval.

## Milestone Sequence

| Slice | Narrow deliverable | Acceptance / evidence | Explicit exclusion |
| --- | --- | --- | --- |
| M2A / Prompt 035 | This architecture/specification | Current API inspection, green M1 CI gate, links/terminology/diff/privacy audit | Production code, tests, LTspice |
| M2B | Exact hashes + circuit approval envelope | Independent digest vectors, current/same-revision staleness, imported flag refusal, warning-set binding, M1 regressions | Export/model registry/runner/UI |
| M2C | Pure passive/source exporter | Static exact-byte goldens, canonical safe names, SI/source fields, fail-closed issues, no partial output/purity | MOS/model lookup, directive/execution |
| M2D | Controlled MOS model provision | Four terminal roles, W/L/model type, exact allowlist, deterministic self-contained declarations, registry approval binding | Arbitrary external model text/path/resolver or transistor solver |
| M2E | Representation/condition gate + netlist adapter | Mocked copy/approval/no-side-effect refusals, directive/mapping/RAW failure paths, full ASC regression | Vision/UI editor, generated-IR parameter sweep, new analyses |
| M2F | Actual local fixture execution | Divider/RC/I/RLC/NMOS/PMOS source/mapping/RAW checks, declared numerical tolerances and source hashes, actual ASC regression | CI simulator install, physical/clean-machine broad claims |
| M2G | Export/adapter acceptance and closure | Independent catalog/matrix, exact expected reports/text, repeat/hash/preservation tests, final full suite/real evidence/limits | M3 extraction or feature expansion |

Each slice adds meaningful focused tests and runs the current full repository suite only after executable changes, records actual counts/exit/skips and reviews staged scope before a separately authorized commit. A successful preceding slice does not authorize the next or a Git operation. Existing 482-test baseline is a regression floor, not a fixed future count. CI remains network/API/LTspice-free for tests; an actual missing portable boundary must be reported, not hidden with skip/fallback.

## Dependencies, Resource and Persistence Decisions

Reuse stdlib dataclasses/enum/Decimal/hashlib/json and existing M1 graph/parser/schema. No model download, NetworkX, serializer framework or authentication dependency. Retain `requirements-circuit-ir.txt` separation and current full test requirements; M2A changes no dependency/packaging/CI file. Frozen typed model coefficients use template-owned dimensions rather than expanding the closed M1 Quantity unit set. `model_context` is only an immutable version/digest pair resolving a sealed exporter-owned in-memory registry; no generic registry class or caller-supplied model objects are needed.

Exact export bytes do not depend on filesystem, clock, environment, paths or Python hash seed. Existing schema lazy loading is the already established M1 exception, not a new user/model file read. Per-run randomness may allocate app-owned folders in M2E but never export names/hashes. There is no universal simulator-ready bit; observable gates and results remain separate.

Do not persist approved execution authority in Circuit JSON. Keep envelopes/provenance in app-managed evidence; strict envelope serialization is a future local sidecar contract, not an M1 schema revision. Direct envelope construction in tests represents a trusted caller; parsing arbitrary envelope JSON cannot manufacture human authorization. Report this local trust boundary honestly.

## Documentation Verification

M2A checks only this new documentation set: relative links/anchors, actual M1 enum/API spellings, proposed/current labels, source/package references, prohibited paths/secrets, whitespace and protected-file hashes. There is no dedicated existing Markdown/link test module; existing schema tests read the parent Circuit JSON spec, which is unchanged. Do not rerun all 482 tests or actual LTspice solely for these Markdown additions.

Required final commands: `git diff --check` and `git status --short`, plus read-only local link/scope/privacy audit. Record exact findings at completion without pretending proposed goldens or simulator tests have passed. The [M2 index](README.md) records the verified baseline CI URL; no CI modification/run is part of this spec task.

### Prompt 035 Local Documentation Evidence

On 2026-10-06 (Asia/Seoul), the read-only documentation audit passed: exactly nine new M2 Markdown files, 48 relative link/anchor occurrences all resolve, balanced code fences, no trailing whitespace, no missing referenced existing API/enum member, and no detected secret/email/personal absolute path. Byte-level SHA-256 comparison of all 224 pre-existing tracked files found no change, including M1 schema/fixtures/tests, current product/runtime, CI, dependencies, packaging, icons, public example and root README. No file is staged; public untracked additions are confined to `docs/v0.2/m2/`. The one-time audit helper is ignored under `simulation_output/`, not a permanent test or proposed exporter implementation.

`git diff --check` completed with exit 0 and no whitespace errors; the existing Windows LF-to-CRLF warning is not a source change (protected-file hashes match). New untracked documents were separately checked for trailing whitespace. There is no dedicated Markdown test module; no full suite, build or actual LTspice run was needed/performed for this spec-only change. The 482-test/green-CI numbers are prior M1 evidence. No dependency, model registry, executable code, approval object or exporter was created, and no add/commit/push/tag/Release operation was performed.

## Open Implementation Checks

The decisions above are concrete initial restrictions, not promises of simulator behavior. M2E/F must prove public editor serialization/newline behavior, token order and source DC/AC/transient semantics, emitted node/current trace availability, controlled model acceptance and fixed ideal-inductor syntax on the installed LTspice version. If a contract cannot be honored, block the affected feature and document a reviewed minimal correction before expanding eligibility. Do not assume a passing M1 golden, PyLTSpice import or text extension proves these checks.

All M1 scope decisions and v0.1 metrics/approval/runtime stay closed. M3 begins image extraction into draft IR only after a distinct reviewed asset/provenance contract; it never supplies trusted model/library/approval content or runnable raw SPICE.
