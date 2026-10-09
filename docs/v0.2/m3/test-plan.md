# M3 evaluation and tests

**Plan only: no images, goldens, tests, recognition metrics or live calls are
created/run in M3A.** [Implementation Plan](implementation-plan.md) owns gates;
[Vision Boundary](vision-boundary.md) owns consent and privacy.

## Owned independent fixture strategy

M3B should introduce a clearly named image-fixture catalog with source drawing,
committed raster, provenance/rights record, hand-authored observation/topology
expectations, planned review events and expected post-correction M1 document.
Reuse public electrical ideas from the existing generic fixtures where useful,
but draw images independently; never use private coursework or copied textbook
scans without explicit rights. Do not add a repository-wide LICENSE implicitly.

A deterministic drawing renderer may reproduce pixels. **It must not generate
topology or expected conversion answers from the code under test.** Independently
author/review goldens and document their reasoning. No automatic bless/update mode.
M2 base/execution goldens remain unchanged and are not exported into new expected
files by production code.

| Fixture family | Independent expected evidence |
| --- | --- |
| Simple divider, RC, current load and RLC | Component/value/source inventory, explicit terminal roles, ground and pin partition |
| Zigzag / rectangular R, R/C/L rotations and mirrors | Catalog/style identity, equivalent topology, stable role convention |
| V/I polarity, direction and typed source settings | Positive/negative terminals, missing-field abstention, complete corrected source |
| NMOS/PMOS four-terminal and three-terminal variants | D/G/S/B mapping, explicit body choice, W/L/model omissions and user-selected demo profile |
| Dot crossing / unconnected crossing / bridge / T / corner / gap | Membership/separation constraints; ambiguous drawings require alternatives, not one truth |
| Shared labels, nearby detached text and multiple ground conventions | Correct attachment/equivalence or unresolved conflict; no proximity/fuzzy join |
| VDD without explicit supply, missing ground/input value/reference label | No synthesized source/value/reference; explicit correction or blocked promotion |
| k/M/u/µ/μ/n/p, units, scientific notation and OCR-like alternatives | Raw text, confirmed notation/SI Decimal values and disagreement rejection |
| BJT/op-amp/unknown block/hierarchy and partial crop | Unsupported/missing-content abstention; no partial executable circuit |
| Injection/malformed response/oversized image/stale review | Data-only text, bounded intake, fail-closed load/patch/admission, zero runner calls |

Fix one-to-one component/terminal correspondence in the catalog. Net names are
arbitrary: compare accepted pin partitions, roles, ground group and label identity,
not only printed net IDs or similar-looking diagrams. For inherently ambiguous
drawings, author the allowed alternatives and required NEEDS_REVIEW disposition;
do not invent a unique hidden topology for accuracy scoring.

Use separate development and held-out examples, including held-out redraws/style
variations. Static provider responses are explicitly synthetic/replay inputs,
not claims that a live model produced those observations. Pin their asset,
response and contract digests. Images sent to a provider require separate consent
and valid provenance even when a fixture is public.

## Evaluation lanes

| Lane | Inputs / execution | Claim permitted |
| --- | --- | --- |
| Deterministic CI | Owned static raster/observations/fake responses; converter/review/graph; injected runner; no network, secrets or installed LTspice | Contract correctness and approval fail-closed behavior |
| Actual extraction | Fresh held-out owned images through the implemented local extractor, or separately opted-in remote adapter | Observed extraction performance for exact catalog/provider/model/settings |
| Actual simulator | Explicit opt-in, installed LTspice, completed review and future image admission plus all current M2 decisions | Real mapped RAW/LOG results for those reviewed images/circuits |

Remote Vision and simulation have independent opt-ins. A live model response does
not grant execution permission; a synthetic observation replay does not establish
actual extraction. Default discovery must never enable either live lane.

## Required deterministic coverage

- Intake type/size/geometry/transform and observation tagged-schema/ID references;
  unknown fields, invalid scores, bounding boxes and resource excess fail closed.
- Components/roles/text/value alternatives, positive and negative contact
  constraints, ambiguous-crossing queue, missing/unsupported item retention.
- Reconstruction repeatability across ordering, hash seeds and working directory;
  no duplicated canonical membership or silent implicit terminal/ground.
- Review edits, type/role remapping, atomic net merge/split, explicit rejection,
  stale callbacks/events, undo as new revision and imported-bundle distrust.
- Explicit confirmation prerequisites; deterministic conversion expected document,
  scalar/notation correctness, current schema round-trip, M1 actual reports.
- Current image-origin export rejection until admission is authorized. Later,
  admission binding/asset mutation/review staleness, all three M2 decisions,
  absent artifacts/files and **zero runner calls** when any boundary fails.
- Original image/response/review/base/fixture hash preservation; app-owned retention
  cleanup and logs contain no keys, raw image payload, text or personal paths.
- Existing M1/M2/v0.1 unit/AppTest regressions. Real backend tests remain opt-in.

Post-correction document expectations are authored independently, not recorded
from the converter. Replaying corrections is explicit test-fixture authority,
never production auto-approval.

## Metrics to record before any accuracy claim

| Measurement | Protocol |
| --- | --- |
| Component recognition | Per-type TP/FP/FN and precision/recall with versioned one-to-one box/identity matching; threshold set before evaluation |
| Names / numeric values | Exact confirmed reference and unit/Decimal agreement; raw-text error separately; no rounding-away unit/sign errors |
| Terminal roles / ground | Exact role assignment and reference-group agreement |
| Connectivity | Exact pin partition match plus connected-pair precision/recall; false joins and missed joins separately |
| Crossing ambiguity | Correct connected/separated or abstained disposition; ambiguous examples excluded from unique-topology denominator |
| False confident connections | Wrong relations presented as resolved/unambiguous; provider score buckets only if actually supplied, no calibration inference |
| Unsupported abstention | Detected unsupported content, false support and omitted real unsupported devices |
| Human correction | Type/value/connection edits, rejection count, unresolved items, time/actions to explicit confirmation; missed elements found by full-image review |
| Post-correction conversion | Exact expected M1 fields/partition and actual technical/export admission outcomes |
| Runtime / usage | Intake/inference/reconstruction/review times separately; actual reported usage/cost or unknown, failures/retries included |

Publish denominators, fixture IDs, failures, abstentions, manual additions and
both pre-review and post-review metrics. No invented percentage, fitted tolerance
or unspecified “accuracy” aggregate. Technical VALID and successful simulation
cannot be scored as visual correctness.

## Real examples and M3 closure evidence

M3F must demonstrate actual extraction → review/correction → image-origin
conversion → M1 → authorized image admission → explicit M2 approval chain →
real LTspice → mapped deterministic result on owned examples. Preserve failed
runs and source hashes; record versions, conditions, review actions, RAW/LOG
references, numerical comparisons and predeclared tolerances.

Use separately authored electrical/theoretical expectations for passive examples.
MOS uses the existing educational profiles/equivalent-device-body checks; do not
claim PDK or transistor physics validation. Exact binary RAW equality is not an
acceptance criterion. A replay-only candidate, manual-origin recast or fake runner
cannot be called a real image E2E test.

If image admission or actual extraction is unavailable, record NOT RUN/BLOCKED;
M3G cannot close the full image execution profile. No fixed fixture count or
accuracy target is selected before the M3B review.
