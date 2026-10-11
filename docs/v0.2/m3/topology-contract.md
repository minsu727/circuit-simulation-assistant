# M3D implemented topology contract

Prompt 045 implements **prepared observations → unapproved topology hypotheses**.
Version: `m3-topology-1`. M1 remains `0.2-draft1`; M2 still rejects image origin.
This is not image recognition, human confirmation, electrical validation or
execution permission. M3E review/conversion/admission remains unimplemented.

## API and ownership

`circuit_image` exports `TOPOLOGY_VERSION`, `TopologyLimits`, `TopologyState`,
`TopologyHypothesis`, `TopologyResult`, `reconstruct_topology`, `validate_topology`,
`topology_to_dict` and `dump_topology`. The immutable records live in
[topology_models.py](../../../circuit_image/topology_models.py); reconstruction
and explicit serialization are separate modules. No final parallel Circuit IR,
CircuitDocument, Connection or approval envelope is created.

```python
result = reconstruct_topology(observation_set, image_artifact)
hypothesis = result.hypothesis  # None on input/identity/resource failure
diagnostics = validate_topology(hypothesis, observation_set, image_artifact)
payload = topology_to_dict(hypothesis)
```

Inputs are validated M3C `ObservationSet` and its exact intake artifact. M3D
reparses the explicit M3C projection and compares typed identity, local IDs,
references and response digest. A dataclass replacement cannot grant authority.
`validate_topology` recomputes and compares the complete hypothesis, detecting
stale digest, altered membership, impossible references or fabricated evidence.
It grants no approval. Invalid input returns stable diagnostics without raw text.

The sidecar contains components referencing carried symbol/text observations,
terminals with provisional roles/alternatives, nets containing wire/label/ground
references, claims, local alternatives, issues, both technical candidate states,
source/extraction identity, limits and digest. **Pin-to-net claims are the sole
candidate terminal membership view**; a component or pin has no hidden net field.
Original value records remain in M3C through text observation references; no value
is repaired or duplicated into a new electrical schema.

## Status is not approval

| Field | Meaning |
| --- | --- |
| `topology_state=RESOLVED` | Prepared connectivity evidence has no unresolved/missing topology issue |
| `NEEDS_REVIEW` | Ambiguous, conflicting or uncertain topology evidence |
| `INCOMPLETE` | Missing required observations, e.g. bulk, terminal or partial coverage |
| `UNSUPPORTED` | Retained unsupported symbol; takes precedence over other issues |
| `conversion_state` | Includes topology plus missing values, source definition, model/W/L and reference-ground prerequisites |
| `candidate_state` | Only `DRAFT` or `NEEDS_REVIEW`; never `CONFIRMED` |
| `review_required` | Always true, even for resolved prepared topology |
| `admission_state` | Always `BLOCKED_M3E`; no execution authorization |

Missing issues also require human review. For state aggregation, unresolved
conflicts precede missing data, while unsupported scope precedes both. A missing
value may coexist with resolved topology and incomplete conversion. A visible
but absent bulk does not become a guessed source-to-bulk tie.

## Coordinates and connectivity

All geometry uses validated original pixels, independent of monitor DPI.
Exact arithmetic over the validated coordinate values determines collinearity
and point-on-segment contact. **Positive join tolerance is zero**: even a
subpixel gap is not a wire. A finite review-distance radius, default **2 px**,
configurable from **0 to 12 px**, identifies nearby unresolved contacts only.
It never authorizes a merge. This is separate from evaluation's 12 px pin match.

- Certain wire segments sharing endpoints, bending at a shared endpoint, or
  overlapping collinearly form evidence-linked continuity groups. Bounding-box
  overlap alone has no electrical meaning. Component bodies create no net edge.
- An explicit connected junction point must lie on every referenced certain
  wire. An explicit separated crossing stays separated. An unexplained geometric
  intersection, including an interior T-contact, retains both local choices.
- Explicit contact candidates preserve touching/separated/unknown meanings.
  Even a proposed touching contact cannot close a gap. Ambiguous contacts block
  geometry from selecting their pin via another wire. Uncertain wire/pin records
  do not acquire authoritative contact merely because the marker is certain.
- A certain pin at an exact contact attaches only if all eligible wires already
  represent one group. Multiple groups produce attached/unassigned alternatives;
  proximity alone yields a review issue. Component ownership stays the exact
  observation reference. No component function/bias plausibility is consulted.
- Contradictory positive and negative contact constraints quarantine the entire
  affected positive group; no insertion-order winner or silent short is chosen.

Union-find constructs only supported candidate connectivity. Opaque net IDs are
content-derived from version and sorted observation members; IDs and results
exclude time, memory addresses, random UUIDs and local paths. Reordering provider
records does not change the normalized response or hypothesis.

## Labels, ground and device semantics

Flat-scope labels use trimmed ASCII case-insensitive identity with bounded simple
identifier spelling; no fuzzy, hierarchy, directive or expression interpretation.
Only certain labels with an explicit certain-wire attachment can merge separated
wire groups. Raw text is retained independently of the equivalence claim.
Unreadable/ambiguous labels never merge. Groups carrying conflicting distinct
labels are reviewed and cannot propagate label equivalence to other groups.

