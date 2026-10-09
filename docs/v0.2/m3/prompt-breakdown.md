# M3 prompt handoffs

**Future work, not implementation performed by Prompt 042.** The
[Implementation Plan](implementation-plan.md) defines phase dependencies and
[Test Plan](test-plan.md) defines evidence lanes.

## Shared constraints for every implementation prompt

Read the M3 contracts and current M1/M2 APIs first; preserve the current working
tree. State the exact starting source/test baseline. Add no automatic approval,
model confidence shortcut, invented component/value/source or partial executable
circuit. Keep untrusted observations and manual decisions separate.

Do not alter M1 `0.2-draft1`, Connection-only membership or existing algorithms
to accommodate Vision output. M2 manual-origin restriction must not be silently
removed. Any separately authorized image-admission change requires its own
reviewed context/invalidation contract and regression tests. No release,
packaging, ASC rewrite, arbitrary SPICE/PDK support or unrelated LLM change.

## M3B — Representative fixtures and independent evaluation

Create owned small printed schematics plus explicit rights/provenance records,
independently reviewed topology/role/value/correction goldens and a catalog.
Cover the drawing/negative families in Test Plan; separate ambiguous drawings
from unique-topology accuracy denominators. Decide matching/resource policies
before later performance evaluation. Do not implement a Vision extractor or
generate expected answers with production code.

Gate: reviewed originals and independent goldens, asset hashes, no private scans,
precise future metrics. No fixture-count or accuracy target invented.

## M3C — Observation types and extraction seam

Implement separate minimal candidate/observation records, strict shape/reference/
resource checks, source/transformed image identity, safe bounded intake and fake/
static response adapter. Retain provider provenance/unknowns without credentials.
Finalize exact tagged payload keys against M3B cases; do not expand M1 schema.

A real provider/local extractor requires an explicit chosen contract, dependency
decision and verified opt-in/data handling. Do not silently install/call a vendor
SDK or use existing AI result-interpretation consent for image upload.

Gate: fake CI path, malformed/untrusted input tests, clear no-live-call guarantee;
provider choice stays optional until separately reviewed.

## M3D — Evidence-linked connectivity inference

Implement wire/terminal/label hypotheses and deterministic derived topology over
selected constraints. Preserve contacts versus separations, pose/role alternatives
and unresolved crossings. No distance/confidence-only canonical merge or hidden
ground/body/source. Unsupported content remains visible/blocking.

Gate: independent pin-partition/ground/role tests, ambiguity/abstention,
stable references and repeatable reconstruction. No UI or real simulator.

## M3E — Review, correction, M1 conversion and admission

Use small checkpoints in order: review transactions; pure M1 projection;
**image-admission contract review/authorization**; minimal UI integration.
Return complete image-origin M1 documents or issues without a partial document.
Run unchanged schema/validation and preserve actual warnings/deferred checks.

Present the smallest image-aware admission design separately before changing M2.
It must bind image/review/promotion evidence at consuming gates, retain original
provenance and preserve all explicit approvals/manual-profile behavior. Current
image export rejection remains the expected result until that change is authorized.
Do not freeze proposed context names/signatures in advance.

Gate: atomic edits, stale-revision rejection, exact independently authored M1
projection, no approval restoration/import trust, current ASC/UI regression.
If admission is deferred, clearly label conversion-only completion.

## M3F — Actual extraction and real E2E examples

Evaluate the actual implemented extractor on held-out owned images, report
failures/abstentions/correction effort and provider/settings/cost evidence.
Remote requests require explicit payload/provider consent. After explicit review,
authorized admission and the three M2 approvals, run separately installed LTspice
through its existing entry point with mapped results.

Gate: actual image-to-RAW evidence, original/copy hashes, independent numerical
expectations/tolerances and existing full regression. Replay/fake/manual-origin
substitutes cannot count as actual image E2E. Missing consent/admission/simulator
is NOT RUN/BLOCKED, not PASS.

## M3G — Independent acceptance and closure

Create an independently reviewable catalog/matrix linking source images,
observations, corrections, M1/M2 boundaries and actual extraction/simulation
evidence. Run deterministic CI and verify the relevant hosted result; inventory
the actual live runs without exposing retained images/paths/secrets.

Gate: no unresolved blocking admission/fidelity/gate defect, explicit limitations,
actual supported-profile evidence, deterministic artifacts and baseline v0.1
preservation. No closure on model confidence or technical VALID alone.

## Decisions deliberately left for later review

| Decision | Owner / blocking consequence |
| --- | --- |
| Exact symbol/style catalog and interpretation conventions | M3B; no unsupported pose/crossing assumptions before tested catalog |
| Provider/model, local extractor and optional SDK | M3C; no remote support claim until consent/retention/resource policy verified |
| Response/candidate wire version, numerical budgets and matching thresholds | M3B/C; proposed M3A record names are not a frozen API |
| Printed mega/micro/units notation table | M3B/C; ambiguous value cannot be promoted without explicit selected interpretation |
| Versioned image-admission interface and evidence binding | M3E reviewed separately; required for image export and M3F/G full execution closure |
| Review-bundle retention and app-owned cleanup details | M3C/E; remote/persisted behavior must be disclosed/tested before enabled |
| Exact overlay/table controls and mode navigation | M3E; minimum operations fixed, widget package/CAD canvas not selected |
| Recognition performance targets supported by held-out data | M3F/G; no unmeasured accuracy/cost guarantee |

These decisions do not prevent completion of the **M3A design**, but they gate
later implementation/closure. The architecture supplies defaults of no cloud
call, no automatic choices and no image execution before admission.
