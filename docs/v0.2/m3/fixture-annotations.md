# M3B fixture annotation contract

`m3-fixture-1` is a **test truth format**, not M1 Circuit JSON and not a frozen
production M3C response API. [Catalog](../../../tests/fixtures/schematic_images/catalog.json)
and [coverage/provenance](../../../tests/fixtures/schematic_images/README.md)
are the independently reviewable inputs. The [evaluation protocol](evaluation-protocol.md)
consumes them only when an actual candidate implementation exists.

## Catalog and image identity

`m3-images-1` records `annotation_version`, `coordinate_space`, declared `style`
and ordered `cases`. Each case requires stable `case_id`, scenario `categories`,
`interpretation_state`, `rationale`, relative `image/source/expected/provenance`
paths, `sha256`, integer `width_px/height_px`, `source_format`, `media_type`,
`ownership`, `annotation_version` and `evaluation_split`.

Current paths are `cases/<case_id>/{schematic.png,source.svg,expected.json,provenance.md}`.
They cannot escape the catalog directory. Each raster is 1000×650 grayscale PNG;
SHA-256 identifies the exact PNG bytes, not SVG rendering equivalence or approval.
Sources are repository-original static SVG; all cases use the development split.

Original pixel frame: stored decoded raster before orientation, x right/y down,
top-left origin. `position=[x,y]`, `bbox=[x,y,width,height]` and polyline `points`
must be finite and within the original image. Boxes have positive width/height.
There are no transforms in this initial catalog. Future transformed candidates
must map explicitly back to this frame before evaluation.

## `expected.json` required fields

| Field | Meaning |
| --- | --- |
| `annotation_version`, `case_id`, `coordinate_space` | Exact catalog/version/frame binding |
| `interpretation_state` | Fixture interpretation outcome, not an M1 technical state or live candidate confirmation |
| `topology_complete` | Whether primary connection truth assigns every terminal; independent of missing values/model or supported execution |
| `observations.regions` | `{id,kind,bbox,text}`: symbol, text, label or ground evidence |
| `observations.wires` | `{id,points}`: visible conductor polylines, not net membership |
| `observations.junctions` | `{id,position,wire_ids,appearance}`: filled_dot, no_dot, unclear_mark or endpoint_gap |
| `expected.components` | `{id,type,reference,evidence_ref,label_ref,value,source_dc}`; visible inventory and selected truth values |
| `expected.pins` | `{id,component_id,role,position,evidence_ref}`; explicit ownership/role and terminal location, never a net field |
| `expected.nets` | `{id,is_ground}`: opaque vocabulary for primary truth and mutually exclusive alternatives; no member lists |
| `expected.connections` | `{pin_id,net_id,evidence_refs}`: sole primary pin membership truth |
| `expected.labels` | `{evidence_ref,text,net_id,scope}`: explicit flat label attachment; null when unresolved |
| `expected.ground_net_id` | Explicit ground group or null; no hidden node 0 |
| `expected.junction_decisions` | `{observation_id,meaning,net_ids,reason}`: connected/separated/continuous/unresolved interpretation, separate from the observed mark |
| `expected.issues` | `{id,kind,targets,evidence_refs,required_review,message,alternative_ids}`: required missing/ambiguous/unsupported choices |
| `expected.alternatives` | `{id,issue_id,description,connections,ground_net_id}`: independently authored mutually exclusive full partitions, not simultaneously accepted edges |
| `expected.model_choices` | `{component_id,profile,required_parameters}`: missing MOS profile and W/L; no visual proof of a process model |

Unknown/missing fields and duplicate JSON keys/definition IDs are integrity
errors. Connection endpoints must resolve; one primary assignment per known pin.
Duplicate assignment rows are errors even if identical. Full alternatives must
retain settled primary truth and belong to their declared issue. Evidence IDs
resolve across regions/wires/junctions. No circular object ownership exists.

`regions`/`wires` describe pixels; `connections` and `junction_decisions` describe
electrical interpretations. A line through a symbol does not short its terminals.
No function derives truth from coordinates. The integrity helper checks records
and declared consistency only; it cannot establish that annotations match pixels.

