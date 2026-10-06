# M2 Approval Contract — Proposed / Not Implemented

## Trust and Two Scopes

Use a separate frozen `ApprovalEnvelope` in future `circuit_ir/approval.py`; no new Circuit JSON field, WireValidationStatus or TechnicalState value. Only an explicit human action through a trusted application/test caller creates it. JSON imports, provider responses and archival approvals are ignored as authority. SHA-256 proves content binding, **not identity, authorship, authentication or an unforgeable human decision**. No account, key, signature, reviewer PII or timestamp system is planned.

The two proposed `ApprovalScope` values are `CIRCUIT_EXPORT` (reviewed circuit → preview) and `REPRESENTATION` (exact preview → eligible for separate condition review). A circuit envelope cannot authorize execution; a representation envelope cannot approve its own parent or analysis conditions.

| Envelope field | Contract |
| --- | --- |
| `contract_version` | Fixed `m2-approval-v1` |
| `scope` | CIRCUIT_EXPORT or REPRESENTATION |
| `approved` | Explicit native bool; must be true at the consuming gate, never inferred from presence |
| `document_id`, `document_revision` | Exact metadata identity/revision, not filename; revision equality alone is insufficient |
| `document_sha256`, `electrical_sha256` | Full reviewed snapshot and normalized electrical projection below |
| `validation_profile`, `validation_ruleset`, `validation_sha256` | Fresh report, initially `m1-local-v1`; hash the current report projection, not imported findings |
| `exporter_contract` | Approved target/format profile `m2-spice-v1`; implementation changes affecting output/gates require a new contract version |
| `model_registry_version`, `model_registry_sha256` | Exact trusted profile context displayed in review; empty registry is explicit `m2-no-models-v1`, not implicit lookup |
| `acknowledged_warning_ids` | Sorted unique fresh WARNING issue IDs; exactly the current warning set, not imported `warnings` or blanket waiver |
| `parent_approval_sha256` | Null for CIRCUIT_EXPORT; exact circuit-envelope digest for REPRESENTATION |
| `base_netlist_sha256`, `mapping_sha256` | Null for CIRCUIT_EXPORT; mandatory for REPRESENTATION |

All fields must be supplied, including nullable ones. Constructor checks are local shape/type/scope checks; fresh validation and application authorization occur in consuming APIs. A malformed envelope or unsupported version fails closed. No simulator state is stored here. Later M2E `ExecutionApproval` remains outside this IR envelope and binds current approved condition/trace choices as well as the representation.

## Snapshot Digest — Reuse M1 Serialization

Define `m2-source-digest-v1` as SHA-256 of `dump_document(document).encode('utf-8')`, including its final LF. Reuse the **existing** explicit M1 serializer: sorted object keys, ensure_ascii=true JSON escaping, indent=2, finite/native values only, original array order and literals. No second full-document serializer and no raw-file-whitespace hash for authorization. The digest is lowercase 64-hex; its algorithm version is part of this approval contract.

Include **all** CircuitDocument fields: IDs/revision/schema/catalog, original quantities, source configuration, connections, labels, confidence, visual evidence, image reference and imported archival validation state/warnings. Archival data does not authorize anything but is part of what the user reviewed. A snapshot change invalidates approval even if fresh electrical findings are unchanged. Raw JSON whitespace/object-key insertion order changes that load to the same typed snapshot do not invalidate it; array order changes do. This conservative rule follows actual M1 equality/round-trip behavior and avoids silent evidence exclusions.

## Electrical Digest — Existing Parent Projection, Not a New Wire Format

