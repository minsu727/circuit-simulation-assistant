# M3 candidate contract

**Proposed typed sidecar; no records/schema implemented.** This contract is separate
from [M1 data types](../m1/data-model.md), especially the existing M1 `Candidate`
record, which contains only an ambiguity ID/description. Do not extend that
record into a Vision response.

## Three layers

1. **Observations:** immutable recorded symbol/text/line/dot/terminal proposals
   and source locations. A “wire” detection is itself an observation hypothesis.
2. **Candidate claims:** explicit inferred type/value/pose/role/contact/label
   alternatives, each linked to evidence. They are not canonical connections.
3. **Reviewed snapshot:** only explicitly accepted or manually corrected choices;
   derived topology is reproducible from dispositions. Confirmation is not an
   M1 technical state or any M2 approval.

Separate collection ownership prevents a provider from overwriting human edits.
No object references back to parents; use bounded IDs and immutable snapshots.
The planned namespace is a separate `circuit_image` package, not `circuit_ir`.
Names below describe future responsibilities, not a frozen public Python API.

## Minimal proposed records

| Record / view | Required information |
| --- | --- |
| ImageAsset | Local opaque asset ID, SHA-256 of original bytes, media type, decoded dimensions; no source path/URL |
| ImageTransform | Working image digest/dimensions, versioned operation parameters, forward/inverse original-pixel transform; interpolation/crop policy |
| ExtractionProvenance | Extraction ID, adapter/schema/catalog/prompt versions, provider/model identifiers when supplied, transmitted image digest; unknown version explicit |
| ObservationSet | Asset/extraction/transform references; immutable symbol, text, terminal, wire-segment and junction observation collections |
| Observation | Locally assigned stable ID, kind, bbox/points in original pixels, raw text if relevant, bounded alternatives, producing method and score metadata |
| Claim | Stable ID, typed claim kind/target refs, finite alternatives with typed payloads, supporting/contradicting observation refs, nullable score/basis and uncertainty/reason per claim |
| CandidateCircuit | Candidate ID/revision, source and observation-set digests, component/terminal hypotheses, claims, conflicts, assembler/catalog versions |
| CandidateGraphPreview | Derived terminal/conductor groups and alternatives; not another stored authoritative pin-to-net relation |
| ReviewEvent | Event ID, base candidate/review digest and revision, action/target/alternative IDs, typed manual patch, evidence refs and disposition note |
| ReviewSnapshot | Current candidate digest, ordered event IDs, chosen claims/corrections, unresolved issue IDs, monotonically increasing review revision |
| Confirmation | Explicit current-snapshot decision plus digest, source/transform/catalog bindings and complete critical-claim coverage; no approval scope |
| PromotionResult | Either complete current CircuitDocument + M3-to-M1 reference map/binding, or issues and no document; never a partial executable graph |

Observation payloads and Claim alternatives must be a **closed tagged union**:
symbol/type/pose; text/value/unit/notation; terminal role; conductor contact or
separation; junction interpretation; label attachment/equivalence; ground and
source polarity; explicit model/source/parameter choices. No raw patch code,
arbitrary JSON field paths or netlist strings. Exact wire keys will be reviewed
with M3B fixtures before M3C implementation.

Type alternatives distinguish a supported current M1 component type from
UNKNOWN/UNSUPPORTED with bounded observed-name text. This preserves an observed
BJT/op-amp/unknown region for abstention and correction without adding executable
M1 device types or rejecting away all evidence of unsupported content.

Use JSON-compatible native fields and references, not recursive object graphs or
NumPy arrays. Confirmed SI values are exact bounded decimal strings; confidence
and geometry are finite native numbers. Required/null semantics, enums and
unknown-field rejection need an explicit M3C wire contract, not reflective dumping.

## IDs, ordering and evidence

Local code allocates safe opaque IDs; provider IDs are untrusted names remapped
inside one extraction. Observation IDs stay stable across review, never renumber
when a table is sorted. A new extraction has a new identity and cannot inherit
old confirmations by matching labels/boxes approximately.

