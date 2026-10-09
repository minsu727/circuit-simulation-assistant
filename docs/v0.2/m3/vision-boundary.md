# Vision adapter, privacy and untrusted input

**Design only.** The [candidate sidecar](candidate-contract.md) is the output
boundary; the provider must not return a trusted CircuitDocument or approvals.

## Proposed provider seam

A replaceable extraction adapter receives a bounded decoded image asset,
explicit extraction options and a versioned observation contract. It returns
either an ObservationSet proposal with provenance/uncertainty or a typed failure.
Local orchestration remaps IDs and validates all fields before assembly.

This is a responsibility contract, not a currently implemented function signature.
Core M1 types know nothing about provider SDKs, network credentials or endpoints.

| Adapter responsibility | Local controller responsibility |
| --- | --- |
| Symbol/text/pose/terminal observations and alternatives | Validate tagged response shape, references, bounds, sizes and non-finite data |
| Report model/version if available, otherwise unknown | Assign local stable IDs and bind source/transmitted image digests |
| Report failure/abstention and optional measured usage | Preserve unresolved claims; do not repair unsupported output into success |
| Optional provider connectivity suggestions | Treat them as claims; reconstruct only reviewed constraints |
| No evaluation/model library paths | No automatic approvals, shell execution or simulator launch |

Default tests use deterministic owned response files/fakes. Provider/model
selection, SDK dependencies, response wire version and exact resource budgets
remain implementation review decisions; no vendor is chosen in M3A.

## Intake and image identity

- Accept PNG/JPEG raster bytes after magic/decoder validation, not extension
  alone. A screenshot is just an image; filenames, URLs and metadata cannot
  select local files. Do not accept SVG/scripts/PDF/archives in the initial lane.
- Bound encoded bytes, decoded pixels, dimensions, observation counts, text
  lengths, candidate alternatives and request duration before expensive work.
  M3B defines fixture-informed numeric budgets; over-budget input fails or
  requests an explicit rescale, never silently loses evidence.
- Detect malformed/truncated/decompression-bomb inputs. Normalization cannot
  overwrite the original; preserve dimensions and original-to-working transform.
  EXIF orientation and later crop/deskew are explicit transformations.
- Remote payload uses a decoded, re-encoded raster without unnecessary metadata.
  Identify both original bytes and exact transmitted raster/crops by digest.
  Image pixels may themselves contain identifying text; stripping metadata does
  not make an image anonymous.
- Estimated deskew/denoise and wire/dot filtering are hypotheses. Keep the original
  view; if a transform hides a junction/value or is not invertible to its evidence,
  require review or reject it. Never supply an overlay in an undocumented frame.

## Consent and retention policy

Default proposed behavior: no network transfer; original/working image and
candidate/review material live in the active session. The user may explicitly
export a local review bundle for reproducibility, with its contents disclosed.
Temporary storage, if required, uses app-controlled ignored runtime locations,
not arbitrary paths from an image/provider response. Deleting the session/bundle
must clear app-owned image/crop/cache copies under a documented retention policy.

Before any remote request, show provider/model if known, purpose, exact full-image
or crop scope, whether visible content/metadata is transmitted, estimated/bounded
usage when available, and the provider's independently verified retention policy.
Require an explicit opt-in action for that identified payload/provider. Image
change, crop expansion, provider switch or new extraction invalidates it. No
automatic upload on file selection/rerun, hidden provider fallback or retry with
a different provider. Retries consume only explicitly disclosed/authorized budget.

Candidate confirmation, M2 simulation approval and the existing optional
result-interpretation API approval are **not** permission to send a circuit image.
Credentials stay in runtime environment/secret storage, never response objects,
JSON fixtures, hashes, browser-visible diagnostics or public logs. Log operational
IDs/status/latency/counts; do not log image pixels, full responses, recognized text,
authorization headers or filesystem paths by default. Optional local evidence
export is a separate deliberate action.

Deletion claims concern app-owned copies only. Never promise zero provider
retention or that consent proves rights to a copyrighted scan. A future remote
adapter is blocked until its actual data handling and limits have been verified.

## Image injection and schema rejection

Visible instructions such as “ignore your rules”, model definitions or commands
are **text observations**, not instructions for the application. Extracted/provider
text cannot become an API credential, URL to fetch, local path, shell argument,
Python expression, SPICE directive, include/library/model body or patch program.

The provider prompt requests data extraction only, but prompting is not the
security boundary. Closed response types, exact references, bounded typed scalars,
operator confirmation and current M1/M2 allowlists are the consuming boundary.
Reject unknown fields/discriminators, executable payloads, non-finite values,
invalid coordinate frames and excess alternatives; retain a bounded diagnostic,
not an auto-converted partial result.

Raw OCR literals stay evidence. Normalize a selected numeric/notation candidate
through existing scalar parsing after review; never evaluate expressions or infer
commands from strings. Model text such as “NMOS”, “2N...” or a printed .model is
not a trusted registry profile. Only a separately selected sealed M2 profile may
be considered later.

[Topology rules](topology-and-uncertainty.md) define abstention and
[Test Plan](test-plan.md) defines prompt-injection/privacy negative cases.
