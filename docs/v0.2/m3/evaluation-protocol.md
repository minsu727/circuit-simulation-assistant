# M3B future evaluation protocol — `m3-evaluation-1`

This is an evaluation **specification**, not an implemented recognition/topology
scorer. Inputs are the [owned catalog](../../../tests/fixtures/schematic_images/README.md)
and [independent annotation contract](fixture-annotations.md). All current tests
check fixture integrity only. There are no accuracy, latency or cost measurements.

## Future input and report boundary

The future evaluator receives a validated CandidateCircuit/observation bundle,
catalog case ID plus image digest, candidate/adapter/schema/settings versions,
original-frame evidence, explicit unresolved claims/alternatives, and optionally
a separately identified human-reviewed snapshot/event log. Provider IDs must be
remapped to bounded local IDs before comparison. No credentials, absolute paths,
provider code, approvals or executable netlist is an evaluation input.

Validate image/digest/version/frame binding first. A malformed, mismatched or
failed extraction is a recorded failure, never silently dropped from totals.
Primitive fixture truth is **not** a production CandidateCircuit or an approved
M1 document. Do not feed truth into the extractor, reveal expected connections in
its prompt, or use labels/ground truth to select a favorable candidate graph.

Future native-JSON aggregate report shape (illustrative; no public API frozen):

```json
{
  "protocol": "m3-evaluation-1",
  "catalog": "m3-images-1",
  "lane": "actual-extraction",
  "run": {"adapter": "declared-version", "settings_digest": "recorded-digest"},
  "cases": [{
    "case_id": "divider",
    "image_sha256": "exact-catalog-digest",
    "status": "NOT_RUN",
    "pre_review": null,
    "post_review": null,
    "issues": [],
    "usage": {"cost": null, "currency": null, "inference_ms": null}
  }],
  "aggregate": {"attempted": 0, "failed": 0, "metrics": null}
}
```

Real metric records contain integer numerator/denominator plus nullable ratio,
eligible case IDs, TP/FP/FN counts, confusion matrix, role mismatches, exact
partition outcome, false joins/missing joins, review errors, correction actions
and stage-specific status. Zero denominator gives `null`/NOT_APPLICABLE, never
100%. Separate NOT_RUN, FAILURE, APPROPRIATE_ABSTENTION and SUCCESS. Failure counts
remain in eligible attempted denominators; detailed uncomputed fields stay null.
All counts/ratios are computed deterministically from recorded outcomes, not by
an LLM. Keep raw/reviewed results and failures separately; never cherry-pick the
best retry or publish replay/fake scores as actual extraction.

## Correspondence rules fixed before inference

1. Use original-frame symbol bboxes. Eligible match: **IoU ≥ 0.50**, regardless
   of proposed type or label. Choose maximum-cardinality one-to-one matching,
   then maximum total IoU, then lexicographically sorted `(truth_id,candidate_id)`
   pairs for ties. Candidate stable IDs are required. Do not let confidence,
   truth label spelling or expected topology influence the correspondence.
2. Each visible component has one truth instance. Duplicate detections are
   unmatched FP; missed instances are FN. Match unsupported observed regions too,
   but track support disposition separately. Empty output on a failed extraction
   contributes misses to eligible recognition denominators.
3. Match visible terminals only within the matched component: one-to-one maximum
   cardinality within **12 original pixels**, then minimum total Euclidean
   distance and stable-ID tie break. Match by geometry before judging role;
   assigning “gate” to the drain point cannot be repaired by role-driven pairing.
   Unknown/null-position bulk is excluded from localization truth and belongs
   to missing-data review. Invented terminal detections are separate FP.
4. Compare explicit type, role and polarity after correspondence. A role/type
   mismatch fails the corresponding metric even if a graph can be renamed to
   look equivalent. Ground and attached labels are semantic anchors. Net IDs
   are compared only through terminal partition and these anchors.
5. Freeze thresholds per protocol before evaluation; report any later protocol
   revision separately. These thresholds specify future correspondence, not an
   inference contact radius or evidence for automatic electrical joins.

## Recognition and text metrics

