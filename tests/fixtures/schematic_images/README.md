# Owned schematic image catalog — M3B

Sixteen original printed-style drawings and separately authored electrical truth.
No Vision/OCR, graph inference, candidate conversion or simulator is implemented
by these fixtures. Passing integrity tests is not recognition accuracy or approval.

- [Catalog](catalog.json): `m3-images-1`, stable relative paths, raster SHA-256,
  dimensions, ownership, annotation version, scenario and interpretation outcome.
- [Annotation contract](../../../docs/v0.2/m3/fixture-annotations.md):
  test-only `m3-fixture-1`; **not** a replacement for Circuit IR `0.2-draft1` or a
  frozen CandidateCircuit wire schema.
- [Evaluation protocol](../../../docs/v0.2/m3/evaluation-protocol.md): future
  candidate matching, topology-first metrics, uncertainty and report definitions.

## Exact coverage

| Case | Categories | Expected interpretation | Electrical review focus |
| --- | --- | --- | --- |
| [divider](cases/divider/schematic.png) | A, N, ordinary_wire | RESOLVABLE | Zigzag resistors, VIN/VOUT, explicit source polarity and GND; continuous corners |
| [rc](cases/rc/schematic.png) | B | RESOLVABLE | Rectangular resistor, capacitor plates, independent input/output groups |
| [rlc](cases/rlc/schematic.png) | C, ordinary_wire | RESOLVABLE | R–L series midpoint, C shunt, 10u H / 1p F |
| [nmos](cases/nmos/schematic.png) | D | INCOMPLETE | Clear D/G/S/B; explicit body return; model/W/L absent |
| [pmos](cases/pmos/schematic.png) | E, numeric_mega | INCOMPLETE | Upper S/right B at supply, lower D at load; printed 1M Ω; model/W/L absent |
| [cross_open](cases/cross_open/schematic.png) | F | RESOLVABLE | Crossing horizontal/vertical conductors remain electrically separate |
| [cross_dot](cases/cross_dot/schematic.png) | G | RESOLVABLE | Filled dot connects the four inner resistor terminals |
| [cross_ambiguous](cases/cross_ambiguous/schematic.png) | H | NEEDS_REVIEW | Faint displaced mark; joined/separated alternatives; no chosen inner partition |
| [shared_labels](cases/shared_labels/schematic.png) | I | RESOLVABLE | Flat-scope VOUT/vout joins physically disjoint segments |
| [rotated_sources](cases/rotated_sources/schematic.png) | J, N | RESOLVABLE | Horizontal V1 plus on right; reversed I1 arrow down; rotated/rectangular symbols |
| [missing_value](cases/missing_value/schematic.png) | B, K | INCOMPLETE | C1 has no numeric/unit text; no normalized quantity invented |
| [unreadable_value](cases/unreadable_value/schematic.png) | B, K | INCOMPLETE | 1?0n F remains unreadable, not 100n F |
| [unsupported_bjt](cases/unsupported_bjt/schematic.png) | L | UNSUPPORTED | NPN base/collector/emitter retained; no MOS substitution |
| [supply_unknown](cases/supply_unknown/schematic.png) | M | INCOMPLETE | VDD/RETURN labels imply neither a source nor ground |
| [near_gap](cases/near_gap/schematic.png) | near_gap | NEEDS_REVIEW | 10-pixel endpoint gap and unresolved VOUT attachment; no silent bridge |
| [nmos_bulk_unknown](cases/nmos_bulk_unknown/schematic.png) | D, bulk_unresolved | INCOMPLETE | Three exposed terminals; B has no position or connection; no implicit S–B tie |

A–N mean divider, RC, RLC, NMOS, PMOS, undotted crossing, dotted crossing,
ambiguous junction, repeated labels, rotated/mirrored symbols, missing/unreadable
value, unsupported symbol, supply/reference ambiguity and source polarity.
Distribution: **7 RESOLVABLE, 2 NEEDS_REVIEW, 1 UNSUPPORTED, 6 INCOMPLETE**.
Topology is fully specified in 13 cases (including the unsupported BJT's observed
roles); 12 have complete topology using supported component categories.

## Authorship and independence

Every case contains `source.svg`, `schematic.png`, `expected.json` and
`provenance.md`. These drawings were created for this repository from generic
electronics symbols, without private/coursework material or downloaded scans.
Ownership is recorded per case; no repository-wide license is added.

The original geometry was authored separately from the explicit pin-to-net rows
and review alternatives. Coordinates help locate evidence but never generate
electrical membership. No M1 graph/export/converter or inference code was called
to author goldens. The authoring agent visually reviewed a contact sheet and
individual challenging cases against the separately written rows. This is
agent-reviewed ground truth, not independent human adjudication.

SVG files are static editable vector sources. PNG files are committed 1000×650
8-bit grayscale rasters, generated with the already available Pillow/Matplotlib
font resources during authoring; ordinary CI only reads them. No rendering
dependency is added, no internet asset is loaded and no bless/regeneration mode
is provided. Manual image changes require a separate truth review and deliberate
catalog hash update; tests never overwrite assets. Temporary geometry authoring,
contact sheets and diagnostics are kept in ignored runtime storage.

This catalog declares a **filled-dot crossing convention**, printed on the
crossing examples. It is not a universal rule for arbitrary drawings. Continuous
corners/T endpoints join; a geometric crossing without a filled dot does not.
The faint mark and endpoint gap remain unresolved. A manual bridge is a proposed
correction, not a claim that an invisible conductor was observed.

## Running integrity checks

From the repository root in the full test environment:

```powershell
python -X utf8 -m unittest tests.test_m3_fixtures -v
```

Tests validate paths, hashes, PNG decoding, dimensions, static SVGs, versions,
IDs, roles, evidence references, duplicate/contradictory assignments, review
outcomes and category coverage. A before/after byte snapshot verifies fixture
files remain unchanged. No LTspice, network, credentials or model is needed.

## Limits and planned use

All 16 images are **development** examples, not held-out performance evidence.
The small clean catalog covers a declared symbol style with readable labels and
some explicit terminal markings. It lacks noisy scans, JPEG/compression/crops,
EXIF/deskew, bridge/hop styles, op-amps, multiple ground conventions, Greek micro
variants, scientific notation, duplicate reference names, hierarchical circuits
and injection/oversize images. Those later negatives must be authored independently.

No post-review M1 document or executable source configuration is claimed here.
MOS needs explicit model/W/L selection, and unclear cases still need decisions.
M3C will implement bounded observation types/intake and fake/replay seams; M3D
will evaluate evidence-linked connectivity hypotheses against these fixed goldens.
Actual extraction, held-out redraws, review/conversion, image admission and real
image-to-LTspice evidence remain later work. Current M2 blocks image-origin export.
