# M1 Data Model (Proposed / Not Implemented)

Use the exact field names of [0.2-draft1 Circuit JSON](../circuit-json-schema.md). Tables below specify future Python records, not new wire fields or implemented classes. All collection fields are immutable tuples; key/value collections become tuples of `(key, value)` pairs. ID references remain strings rather than recursive object pointers.

## Defaults and Construction

All parent-required keys remain required, including nullable keys. A missing key is not equivalent to an explicit null. Empty collections must be supplied explicitly; never add a ground, pin, model, source value or confidence score as a default. Optional value means the wire field may be null, not silently omitted. Constructors have no inference or file/network side effects.

`load_document` parses and shape-checks primitive JSON before building records. `validate_document` also guards directly constructed records; dataclass annotations alone do not enforce runtime types. Reject bool as an integer revision/coordinate/score, string-to-number coercion and unknown enum values. Runtime result defaults are permitted only for diagnostics: no issues/skipped checks before validation, `UNVALIDATED`, not `VALID`.

## Core Types and Fields

| Python record | Required fields (nullable marked `?`) | Default / invariant |
| --- | --- | --- |
| `CircuitDocument` | schema_version, metadata, source_image_reference?, components, pins, nets, connections, labels, visual, confidence, ambiguities, warnings, validation_state | No missing-key defaults. Frozen source document; graph/results derived separately |
| `Metadata` | circuit_id:str, revision:int, origin:manual/image, catalog_version:str | revision nonnegative; imported revision is data, not authorization |
| `SourceImageReference` | asset_id:str, sha256:str, width_px:int, height_px:int | Opaque ID; lowercase 64-hex hash and positive dimensions. M1 does not fetch/open the asset |
| `Component` | id, type, pin_ids, value?, model_ref?, parameters, source?, visual_ref? | References only. Type controls legal quantity/source/model fields |
| `Pin` | id, component_id, role, visual_ref? | Globally unique pin ID; one owner; role separate from ID/display name |
| `Net` | id, is_ground:bool | No connected_pins storage. NetRole is a derived view of is_ground |
| `Connection` | pin_id, net_id, visual_refs, confidence | Sole pin-to-net assignment; at most one row per pin |
| `Label` | id, text, scope, net_id?, visual_ref? | scope=flat. Null attachment is unresolved; aliases remain separate label records |
| `Quantity` | literal:str?, si_value:str?, unit, grammar | Original text retained. Decimal interpretation is derived, never a stored float |
| `SourceConfiguration` | dc:Quantity?, ac:ACConfiguration?, waveform:Waveform | Explicit DC including zero; no raw expression string |
| `ACConfiguration` | magnitude:Quantity, phase:Quantity | V/A magnitude nonnegative; phase in degrees |
| `Waveform` | kind, parameters | none→empty; sine/pulse require exact typed key sets |
| `VisualProvenance` | coordinate_space, entities | coordinate_space=original_pixels; no image processing |
| `VisualEntity` | id, kind, bbox?, position?, orientation, points, text?, method, confidence | Retains catalog pose/observations; not electrical terminal order |
| `BoundingBox` | x, y, width, height | Internal convenience record for the four-number wire array; finite, nonnegative, bounded by source dimensions when present |
| `PixelPoint` | x, y | Two-number wire array; finite/nonnegative; image dimensions checked structurally |
| `Confidence` | score:number?, basis, calibrated:bool | Score finite in [0,1] or null; no default probability or approval |
| `Ambiguity` | id, kind, target_refs, candidates, state, selected_candidate_id?, resolution_note? | Unresolved blocks. Resolution references a candidate or nonempty manual note |
| `Candidate` | id, description | Text for display only; not a patch, type guarantee or executable command |
| `ImportedFinding` | id, code, severity, target_refs, message, visual_refs | Exact parent finding keys; imported report is not validation evidence |
| `ImportedValidationState` | status, validated_revision?, ruleset_version?, findings | Exact wire validation_state snapshot; fresh result is independent |
| `ValidationIssue` | issue_id, severity, code, message, target_refs, entity_type?, entity_id?, field?, suggested_action?, blocking, provenance | Runtime-only enriched diagnosis; exact contract in [Validation Plan](validation-plan.md) |
| `ValidationResult` | profile, ruleset_version, document_revision?, technical_state, issues, completed_stages, skipped_stages, deferred_checks | Fresh deterministic report; no approval flag and no execution permission |
| `LoadResult` | document?, issues | Parse/shape failure gives no document; cannot build a partial typed circuit |
| `GraphBuildResult` | graph?, issues | Broken prerequisites give no graph; no skipped or guessed edges |
| `ValueParseResult` | quantity?, issues | Invalid input gives no quantity, never zero/default |

