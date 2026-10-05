# Seven Future Codex Prompts (Proposed / Not Executed)

These are implementation handoff templates. Prompt 027 does **not** execute them or authorize current code/dependency/commit changes. Each future task should start by reading the M1 plan and existing changes, preserve unrelated work, run its targeted tests, review the diff and wait for any separately required commit permission.

Shared guardrails: [canonical contract](../circuit-json-schema.md), [M1 boundary](implementation-plan.md), [validation profile](validation-plan.md). No image/OCR/LLM/UI/exporter/LTspice/packaging work. No code changes to v0.1 calculations, parser, approval, Summary or launcher. No silent schema/ADR migration. Every slice must remain independently importable and testable.

## M1A — Core Records and Enums

**Goal:** Implement frozen stdlib records/enums and minimal public exports matching [Data Model](data-model.md).

**Allowed future files:** models.py, __init__.py and test_circuit_ir_models.py.

**Acceptance:** Exact parent field/null/enum mapping, immutable nested collections, no object-reference cycles or import side effects. Keep TechnicalState separate from WireValidationStatus; no approval type. Targeted stdlib tests pass.

**Do not:** Add Pydantic/jsonschema yet, build a graph or mutate parent docs. Depends on the agreed plan only. Review/commit boundary: core types and tests as one isolated slice.

## M1B — Exact Values and Primitive Serialization

**Goal:** Implement finite value parser and explicit typed-to-wire JSON projection plus strict primitive JSON decode.

**Allowed future files:** value_parser.py, serialization.py, value/serialization tests, minimal export additions.

**Acceptance:** All required suffix examples including M/m/Meg; exact long decimals, bounded exponent/output; literal preservation; duplicate-key/non-finite rejection; valid explicitly constructed records dump deterministically.

**Do not:** Implement an unvalidated full document loader or silently normalize imported inconsistent values. Full load→typed round-trip awaits M1C. Depends on M1A. Review/commit boundary: parser and serialization utilities with tests.

## M1C — Bundled Schema and Typed Loader

**Goal:** Implement the parent 0.2-draft1 shape contract, strict typed loading and complete semantic round-trip.

**Allowed future files:** schema.py, circuit-json.schema.json, schema/serialization tests, loader exports. Under explicit authorization for this future task, add requirements-circuit-ir.txt and include it from requirements-test.txt; do not change core/LLM requirements or CI workflow.

**Acceptance:** Bundled schema matches the parent's JSON block; meta-schema check; internal refs only/no remote fetch; unknown/missing/type-invalid input rejected before construction; missing direct dependency fails clearly, not by skipping validation. Imported reviewed snapshots grant no authority.

**Do not:** Write a custom partial JSON Schema engine or introduce a second Pydantic schema. Depends on M1A/B. Review/commit boundary: shape/loader and explicit isolated dependency wiring, not product integration.

## M1D — Checked Native Graph

**Goal:** Build component–pin–net incidence views with checked IDs/ownership/references and no inferred connections.

**Allowed future files:** graph.py, graph tests and small authored graph data; exports as needed.

**Acceptance:** Duplicate definitions never overwrite; unknown references/multiple incidence fail safely; net members derive only from connections; array ordering and coordinates do not alter electrical membership. Graph availability is not a validity/approval flag.

**Do not:** Add NetworkX, wire reconstruction, label merging or simulator-name generation. Depends on M1C. Review/commit boundary: graph API and focused tests.

## M1E — Structural Validation and Result Contract

**Goal:** Implement ordered schema/ID/reference/pin/ground/label stages, root-cause suppression and fresh runtime issue/result records.

**Allowed future files:** validation.py, validation tests and initial invalid/ambiguous JSON fixtures; minimal model adjustments consistent with the plan.

**Acceptance:** Stable parent codes, separate enriched result envelope, severity/blocking consistency, skipped-stage reasons, repeatable report ordering. INVALID/AMBIGUOUS cannot become VALID via imported status/confidence. Other device stages remain explicitly incomplete rather than returning a full passing report.

**Do not:** Mark the interim validator complete, grant ready_for_review/reviewed or copy results into authorization fields. Depends on M1D. Review/commit boundary: structural rules plus incomplete-stage contract and tests.

## M1F — Device, DC and Ambiguity Rules

**Goal:** Complete local R/C/L/V/I/MOS rules, narrow DC projection/constraints, explicit ambiguity/confidence handling and m1-local-v1 state aggregation.

**Allowed future files:** validation.py, graph.py, corresponding tests and authored fixture additions.

**Acceptance:** Detect source shorts, invalid dimensions/configuration, missing MOS role/body/ref and proven floating/island/DC contradictions. Conditional nonlinear paths warn; catalog/asset/full checks stay deferred. Manual null confidence alone is valid; critical unresolved inference blocks. Input unchanged.

**Do not:** Resolve model files, perform transistor bias calculations, implement analysis-specific execution checks, calibrate vision scores or add exporter/approval objects. Depends on M1E. Review/commit boundary: completed local profile and targeted rules/tests.

## M1G — Fixture Acceptance and Regression

**Goal:** Complete the independently authored 38-case catalog and matrix, then verify M1 acceptance without widening scope.

**Allowed future files:** Six planned test modules and tests/fixtures/circuit_ir/{valid,invalid,ambiguous}; only minimal circuit_ir fixes for discovered defects. Do not edit existing v0.1 tests to make failures disappear.

**Acceptance:** Eight VALID, twenty INVALID and ten AMBIGUOUS cases under the declared profile; exact expected findings/skips/deferrals; strict round-trip and input preservation. All applicable blocking rules have negative coverage. Targeted and existing full tests pass with exit/count/skips recorded; no LTspice/cloud/image dependency. Record actual counts rather than calling the planning budget “96 tests passed.”

**Do not:** Generate expected reports from validator output, implement UI/M2 netlists, run unrelated simulations or commit/push without separate permission. Depends on M1A–F. Review/commit boundary: deterministic fixture/test evidence and acceptance documentation, with deferred work explicit.

## Handoff Checklist for Every Future Slice

Read current diff and parent contract; list touched files and non-goals; implement only the slice; run meaningful targeted tests; inspect failures rather than adding skip/coercion; keep unsafe/incomplete state blocked; review dependency scope; check diff/privacy; report evidence and deferred work. Schema/rule contradictions require a documented decision before changing prior specifications. These prompts are ready for later assignment, not a claim that any slice has run.
