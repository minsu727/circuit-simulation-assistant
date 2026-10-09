# Topology and uncertainty

**Proposed rules, not recognition claims.** The [candidate](candidate-contract.md)
holds hypotheses; only [reviewed conversion](review-contract.md) creates canonical
M1 connections.

## Reconstruction contract

Work in original-pixel coordinates using recorded transforms. Symbol/body masks,
terminal candidates, wire endpoints/segments, crossings and labels are separate
evidence. A line through a resistor/MOS body is not necessarily a conductor.

Build a constraint view: candidate contact/equality, explicit separation and
alternative interpretation. A preview may show a provisional choice, clearly
marked unconfirmed. It must not discard other plausible interpretations.
For confirmed constraints, deterministic union-find can form equipotential
groups; separation conflicts, unresolved contacts and unowned terminal references
block promotion. Never merge by closeness/confidence alone.

Component ownership is not electrical conductivity. Do not join all terminals of
a component, infer a MOS channel path as a wire, or treat DC-open C as absent.
Existing M1 remains responsible for electrical/reference checks after conversion.

## Drawing interpretation

| Feature | Candidate treatment / required review |
| --- | --- |
| Zigzag / rectangular resistor | Same resistor type hypothesis under separate catalog styles; preserve body/terminal evidence |
| Continuous corner / wire turn | Segment contact hypothesis from endpoints; bounded gap evidence, no proximity-only bridge |
| Wire endpoint at a pin | Explicit terminal-contact claim, not contact with the entire symbol bbox |
| Dot at crossing | Positive junction evidence; distinguish from text/noise and confirm junction membership |
| Crossing without dot | Connected/unconnected alternatives according to selected style; no universal “no dot” rule |
| Bridge/hop / T contact | Preserve bridge/separation or T-contact evidence; unclear/occluded styles remain NEEDS_REVIEW |
| Wire gap / near contact | Connected and separated alternatives; never silently close the gap |
| Net label | Explicit attachment claim to a conductor; proximity alone cannot establish it |
| Repeated label | Confirm same flat-scope identity and attachments before joining; use M1 trimmed ASCII case-insensitive identity, never fuzzy matching |
| Rotated / mirrored symbol | Catalog pose transform plus terminal-role choices; retained original evidence |
| Multiple possible graphs | Keep bounded alternatives and affected membership deltas; ask for a choice, not a highest-score topology |

A clear image can still be interpreted incorrectly. The user must inspect the
full drawing and all accepted critical relations, not only a confidence-filtered
issue list. Resource limits can cap alternatives; exceeding the cap yields
NEEDS_REVIEW/unsupported complexity, not automatic pruning to one circuit.

## MOS, power and reference handling

| Situation | Rule |
| --- | --- |
| NMOS versus PMOS | Type alternatives and symbol/arrow evidence; no choice from visual location alone |
| Gate/drain/source/bulk | Explicit role mapping after pose review; emit existing M1 D/G/S/B roles, never order by coordinates or pin-list position |
| Three-terminal symbol | Bulk unresolved until an explicit catalog convention and user-confirmed bulk net; no automatic source tie |
| Visible body tie | Separate connection evidence; must agree with role and net choices |
| Missing W/L/model | Required review input; no default geometry/model from provider or simulator |
| Printed model identifier | Evidence only; selecting an educational sealed profile is an explicit modeling choice, not identity with that named device/PDK |
| VDD/VSS label without source | A labeled net does not create a supply component/value/reference. Missing supply semantics block executable promotion |
| Ground symbol(s) | Explicit ground-group confirmation; multiple marks may share one accepted reference group, distinct earth/chassis/power conventions are not assumed equivalent |
| Missing ground | No hidden node 0. User must supply/confirm a reference or reject the interpretation |
| Source polarity/arrow | Confirm positive/negative terminal roles; retain sign/direction, no automatic reversal after rotation |
| Incomplete input source | Missing DC/AC/waveform fields are review issues; no 1 V AC, zero bias, phase or waveform invented |
| Missing input/output labels | Opaque net IDs are allowed; target/reference selection remains a later explicit analysis choice |

If a user deliberately adds a missing supply, reference or parameter, record it
as a manual correction/modeling assumption distinct from observed image facts.
Require explicit value, component type, both source terminals and connections;
a “VDD” string alone cannot instantiate a source. Preserve Origin.IMAGE.

Current M2 admits only sealed demo NMOS/PMOS profiles and explicitly constrained
source syntax, including DC/initial value agreement for SINE/PULSE. M3 may not
weaken those conditions or infer a hidden body/model to pass them.

## Numeric and text interpretation

Preserve raw text/crop, recognized alternatives, unit and notation selection.
M1 SPICE grammar treats M/m as milli and Meg as mega. Printed “1 MΩ” commonly
suggests a different notation, so **do not send it blindly through SPICE parsing**.
Present notation alternatives and require explicit confirmation when unclear.

Confirmed printed engineering k/mega/u/µ/μ/n/p and unit spellings map by a
versioned local notation table to a legal bounded SI scalar/unit, retaining the
original evidence. Greek micro, Ω, decimal punctuation, OCR “O/0”, “l/1” and
scientific notation changes need attributable normalization; ambiguity stays
visible. M1 Quantity consistency, finite bounds and device dimensions are
unchanged. No arbitrary formulas, W/L ratio expressions, arithmetic evaluation,
unit guessing from identifier or default missing value.

Labels/reference IDs stay separate from numeric text. Duplicate or unreadable
reference names require correction or safe opaque ID mapping with an explicit
display association. Do not truncate names or create a known reference by fuzzy
matching.

## Fail-closed outcomes

NEEDS_REVIEW blocks confirmation/promotion for unclear crossing, role, label,
source polarity, missing value/terminal/ground/model, contradictory contacts or
multiple topologies. Malformed assets/records give failure without a candidate.
Actual unsupported BJT/op-amp/IC/hierarchy yields a retained blocking issue;
unsupported components are never omitted from an executable partial circuit.

A user may reject a false detection with a reason. Rejecting an interpretation
does not authorize removal of a real unsupported device; deliberate redesign is
outside the initial fidelity benchmark. M1 errors cannot be waived by confidence
or a review click. Simulator success never resolves topology ambiguity.

Proposed M3 diagnostics (e.g. unresolved junction, missing source definition,
unsupported image component) are sidecar diagnostics, **not new M1 issue codes**.
The exact code catalog will be authored with independent M3B expectations.
