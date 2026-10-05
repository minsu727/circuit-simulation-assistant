# M1 Implementation Plan (Proposed / Not Implemented)

This is an implementation-ready decomposition, not source code or a completion claim. The [parent Circuit JSON contract](../circuit-json-schema.md) remains authoritative. Scope conflicts are recorded in the [M1 index](README.md); do not silently alter prior ADRs.

## Exact Boundary

Include canonical typed records/enums, strict JSON loading, Draft 2020-12 shape validation, value normalization/checking, native component–pin–net graph, deterministic local electrical rules, fresh validation results, serialization, authored JSON fixtures and unit tests.

Exclude image processing, OCR, OpenCV, multimodal/AI inference, cloud access, user image-upload flow, Streamlit review/editor, schematic rendering, SPICE/ASC generation, LTspice execution, model-library resolution and transistor operating-point analysis. Do not infer body ties, connectivity or missing values. M1 reads explicit JSON records; it does not reconstruct nets from pixels or merge nets automatically.

## Smallest Maintainable Package — Future Files Only

```text
circuit_ir/
  __init__.py
  models.py                 enums and immutable records
  schema.py                 bundled-schema validation and type construction
  circuit-json.schema.json  authoritative 0.2-draft1 shape contract
  value_parser.py           finite grammar / exact Decimal quantities
  graph.py                  checked indices, incidence and DC projections
  validation.py             staged rules and fresh ValidationResult
  serialization.py          strict JSON decoding and explicit wire projection
tests/
  test_circuit_ir_models.py
  test_circuit_ir_schema.py
  test_circuit_ir_values.py
  test_circuit_ir_graph.py
  test_circuit_ir_validation.py
  test_circuit_ir_serialization.py
  fixtures/circuit_ir/{valid,invalid,ambiguous}/
```

Seven Python files and one schema resource are sufficient initially. Keep enums in `models.py`; a separate enums module adds navigation without a separate responsibility. Keep validation rules as small functions in one file, grouped by stage. Split structural/electrical modules only after duplication or review difficulty is demonstrated. Do not introduce plugins, a service container, generic graph framework or abstract validator hierarchy.

`__init__.py` only re-exports the small API; import must not open files, validate a schema, create directories or import the v0.1 app. Core records do not import graph/validation. Serialization projects primitive fields explicitly; schema loading uses a package-relative bundled resource, independent of working directory. Schema and validation errors flow into typed results, not hidden global state.

## Primitive Choices

| Area | Choice | Why / alternatives |
| --- | --- | --- |
| Records | `dataclass(frozen=True, slots=True)` with tuple collections | Lightweight standard library, immutable ownership/connectivity records. Dataclasses do not validate input by themselves; shape/semantic validation precedes their construction. TypedDict/plain dict are wire transport only |
| Schema | JSON Schema + future direct `jsonschema` dependency | Preserve the existing machine-readable contract rather than implement a partial standards engine. Pydantic would introduce a second source of schema/coercion rules |
| Graph | Python dict/set/tuple, BFS and bounded weighted union-find | Small explicit incidence/constraint graph; no NetworkX needed for M1 |
| Quantities | `Decimal` and exact integer/exponent operations; `Fraction` only for exact DC constraint arithmetic | Preserve original literals and decimal precision; avoid float-based rounding and trigonometric/solver work |
| JSON | Standard `json`, explicit encoders/decoders | Strict unknown-field policy, duplicate-key detection, no generic object introspection or circular serialization |

The standard library is sufficient for records, graph, arithmetic and JSON, but it does not implement the existing complete Draft 2020-12 schema. Hand-writing that validator would duplicate contract semantics and be harder to audit. Therefore propose **one new direct dependency, jsonschema**, for the future isolated package; do not rely on an accidental Streamlit transitive installation. Its [official validator documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/) supports schema checking and instance error iteration. Choose a tested pin at implementation time; no new package/version is installed or requirement changed here.

A future M1C task must explicitly authorize a small dedicated `requirements-circuit-ir.txt` manifest and its inclusion in the full-test requirements. That keeps the existing test-install workflow meaningful without relying on a transitive package or changing the CI workflow. Do not move optional LLM packages into this manifest or change core requirements. These future manifest changes are not performed by Prompt 027. Missing the validator is a clear setup error, never a reason to skip shape validation. Keep the schema bundled with internal references only; validation cannot fetch schema URLs or contact a network.

## Proposed API Contracts

| API | Result / failure contract |
| --- | --- |
| `load_document(text)` | `LoadResult(document or None, issues)`; reject parse/shape failures before typed construction |
| `dump_document(document)` | Strict deterministic JSON text; no inferred field updates or validation/approval side effects |
| `parse_quantity(literal, unit, grammar)` | `ValueParseResult(quantity or None, issues)`; exact normalization, no arbitrary expressions |
| `build_graph(document)` | `GraphBuildResult(graph or None, issues)`; no dict overwrite on duplicate IDs, no guessed incidence |
| `validate_document(document)` | Fresh `ValidationResult` for fixed `m1-local-v1` ruleset/profile, independent of imported validation snapshots |
| `result_to_dict(result)` | Separate report envelope, not a Circuit JSON approval update |