`warnings` in CircuitDocument contains IDs into the imported finding snapshot. Fresh warnings are selected from ValidationResult issues. Do not copy imported warnings into fresh results or mutate canonical connections to fix findings. Definition IDs are globally unambiguous across the document's electrical/visual entities, labels, ambiguities and imported findings. Candidate IDs are local to their containing ambiguity for selected_candidate_id and cannot be bare target_refs. Fresh result issue IDs belong to a separate report envelope. Validate reference namespace explicitly, not by blindly searching any string in any array.

## Enums — Keep Them in models.py Initially

| Enum | Values / mapping |
| --- | --- |
| `ComponentType` | resistor, capacitor, inductor, voltage_source, current_source, nmos, pmos, unknown |
| `PinRole` | a, b, positive, negative, drain, gate, source, bulk, unknown. Do not add a redundant PinType |
| `IssueSeverity` | ERROR, WARNING, AMBIGUOUS, CONFIRMED |
| `WireValidationStatus` | draft, blocked, ready_for_review, reviewed; imported snapshot only in M1 |
| `TechnicalState` | UNVALIDATED, INVALID, AMBIGUOUS, VALID; fresh M1 result, not a replacement wire enum |
| `NetRole` | GROUND/NORMAL, derived from is_ground; not another persisted field |
| `WaveformKind` | none, sine, pulse. V/I distinction already belongs to ComponentType; no redundant SourceType |
| `ValueGrammar` | spice, si, manual, unresolved |
| `ConfidenceBasis` | provider_score, heuristic, manual, unknown |
| Supporting closed enums | Origin, VisualKind, Orientation, AmbiguityKind and AmbiguityStatus match the parent schema exactly |

## Supported Devices and Pin Schemas

| Component | Expected roles | Required configuration |
| --- | --- | --- |
| Resistor | a,b | Positive finite ohm value; no source/model/width/length |
| Capacitor | a,b | Positive finite F value; no source/model/width/length |
| Inductor | a,b | Positive finite H value; no source/model/width/length |
| Voltage source | positive,negative | Source DC/AC/waveform in V; positive-minus-negative voltage convention |
| Current source | positive,negative | Source in A; current flows positive→negative |
| NMOS / PMOS | drain,gate,source,bulk | Positive width/length in m; model_ref selected; catalog existence/polarity lookup deferred |

The order of `pin_ids` does not infer roles. `M1.p1` could be a gate if its explicit role says gate; `.gate` is a useful naming convention, not a parser rule. There is no extra required pin name field. Orientation belongs only to visual provenance. Three-pin MOS is not expanded by tying body automatically.

Ground/wire/net label remain structural entities. Diode, BJT, op amp and dependent sources are unsupported: raw type strings fail the enum/schema; a draft may use `unknown` with preserved visual text and explicit ambiguity. Unknown with an unresolved type decision is AMBIGUOUS; unknown without a pending decision is ERROR. Neither case is dropped, exported or accepted merely because its description resembles a known device.

## Canonical Nets and Labels

Use opaque net IDs, including unlabeled nets. No M1 simulator-name allocation or automatic net merging is required. Exactly one accepted net has is_ground=true; any number of ground visual marks can refer to it in later reconstruction. M1 never creates ground from label `0` or from coordinates.

Compare accepted labels using trimmed ASCII case-insensitive identity in flat scope. Preserve original spelling in records; do not fuzzy-match. Same normalized name on different nets is LABEL_CONFLICT. Different labels on one net are aliases with LABEL_ALIAS warning; choosing an emitted primary name belongs to later review/export. Whitespace-only labels and reserved ground-name conflicts are invalid. Connections remain authoritative; net membership queries return sorted derived pin IDs.

## Value Parsing Contract

Proposed API takes the literal, expected unit and explicit grammar; it does not infer units from a component name. Parse an optional sign, finite decimal mantissa/exponent and at most one SPICE suffix. Trim only outer whitespace for parsing while preserving the original literal. Longest suffix match first; suffixes are case-insensitive.

