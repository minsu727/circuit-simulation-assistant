# M1 Graph and Validation Plan (Proposed / Not Implemented)

This plan specifies **local deterministic checks**, not a simulator, visual classifier or approval engine. Parent codes and categories come from [validation-rules.md](../validation-rules.md). The distinction between M1 technical validity and full generation readiness is mandatory.

## Checked Graph Algorithm

1. Shape-check the document; validate all definition IDs before building dictionaries. Duplicate definitions are retained as issues, not overwritten by the last record.
2. Build checked component/pin/net indices and separate visual/label/report reference indices. Verify owners, reverse pin lists and connection endpoints. No name-based implicit pin creation.
3. Create typed node keys `(component,id)`, `(pin,id)`, `(net,id)`; ownership edges come from verified component/pin records and incidence edges only from connections.
4. Reject repeated incidence rows, even if they point to the same net. Missing incidence stays unresolved; do not guess from coordinates or labels.
5. Build immutable sorted adjacency, net-members and role lookup views. Label attachment is checked, not used to silently merge nets.
6. BFS connected components for incidence structure. Preserve component/pin/net identity in diagnostics; a component edge does not imply conduction.
7. Build a separate DC-reference projection using only validated R, L and independent V branches. C, I sources and MOS gates add no conductive/reference edge. MOS drain/source/body paths remain conditional and are not used to certify an operating point.
8. Traverse from the accepted ground net for proven linear reference reachability. A disconnected incidence island produces ISOLATED_SUBNETWORK first; suppress derived floating errors for that already-invalid island. For referenced regions, a node attached only through C/gate/I and without a supported DC path produces FLOATING_DC_NODE; nonlinear-only paths produce DC_REFERENCE_UNPROVEN instead of a false proof.

Index construction and graph traversal are O(components + pins + nets + connections), excluding deterministic sorting, which is O(N log N). Memory is O(N+E). Shape/value validation is proportional to bounded input size. Do not claim overall linear cost for arbitrary-precision arithmetic or sorting.

Independent DC V sources and ideal L branches form a separate potential-constraint graph. Use weighted union-find or a deterministic potential traversal with exact Fraction arithmetic to detect proven inconsistent DC cycles/parallel constraints; L contributes zero potential difference. Conditional waveform/AC/nonlinear constraints beyond a direct exact comparison are deferred with a warning. A finite graph check is not an operating-point solver.

Proposed local resource guards: at most 1 MiB JSON text, nesting depth 32, 256 components, 1024 pins/nets/connections, 4096 visual entities and parent field-length bounds. Reject before expensive construction when exceeded. These are M1 loader limits, not image-upload limits or a new wire schema. Do not open image assets, model files or schema URLs.

## Nine Ordered Stages

| Stage | Work | Failure / dependency handling |
| --- | --- | --- |
| 1. Parse/schema/type | Strict decode, duplicate JSON keys, version, bounded size/depth, bundled shape, finite numbers | SCHEMA_INVALID; no typed document/graph. Normalize nested schema errors to actionable paths rather than every oneOf branch |
| 2. IDs | Definition uniqueness and required namespace identity; component-ID case collisions. Label text is checked in stage 5, not mistaken for duplicate definition IDs | DUPLICATE_ID; abort indexing/graph stages globally. Never choose one duplicate |
| 3. References | Owner↔pin_ids agreement, unknown net/pin/visual/label/warning/candidate targets | BROKEN_REFERENCE; graph unavailable. Aggregate independent reference issues, skip dependent topology checks |
| 4. Pins/connectivity | Expected role sets, unknown role, multiple incidence, missing incidence, orphan device | Known contradictions ERROR; unknown roles/missing incidence AMBIGUOUS. Body-specific missing incidence uses MOS_BODY_UNRESOLVED, not duplicate generic errors |
| 5. Ground/reference prerequisites | Exactly one ground; label scopes/collisions/aliases | GROUND_MISSING blocks ground-dependent checks. Safe device/value checks may continue; no cascade of every node floating |
| 6. Component/value/source | R/C/L units/positivity, source polarity/configuration, MOS role/body/W/L/ref presence, source-same-net | Evaluate only components with satisfied pin/reference prerequisites. Catalog lookup deferred, not passed |
| 7. Graph/DC checks | Incidence islands, DC reference, bypassed passives, exact DC source constraints | Skip affected invalid regions; record skipped reason. Nonlinear/unsupported constraint proof remains a warning/deferred check |
| 8. Ambiguity/confidence/provenance records | Explicit unresolved choices, valid resolution references, declared critical inference requiring review, static coordinate bounds | No image/OCR or calibration inference. Consume root ambiguities already diagnosed in earlier stages to avoid repeated warnings |
| 9. Fresh result | Severity precedence, deterministic IDs/order, completed/skipped/deferred lists | Return profile-specific state. Do not set reviewed, approve, export or execute |