A direct Python caller must not bypass shape/reference guards: `build_graph` checks its prerequisites and `validate_document` runs the full pipeline. Result functions do not mutate the input. Typed constructors are convenience records, not authorization or proof of validity.

## Ten-Step Implementation Order

| Step | Future files touched | Tests before / after | Complexity / prerequisite |
| --- | --- | --- | --- |
| 1. Core types | models.py, __init__.py, model tests | Field/enum/immutability cases first; review wire-field mapping afterward | Small; parent schema |
| 2. Exact quantities | value_parser.py, value tests | Suffix and precision goldens first; rejection/limits afterward | Small–medium; step 1 |
| 3. Strict round-trip | serialization.py, serialization tests | Duplicate JSON keys/non-finite input first; full nested projection afterward | Small; steps 1–2 |
| 4. Schema + loader | schema.py, schema JSON, schema tests; future isolated dependency manifest | Parent example/meta-schema first; bad type/unknown-field/path errors afterward | Medium; steps 1–3 |
| 5. Graph construction | graph.py, graph tests | Duplicate/unknown-reference failure first; incidence/BFS/order invariance afterward | Medium; step 4 |
| 6. Structural stages | validation.py, validation tests, initial invalid fixtures | Ground/pin/label/orphan cases first; non-cascading behavior afterward | Medium; step 5 |
| 7. Device/value stages | validation.py, value/validation tests, source/MOS fixtures | Unit/polarity/body/source-short cases first; local-valid and deferred-model cases afterward | Medium; steps 2, 6 |
| 8. DC/ambiguity/result | graph.py, validation.py, graph/validation tests | Floating/cycle/explicit ambiguity cases first; warning/severity precedence afterward | Medium–high; steps 5–7 |
| 9. Complete goldens | planned fixture files and all six test modules | Review authored topology expectations first; all 38 fixture cases afterward | Medium; steps 1–8 |
| 10. Acceptance / regression | acceptance cases within validation/schema/serialization tests; no app wiring | End-to-end local load→graph→report→round-trip first; existing regression after | Small execution scope; all prior steps |

Tests are written in future implementation tasks, not this prompt. A step that reveals a contract inconsistency pauses that change for a documented decision; it must not edit old ADRs silently. Commit permission remains a separate user decision, even if a future slice is independently reviewable.

## Acceptance Criteria

M1 completion requires all of the following in a later implementation:

1. Every supported record loads into immutable typed representation, with strict fields, enum values, null semantics and version checks.
2. IDs, ownership and pin/net references are deterministic and do not depend on coordinates or array order.
3. R/C/L, V/I, NMOS/PMOS role/value rules work; unsupported input is rejected or explicitly unresolved, never dropped.
4. Missing/conflicting ground, orphan/missing pins, source-short, label conflict, isolated and proven floating cases are detected.
5. Explicit ambiguities and relevant inference-confidence review requirements block local validity; high confidence cannot override ERROR.
6. Valid fixtures reach `VALID` in **m1-local-v1 only**. Every report records deferred checks; no M1 result grants generation, execution or human approval.
7. Semantic JSON round-trip preserves original literals, decimal strings, IDs, explicit connections and unresolved data. Imported state is never trusted.
8. All 38 planned deterministic fixtures exist with independent expected states/codes, plus the module boundary cases in [Test Plan](test-plan.md).
9. Targeted tests run without LTspice, image/Vision dependencies, Streamlit, API keys or network. No hidden installed model/symbol library is required.
10. Reports are repeatable; earlier failures suppress dependent nonsense errors; input records remain unchanged on both success and failure.
11. All parent M1-applicable blocking rules have negative coverage; deferred full-v0.2 checks are listed, not marked passed.
12. Future executable changes pass the existing regression suite; current ASC execution, numerical algorithms, Summary and approval behavior remain untouched.

## Ranked Implementation Risks

| Rank | Trap | Mitigation |
| --- | --- | --- |
| 1 | Local VALID misread as simulator-ready or approved | Profile/deferred report, no approval type or exporter, explicit future gates |
| 2 | Two connectivity stores drift | Only connections canonical; derive net members, role views and graph |
| 3 | Visual pin order treated as electrical role | Role-based checks; orientation stays in provenance; no coordinate-based inference |
| 4 | Cascading graph errors after duplicate/broken IDs | Prerequisite gates, checked indices and skipped-stage reasons |
| 5 | Decimal/SPICE suffix or serialization precision loss | Literal preservation, exact arithmetic, no float/default-context normalization |
| 6 | Fragile issue/schema/version duplication | Existing code/version retained; runtime diagnostics projected explicitly; one bundled schema |
| 7 | M1 grows into a solver/catalog resolver/editor | Explicit non-goals and deferred-check inventory |

Also guard against treating ground as a device, confidence as approval, deep mutability in frozen records, circular serialization and premature version migration. Interfaces remain simulator-neutral; SPICE text is only one value grammar, not the IR structure.