The parent [Circuit JSON hash contract](../circuit-json-schema.md#geometry-alternatives-and-revisions) already requires sorted normalized electrical hashing. Define a versioned **derived hash projection** `m2-electrical-digest-v1`, built from `document_to_dict(document)`, not another CircuitDocument serializer:

- Include `schema_version`, `metadata.catalog_version` and explicit electrical arrays `components`, `pins`, `nets`, `connections`, `labels` only. Sort each by exact ASCII ID; connections sort by `(pin_id, net_id)`. This operates only after valid IDs/incidence, never on a partial graph.
- Component projection: id/type, sorted owned pin_ids, value, model_ref, sorted parameter map and typed source. Quantity projection is `{si_value, unit}` with exact M1 SI-parser normalization; preserve null where permitted. Source projection includes DC, optional AC magnitude/phase, waveform kind and exact parameter map. Never infer omitted/null data.
- Pins: id/component_id/role. Nets: id/is_ground. Connections: pin_id/net_id only. Labels: id/scope/net_id and text trimmed with the same ASCII-only case identity used by M1; no fuzzy resolution or merging.
- Exclude visual refs, geometry, confidence, observation text, imported report/warnings, document ID/revision and image bytes/reference. Source/model selection still belongs to component fields. Registry identity is bound separately by the envelope.
- Encode the explicit projection as JSON with sort_keys=true, separators=(',', ':'), ensure_ascii=true, allow_nan=false; no trailing LF; UTF-8 → SHA-256. Projection version is included as a fixed `digest_profile` key. Never use reflection, Python repr, pickle or platform locale.

Electrical equivalence is useful for diagnostics; it never waives a different snapshot/revision/image or approval. This separate purpose preserves the parent's electrical/visual separation. Initial M2 manual admission has no image asset, and future image-origin admission needs explicit asset-content/review verification, not just this electrical hash.

## Fresh Report and Other Digests

`validation_sha256` hashes a versioned explicit native projection (`digest_profile=m2-validation-digest-v1`) of **all stored stable contract fields**: profile/ruleset/document_revision/technical_state, completed_stages in order, sorted skipped-stage pairs, deferred_checks in their deterministic order, and each issue's issue_id/severity/code/target_refs/entity_type/entity_id/field/provenance. Exclude message/suggested_action prose and redundant computed counts/blocking flags; a prose translation must not invent a new technical result. Existing M1 ordering/IDs are preserved, not re-sorted into a different result. Compact sorted JSON, no LF, UTF-8/SHA-256 as above. Hashing a supplied result does not prove it is fresh.

`approval_sha256` hashes all envelope fields using an explicit native projection including `contract_version`, enum values and nulls; the digest is derived, not a self-referential envelope field. `mapping_sha256` hashes `mapping_profile=m2-mapping-v1` plus complete sorted element/net/model ID-name pairs. Registry digest hashes its explicit version and sorted typed model-profile coefficients/polarities; no paths or raw model text. Base/execution netlist hashes cover **exact** UTF-8 bytes, including LF/newline. Digests are deterministic; there is no approval timestamp inside any hash or artifact comment.

## Verification and Invalidation

At review, compute fresh `validate_document(document)`, M2 preflight, mappings/model selection and current WARNING set. Display the actual circuit, fields and warnings. Only explicit approved=true with exact acknowledgement creates CIRCUIT_EXPORT. At export, recompute validation internally; match exact profile/ruleset/report revision, both document hashes, registry/exporter context and warning IDs. A caller-supplied `ValidationResult` or same-revision VALID flag cannot bypass this recomputation. M1 does not currently store a document hash in its result, so result equality/revision alone is insufficient.

After success, show the exact base text and mappings. An explicit second action creates REPRESENTATION referring to the circuit envelope and exact artifact/mapping hashes. Verify all parent bindings again at execution. The circuit envelope does **not** contain the artifact hash; representation approval is created only after generation. Base bytes contain no representation-approval digest; this prevents circular hashing.

| Change | Required invalidation |
| --- | --- |
| Component/value/source/net/pin/label/model/circuit edit | Increment revision; rerun graph/validation/preflight; invalidate both IR approval scopes and condition approval |
| Provenance/confidence/imported snapshot/order-only edit | New snapshot invalidates approval even if electrical digest/report match; trusted edit action increments revision |
| Same revision but different contents | Hash mismatch blocks; do not trust dishonest revision maintenance |
| Model registry/exporter/ruleset change | Revalidation/review/export/representation approval required; no automatic migration |
| Base netlist or mapping tampering | Representation mismatch blocks; regenerate through exporter and obtain new approval |
| Analysis/trace/point/measurement change | Invalidate execution approval; unchanged circuit/representation approval can remain |
| New image in a future image-enabled profile | Asset/snapshot/revision approval invalidation even if electrical hash matches |

Warning acknowledgement cannot override ERROR, AMBIGUOUS or [M2 blocked warnings](validation-boundary.md#warning-and-deferral-policy). It records review of an already eligible payload, never exemption authority. Bound envelopes live in application-managed evidence, not embedded in a provider's Circuit JSON.
