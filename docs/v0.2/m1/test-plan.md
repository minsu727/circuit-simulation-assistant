# M1 Test and Fixture Plan (Proposed / Not Implemented)

No tests or fixture files are created here. All states below mean fresh **m1-local-v1** technical state, not human approval or simulator readiness. The [validation pipeline](validation-plan.md) determines prerequisites, severity precedence and suppression.

## Fixture Authoring Rules

Plan **38 fixture cases: 8 valid, 20 invalid, 10 ambiguous**. These are JSON records, not the separate future 20-image benchmark. Each future case stores a complete authored `circuit.json` and `expected.json` with profile, state, required/forbidden findings, target IDs and completed/skipped/deferred checks.

Start from independently reviewed manual circuits with explicit values, roles, source settings and ground. All confidence objects are explicit; normal manual records use null score/basis=manual. MOS records provide positive W/L and a symbolic model_ref; no model file lookup is performed. Author expected topology and reports before running the implementation; do not generate goldens by copying actual validator output.

Each invalid/ambiguous case makes the described controlled edit while preserving unrelated valid fields. Below are **required root codes**; final authored expected reports also enumerate all applicable warnings and skipped/deferred checks. Do not make assertions on exception strings, timestamps or accidental list ordering. Catalog deferral and DC_REFERENCE_UNPROVEN are recorded for applicable MOS cases, not mistaken for failures.

## Valid Fixtures — 8

| ID / future case | Purpose | Expected state | Required issue codes |
| --- | --- | --- | --- |
| V01 resistor_divider | Explicit V source, two resistors, vin/vout labels and one ground | VALID | No blocking findings |
| V02 rc_low_pass | Capacitor output with a genuine R/V DC-reference path | VALID | No blocking findings; no FLOATING_DC_NODE |
| V03 rlc_network | R/L reference edges and C open behavior without confusing incidence and conduction | VALID | No blocking findings |
| V04 current_source_load | Positive→negative source direction and resistor-ground reference | VALID | No blocking findings |
| V05 nmos_common_source | Four roles, explicit body, R load, bias source and W/L | VALID | CHECK_DEFERRED for model lookup |
| V06 pmos_current_source | PMOS body/source connection explicit; nonlinear drain reference not solved | VALID | CHECK_DEFERRED, DC_REFERENCE_UNPROVEN where path is conditional |
| V07 nmos_differential_pair | Two ordinary four-terminal MOS devices and tail current source; no new primitive | VALID | CHECK_DEFERRED, DC_REFERENCE_UNPROVEN for conditional tail path |
| V08 equal_parallel_dc_sources | Equal ideal voltage constraints, distinct terminals, resistor load | VALID | SOURCE_CONSTRAINT_CONFLICT as WARNING for redundant constraints, not ERROR |

The differential pair is only a connectivity representation, not a transistor operating-point or analog-performance validation. No expected gain/current result is stored.

## Invalid Fixtures — 20