| Metric | Numerator / denominator and error policy |
| --- | --- |
| Localization precision / recall | Matched boxes / predicted boxes; matched boxes / visible truth instances, across attempted cases |
| Per-class component precision | Correctly matched predicted type c / all detections predicted c, including unmatched/wrong-type predictions |
| Per-class component recall | Correctly matched type c / all visible truth instances of c; unmatched/wrong-type observations miss |
| Class confusion | Ground-truth type × predicted type for geometry-matched instances; separate unmatched FP/FN margins |
| Reference-label correctness | Exact visible reference text on correctly localized component / eligible visible reference labels; missing localization counts incorrect |
| Raw value-text correctness | Exact Unicode raw scalar/unit evidence / readable eligible printed values; compare scalar and unit text separately; no OCR cleanup hides errors |
| Normalized value correctness | Exact Decimal numerical equality **and** selected unit/notation / eligible known quantities; missing, wrong sign/unit or invented unit is incorrect |
| Terminal-role correctness | Correct role at matched original terminal position / all visible truth terminals; missed roles are incorrect |
| Source-polarity correctness | Both positive/negative (or arrow-defined current) roles correct / sources with explicitly known polarity; all-or-nothing |

Unreadable/missing quantity cases are excluded from known-value denominators,
included in review/missing-data metrics. A proposed plausible number for `1?0n F`
is a false confident value, not numeric accuracy. Printed mega normalization
cannot be evaluated under SPICE's milli-M rule. Literal truth retains exact text;
only flat net-label identity uses M1's trimmed ASCII case-insensitive comparison.
No fuzzy equivalence, unit guessing or component-ID-based correspondence.

## Topology is the primary success criterion

**Topology exactly correct** requires all expected supported visible components
and terminals matched with correct type and terminal role/polarity; no added
component/pin; exactly one accepted net per required terminal; the complete
terminal-role-aware pin partition equal to truth; correct ground group and every
resolved label attachment/equivalence; and every resolved junction/contact or
separation decision correct. A declaration of unresolved membership is not an
exact complete graph.

Allow a bijective renaming of opaque net IDs only when it preserves the **entire
partition**, ground and attached-label anchors. It cannot hide merged/split nets,
missing nodes, D/G/S/B swaps or polarity inversion. Do not compare net counts or
successful M1 validation/simulation as a substitute. Nets listed solely as
alternative vocabulary are not extra primary nets: membership rows define the
active partition. No production inference/union-find is used to produce truth.

Unique supported topology denominator currently contains **12 cases**: all
`topology_complete=true` except the unsupported BJT. Incomplete numeric/model
cases can enter topology metrics while remaining non-convertible. The BJT has
separate observed-role recognition and correct unsupported disposition metrics.
Three-terminal bulk-missing, ambiguous crossing and gap cases have no unique
complete topology denominator. Publish exact eligible IDs, not only the count.

Current eligible IDs: `divider`, `rc`, `missing_value`, `unreadable_value`, `rlc`,
`nmos`, `pmos`, `cross_open`, `cross_dot`, `shared_labels`, `rotated_sources`,
`supply_unknown`. This list describes available truth, not attempted extraction
or a measured rate.

| Topology metric | Definition |
| --- | --- |
| Exact topology rate | Exact complete successes / attempted unique-supported-topology cases; failures/abstentions here count as no exact success |
| Pin assignment accuracy | Role-correct matched pins in a correctly corresponding net group / required pins in eligible unique truth; missing/duplicate assignment is incorrect |
| Connected-pair precision | Correct joined unordered terminal pairs / all predicted joined pairs; include pairs involving spurious/unmatched terminals as FP |
| Connected-pair recall | Correct joined pairs / all truth joined pairs among visible terminals; missed detections/edges cause FN |
| False joins / missing joins | Predicted joined but truth separated pairs / truth joined but predicted separated or unassigned pairs; publish counts and relevant pair denominators |
| Net merge | A predicted group intersects >1 truth group; count offending predicted groups / predicted groups and wrong joins |
| Net split | A truth group is represented in >1 predicted group **or has unassigned/missed members**; count affected truth groups / truth groups |
| Junction interpretation | Correct connected/separated disposition / resolved annotated junctions; missing/abstaining decisions incorrect; ambiguity scored separately |

For per-pin assignment in imperfect graphs, find a maximum-overlap bijection
between predicted and truth groups on correctly role-matched terminals, with
ground/label anchor compatibility required; maximize correctly assigned pins,
stable-ID tie break. Unmatched groups/pins fail. A merged group may match at most
one truth group; a split at most one predicted group. Pair errors independently
expose every join/split, so assignment accuracy never hides a false connection.
Electrical conductivity *through* R/C/L/sources/MOS is not a wire/net edge.

No generic aggregate “accuracy” can outweigh topology errors. Report component
metrics next to topology metrics, not as proof of conversion success.

## Uncertainty, alternatives and false confidence

- Required-review recall: correctly surfaced blocking issue kind/target/evidence
  / authored required issues across attempted cases. Wrong target does not match.
  Missing model/W/L, bulk, ground, value and unsupported content are included.