After a globally unsafe parse/ID/reference stage, later graph/device checks are not run and report why. For local component failures, unaffected value checks may proceed; omit judgments relying on corrupted topology. An empty/no-device document must not pass through vacuous checks: ORPHAN_DEVICE plus ground diagnostics as applicable. Absence of errors in skipped stages is not evidence that they passed.

## Issue Contract and Naming

Runtime ValidationIssue fields:

| Field | Required / behavior |
| --- | --- |
| issue_id | Required, assigned after deduplication/sorting; e.g. issue_0001. Unique within the fresh report, not a circuit entity |
| code | Required stable parent machine code; never parse a translated message |
| severity | Required ERROR / AMBIGUOUS / WARNING / CONFIRMED |
| message | Required bounded explanation from a stable template |
| target_refs | Required sorted tuple of affected definition IDs; empty for document errors |
| entity_type / entity_id | Nullable primary semantic entity selection; no duplicated electrical state |
| field | Nullable semantic field selector when IDs are known; raw JSON pointer for parse/shape errors |
| suggested_action | Nullable bounded corrective hint; no automatic edit/patch |
| blocking | Derived true iff ERROR or AMBIGUOUS; callers cannot set a conflicting boolean |
| provenance | Required immutable visual-ref tuple; empty when there is no visual evidence |

Deduplicate by `(code,severity,target_refs,semantic_field)`; sort by ERROR, AMBIGUOUS, WARNING, CONFIRMED, then code/target/field. Assign sequential report IDs afterward. Array permutations preserve logical graph/findings where identity is valid; raw schema pointers retain the input array indices and are not promised identical under malformed-array reordering.

Keep parent codes such as DUPLICATE_ID, BROKEN_REFERENCE, PIN_ROLES_INVALID, PIN_NET_INVALID, GROUND_MISSING and SOURCE_SAME_NET. Do **not** replace them with E_DUPLICATE_COMPONENT_ID or invent competing code sets. Optional display classification uses `E_<code>`, `A_<code>`, `W_<code>`, `I_<code>` for ERROR, AMBIGUOUS, WARNING, CONFIRMED respectively; prefixes are derived, not serialized canonical codes.

Three planned M1 report extensions use the existing code grammar: `CHECK_DEFERRED` (WARNING), `AMBIGUITY_UNRESOLVED` (AMBIGUOUS for explicit unresolved choices without a more specific parent rule) and `CONFIDENCE_REVIEW_REQUIRED` (AMBIGUOUS for declared critical inference lacking review). Do not append these fields/codes to old ADRs silently. Parent findings are a six-key projection: id, code, severity, target_refs, message, visual_refs. The enriched result envelope is separate and must not be inserted into the closed Circuit JSON schema. Warning is an IssueSeverity, not a separate mutable Warning collection.

## Technical States versus Wire/Human States

| Fresh M1 TechnicalState | Exact condition |
| --- | --- |
| UNVALIDATED | No fresh report yet; not returned as a successful final validation |
| INVALID | At least one ERROR, including failed parse/schema |
| AMBIGUOUS | No ERROR and at least one AMBIGUOUS |
| VALID | All applicable M1 stages completed or safely scoped; no ERROR/AMBIGUOUS. WARNING/deferred checks can remain |

ERROR takes precedence when both ERROR and AMBIGUOUS exist. AMBIGUOUS is an issue severity and a fresh aggregate technical state; the parent wire status remains blocked for either category. VALID is always qualified by `profile=m1-local-v1` and its deferred-check list.

M1 does not emit APPROVED or update the wire status to reviewed. Imported draft/blocked/ready_for_review/reviewed are archival snapshots, never fresh readiness. Validate even an imported reviewed circuit; a forged flag cannot remove findings. Keep fresh reports separate from input JSON. Later runtime ingestion resets stale snapshots and applies the full parent state machine.

