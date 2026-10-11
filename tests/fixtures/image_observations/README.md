# M3C offline observation replays

These ten repository-owned samples were independently hand-composed for contract
tests. They are **not model predictions, accuracy evidence, M3B expected.json
copies, accepted connectivity or Circuit IR**. Coordinates/classifications may
be deliberately incomplete or incorrect. All valid samples report partial
coverage. The malformed/dangling-reference samples must fail atomically.

`catalog.json` names the matching existing M3B PNG case and expected adapter
status. Only image bytes are used to bind source/normalization/transform hashes;
electrical ground truth is neither read nor converted into these responses.
No real provider/model metadata, uploaded images or personal paths are stored.

| Replay | Purpose |
| --- | --- |
| divider_partial.json | Resistor/value evidence, missing detections, incomplete wire/contact |
| mos_missing_bulk.json | NMOS/PMOS and D/S alternatives; bulk absent without fabricated geometry |
| pmos_mega_text.json | Provisional PMOS role and printed megaohm candidate |
| crossing_ambiguous.json | Crossing/junction alternatives without a net merge |
| near_gap_labels.json | Near gap, possible label equivalence, uncertain attachment |
| unknown_unreadable.json | Unknown symbol, unreadable text and uncertain ground |
| unsupported_symbol.json | Unsupported BJT remains visible without a new executable type |
| source_polarity.json | Polarity alternatives and DC/AC/waveform text without execution |
| invalid_reference.json | Untrusted dangling component reference |
| malformed.txt | Truncated provider JSON |

Load a sample explicitly with test-owned filesystem code, then pass its bytes to
`StaticReplayProvider`. The production adapter accepts bytes/text, never paths or
URLs. See the [implemented contract](../../../docs/v0.2/m3/observation-contract.md).