Explicit signal-ground observations require **one observed lead endpoint** in
their geometry points and an unambiguous contact group. A bbox alone is not an
attachment point. Earth/chassis/unknown conventions require review. Disconnected
ground symbols do not acquire a hidden global net. `GND`, `RETURN`, `0`, `VDD` and
`VSS` text do not automatically become ground or numeric independent sources.

Source positive/negative and arrow-defined current-source roles are preserved in
`terminal_role` claims and terminal records, including rotated symbols. MOS
D/G/S/B/UNKNOWN roles and alternative role observations are carried unchanged:
no D/S swap, bulk tie, model profile or process parameter inference. Unsupported
symbols and their pins are retained. The BJT replay preserves unknown M3C roles
rather than expanding the supported pin vocabulary or replacing it with a MOS.

## Alternatives, evidence, serialization and bounds

Every electrical claim has existing observation evidence: pin + conductor,
junction + referenced wires, ground + contact, labels + attachments, or symbol +
terminal for role claims. Alternatives retain their original M3C choice ID when
available. Issues identify affected observations and distinguish topology from
conversion prerequisites. Raw image bytes, filesystem paths, provider secrets,
M1 validation states, simulation directives and approval records are excluded.

Canonical JSON maps records explicitly and sorts semantic sets. The digest binds
image/source, exact observation response/extraction, topology version, all limits,
normalized claims/nets, alternatives, issues and states. It is reproducibility
and staleness protection, **not an approval token or signed fidelity proof**.

Default budgets: 8,192 claims; 64 ambiguities; 8 choices per ambiguity; 64 total
choice combinations; depth exactly 1; 100,000 geometric pair checks; 65,536
evidence references. These are configurable finite positive budgets, with the
actual settings bound in the digest. Depth and review radius have hard contract
limits. The product of independent local option counts is a conservative upper
bound, not a list of certified full alternative circuits. No Cartesian product
is materialized and no first option is selected on overflow. Budget violation
returns no hypothesis with `TOPOLOGY_LIMIT_EXCEEDED`.

## Independent evaluation

[topology_evaluation.py](../../../circuit_image/topology_evaluation.py) provides
`evaluate_topology(hypothesis, observations, image, reference)` and frozen
evaluation-only reference records. References are bounded, source-bound,
in-memory projections of independent annotations, not a new final circuit schema
or a reconstruction input. Unknown/duplicate references, non-finite geometry,
wrong identity and stale predictions fail closed. The evaluator performs no I/O.

Protocol remains `m3-evaluation-1`, lane **prepared-observations**. Symbol matching
uses IoU ≥ 0.50; terminal matching occurs within matched symbols and ≤ 12 original
px. Correspondence maximizes cardinality, then total IoU / minimum total Euclidean
distance, then lexicographic stable-ID pairs. Bounded residual-flow matching can
revise earlier choices; it is not greedy or factorial enumeration. Type, polarity
and role are judged **after geometry**, never used to improve correspondence.

Opaque net IDs are aligned by maximum correctly role-matched pin overlap with
ground and flat-label anchor compatibility. Separate false/missing terminal-pair
joins and net merge/split counts expose imperfect partitions. Spurious connected
pins, duplicate components, missed terminals, incorrect roles, added ground and
wrong label/junction disposition invalidate exact topology. Zero denominators
are null, never fabricated 100% accuracy.

For ambiguous truth, only joins/separations shared by all authored partitions
are required. Joined uncertain pairs and false confident connected junctions are
reported separately from correct abstention. Required-review recall compares
kind **and localized target**, with explicit aliases for missing/unreadable value,
gap/contact and missing bulk terminology. Review precision is not claimed: extra
genuine issues need independent adjudication.

The independent [replay catalog](../../../tests/fixtures/topology_observations/README.md)
contains 16 handcrafted inputs; original M3B images/annotations and M3C partial
replays remain unchanged. Twelve eligible unique supported cases pass exact
topology, **82/82 required pins**: divider, rc, missing_value, unreadable_value,
rlc, nmos, pmos, cross_open, cross_dot, shared_labels, rotated_sources,
supply_unknown. Cross ambiguity/gap abstain, missing bulk is incomplete, BJT is
unsupported. BJT role/anchor errors are reported honestly and excluded from the
supported exact denominator. There are no false primary joins in these prepared
cases. This does **not** measure AI recognition accuracy or held-out generalization.

## Known limits and M3E prerequisites

The original prerequisite list below is now implemented in the scoped M3E domain
[Promotion and Admission contract](promotion-and-admission.md), authorized by
Prompt 046. Original M3D hypotheses still remain unapproved and unchanged;
UI, live extraction and actual image execution are not implemented.

Prepared observations may themselves be wrong despite valid syntax and coherent
geometry. No pixel-based recognition, inferred symbol/body masking, fuzzy snapping,
hierarchy, arbitrary labels, full alternative graph enumeration or ground/supply
convention inference is implemented. A topology digest cannot attest image fidelity.

M3E must implement exact-image/observation/topology-bound review revisions,
explicit dispositions/corrections for each unresolved contact/role/value/model,
atomic stale-safe human confirmation, a pure image-origin M1 adapter and unchanged
M1 validation. It must specify and receive authorization for any image-aware
admission extension; current M2 image-origin restrictions remain intact. Human
review, technical validity, CIRCUIT_EXPORT, REPRESENTATION and EXECUTION approvals
must remain separate. Only then may UI or actual image execution be considered.