Each reviewed field/relation maps to a claim and its observation or explicit
manual event. A manual addition needs an operation note distinguishing missing
image content from a user-added circuit element. Alternatives are mutually
exclusive choices, not simultaneous graph rows. Contradictory evidence stays
visible after resolution.

Original coordinates use the stored decoded raster before EXIF orientation:
top-left origin, x right, y down. Record EXIF/display/crop/scale/deskew transforms
explicitly. Provider coordinates identify their transmitted frame and are mapped
back before storage; missing/ambiguous frame identity blocks assembly. Points
must be within original dimensions and boxes must fit completely. Review display
overlays apply the matching display transform, never an assumed frame.

Sort deterministic derived views by stable IDs. Original observation order can
remain archival; accepted ordering/ID allocation uses a versioned documented
policy. Canonical net IDs derive from sorted accepted conductor/terminal
membership, not coordinate proximity or OCR label spelling. Member changes
invalidate affected net identities/maps and downstream confirmation.

## Confidence and proposed candidate states

Score is nullable, bounded and finite; include basis/method and whether calibration
has actually been demonstrated. Do not treat provider scores as probabilities
or synthesize scores for providers which supply none.

| Candidate state | Meaning |
| --- | --- |
| DRAFT | Observations/claims exist; no complete confirmation |
| NEEDS_REVIEW | Missing/competing/unsupported required interpretation |
| CONFIRMED | Explicit current complete snapshot confirmation; not VALID/exportable |
| REJECTED | User rejected the interpretation; retained for provenance, no promotion |

State is derived from current content/dispositions and confirmation. These names
are M3-only proposals, not additions to M1 TechnicalState or ApprovalScope.
Malformed intake/response is a failure result without a fabricated candidate.
Unsupported real devices remain blocking; rejecting a false detection is not
permission to delete a real unsupported device from the circuit.

## Proposed projection to existing M1

| Accepted M3 material | Existing M1 field / rule |
| --- | --- |
| Source | Origin.IMAGE, SourceImageReference(asset ID, original digest, dimensions), schema_version `0.2-draft1` |
| Identity | Stable circuit ID; new metadata.revision for every promotion-relevant accepted revision; catalog_version identifies confirmed symbol catalog |
| Components | Exact supported ComponentType, safe ID, explicit pins, accepted Quantity/source/model/width/length |
| Terminals | Pin.component_id and explicit PinRole; visual position is not electrical ordering |
| Net groups | Net IDs and exactly one explicitly selected ground group |
| Pin membership | One Connection per required pin; sole canonical assignment |
| Label choices | Explicit attached flat labels under M1's trimmed ASCII case-insensitive identity; retain spelling, no fuzzy matching |
| Evidence mapping | M3 sidecar map from each M1 entity/field/relation to accepted claim and source evidence |
| Confidence | Accepted decision basis MANUAL, score null unless explicitly meaningful; never provider probability masquerading as approval |
| Imported status | DRAFT, no fresh-report/approval claims; ambiguities/warnings/findings empty after sidecar resolution |

Keep rich pixel/score/provider/review material in the M3 sidecar. First projection
uses empty M1 visual entities, null component/pin/label visual refs and empty
Connection.visual_refs; source identity remains present. Existing visual fields
need no schema expansion. If later a small visual subset is projected, every
reference/coordinate must satisfy the existing schema and provenance rules.

For printed literals incompatible with the M1 scalar grammar, retain exact text
in M3 and record the explicit accepted normalization. M1 Quantity.literal is
then the legal confirmed scalar actually passed to `parse_quantity`; its SI
string/unit/grammar must agree. Never pretend the normalized literal was the
original OCR text.

The promotion binding records original/working/transmitted image digests,
candidate/observation/review/confirmation digests, converter/catalog versions,
M3-to-M1 refs and exact M1 document digest. Hashes detect stale content, not
authenticated consent. Evidence retained only locally by default.

Prerequisites, failure handling and future admission are specified in
[Review Contract](review-contract.md) and [Architecture](architecture.md).
