# cross_ambiguous provenance and manual truth review

Original drawing created specifically for this repository on 2026-10-09.
Repository-owned authoring; generic electrical symbols, no downloaded image,
coursework, proprietary schematic or external scan. No repository-wide license
is introduced by this record. Source: `source.svg`; review raster: `schematic.png`.

## Independent electrical review

Four resistor inner terminals meet geometrically at the center. A faint displaced mark cannot establish junction membership; both partitions are retained, with no selected inner-terminal truth.

`expected.json` connection rows and alternatives were written separately from
the geometry authoring instructions, by tracing each terminal on the original
image. The drawing helper contains no electrical graph. No inference, M1 graph,
exporter or converter produced these answers. Symbol/text regions and wire
polylines are visual evidence, not a second electrical membership table.

- Geometric intersection alone is not conductivity. This mark requires an explicit choice.

Connection rows are the only pin-to-net truth for each mutually exclusive
interpretation. They do not conduct across component bodies. Named labels attach
only to the indicated conductor. Normal continuous corners/T endpoints are joined;
crossing lines require a filled dot under this catalog's explicitly printed style.
Other schematic conventions must not inherit that rule automatically.

## Deliberately unresolved or out-of-scope information

- Choose joined or separated after inspecting the faint mark.

MOS profile choice is never proven by a generic symbol. An absent AC/waveform
annotation is not an implicit AC=1, phase=0 or zero DC source. Fixture hashes bind
image bytes only; no user confirmation, M1 VALID or execution permission exists.
Review was performed by the authoring agent; independent human adjudication and
held-out redraws remain future evaluation work. No extraction accuracy was tested.
