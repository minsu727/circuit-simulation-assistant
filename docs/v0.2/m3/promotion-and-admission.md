# M3E review, promotion and image admission

Prompt 046 implements an API/domain boundary over prepared M3C observations and
M3D hypotheses. No image recognition, review UI, simulator or runtime execution
is implemented here. **M3 remains open.** See [Review Contract](review-contract.md)
for the broader proposed UI and [Topology Contract](topology-contract.md) for
the unchanged conservative reconstruction inputs.

## Decisions and public interfaces

```text
start_review → apply_corrections → confirm_review
    → promote_review → unchanged M1 validate_document
    → issue_image_admission → M2 export eligibility
    → explicit CIRCUIT_EXPORT → explicit REPRESENTATION → explicit EXECUTION
```

The functions are exported from `circuit_image`. Typed correction/session records
live in [review_models.py](../../../circuit_image/review_models.py), with explicit
serialization in [review_serialization.py](../../../circuit_image/review_serialization.py).
Review, promotion and admission return records plus bounded, data-free diagnostic
codes. A failed correction returns no replacement session and leaves its input
untouched. Callers must preserve/display the previous state.

| Contract | Version | Authority |
| --- | --- | --- |
| Review | `m3-review-1` | Current typed corrections and explicit `ReviewDecision.CONFIRM` |
| Promotion | `m3-promotion-1` | Deterministic existing M1 projection, not validity/approval |
| Image admission | `m3-image-admission-1` | Eligibility context, never any M2 approval |
| M1 wire / validation | `0.2-draft1` / `m1-local-v1` | Existing schema and technical rules, unchanged |
| M2 approval / exporter | `m2-approval-v1` / `m2-spice-v1` | Existing three explicit approval stages |

## Review lifecycle and atomic changes

`start_review(hypothesis, observations, image)` rechecks actual image bytes,
normalized image/transform, strict observations and deterministic topology.
The immutable session retains the initial hypothesis, exact source bindings,
ordered events, current snapshot, issue/unsupported findings and confirmation.

`apply_corrections(session, tuple_of_operations, base_revision_digest=..., ...)`
replays/rechecks the entire current session, validates every operation/entity,
rejects duplicate/contradictory writes and applies an atomic batch. Independent
operations within a batch are canonically ordered. A successful batch creates
revision N+1 with the parent revision digest; even a no-op invalidates confirmation.
There are no authoritative timestamps, random IDs, local paths or free-form notes.

Limits: 256 correction events, 64 operations per batch, 1,024 combined membership
actors/components. Net partitions are exact, disjoint covers; topology-changing
operations that overlap one another cannot share a batch. Operations may be
applied in successive revisions. Ordinary field edits can share an atomic batch.

| Typed operation | Explicit effect |
| --- | --- |
| `SetComponentType`, `SetReference` | Select supported type / bounded reference. Type change withdraws dependent value/source/model proposals; roles must be reviewed separately. |
| `SetValue`, `SetSource` | Supply a syntactically consistent M1 quantity or typed DC/AC/NONE/SINE/PULSE source. No expressions/directives. |
| `SetMOSModel` | Select an existing sealed repository profile and explicit W/L quantities. No geometry-based model/dimension choice. |
| `SetTerminalRole`, `SetTerminalOwner` | Correct explicit roles/polarity/ownership. Contradictory/duplicate required roles block confirmation. |
| `AddTerminal` | Explicitly author a missing terminal with provenance; it starts disconnected. Never auto-create bulk or tie it to source. |
| `ConnectPin` | Set one pin's exact existing group or disconnect it with null. Required disconnected pins block confirmation. |
| `ChooseTopology`, `ConfirmContact` | Explicitly choose supported crossing/contact alternatives or connected/separated evidence. A separated choice cannot silently survive a contradictory merge. |
| `MergeNets`, `SplitNet` | Change whole membership groups; split requires an exact partition including attached labels/grounds. |
| `SetLabel`, `LabelEquivalence` | Correct/detach label attachment or confirm exact ASCII label equivalence; no fuzzy guessing. |
| `SetGround` | Attach/remove an observed ground claim; never turn a supply label into an invented ground/source. |
| `MarkUnsupported`, `RetainIssue` | Record unsupported/missing facts. Neither operation waives a blocking issue or permits a fake substitute. |

The original M3C visible text/extraction candidates and M3D evidence remain
immutable. Corrected values and source/model choices live in the event/snapshot
sidecar. Ambiguous values with reasons/alternatives are not adopted automatically.
Unknown required type/reference/value, missing source/MOS fields, uncertain
ownership/roles, unresolved connectivity/ground/labels, unsupported components,
incomplete observations and contradictory choices block confirmation.

`confirm_review` requires the exact current base digest, a typed explicit decision
and the sorted complete set of source claim IDs. This is a full-snapshot review of
the current corrected interpretation, not agreement with every original machine
proposal. Typed event history records corrected/rejected proposals. Confirmation
binds source identity, observation digest, topology digest, revision and version.
It does not authenticate a person; a trusted controller must obtain the actual
human action. No production constructor automatically confirms a review.

