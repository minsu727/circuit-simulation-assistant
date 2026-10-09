# supply_unknown provenance and manual truth review

Original drawing created specifically for this repository on 2026-10-09.
Repository-owned authoring; generic electrical symbols, no downloaded image,
coursework, proprietary schematic or external scan. No repository-wide license
is introduced by this record. Source: `source.svg`; review raster: `schematic.png`.

## Independent electrical review

VDD is only attached text on R1.a. R1.b and R2.a share the drawn return bend. R2.b has a RETURN label without a ground symbol. There is no voltage source or ground entity to invent.

`expected.json` connection rows and alternatives were written separately from
the geometry authoring instructions, by tracing each terminal on the original
image. The drawing helper contains no electrical graph. No inference, M1 graph,
exporter or converter produced these answers. Symbol/text regions and wire
polylines are visual evidence, not a second electrical membership table.



Connection rows are the only pin-to-net truth for each mutually exclusive
interpretation. They do not conduct across component bodies. Named labels attach
only to the indicated conductor. Normal continuous corners/T endpoints are joined;
crossing lines require a filled dot under this catalog's explicitly printed style.
Other schematic conventions must not inherit that rule automatically.

## Deliberately unresolved or out-of-scope information

- VDD text is not an independent source or voltage value.
- RETURN is not an explicit ground convention; require a reference.

MOS profile choice is never proven by a generic symbol. An absent AC/waveform
annotation is not an implicit AC=1, phase=0 or zero DC source. Fixture hashes bind
image bytes only; no user confirmation, M1 VALID or execution permission exists.
Review was performed by the authoring agent; independent human adjudication and
held-out redraws remain future evaluation work. No extraction accuracy was tested.
