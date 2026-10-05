# Deterministic Validation and Review (Proposed / Not Implemented)

The rules below are a future implementation contract. They are not a validator added to v0.1. See the [Circuit JSON schema](circuit-json-schema.md) and [architecture](architecture.md). Validation checks consistency and some electrical hazards; it does not prove that the extracted circuit matches the image, has a valid operating point, or meets a design goal.

## Findings and Gates

| Category | Meaning | Proposed consequence |
| --- | --- | --- |
| `ERROR` | Known invalid/unsupported structure, value or configuration | Block generation and execution; correction required, no user override |
| `AMBIGUOUS` | More than one plausible interpretation or missing visual evidence | Block generation and execution; explicit typed decision and revalidation |
| `WARNING` | Non-blocking limitation/suspicion with a valid representation | Show during review; explicit acknowledgement before circuit review completes |
| `CONFIRMED` | A deterministic rule passed or a specific user decision was revalidated | Per-rule finding, not blanket proof of circuit correctness or permission to execute |

Every finding contains code, severity, target IDs, explanation and visual references when available. Reports are reproducible for the same canonical revision, ruleset and catalog. Warnings are not silently deleted. `warnings` is an index into report findings, not an independent diagnosis list.

## Structural and Electrical Rules

| Code | Deterministic check | Category / handling |
| --- | --- | --- |
| `SCHEMA_INVALID` | Closed shape schema, finite JSON numbers, valid enum/decimal form, bounded sizes and string lengths | ERROR; reject malformed input before assembly |
| `DUPLICATE_ID` | Unique device/pin/net/label/visual/finding/ambiguity IDs; globally unambiguous references; case-insensitive simulator device/name collisions | ERROR; no automatic renaming of electrical identities |
| `BROKEN_REFERENCE` | Every owner, pin ID, net ID, visual ref and warning ID resolves; ownership in both directions agrees | ERROR |
| `PIN_ROLES_INVALID` | R/C/L exactly a,b; V/I exactly positive,negative; MOS exactly drain,gate,source,bulk; no duplicates/unknown roles when ready | ERROR for contradiction; AMBIGUOUS for unknown mapping |
| `PIN_NET_INVALID` | A pin has at most one incidence; duplicate connection rows rejected; ready pins have exactly one net | ERROR for multiple membership; AMBIGUOUS for unresolved connection |
| `ORPHAN_DEVICE` | Device without its expected pins, ownerless pin, or device with no connected terminals | ERROR; repair/remove through review |
| `GROUND_MISSING` | Exactly one confirmed electrical ground net after accepted ground-symbol merging | ERROR for absent/conflicting ground; never infer ground from a nearby line |
| `MOS_BODY_UNRESOLVED` | Four roles known; bulk has a net; any implied 3-pin body tie supported by catalog and explicitly confirmed | AMBIGUOUS; do not silently tie bulk to source |
| `MODEL_INVALID` | MOS model exists in approved versioned local catalog, polarity matches, W/L positive and finite | ERROR for unsupported/conflicting model; AMBIGUOUS when model not selected |
| `SOURCE_INVALID` | V/I terminal identity and polarity/direction known; DC specified; typed source dimensions and parameter keys valid | ERROR for contradictory settings; AMBIGUOUS for missing polarity/value |
| `SOURCE_SAME_NET` | Both source terminals resolve to the same net, including a collapsed zero-V source | ERROR in this limited profile; review wiring rather than simulate a suspicious source |
| `SOURCE_CONSTRAINT_CONFLICT` | Parallel ideal V sources have inconsistent DC/waveform constraints; ideal V-source/inductor loops have incompatible potential sums | ERROR for proven inconsistency; WARNING for redundant constraints or nonlinear/analysis-dependent cases not decidable here |
| `ISOLATED_SUBNETWORK` | Connected components of typed incidence graph have no reference to accepted ground | ERROR when clearly unreferenced; WARNING for intentionally independent grounded branches, not automatic rejection |
| `FLOATING_DC_NODE` | Device-aware DC projection finds only C/MOS-gate/I-source attachments with no DC potential reference in a supported linear/gate-only region | ERROR for proven absence; do not use component ownership as conduction |
| `DC_REFERENCE_UNPROVEN` | Nonlinear/conditional device paths prevent a simple reference proof | WARNING; model and operating-point limitation visible; solver result remains a later check |
| `PASSIVE_BYPASSED` | Both passive terminals are the same net | WARNING; could be intentional but requires acknowledgement, no automatic deletion |
| `LABEL_UNRESOLVED` | Attachment lacks a confirmed net or multiple wires are plausible | AMBIGUOUS |
| `LABEL_CONFLICT` | Identical normalized label in flat scope attaches to separate unmerged nets; reserved ground name conflicts | ERROR; user must confirm merge or rename |
| `LABEL_ALIAS` | Different labels intentionally refer to one net | WARNING until primary emitted name/aliases are reviewed; not automatically an electrical conflict |
| `CROSSING_UNRESOLVED` | Cross/bridge/dot hypothesis has not been selected using visual evidence or user correction | AMBIGUOUS; union-find excludes that edge |
| `DANGLING_WIRE` | Segment end is neither a pin, accepted junction nor label endpoint | AMBIGUOUS for possible broken connection; WARNING only after explicit confirmation of an unused stub |
| `VALUE_INVALID` | Missing/non-finite/wrong-dimension/unsupported quantity; nonpositive R/C/L or W/L | ERROR for invalid input; AMBIGUOUS for OCR alternatives |
| `UNSUPPORTED_FEATURE` | Out-of-profile symbol, hierarchy, multi-page continuation, expression/behavioral source | ERROR; no partial export |
| `IMAGE_PROVENANCE_INVALID` | Image origin without source/hash; invalid pixel bounds or unsafe references | ERROR; manual origin may omit image but cannot claim image evidence |