## Promotion and evidence mapping

`promote_review(session, hypothesis=..., observations=..., image=...)` rechecks
the current explicit confirmation and refuses incomplete/nonrepresentable state.
It builds the existing M1 document, strict-loads its deterministic serialization,
and calls the unchanged `validate_document`. **Confirmed-but-INVALID returns the
document and actual INVALID report; it is never repaired into VALID.**

| Reviewed data | Existing M1 projection |
| --- | --- |
| Component identity | Safe explicit reference (e.g. R1) becomes Component ID; full M3→M1 sidecar map |
| Terminal | Hash-derived bounded Pin ID, exact component owner and reviewed role |
| Electrical group | Hash-derived bounded Net ID; explicit ground membership determines `is_ground` |
| Pin membership | Exactly one `Connection` per reviewed pin; sole canonical pin-net relationship |
| Accepted labels | Bounded hash-derived Label ID, exact text and existing net ID; detached rejected label retained in review only |
| Source image | `Origin.IMAGE`, `SourceImageReference` with original SHA/dimensions; never disguised as manual |
| Review revision | M1 metadata revision = correction revision; even electrically identical edits invalidate snapshot approval |
| Catalog | Preserve the exact original observation provider catalog version in M1 metadata; correction contract versions remain in the sidecar |
| Confidence / visual | MANUAL decision basis, null score, uncalibrated; empty original-pixel visual entities, no schema extension |

Ordering/IDs depend on exact source identities and sorted reviewed records, not
insertion order or time. Hash-ID collisions fail closed. All membership groups
are preserved, including wire-only groups; M1 may report islands/floating nodes.
No electrical group is discarded to obtain VALID.

`PromotionRecord` binds source/observation/topology, complete session/revision/
confirmation, promoted document and actual validation digests, contract version
and component/pin/net/label mapping tables. The full immutable context retains
original observation geometry/text/claim evidence and correction events: each M1
field/relation is traced through the mapping to initial proposals and explicit
review decisions. These extra records stay in a sidecar; M1 gains no ad-hoc fields.
The source identity includes normalized image/transform identity as well as bytes.

## Admission and the narrow existing M2 extension

`issue_image_admission(promotion, review, ...)` recomputes promotion and requires
the exact fresh complete VALID M1 result. It binds all preceding hashes, promotion
record digest, document/validation digests, M1 profile/ruleset and three M3E
contract versions. `ImageAdmissionContext` carries actual immutable source data,
review, promotion/report and admission, rather than a boolean/hash alone.

`verify_image_admission(document, context, validation=...)` rechecks the full
chain and exact supplied validation where present. Any source, observations,
topology, correction, confirmation, document/report, ruleset/version or binding
change refuses old admission. Verification never silently refreshes it.

Prompt 046 explicitly authorizes the previously deferred minimal M2 interface:
optional keyword `image_admission=ImageAdmissionContext` in existing eligibility,
export, circuit/representation approval and pure execution verification/composition.
The original image block remains without a valid exact context. The same restricted
exporter, model registry, warning policy and explicit approvals are used.

An image-bound `ApprovalEnvelope` adds optional `image_admission_sha256`, covered
by its digest and inherited by REPRESENTATION. EXECUTION already binds the exact
representation approval digest. Every downstream verification rechecks the current
admission. Manual calls retain the same signatures/default behavior and exact
existing digest projection; the optional field is omitted when null. Legacy
unbound image envelopes remain representable for compatibility but cannot export
with new admission. Admission is not an ApprovalEnvelope or ExecutionApproval.

**The actual runner is not extended or invoked in M3E.** Its default checks still
block image execution without context. M3F must thread the current context through
the existing complete-chain runner and separately verify real execution; no
alternate simulator path is authorized here.

## Persistence, safety and remaining scope

`dump_review`, `dump_promotion`, `dump_admission` use explicit canonical JSON and
stable digests. Loaders reject unknown fields/versions, duplicate keys, malformed
IDs, non-finite numbers and inconsistent bindings. Review archives are bounded
to 2 MiB and replayed against current actual inputs. `load_review` always returns
**unconfirmed** data, including when an archived confirmation is internally
consistent. Promotion/admission archives require an independently current live
confirmation/context; imported flags do not revive authority.

No file lookup, commands, provider, API, executable text or simulator is reachable
from correction payloads. Image-derived `.include`, `.lib`, `.model`, analysis
directives and path text remain inert observations; reference/label/quantity/source
corrections use bounded typed grammars. Model choice is sealed, not arbitrary text.

Prepared replay tests demonstrate domain transitions, not actual image-recognition
fidelity, human identity, held-out accuracy or simulation success. A technically
VALID but incorrectly reviewed circuit is still possible. Adding/removing arbitrary
components, broad missing-observation authoring, pose/CAD edits and undo UI remain
future review scope; incomplete/unsupported examples remain blocked. M3F owns
review UI, controller-held current context, runner handoff and actual LTspice
acceptance. Live Vision/OCR consent/provider evaluation and M3G closure remain
separate work. No M1 schema/validation, v0.1 behavior or packaging change.
