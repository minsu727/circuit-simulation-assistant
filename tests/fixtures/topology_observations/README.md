# Prepared topology observations

Sixteen static M3C responses for M3D reconstruction tests. These are **manually
prepared observations**, transcribed from the repository-owned public schematic
drawings, not Vision/OCR output. No recognition accuracy is claimed.

`catalog.json` records payload hashes and the associated M3B image case. Image
identities are bound by intake of the original PNG. The observations use original
1000 × 650 pixel coordinates, separately assigned provider aliases, observed
component/pin geometry, split two-point conductors and visible labels/contacts.

Prediction inputs live here; the independently authored comparison targets stay
in `../schematic_images/cases/*/expected.json`. Reconstruction does not read those
targets. Tests build predictions before loading the targets for evaluation.
Existing partial M3C replays in `../image_observations` remain unchanged.

- `divider`, `rc`, `rlc`: ordinary continuity and explicit visible dots/ground.
- `missing_value`, `unreadable_value`: resolved topology, incomplete quantities.
- `nmos`, `pmos`: observed D/G/S/B and source polarity, no model/W/L invention.
- `cross_open`, `cross_dot`: explicit separation/connection evidence.
- `cross_ambiguous`: both local crossing choices, no selected winner.
- `near_gap`: observed gap, optional manual repair and separation, ambiguous label.
- `shared_labels`: separated conductors with the same flat-scope label.
- `rotated_sources`: observed polarity/direction is preserved despite orientation.
- `nmos_bulk_unknown`: missing bulk stays missing; no source-to-bulk tie.
- `supply_unknown`: rail names remain labels, not voltage sources or ground.
- `unsupported_bjt`: retained unsupported symbol and unknown M3C terminal roles.

An explicit ground attachment point denotes the end of its lead, not the text or
ground body's bounding-box center. A prepared connected T-contact is an explicit
observation; the engine does not infer all geometric T-intersections as connected.
The BJT has no observed external collector wire, so none is fabricated to complete
its candidate. Unsupported role localization is reported separately from the
unique-supported-topology denominator.

Preparation omissions are visible: the initial divider/RC-family inputs omitted
their drawn corner dots; independent junction evaluation rejected those exact
matches. The missing dot observations were added from the public SVG drawings;
golden annotations and images were not edited. These are development fixtures,
not held-out recognition benchmarks or independent human adjudication.