Future preview generation requires a fresh **full** profile with all required checks complete, no ERROR/AMBIGUOUS, matching revision and human circuit review with warnings acknowledged. Execution additionally requires exact generated-representation approval and existing simulation-condition approval. These future gates cannot be satisfied by M1 alone. No `can_execute=true` or convenience approval object is part of the M1 API.

## Rule Coverage and Deferred Work

| Parent rule / domain | M1 implementation plan | Deferred boundary |
| --- | --- | --- |
| SCHEMA_INVALID, DUPLICATE_ID, BROKEN_REFERENCE | Complete local shape/index/reference checks | No remote schema resolution |
| PIN_ROLES_INVALID, PIN_NET_INVALID, ORPHAN_DEVICE, GROUND_MISSING | Complete explicit-record checks | Pixel-derived pin/ground decisions are not made |
| SOURCE_INVALID, SOURCE_SAME_NET, VALUE_INVALID | Typed fields, dimensions, positivity, finite values and exact finite grammar | Analysis-specific excitation readiness is later; zero source is not automatically illegal |
| MOS_BODY_UNRESOLVED, MODEL_INVALID | Explicit roles/body-net and W/L; null model_ref is AMBIGUOUS; wrong non-MOS field use ERROR | Model existence/polarity/body convention lookup deferred. A syntactically present ref is not confirmed |
| SOURCE_CONSTRAINT_CONFLICT | Proven exact DC contradictions; direct typed parallel-setting contradictions when provable | General AC/waveform constraint reasoning, ideal-loop rank/solver behavior; no convergence claim |
| ISOLATED_SUBNETWORK, FLOATING_DC_NODE, PASSIVE_BYPASSED | Explicit topology and narrow device-aware projection | No transistor bias/conductance solution |
| DC_REFERENCE_UNPROVEN | Warning on conditional nonlinear path | Solver/operating-point validation remains later |
| LABEL_UNRESOLVED, LABEL_CONFLICT, LABEL_ALIAS | Exact accepted label/net records | No OCR attachment, fuzzy matching or simulator name generation |
| CROSSING_UNRESOLVED, DANGLING_WIRE | Consume declared ambiguity records/explicit unused-stub decisions | No coordinate-based wire extraction or dangling detection from pixels |
| UNSUPPORTED_FEATURE | Out-of-schema raw types rejected; unknown draft type remains blocking | No unsupported-device interpreter |
| IMAGE_PROVENANCE_INVALID | Shape, origin/reference consistency and coordinate bounds if supplied | Asset existence/content-hash verification, normalization and upload admission deferred |
| Confidence/review | Range/basis + explicit inference-pending findings; null manual score alone not blocking | No calibration, threshold auto-accept or human approval |

Record catalog/asset/inference/full-export checks as deferred, never CONFIRMED. For MOS with a supplied model_ref, emit CHECK_DEFERRED while still allowing VALID@m1 if local rules pass. Missing model_ref gets MODEL_INVALID AMBIGUOUS. No MODEL_INVALID existence pass is generated without a resolver.

Imported visual observations may have null geometry in authored manual fixtures. Static schema/coordinate checks do not fabricate an image. The absence of a real asset resolver is always visible when an image reference is supplied.

## Root-Cause Suppression Examples

- Missing referenced net → BROKEN_REFERENCE; no SOURCE_SAME_NET/floating conclusion from a partial graph.
- Device with zero pins → ORPHAN_DEVICE; suppress duplicate missing-role findings for that device.
- Unknown MOS role → PIN_ROLES_INVALID AMBIGUOUS; do not assert a wrong body tie afterward.
- Missing bulk incidence → MOS_BODY_UNRESOLVED, instead of a second generic PIN_NET_INVALID for the same root cause.
- Missing ground → GROUND_MISSING; skip ground-dependent floating/island judgments.
- Declared crossing ambiguity → CROSSING_UNRESOLVED; do not create an edge or add a redundant AMBIGUITY_UNRESOLVED for the same item.
- Low confidence cannot soften a known source-short ERROR; high confidence cannot make it VALID.

All stage skips, deferrals and report templates must be covered in the future [test matrix](test-plan.md). No source or tests are written by this plan.
