# M1 Closure — Prompt 034

## Implemented Scope

M1A–M1G implements the local `circuit_ir` package: immutable typed records/enums, bounded exact SPICE scalar parsing, explicit JSON serialization, bundled Draft 2020-12 schema and strict typed loading, checked native component–pin–net graph, deterministic structural/device/DC/ambiguity/provenance rules and fresh `ValidationResult` aggregation. The wire version remains `0.2-draft1`; `connections` remains the only canonical pin-to-net relation.

The [catalog](../../../tests/fixtures/circuit_ir/catalog.json) now contains the planned **38 cases (8 VALID / 20 INVALID / 10 AMBIGUOUS)**. The [matrix](acceptance-matrix.md) maps them and named existing unit subcases to applicable M1 rules. There are 39 static fixture pairs on disk because the pre-existing `simple_source_resistor` remains a supplemental regression outside the planned count; 11 other existing pairs are reused inside the catalog and 27 pairs were added. No existing fixture was rewritten. No UNVALIDATED case is in the approved 38-case benchmark.

## State and Pipeline Boundary

- Shape-invalid I19 is rejected by typed loading with no partial document, graph or validation report. Its INVALID catalog classification does not claim that validation ran.
- The other 37 catalog cases load typed documents, invoke public graph building and validation, and compare exact authored contracts. Six graph-prerequisite failures return no graph; later conclusions are suppressed with explicit reasons.
- Fresh ERROR takes precedence over AMBIGUOUS; either blocks the local contract. WARNING-only results can be VALID after required stages complete. UNVALIDATED remains the state for incomplete required checks; existing M1F subcases test this separately.
- `VALID@m1-local-v1` means local deterministic contract consistency, not model existence/polarity, correct transistor operation, human approval, exporter authority or simulator readiness. Imported wire status/findings never grant fresh validity or approval.

## Verification

Local Windows verification used the existing full test environment; no dependency, CI workflow, simulator or product change was required.

```text
python -X utf8 -m unittest tests.test_circuit_ir_acceptance
python -X utf8 -m unittest discover -s tests -p "test_*.py"
python -m pip check
git diff --check
git status --short
```

- Acceptance: **13 test methods**, all 38 planned cases plus the preserved supplemental case; 0 failures/errors/skips, exit 0.
- Full repository: **482 tests** (469 baseline + 13 acceptance methods), 0 failures/errors/skips, exit 0; local run completed in 95.432 seconds. Fixture subcases are not counted as extra unittest methods.
- `pip check`: `No broken requirements found.`, exit 0. `git diff --check`: exit 0, no whitespace errors; Git only noted the existing Windows LF-to-CRLF conversion policy.
- Acceptance verifies catalog IDs/paths/distribution/inventory, exact issue sets/severity/targets, schema rejection, graph-gate suppression, stable issue IDs/order and completed/skipped/deferred metadata, typed round-trip, original byte hashes, array-order/visual separation and independent-process hash seeds.
- All expected files are static reviewed contracts, not captured validator output; write attempts are blocked during acceptance. No update/bless mode exists.
- Final scope/path audit: all 59 added/changed public files are limited to M1 documentation, the acceptance test and fixture catalog/pairs; their relative links and JSON parse checks pass, with no personal absolute paths, secrets or trailing whitespace found. The 166-file baseline hash comparison identifies only the intended M1 index edit among pre-existing tracked files: all existing fixtures, IR implementation, v0.1 source/tests, CI, requirements, packaging and assets are byte-preserved. Nothing is staged; generated authoring/audit tools and test logs remain ignored under `simulation_output/`.
- An initial test harness reference to `ValidationIssue.id` was corrected to the existing public `issue_id`. Expectations and production code did not change to conceal a mismatch; the independently authored contracts passed without engine fixes.

These local tests are compatible with the existing Windows CI discovery command. M1 acceptance uses only stdlib test utilities and the already declared bundled-schema dependency; it needs no LTspice, network, API key, private circuit, image asset or external model library. A new hosted CI run was not triggered by this uncommitted work.

## Deferred Scope and Known Limits

No Vision/OCR/image parsing, schematic reconstruction, Streamlit editor, netlist generation, Circuit IR simulator adapter/execution, v0.1 integration, human approval envelope, model-library resolution, transistor physics, calibration or design-quality judgment was added. Image-origin/geometry checks validate declared local records without decoding/fetching the asset. Nonlinear DC reference and general dynamic-source equivalence remain qualified warnings/deferrals rather than solver proofs. The 38-case catalog is a finite authored contract benchmark, not a guarantee for all circuits or a code-coverage percentage. No schema, model, graph, serialization or technical-state redesign occurred.

The original [implementation plan](implementation-plan.md), [test budget](test-plan.md) and [prompt templates](prompt-breakdown.md) are preserved as planning history. Their proposed counts do not substitute for actual passing test counts. Root README, v0.1 source/tests/UI/runtime, packaging, public LTspice example, Git tags/Releases/assets and dependency files are unchanged by M1G.

## Readiness and Next Boundary

M1 is locally accepted under its agreed profile. The next milestone remains [M2 — Manual JSON to SPICE](../roadmap.md): reviewed manual JSON, restricted deterministic exporter with exact device/model/value/terminal mapping, a separate approval envelope and separate netlist adapter, followed by actual LTspice comparison and original-JSON/approval/v0.1 ASC regressions. None of that is authorized by a M1 VALID result; ASC compatibility cannot be supplied by renaming a file suffix. Interactive editing remains M4 under the documented scope decision. Full model/export checks require their own subsequent decisions and validation.

No add/commit/push/tag/Release operation was performed for Prompt 034.
