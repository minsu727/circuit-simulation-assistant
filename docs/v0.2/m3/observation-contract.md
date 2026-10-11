# M3C implemented observation contract

Prompt 044, 2026-10-11 (Asia/Seoul). **Offline foundation only; M3 is not closed.**
No live Vision/OCR, topology, review UI, M1 conversion, image-aware M2 admission
or simulator execution is provided. The candidate/review layers in
[Candidate Contract](candidate-contract.md) remain proposals.

## Public API

The independent `circuit_image` package exports:

```python
from circuit_image import (
    ingest_image, ImageLimits, parse_observations, ObservationLimits,
    STATIC_PROVIDER, StaticReplayProvider, extract_observations,
    observations_to_dict, dump_observations,
)

intake = ingest_image(png_or_jpeg_bytes)
if intake.artifact is not None:
    # Explicitly supplied untrusted JSON bytes, never a path or URL.
    result = extract_observations(
        intake.artifact, StaticReplayProvider(observation_json_bytes),
        extraction_key="attempt_one", timeout_s=60,
    )
    if result.observation_set is not None:
        wire_json = dump_observations(result.observation_set)
```

- `ingest_image(data: bytes, *, limits=ImageLimits()) -> IntakeResult`:
  immutable artifact or data-free diagnostics.
- `parse_observations(payload: str | bytes, artifact, *, provider: ProviderInfo,
  extraction_key="replay", limits=ObservationLimits(), image_limits=ImageLimits())`:
  `ObservationResult(observation_set | None, diagnostics)`.
- `extract_observations(image, provider: VisionObservationProvider, *,
  timeout_s=60.0, extraction_key="replay", limits=ObservationLimits(),
  image_limits=ImageLimits())`: `ExtractionResult(status, observation_set, diagnostics)`.
- `observations_to_dict(set)` / `dump_observations(set)`: explicit wire projection,
  native JSON or deterministic UTF-8 JSON text; not an admission/approval API.

Frozen records, tuples and ID references avoid mutable defaults/cycles and a
competing Circuit IR. Direct dataclass construction/replacement is not validation
or authority: all untrusted admission uses the parser. Provider/parser boundaries
re-ingest original bytes and compare the complete artifact, including normalized
bytes. No graph, net membership, technical state or approval fields exist.

## Intake and identity

| Configurable budget | Default |
| --- | --- |
| Encoded bytes | 8 MiB |
| Each original side | 64–4096 pixels |
| Original decompressed pixels | 8,000,000 |
| Format/frame | Actual PNG/JPEG, one frame |

Byte checks precede opening; header dimensions/pixels precede pixel decoding.
Magic, decoder format, PNG verification, full decoding and end markers are checked.
Reject corruption/truncation, animation, invalid EXIF, decompression warnings and
ambient permissive truncated-image mode. The stricter end-marker policy also
rejects decodable files with trailing content. No SVG/PDF/source path input.
Metadata/content is never executed; global decoder settings are not changed.

`SourceIdentity` records `m3-intake-1`, original SHA-256/length, detected format,
original/display dimensions, normalized SHA-256, EXIF orientation, exact forward/
inverse affine matrices and transform digest. Its digest binds canonical metadata
and those hashes, with no path, username, timestamp or randomness. Identical bytes
produce identical source identity under the same codec version/settings.

Normalization applies EXIF orientation, converts to RGBA and writes a fresh
metadata-free PNG in memory. No crop/resize/interpolation/deskew/denoise. Original
bytes remain immutable. A future Pillow version may change normalized-byte
identity; original-byte SHA-256 remains exact. Nothing is transmitted or persisted.
Callers own memory lifetime; secure erasure of Python memory is not promised.

## Geometry

Original frame is the decoded raster **before EXIF**: top-left origin, x right,
y down. Continuous **pixel-edge** coordinates span `[0,width] × [0,height]`;
pixel centers are `(column+0.5,row+0.5)`. Bboxes are `[x,y,width,height]`, strictly
positive extents, wholly in-frame. A wire has two ordered distinct endpoints;
pins/junctions/crossings have one point. No clipping, snapping or joining occurs.

Input frames are `original_pixels` or `display_pixels`, bound to all four artifact
digests. Display geometry is mapped back into original coordinates before storage;
bboxes use all four corners. EXIF 1–8 supplies invertible six-coefficient affine
matrices with a digest. Pose is `r0/r90/r180/r270`, each with optional `_mirror`,
or `unknown`. Reflection is horizontal first, then screen-clockwise rotation;
frame conversion composes inverse EXIF with that pose. **Roles never swap or
become inferred from geometry.**

## Wire schema: m3-observations-1