## Outcome and incompleteness policy

| Outcome | Truth policy |
| --- | --- |
| RESOLVABLE | Unique fully specified visual topology and no deliberately missing required fixture fact; still unconfirmed, unvalidated and non-executable |
| NEEDS_REVIEW | Unchosen crossing/gap alternatives; primary rows contain only uncontested assignments, not a hidden winner |
| UNSUPPORTED | Accurately retained BJT outside M1/M2 support; its visible terminal truth is test data, not a new executable type |
| INCOMPLETE | Missing/unreadable value, model/W/L, bulk, supply or ground; only known facts are supplied |

No outcome uses M1 VALID. Clear MOS topology can be complete while the overall
fixture is INCOMPLETE because model/W/L are absent. There is no human confirmation,
technical validation report, conversion readiness success or execution approval.

Current fixture issue kinds are `missing_value`, `unreadable_value`,
`model_selection_required`, `bulk_unresolved`, `junction_unclear`, `wire_gap`,
`label_attachment_unresolved`, `unsupported_component`,
`supply_definition_missing`, `ground_missing`. They are test-side expectation
labels, **not** additions to M1 diagnostic codes or a final production M3 API.
All require review. Model, bulk and source choices cannot be inferred away.

The latent `M1.bulk` record in the three-terminal case documents a required
missing role: `position=null`, no Connection and a `bulk_unresolved` issue. It is
not an observed fourth pin and must not enter terminal-detection denominators.
For four-terminal NMOS, D→VOUT, G→VIN, S→GND, B→GND. For PMOS, D→VOUT,
G→VIN, S→VDD, B→VDD; upper/lower page position alone does not define those roles.
The BJT's `unsupported_bjt`/base/collector/emitter names are fixture-only observed
categories; no M1 enums or allowed exporter types are changed.

## Text and quantity semantics

Each quantity has `raw_text`, `unit_text`, `notation`, `si_value`, `unit`, `state`.
Known values use explicitly printed unit evidence and `printed-engineering`
notation. SI values are exact bounded decimal strings compatible with current M1
units. Missing text/unit remains null; unreadable text stays raw with `si_value=null`
and `notation=unresolved`. A known device category does not manufacture unit text.

| Printed scalar + unit | Selected engineering meaning | M1-compatible SI scalar/unit |
| --- | --- | --- |
| 1k Ω / 10k Ω | kilo-ohm | `1000` / `10000`, `ohm` |
| 1M Ω | mega-ohm under the declared printed convention | `1000000`, `ohm` |
| 100n F | nano-farad | `0.0000001`, `F` |
| 10u H | micro-henry | `0.00001`, `H` |
| 1p F | pico-farad | `0.000000000001`, `F` |
| 1m A | milli-ampere | `0.001`, `A` |

Printed `1M Ω` does **not** pass unaltered through SPICE grammar, where M/m means
milli and Meg means mega. Future normalization preserves raw evidence and requires
an explicit notation selection; these goldens specify the intended printed
meaning, not an already approved conversion. `1?0n F` has no numeric answer.

`source_dc` records only the printed DC magnitude with positive/negative terminals.
For current sources positive→negative follows the drawn arrow. Missing AC phase,
amplitude or waveform fields are not defaults or full source configuration.
No simulation request is inferred from a drawing. Ground comes only from the
explicit ground symbol; VDD and RETURN labels are not source/ground components.

## Test-only implementation and future projection

[Integrity helper](../../../tests/m3_fixture_contract.py) and
[tests](../../../tests/test_m3_fixtures.py) read fixed assets without rewriting
them, inference, M1 loading, validation or graph reconstruction. No new dependency.
The annotated boxes are manually reviewed evidence regions, not a segmentation
mask or a calibrated detector target. Fixtures are never production auto-approval.

M3C should version its own strict observation types and bounds, retaining nullable
unknowns and evidence. M3D may compare proposals with this independently authored
truth. M3E must separately author reviewed corrections and M1 conversion goldens;
none is generated/blessed here. M1 schema/Connection-only connectivity and M2
manual-only admission are unchanged. M3 is not closed.
