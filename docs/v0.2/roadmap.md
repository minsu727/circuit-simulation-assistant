# v0.2 Roadmap, Tests and Fixtures (Proposed / Not Implemented)

All milestones, datasets and acceptance criteria below are **planned**. No images, trained model, v0.2 validator, exporter or tests are added by Prompt 026. See the [architecture](architecture.md), [schema](circuit-json-schema.md) and [rules](validation-rules.md).

## Six Small Milestones

| Milestone | Deliverable | Acceptance criteria | Major risk |
| --- | --- | --- | --- |
| M1 — Circuit JSON + validation | Versioned schema, manual record editor/loader, native graph and deterministic findings | Six hand-authored circuit goldens plus at least one negative case for each blocking rule; repeatable reports, strict JSON, no simulator generation for invalid/ambiguous/stale records | Shape validation mistaken for electrical or visual correctness |
| M2 — Manual JSON to SPICE | Neutral device model, restricted exporter, approval envelope and separate netlist adapter | Reviewed divider, RLC and educational NMOS/PMOS goldens; repeatable export, exact terminal/model/value mapping; real LTspice AC/Transient/DC where applicable; original JSON unchanged; approval and v0.1 ASC regressions pass | Current executor/UI are ASC-specific; compatibility cannot be obtained by suffix renaming |
| M3 — Clean LTspice screenshots | Phase A catalog, local wire/pin extraction, candidate JSON with alternatives; optional text provider behind consent | Proposed 20-base-circuit benchmark processed; publish per-stage errors and pre-review metrics; every unresolved topology item blocks export; no invented hidden source/model settings | Missing dots/wires and high-confidence wrong extraction |
| M4 — Human review UI | Image/list overlay, ambiguity queue and typed edits | Correct all known benchmark errors through UI; merge/split/add/remove preserve references; edits invalidate approval; narrow layout usable; cloud consent independent | Corrections create new topology mistakes or stale approval reuse |
| M5 — End-to-end demo | Image → reviewed JSON → approved netlist → existing analysis/Summary | Repository-owned NMOS screenshot, AC and Transient through actual LTspice; compare emitted topology and metrics against authored circuit under matching conditions; preserve source hash, RAW/LOG, approval and failure evidence | Simulator success conceals a visually wrong but runnable circuit |
| M6 — Textbook-style expansion | Separate Phase B symbol/crossing profiles and repository-authored diagram fixtures | At least ten new authored base diagrams; evaluate on a separated hold-out group; retain Phase A results and blocking rules; no claim of handwriting support | Style-generalization failure, ambiguous crossing conventions and fixture provenance |

Finish one boundary before the next. M1/M2 allow meaningful progress without any vision provider. M3 may use a diagnostic candidate viewer; production review/editing remains M4. M2's simulation tests use reviewed manual JSON, so they do not bypass an image review that has not yet been implemented. M6 and hand-drawn Phase C are expansion work, not prerequisites for the first Phase A demonstration.

M5 tolerances must be declared before comparing results and tied to simulator/model/sweep/timestep settings. Existing [public NMOS references](../../examples/common_source_amplifier/README.md) are useful demo anchors, not universal acceptance constants. A new netlist route needs its own actual comparison; old ASC evidence alone cannot validate it.

## Future Test Pyramid — Eight Levels

| Level | Fixtures and assertions | Determinism / execution |
| --- | --- | --- |
| 1. Schema units | Missing fields, unknown keys, malformed quantities, invalid enums/coordinates, schema evolution, forged state | Local, no image/model/simulator |
| 2. Component/value parser | Expected pin roles, source units/polarity, SPICE m/M/Meg, OCR alternatives, dimensions, invalid expressions | Fixed literals and catalog version; no evaluator/network |
| 3. Graph validation | Pin ownership, same-net source, missing ground, isolated subnetworks, DC projection, labels, body, crossings and dangling wires | Hand-authored JSON and expected finding codes/severity/targets; permuting array order must not change meaning |
| 4. Synthetic images | Lines/dots/bridges, rotations/mirrors, gaps, text placement and resolution variants | Repository-authored graphics with known geometry and labels |
| 5. Clean LTspice screenshots | Authored ASC + screenshots + ground-truth JSON, including the public example | Capture recipe and simulator version; image fixtures do not require LTspice in every unit test |
| 6. Textbook-style diagrams | Owned clean diagrams with explicit crossing conventions | Deferred Phase B corpus; no copyrighted textbook scans |
| 7. Image to JSON E2E | Shape validity, component/value matching, partition/topology accuracy, unresolved-item blocking, review corrections | Recorded candidate-provider responses for deterministic contracts; live inference evaluated separately for variance |
| 8. JSON to simulator E2E | Approved export, actual topology/terminal mapping, RAW traces and deterministic metrics; originals unchanged | Opt-in installed LTspice tests; separate from synthetic/mock CI and from clean-machine package validation |

Keep many schema/graph tests and a small number of expensive inference/simulation checks. A frozen provider response proves downstream contracts, not real recognition quality. Live provider evaluations record provider/version, configuration, response and variation; repeated stochastic runs are not called deterministic merely because temperature is low.