Top-level keys are exactly `version`, `image`, `coordinate_frame`, `provider`,
`coverage`, `observations`. `image` has exactly `source_identity_sha256`,
`source_sha256`, `normalized_sha256`, `transform_sha256` matching the artifact.
`coverage` is `partial` or `reported_complete`; empty complete sets fail.

Provider fields: `provider_id`, `provider_version`, `model_id`, `model_version`,
`adapter_version`, `catalog_version`, `prompt_version`, `mode`. Configured metadata
must exactly match response metadata. Default replay uses static-replay / 1 /
m3-static-1 / m3-images-1 / replay, with real model and prompt fields **null**.
No real model metadata is fabricated. Required/null semantics are explicit.

Every row has exactly `id`, `kind`, `source_sha256`, `geometry`, `data`,
`confidence`, `uncertainty`. See [complete replay examples](../../../tests/fixtures/image_observations/README.md).

| Kind | Closed `data` fields |
| --- | --- |
| symbol | classification, component_type, observed_name, reference_text |
| text | raw_text, purpose, component_ref, value |
| label / supply_label | raw_text, attachment_ref |
| pin | component_ref, role |
| wire_segment | Empty object; endpoints are geometry |
| junction / crossing | wire_refs, interpretation (connected/separated/unknown) |
| ground | style (signal/earth/chassis/unknown) |
| unknown_symbol | observed_name |
| contact_candidate | refs (two), interpretation (touching/separated/equivalent/unknown) |

`geometry` is null only where allowed; otherwise exact bbox/points/orientation.
Visible symbol/text/label/ground/unknown records require a bbox. Contact may lack
its own geometry; missing pin/text may have null geometry. Missing pin geometry
**must** be null, not invented from a symbol bbox.

Supported symbol types reuse M1 categories. Unsupported/unknown regions have
`component_type: null`, retain observed names and require uncertainty reasons.
Pin/text component refs resolve to symbol observations; attached labels to wires;
junctions to at least two wires; contacts to wire/pin/label/supply-label.
Related refs may be any other observation. Existence, type, uniqueness and
self-reference checks include alternatives. These are provider hypotheses, not
canonical net membership, accepted contact constraints or reconstruction.

## Uncertainty

`confidence` is exactly score (null or finite native number 0–1), basis
(unknown/synthetic/provider_score/heuristic), calibrated (false only). Unknown
basis cannot claim a score; M3C supplies no calibration evidence or manual score.

`uncertainty` is exactly state/reasons/related_refs/alternatives. States are
provisional, ambiguous, missing, unreadable; no confirmed/resolved state exists.
Non-provisional states require reasons. Alternatives are zero or 2–8 distinct
`{id,data}` choices of the same row kind and require ambiguous state. Reasons/refs
are unique, bounded and validated. Alternatives are not simultaneously accepted.

Reasons cover unclear symbol/crossing/contact/polarity/MOS-role/ground, possible
label equivalence, missing bulk/value, unreadable text, unsupported notation/symbol
and incomplete wire. Unknown/unsupported and unnormalized values need reasons.
Nothing inserts a wire/value/supply/ground/body connection to make a circuit valid.

## Text, values and MOS

Raw text is preserved exactly as data. Purposes: generic, reference, value,
source_dc, source_ac, source_waveform, device_width, device_length. Waveform text
does not become a source object; absent amplitudes/DC remain absent, never zero/one.

Optional value has raw_scalar/raw_unit/notation/unit/si_value. SI values are bounded
exact Decimal strings. Explicit notation is printed_engineering/spice/si/unresolved.
Existing M1 scalar parsing verifies the proposal, without choosing an interpretation
or performing electrical validation. A supplied SI value must match the literal,
explicit unit and notation. No unit is guessed when absent. Failed/unsupported
normalization retains the raw evidence with null SI value and a reason.

Printed `1M Ω` is 1,000,000 ohm; SPICE `1M`/`1m` is 0.001 and `1Meg` is 1,000,000.
Base unit tokens: Ω/ohm/F/H/V/A/Hz/s/deg/m. Initial printed units also support
kΩ/MΩ, nF/pF/uF/µF/μF, um/µm/μm. Printed scalar prefixes:
T/G/M/k/m/u/n/p/µ/μ/Meg. Signed/scientific scalars reuse M1 precision bounds.
Other notation/expressions are not evaluated; this is not a general OCR/unit parser.

MOS roles reuse `PinRole` drain/gate/source/bulk/unknown (D/G/S/B). NMOS/PMOS
classification, pose, visible roles and alternatives survive frame remapping.
Missing B is a missing observation with null geometry, not a body connection.
No source-body tie, net ID, sealed model/profile or inferred W/L is introduced.