| ID / future case | Controlled fault / purpose | Expected state | Required issue codes |
| --- | --- | --- | --- |
| I01 duplicate_component_id | Duplicate a component definition; never last-write-wins | INVALID | DUPLICATE_ID |
| I02 duplicate_pin_id | Two terminal definitions share one identity | INVALID | DUPLICATE_ID |
| I03 missing_ground | All nets have is_ground=false; skip derived reference complaints | INVALID | GROUND_MISSING |
| I04 conflicting_grounds | Two distinct nets marked ground | INVALID | GROUND_MISSING |
| I05 missing_resistor_role | Remove b from pin records, owner pin_ids and connections consistently | INVALID | PIN_ROLES_INVALID |
| I06 unknown_net_reference | Connection points to an undefined net | INVALID | BROKEN_REFERENCE |
| I07 duplicate_connection | Repeat the same pin→net row | INVALID | PIN_NET_INVALID |
| I08 pin_in_two_nets | Assign one pin to two existing nets | INVALID | PIN_NET_INVALID |
| I09 voltage_source_short | Both V terminals mapped to one net | INVALID | SOURCE_SAME_NET |
| I10 current_source_short | Both I terminals mapped to one net | INVALID | SOURCE_SAME_NET |
| I11 orphan_device | Add a resistor with zero pins, valid value and no owned pin records | INVALID | ORPHAN_DEVICE; no duplicate role-count root error |
| I12 conflicting_labels | Same trimmed/case-normalized label assigned to distinct unmerged nets | INVALID | LABEL_CONFLICT |
| I13 floating_capacitive_node | Node attached only by capacitors, no R/L/V DC path, otherwise grounded circuit | INVALID | FLOATING_DC_NODE |
| I14 isolated_resistor_island | Separate resistor/pin/net island alongside a valid grounded circuit | INVALID | ISOLATED_SUBNETWORK; suppress duplicate floating root |
| I15 negative_resistor | Negative finite resistance with selected grammar | INVALID | VALUE_INVALID |
| I16 wrong_capacitor_unit | Capacitor quantity in H instead of F | INVALID | VALUE_INVALID |
| I17 pulse_timing_conflict | rise + width + fall exceeds period | INVALID | SOURCE_INVALID |
| I18 conflicting_parallel_dc | Distinct-terminal parallel V constraints disagree exactly | INVALID | SOURCE_CONSTRAINT_CONFLICT as ERROR |
| I19 raw_unsupported_type | Raw type=diode, outside the unchanged enum | INVALID | SCHEMA_INVALID; no partial document |
| I20 broken_warning_reference | Imported warnings points to a nonexistent imported finding | INVALID | BROKEN_REFERENCE; stale report does not become fresh evidence |

## Ambiguous Fixtures — 10

| ID / future case | Unresolved data / purpose | Expected state | Required issue codes |
| --- | --- | --- | --- |
| A01 mos_role_unknown | A MOS terminal role is unknown, references otherwise valid | AMBIGUOUS | PIN_ROLES_INVALID as AMBIGUOUS |
| A02 mos_body_unconnected | Explicit bulk pin exists but has no incidence | AMBIGUOUS | MOS_BODY_UNRESOLVED; no duplicate generic pin-net root |
| A03 unknown_type_pending | Type=unknown with explicit unresolved symbol_type choice | AMBIGUOUS | UNSUPPORTED_FEATURE as AMBIGUOUS |
| A04 pin_connection_pending | Known R pin lacks a connection record | AMBIGUOUS | PIN_NET_INVALID as AMBIGUOUS |
| A05 label_attachment_pending | Label net_id=null | AMBIGUOUS | LABEL_UNRESOLVED |
| A06 crossing_pending | Authored junction evidence and explicit unresolved crossing record | AMBIGUOUS | CROSSING_UNRESOLVED; no geometry-driven merge |
| A07 source_dc_missing | Source dc=null rather than an explicit zero | AMBIGUOUS | SOURCE_INVALID as AMBIGUOUS |
| A08 value_ocr_alternatives | Unresolved quantity with 1k/10k choice and null normalized value | AMBIGUOUS | VALUE_INVALID as AMBIGUOUS; no expression evaluation |
| A09 mos_model_missing | MOS model_ref=null, roles/W/L otherwise complete | AMBIGUOUS | MODEL_INVALID as AMBIGUOUS |
| A10 critical_confidence_unreviewed | Synthetic provider-score/uncalibrated connection without explicit review | AMBIGUOUS | CONFIDENCE_REVIEW_REQUIRED; manual fixture authoring does not imply the inferred item was reviewed |

A06 uses manually authored visual records with null geometry, not a real screenshot or Vision output. A10 uses synthetic confidence metadata, not a provider call or calibration measurement. Neither requires an image decoder. Raw unsupported type and unresolved unknown type are intentionally distinct tests.

## Module Matrix — Approximately 96 Scenario Groups

Counts are planning budgets, not a passed test count. Data-driven groups may contain multiple subcases; actual unittest method count must be recorded after implementation rather than inferred from this table. No coverage quota is achieved by duplicating assertions.