Current v0.1 regression suite and actual integration evidence remain distinct. Future executable changes must rerun existing tests; real ASC regression is opt-in and may depend on local fixtures described in [Validation](../validation.md). Do not expand CI to install LTspice or use API secrets by default.

## Dataset / Provenance Strategy

Use repository-created synthetic circuits, screenshots of owned LTspice examples, and self-created textbook-style diagrams. Do not copy textbook scans, private coursework or unknown-license web images. Keep an authorship/provenance record; adding example provenance does not decide a repository-wide LICENSE.

Proposed initial benchmark: **20 base circuits**, not 20 claimed completed fixtures:

- Eight small passive R/C/L networks with sources and labels.
- Six NMOS/PMOS circuits with explicit reviewed model/body settings.
- Four wiring/source stress circuits: crossings, remote labels, source polarity and mirror/rotation variants.
- Two deliberately invalid circuits, such as missing ground and a collapsed source, with expected blocking findings.

Split by **base topology**, for example ten development, five calibration-study and five hold-out cases. Augmented crops/rotations/resolutions from one base stay in the same partition to prevent leakage. This small study is insufficient to establish reliable probability calibration or broad accuracy claims; keep critical auto-accept disabled and expand the corpus before trusting score thresholds.

Proposed future fixture layout:

```text
fixtures/circuit_images/<case_id>/
  input.png
  provenance.md
  expected.circuit.json
  expected-validation.json
  capture-settings.json
```

Ground truth is authored from a known circuit independently of extraction. Store expected components, terminal roles, net membership, ground/labels, source/model settings, and expected ERROR/WARNING/AMBIGUOUS/CONFIRMED outcomes. Ambiguous images include expected alternatives; goldens must not secretly force a choice the pixels cannot support. Review ground truth manually against the schematic/netlist before using it as an oracle.

Only owned input images, authored JSON and documentation belong in Git. Keep copied/generated ASC/netlists, model responses containing sensitive information, RAW/LOG, temporary crops and reports in ignored simulation/output areas. Capture with neutral titles and no personal paths, account information or private windows.

## Evaluation Metrics

Primary results should include numerators, denominators, partition and pre-/post-review status, rather than a single “AI accuracy” number.

| Metric | Definition / comparison policy |
| --- | --- |
| Component precision / recall | Correct one-to-one detected devices divided by detections / ground-truth devices. Match by type and agreed geometry overlap; distinguish correct detection from correct type/value |
| Value exact-match | Correct normalized quantity and unit / required ground-truth fields. Missing/unresolved is incorrect; also report literal OCR exact-match separately |
| Pin-to-net accuracy | Correct terminal memberships / required ground-truth terminals, after best **one-to-one** alignment of anonymous net IDs; missing pins count as wrong. Do not let a merged predicted net map to multiple true nets |
| Exact topology match — primary | Entire terminal-role-preserving net partition, ground and accepted label associations match; anonymous net renaming ignored. Compare component identity/type separately, and report combined electrical-model exact-match including values/models/sources |
| Invalid/ambiguous blocking — primary safety metric | Cases with ERROR/unresolved AMBIGUOUS that never reach exporter/simulator / all such cases. Track false acceptance separately; target zero on the authored adversarial set |
| Simulator-ready success — primary E2E metric | Cases that pass review/approval, produce the expected electrical model and successfully run the requested analysis / all eligible cases. Separate pre-review extraction from corrected success; solver success alone is insufficient |
| Human corrections — primary UX metric | Typed edits and unresolved items resolved per base circuit; distinguish confirmations, edits and re-uploads. If time is measured, document the study protocol rather than claiming productivity improvement |

For topology comparison, reduce nets to sets of stable `(component_id, terminal_role)` endpoints plus ground/label annotations. Sorting net IDs is not a sufficient test. Different equivalent wire segmentations may yield the same correct electrical graph. Report failures by symbol/value/wire/junction/body/label category so a high component recall cannot hide dangerous net errors.

Acceptance gates should first require correct schema, faithful goldens, full blocking, explicit approvals and source preservation. Recognition-rate targets are to be set after an actual baseline; the proposed threshold bands in [validation rules](validation-rules.md) are not benchmark results.

## Main Risks / Exit Criteria

- Visually plausible wrong topology: require full-image review and pin-partition goldens, not simulation success alone.
- Hidden source/model/body settings: manual explicit completion or block; no defaults invented by vision.
- Small/style-specific dataset: report scope, held-out partition and uncertainty; defer handwriting.
- Netlist adapter regressions: preserve ASC branch, model/node mapping and current deterministic algorithms.
- Cloud leakage/dependency weight: local path first, consent/crop preview and optional providers; no new API key requirements for core use.
- Scope growth into a CAD editor: table-based correction and netlist-first export; separate ASC layout work.

No implementation proceeds by weakening the [invariants](README.md). If a milestone cannot meet its gate, remain at that boundary and revise the proposal rather than labelling a guessed circuit simulator-ready.