Checks are analysis-aware where necessary. A capacitor's lack of DC conductance does not make every capacitor-only branch invalid; inspect the node reference, not just the component type. Multiple ideal constraints may require a solver and cannot be fully certified by a graph. First scope is conservative: uncertain diagnostics remain visible, and no convergence guarantee is made.

## Value and Source Rules

Use a finite grammar and Decimal normalization; no arbitrary evaluator. Record the original literal, selected grammar and normalized SI result. SPICE `M` is milli; ambiguous OCR/engineering suffixes prompt the user. Permit only explicit supported quantities, not arbitrary `.param`, function expressions, `.include` paths or model statements. Missing values never acquire hidden defaults.

SINE requires offset/amplitude in V or A and positive frequency in Hz. PULSE requires both levels, nonnegative delay and positive rise/fall/width/period; require rise + width + fall no greater than period in this MVP profile. AC magnitude is nonnegative and phase is explicit. Zero excitation is legal data but an AC request without a reviewed nonzero source produces a blocking condition-review error, not fabricated gain. Do not assume a source has AC=1 just because the desired measurement is gain.

## Ambiguity Model and Confidence

Examples include NMOS/PMOS alternatives, 1k/10k OCR, connected/unconnected crossing, uncertain label attachment, and unclear MOS pin roles. Keep the crop, candidate descriptions, target IDs, selected choice/manual note and revision-specific finding. A provider confidence number is not a calibrated probability.

Proposed score bands are **experimental UX thresholds**, not measured accuracy:

| Score / evidence | Future behavior |
| --- | --- |
| Null, uncalibrated, or conflicting critical evidence | Mandatory item review regardless of any global score |
| Below 0.60 | Do not assemble the uncertain field; ask for correction/better image. Unsupported/unreadable input is rejected at admission |
| 0.60 to below 0.98 | Show alternatives and block until explicit resolution |
| At least 0.98, calibrated on held-out style-specific fixtures, no contradictions | May prefill a candidate; any auto-accept into the draft is limited to noncritical visual metadata, never circuit/representation/execution approval |

Initially calibration is insufficient, so **automatic critical-field acceptance is disabled**. Junctions, pin roles, body ties, values and labels always receive circuit review. Do not average type/value/wire confidence into a score that erases a local ambiguity. Scores from different providers are not interchangeable. Rejection preserves evidence and permits re-upload; it never executes a guessed circuit.

## Review Actions and State Machine

1. Ingestion/extraction creates `draft`; imported state flags and approvals are discarded.
2. Fresh schema + semantic validation creates `blocked` if any ERROR/AMBIGUOUS remains; otherwise `ready_for_review`.
3. User compares the entire image/list/overlay, corrects items, confirms body/models/sources and acknowledges warnings. Validity must still hold on the current revision. Completion creates `reviewed` in app-controlled state.
4. Only `reviewed` permits neutral export and simulator preview generation. Raw vision cannot invoke an exporter, even if it emitted a plausible netlist.
5. User approves the exact preview. An app-managed representation approval binds circuit revision, original image hash (when present), electrical hash, model catalog/exporter versions, node mapping and generated base-artifact hash.
6. Existing request review and simulation-condition approval remain separate. Run requires both representation approval and the condition approval for the same circuit. API/image consents remain independent.

Every circuit/model/source/net edit increments revision, recomputes graph/findings and invalidates representation and simulation approvals. A new image invalidates image consent and circuit approval even if the resulting electrical hash happens to match. Analysis-condition edits invalidate simulation approval; they need not force re-extraction of an unchanged circuit. Derived execution copies may contain the explicitly approved analysis directive or sweep values; these do not mutate the canonical source.

Minimal review actions: confirm, change type/value, reconnect a pin, merge/split a net, assign label, add/remove component and choose model/source settings. All actions use typed forms and atomic referential updates, not executable model-returned patches. User confirmation cannot bypass a failed deterministic rule.

## Export / Runtime Failure Boundary

Export rechecks current hashes/validation/review. Repeated preview generation must be deterministic and must not run LTspice. Simulator failure, missing traces, unavailable metrics and non-finite data use the existing error/analysis paths. A successful run does not turn unconfirmed image evidence into a verified extraction. RAW/LOG and outputs retain their circuit/run revision association.

Future regression tests must prove that unresolved/error/stale/unapproved cases never reach the exporter or simulator. Generation permission, execution permission and cloud permission are separate assertions, not a single boolean copied from JSON.