- Review precision: justified reported blocking issues / all reported blocking
  issues. Additional genuine issues need independent adjudication, never silent
  alteration of a golden to improve a score.
- Ambiguity retention: unresolved case correctly retains both authored contact
  partitions with no selected winner / inherently ambiguous topology cases.
  Renaming is allowed per strict partition equivalence; alternatives must retain
  settled truth. One correct unconfirmed alternative is insufficient if the
  other required alternative is discarded. The gap's joined alternative is an
  explicit manual repair, not evidence of an observed invisible line.
- False confident interpretation: wrong type/role/value/contact or missing required
  information presented as resolved; count errors / all resolved critical claims
  and count affected cases / attempted cases. Also report **false confident
  electrical joins separately** from ordinary wrong abstained hypotheses.
  “Confident” means resolved/unambiguous disposition, not an invented score cutoff.
- Inappropriate abstention: unresolved/absent claim on an otherwise clear authored
  fact / clear eligible facts; case-level abstention / RESOLVABLE attempted cases.
  Appropriate ambiguity abstention is a safe outcome, **not** exact-topology success.
- Unsupported recall: retained unsupported regions with blocked support disposition
  / real unsupported regions. False support and omission get separate counts.
- Invented missing values/ground/source/body/model are counted separately, even
  if a future simulator would accept them. Provider scores remain uncalibrated
  unless a distinct held-out calibration study is recorded.

No alternative is automatically selected by evaluator or highest provider score.
Post-review scoring uses explicitly recorded decisions and manual additions,
with full-image fidelity review; it cannot overwrite original predictions.

## Workflow, runtime and resource policy

Report action counts by corrected type, role, value, contact/net merge/split,
label/ground, source/model parameter, rejected false detection and added missing
element. Report total manual actions, median/range actions per attempted review
session and time to explicit confirmation for completed sessions; retain cancelled
or failed sessions with separate denominators. Undo counts as another action.

Conversion readiness = complete explicit dispositions, fields and confirmation
meeting future converter prerequisites / attempted reviewed sessions. It is not
M1 VALID or image export authorization. Post-conversion technical validation,
image admission, CIRCUIT_EXPORT, REPRESENTATION, EXECUTION and actual RAW analysis
are separate stage statuses with eligible counts. E2E success requires **actual**
implemented extraction on held-out inputs plus all approved stages and real RAW;
no fake/replay/manual-origin substitute qualifies. It is currently NOT_RUN/BLOCKED.

Record stage intake/inference/assembly/review/conversion/runner durations in ms,
attempts/retries/timeouts/failures and actual provider usage/cost/currency or null.
No fabricated estimate is a measured cost; do not discard failed-call cost.
Publish count plus median/range and timeout count; do not treat a timeout as a
successful latency sample. No model provider is selected or contacted in M3B.

Fixture-informed **proposed M3C limits**, not implemented intake guarantees:
encoded PNG/JPEG ≤8 MiB; sides 64–4096 px; decoded pixels ≤8,000,000; ≤128 symbols,
512 terminals, 1024 text regions, 2048 segments, 512 junctions; text ≤256 codepoints,
≤8 alternatives/claim, ≤64 competing topology alternatives; caller-visible
inference deadline ≤60 s, ≤2 explicitly authorized attempts with a shared budget.
These comfortably contain the 1000×650 fixtures. M3C must validate actual decoded
allocations/transforms and review limits before implementation. Exceeding limits
must fail/review rather than silently downsample away a dot or prune to a winner.

## M3C/D compatibility and limits

M3C's exact next scope: separate observation/candidate-sidecar types, strict tagged
records, original/transmitted identities and transforms, bounded PNG/JPEG decode,
reference/finite/resource checks, and a deterministic fake/static replay adapter.
It does not reconstruct nets, convert to M1, approve, change UI or execute LTspice.
A real provider choice, SDK and remote consent/retention need separate review;
no live API is implied by this protocol.

M3D adds evidence-linked conductor/terminal/label hypotheses and bounded topology
alternatives, evaluated against fixed independent partitions. Future scorer code
must use this protocol/version; M3B deliberately provides no fake detection model
or pixel-derived electrical truth. Post-review M1 goldens remain separate M3E work.

All current cases are clean agent-authored development images, not held-out;
printed convention legends and D/G/S/B markings may aid recognition. No human
inter-annotator agreement, provider measurements or recognition target is claimed.
Add independently reviewed held-out redraws and broader style/noise/security
negatives before performance statements. Current M2 still rejects image origin
and source image references. M3 is **not closed**.