| Input, grammar=spice | Exact SI value | Note |
| --- | --- | --- |
| 1k / 2.2k | 1000 / 2200 | k is kilo |
| 10u / 4.7n | 0.00001 / 0.0000000047 | ASCII u and n |
| 1Meg / 1MEG | 1000000 | Explicit mega |
| 100m / 1M | 0.1 / 0.001 | M is milli, not mega |
| 1p / 1f / 1G / 1T | 1e-12 / 1e-15 / 1e9 / 1e12 | Supported finite suffix set |
| -2.5 / 1e3 | -2.5 / 1000 | Sign allowed syntactically; device rules decide legality |

`si` and `manual` permit plain decimal/exponent input only; prefixes use the explicitly selected spice grammar. Reject internal whitespace, trailing unit text such as `1kOhm`, Unicode μ, malformed numbers, empty strings, NaN/Inf, `1kk`, `1/2`, `{R}`, functions, statements and path/directive text. This is a deliberately finite subset, not a full SPICE expression parser. Unresolved OCR alternatives produce an ambiguity, not expression evaluation.

Preserve `literal` + normalized decimal string + explicit unit + grammar. Use exact decimal-tuple exponent shifts, never `float` or default-context Decimal.normalize/multiplication that could round long coefficients. Normalize parsed zero to `0`, trim insignificant zeros exactly, and use a deterministic decimal/scientific representation that fits the parent 128-character limit. Reject overflow of that output limit rather than truncate. Keep numeric exponent magnitude within 300 in the M1 resource profile; this is a bounded parsing limit, not a physics claim. Test long coefficients beyond default Decimal precision.

When loading an existing Quantity, check literal/SI consistency for supported selected grammars without overwriting either field. A mismatch is VALUE_INVALID. Null required SI data is invalid/missing or explicitly ambiguous. Zero/negative R/C/L and W/L fail device rules, while signed DC values and explicit source zero can be valid. Fraction conversion for DC constraints uses already bounded Decimals and produces no new float fields.

## Confidence Contract

The confidence object is parent-required; score may be null. Missing object/keys is SCHEMA_INVALID. A manually authored fixture with null score and basis=manual is not ambiguous solely for lacking vision confidence. An explicitly unresolved choice or incomplete connection still blocks it.

Retain existing confidence locations: document summary, connections and referenced visual entities. Do not add component/value confidence keys to the closed schema. Per-component/per-field views resolve their visual references; absence of evidence is unknown, not 1.0. Imported calibrated=true is merely a declared flag, not calibration proof. M1 never auto-accepts critical inference based on a score; pending inferred fields with unknown/uncalibrated confidence require review. Existing 0.60/0.98 bands remain future UX policy, not measured accuracy or solver authorization.

## Serialization and Versioning

- Retain `schema_version=0.2-draft1`; ruleset/profile names are separate. Unsupported versions fail closed, without automatic migration.
- Use UTF-8 standard JSON, reject duplicate object keys and NaN/Infinity/non-finite numeric overflow, and emit allow_nan=false.
- Unknown keys fail the bundled closed schema. No coercion, omitted-null expansion or arbitrary object serialization.
- Sort object keys for reproducible dumps; preserve array order and original literals/decimal strings for archival round-trip. Derived graph/report ordering is separately canonicalized by IDs.
- Explicit wire projection converts enums to their values and tuples to arrays; no recursive object references, pickle, filesystem access or provider calls.
- Round-trip criterion: load→dump→load preserves all semantic records, references, unresolved items and provenance; whitespace/object-key order may change. Failed loading does not modify the source.
- Imported validation snapshots can be retained as **untrusted archival data** in lossless round-trip. Validation always creates a separate fresh result. Runtime ingestion in later integration must reset/discard stale authorization; never treat an archival reviewed flag as human approval.
- Do not implement electrical hash/approval tokens or version migrations in M1. Stable serialization bytes are not a ready-made approval mechanism; later hashes use the parent normalized electrical projection.

## Conflict Accounting

No new fields are added to the parent closed schema. Enriched runtime issues, TechnicalState and profile/deferred information live in a separate result envelope. The full model-catalog rule remains deferred as described in [M1 scope conflicts](README.md). Original wire statuses, issue codes, model_ref and canonical connections stay unchanged.