| Future test module | Budget | Happy path | Boundary | Failure | Round-trip / repeatability |
| --- | ---: | --- | --- | --- | --- |
| test_circuit_ir_models.py | 8 | All record/enums and field mappings | Explicit null versus missing, manual confidence, tuple collections | Direct bad construction caught at validation, bool versus int | Immutable copies and complete nested projection |
| test_circuit_ir_schema.py | 10 | Parent example and each $defs shape | Version, coordinate/score limits, resource bounds, required nullable keys | Unknown field/enum, duplicate JSON keys, non-finite input, malformed structure | Bundled-schema equivalence and load/dump/load |
| test_circuit_ir_values.py | 14 | Required literals and suffix families | M/m/Meg, zero/sign, long coefficients, exponent/output-length limit | Empty/junk/expression, unit mismatch, literal/SI inconsistency | Exact literal preservation and Decimal equality |
| test_circuit_ir_graph.py | 12 | Incidence/ownership/net-members, R/L/V DC paths | Unlabeled nets, aliases, reordered arrays, equivalent IDs not coordinates | Duplicate definitions/broken references/multiple incidence with no usable graph | Sorted views unchanged by serialization and harmless geometry changes |
| test_circuit_ir_validation.py | 40 | 8 valid goldens; profile-local validity | 10 ambiguous goldens; two composite precedence/non-cascade cases | 20 invalid goldens and skipped-stage contracts | Repeat validation identical; document byte/semantic content unchanged |
| test_circuit_ir_serialization.py | 12 | Full nested JSON records and result envelope | Unicode text, original decimals, empty/null data, imported snapshots | Unknown version, illegal constant, mutable/object recursion, result fields inserted into closed document | Semantic round-trip, deterministic key order, no approval mutation |
| **Total planned** | **96** | Includes all 38 fixture states | No LTspice/cloud/image requirement | No blanket skip or expected-output generation | No completed implementation claim |

`__init__.py` needs an import-isolation assertion within model tests: importing circuit_ir must not import Streamlit/app, perform IO or contact a network. Bundled schema is meta-validated once and compared against the parent's proposed schema rather than drifting into a second contract. Graph/value helpers and validation must be exercised through their public APIs, including directly constructed models.

Table groups use additional subcases for rules not needing a standalone fixture: unknown owner/visual/candidate refs; unsupported unknown without pending decision; whitespace/reserved labels and aliases; positive R/C/L/W/L limits; non-MOS model/source fields; SINE/AC dimensions; passive bypass; resolved ambiguity with nonexistent candidate; malformed image-origin/hash/dimensions; explicit unused stub; forged reviewed snapshot; low/high confidence with a hard source-short ERROR. Stage/prerequisite assertions belong beside the rule, not in a separate mirrored implementation.

## Deterministic Golden Assertions

- Every fixture has an independently authored expected profile, state, root targets, severity and required/forbidden codes. Include complete fresh warnings/skips/deferrals after reviewing the planned stage contract; do not loosen matches to “some error occurred.”
- Compare report logical fingerprints, not incidental prose translations or raw schema index paths under array permutations.
- Apply array permutations and visual-coordinate changes to valid fixtures: electrical topology must stay the same. A changed explicit connection must change the graph/report when meaningful.
- For failures, preserve the source and prove no partial graph was used for dependent conclusions.
- Test ERROR + AMBIGUOUS precedence and mixed valid/invalid components. A high confidence or imported reviewed status never overrides a hard finding.
- Round-trip imported reports as untrusted archival data, then obtain a fresh result. Never preserve stale authorization in a future live ingestion path.
- No simulator/exporter stub is necessary: M1 has neither. Test the absence of generation/approval capability and the qualified report contract rather than claiming end-to-end simulation safety from mocked code.

## Future Test Execution / Acceptance Evidence

The future targeted command uses standard unittest discovery for `test_circuit_ir_*.py` after installing the isolated validator dependency. Record test method count, subcase failures, skips and exit code. Network access, LTspice binaries, installed symbol/model libraries, API keys and GUI/image packages must not be test prerequisites.

After M1 executable work, run the existing full suite with its established test environment plus the explicitly authorized direct IR requirement. Preserve v0.1 functionality and classify existing real integration separately; do not run actual LTspice just to validate M1 JSON. The full-test manifest integration must be explicit, not a transitive-package assumption. Current tests are not rerun by this planning-only prompt.

Definition of done: [M1 acceptance criteria](implementation-plan.md) plus every in-scope blocking rule covered by a negative fixture or listed focused subcase. Deferred model/image/full-export checks remain visibly incomplete and cannot be marked CONFIRMED by a golden.