## Limits, diagnostics and provider interface

| Observation budget | Default |
| --- | --- |
| UTF-8 JSON bytes / total rows | 2 MiB / 4096 |
| Symbols / texts / pins | 128 / 1024 / 512 |
| Wires / junction-family / contacts | 2048 / 512 / 512 |
| Visible text / scalar / unit token | 256 / 128 / 32 chars |
| Alternatives / reference-list entries | 8 / 16 |
| JSON depth / visited values | 16 / 100,000 |
| Callback budget | >0–60 s, cooperative |

Reject malformed UTF-8/JSON, duplicate keys/IDs, unknown fields/types/versions,
wrong refs, invalid metadata/confidence, boolean/nonfinite geometry, out-of-frame
coordinates, contradictory alternatives and budget violations. No partial set is
returned for malformed input. Payload/depth checks precede JSON allocation; node
count follows bounded parsing. Stable code/field/message diagnostics never echo
input values or exception text. Families: IMAGE_*, OBS_*, PROVIDER_*; focused
tests assert exact codes for failures.

`VisionObservationProvider` has `info: ProviderInfo` and
`extract(image: ImageArtifact, *, timeout_s: float) -> str | bytes`. Only replay is
active. Remote mode fails **before** callback; local inference is unavailable.
No vendor SDK, endpoints or credentials are imported. TimeoutError,
ProviderUnavailable and generic exceptions become sanitized failures. No retry.

Timeout is **cooperative**, not isolation: exception or late return fails; arbitrary
Python callback code cannot safely be preempted. Built-in replay is nonblocking.
The seam is for trusted adapter code with untrusted outputs, not a callback sandbox.
Real/local adapters need separately reviewed hard deadlines, consent/transport,
retention and dependency choices before activation.

Statuses: FAILED/no set; INCOMPLETE/valid partial set plus OBS_INCOMPLETE;
SUCCESS/nonempty shape-valid set reporting complete coverage. SUCCESS is never
measured completeness, visual correctness, technical VALID, confirmation or approval.

## Replay, identity and serialization

`StaticReplayProvider` holds explicitly supplied JSON bytes/text; it never opens
paths, looks up goldens or inspects pixels. Ten separately hand-composed samples
include correct/incorrect/missing/ambiguous/unknown/unreadable/invalid observations.
All valid samples declare partial coverage. Tests read only the matching PNG for
image bindings, never M3B expected.json to manufacture provider responses.
These are contract tests, not recognition accuracy evidence.

Explicit projection maps each variant. Serialization contains no pixels or
approval/topology structures. Unordered rows/reasons/refs/alternatives sort by IDs;
ordered wire endpoints are retained. Canonical UTF-8 JSON has sorted keys, compact
separators, native finite numbers and a final LF. Provider-local aliases are safely
remapped into extraction-local observation IDs. Response SHA-256 binds canonical
**original-frame content**, not response whitespace/order. All image digests and
provider provenance are bound. Dump/reparse with the same artifact/provider/key
reproduces the typed set; it does not restore an approval.

`extraction_key` is an explicit safe local attempt token. Same content/key yields
the same identity; a new key changes extraction/observation IDs while keeping
response digest. Default replay is for offline reproducibility. Future orchestration
must use a fresh token for a new extraction/review scope, never inherit old human
decisions by matching text/coordinates/content. No such decisions exist here.

## Security, limitations and M3D prerequisites

No automatic logging. Image/response/raw text is hidden from default repr;
deliberate serialization still contains potentially private visible text.
Shell commands, paths, .include/.lib/.model/.step/.param and fake approval strings
are bounded data, never looked up/executed/emitted as directives. No filesystem,
network or process call is reachable from provider text. Existing M2 image-origin
gate and all approvals are unchanged; ObservationSet is not approval input.

Limits: no actual recognition, completeness estimation, held-out performance,
hard callback isolation, retained bundle policy, topology/review/promotion or image
execution. Complex notation, extra transforms and codec isolation need future
review. M3B assets/truth remain unchanged; EXIF/JPEG/security images are generated
only in test memory. No new dependency is added; Pillow is already in core runtime.

M3D prerequisites: this validated original-frame set plus immutable artifact;
M3B style catalog and independent topology truth; separately versioned evidence-
linked claim IDs/resource bounds; deterministic contact/separation/label hypotheses;
unresolved MOS/polarity/ground/value alternatives; independent partition/abstention
tests. Geometry/confidence alone cannot merge canonical nets. No conversion/UI/
real inference/image admission is authorized by M3C.

Commands/results: [test lane](test-plan.md#m3c-offline-contract-lane) and
[checkpoint](implementation-plan.md#m3c-intake-observation-and-replay-checkpoint).
