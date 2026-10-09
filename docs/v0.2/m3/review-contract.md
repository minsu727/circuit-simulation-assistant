# Human review and M1 conversion

**Future contract only.** [Candidate Contract](candidate-contract.md) owns records,
[Topology](topology-and-uncertainty.md) owns interpretation and
[Architecture](architecture.md) owns the unresolved M2 image-admission gate.

## Minimum proposed Streamlit interface

Desktop: original image and overlay on one side; components/values, terminal-net
table and unresolved issue queue on the other. Narrow layouts stack the panels.
Use stable IDs, text statuses and highlighted regions, not color alone. Overlays
and crops reference original pixels; provide the unmodified original view.

Use tables/selectors/atomic forms before an editable CAD canvas. Each issue shows
evidence, alternatives, affected components/pins and the current provisional
membership. Minimum actions:

- Select/correct component type, reference ID, value/unit/notation and supported
  source/model/W/L fields.
- Confirm or correct pose and explicit terminal roles; reconnect a terminal.
- Choose crossing connected/separated, accept a wire contact or reject a false
  observation; merge/split nets only with a before/after pin-membership preview.
- Confirm label attachment/equivalence, ground group and source polarity.
- Add a missing component/value/contact explicitly with provenance; reject a
  complete incorrect interpretation without forcing it into executable output.

No remote inference on rerun. No high-confidence item auto-accept. A full-snapshot
confirmation is enabled only after every critical claim has an explicit accepted,
corrected or justified rejected disposition and no unresolved required issue.
The final confirmation asks the user to compare the entire image and reconstruction;
it cannot prove that every missed element was detected.

## Review transactions and revision binding

Apply typed operations against an exact base candidate/review digest and revision.
Validate references and execute related changes atomically: replacing a component
type remaps/reviews owned terminal roles; removing a false component removes its
owned pins/contacts; net merges/splits update all affected assignments and labels.
Invalid patches preserve the previous snapshot and return an issue, not a
partially edited graph. Free-form notes are never executable patches.

Keep original observations immutable and preserve ordered event history. Undo is
a new event/revision, not history deletion or automatic approval restoration.
Stale callbacks, provider responses and concurrent tabs cannot apply to a different
revision. New extraction/image/transform invalidates previous confirmation even
if the picture appears similar.

Accepted field, connection, model/source choice or promotion-relevant evidence
changes invalidate confirmation, projected M1 validation and all downstream
approvals. Produce a new M1 document revision even when the electrical projection
is unchanged, so existing exact-snapshot approvals cannot be reused. View-only
zoom/selection does not change the accepted snapshot. Prior results retain their
old source/revision/evidence association and cannot be presented as current runs.

## Deterministic conversion prerequisites

The proposed pure converter consumes current CandidateCircuit, ReviewSnapshot
and explicit Confirmation; it returns PromotionResult. No provider, asset fetch,
network or simulator in conversion.

| Prerequisite | Refusal if absent / inconsistent |
| --- | --- |
| Original asset/observation/transform/catalog bindings | Stale or mismatched source/evidence; no document |
| Current explicit complete confirmation | Unconfirmed/rejected/stale snapshot; no document |
| Supported component/type/value/source choices | Unknown type, incomplete mandatory source/value/model/W/L; no partial document |
| Canonical accepted constraints | Multiple topology choices, separation conflict, missing/repeated pin membership |
| Explicit roles/ownership/ground/labels | Missing ground/polarity/bulk/attachment or unsafe/conflicting IDs |
| Selected scalar grammar/normalization | Unreadable, non-finite, unsupported expression/unit or literal/SI disagreement |

Assemble the current M1 fields exactly as specified in
[Candidate Contract](candidate-contract.md#proposed-projection-to-existing-m1).
No M1 schema/version changes; `connections` alone carries electrical membership.
Emit Origin.IMAGE and source digest/dimensions. Empty visual arrays and sidecar
evidence avoid expanding M1's geometry/confidence vocabulary. MANUAL confidence
basis means the relation was explicitly decided by the user, not that the
document originated without an image. Do not invent a calibrated score.

The proposed adapter verifies every projected entity/field/relation is accountable
to a disposition or explicit manual correction and keeps stable M3-to-M1 refs.
Identity/ordering normalization does not add an electrical fact.

## Existing validation and separate decisions

1. Conversion constructs a complete typed document; it does not declare VALID.
   Check current schema/typed loading/serialization consistency and call the
   unchanged `validate_document`. Preserve its actual issues, warnings, stages
   and deferred checks.
2. INVALID, AMBIGUOUS or UNVALIDATED blocks downstream work. Correction starts
   a new revision and revalidation; neither human confirmation nor confidence
   waives a technical finding.
3. VALID still does not establish image fidelity, external model availability
   or export permission. Current M2 **blocks image-origin export**. Until the
   separately authorized image-admission policy exists, show that boundary and
   make no representation/execution request.
4. Future admission must verify the actual source asset, review and promotion
   bindings before current explicit CIRCUIT_EXPORT review. Bind/recheck that
   evidence throughout subsequent M2 stages; a boolean “image reviewed” is
   insufficient.
5. Review exact restricted preview/maps/source/model choices, then explicitly
   grant REPRESENTATION. Separately choose target/reference/requested measurements
   and typed AC/TRAN/DC conditions, then explicitly grant EXECUTION.
6. Only the complete current chain reaches `run_ltspice_netlist`. It writes
   controlled copies, checks RAW/LOG and uses existing mapped analyzers. No
   alternate raw-netlist or ASC-renaming launcher is permitted.

Candidate confirmation, circuit approval, representation approval, execution
approval and remote image consent are distinct actions with distinct payloads.
This contract does not authenticate reviewers; trusted controller ownership and
future admission design must be separately established.

## Further refusal and persistence rules

Missing required source settings are not simulation conditions to invent later.
For example AC amplitude is a circuit source field, whereas AC start/stop is
a separate typed request. Changing either invalidates its relevant bindings.
Net names selected for target/reference are exact accepted IDs/maps; no silent
similar-name replacement.

A locally exported review bundle contains source/sidecar/projected-document hashes
and explicit retention disclosure. Loading that bundle is imported data, not a
trusted live confirmation or M2 approval. Recheck asset integrity and require a
current explicit review action. No persisted checkbox or imported reviewed
status automatically restores execution authority.

The future image-admission implementation is an M3E prerequisite requiring
separate review/authorization. Until resolved, M3E conversion-only acceptance can
pass while M3F execution and M3G full M3 closure remain blocked.
