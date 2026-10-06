# Netlist Format — Proposed m2-spice-v1

## Artifact, Ordering and Names

Primary artifact: plain text **`.cir`** circuit netlist, not `.asc`. Internally UTF-8 without BOM, ASCII-only generated content, LF endings, one final LF, no blank/continuation lines. It is a base circuit preview with no selected analysis; the current app cannot execute this route yet. `.end` terminates it; M2E inserts a reviewed analysis on a separate copy.

Official [LTspice syntax reference](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/SPICE-SYNTAX-REFERENCE.html) documents text-netlist support, ground, numeric tokens and UTF-8. Our narrower names/grammar are design restrictions, not LTspice's complete grammar. The [circuit-elements reference](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/CIRCUIT-ELEMENTS-REFERENCE.html) supplies terminal/source conventions; real compatibility is a later test gate.

1. Fixed title: `Circuit Simulation Assistant restricted circuit`.
2. Fixed comment: `* exporter m2-spice-v1`.
3. `* source_sha256 <full reviewed snapshot digest>` and `* electrical_sha256 <electrical projection digest>`; no raw source ID/labels, approval timestamp or later representation-approval hash.
4. Used controlled model declarations sorted by registry profile ID (M2D only).
5. Components in exact ASCII component-ID sort order, not original array/pin order.
6. `.end` and final LF.

Names use allocation, **not lossy normalization**:

| Entity | Mapping |
| --- | --- |
| Unique explicit ground net | `0` only; do not infer from labels or ID text |
| All other nets | Sort exact ASCII net IDs excluding ground; assign `n_0001`, `n_0002`, … |
| Elements | Group by prefix R/C/L/V/I/M; sort component IDs within each group; assign `R_0001`, `V_0001`, etc. NMOS and PMOS share the M group |
| Used trusted models | Sort distinct exact profile IDs; assign `mdl_0001`, …; one declaration per selected profile |

Minimum ordinal width is four digits, growing normally above 9999; never truncate, wrap or reuse. Net/model names use lowercase ASCII, element prefixes uppercase; verify uniqueness under SPICE case-insensitive comparison as well as exact identity. Source IDs that differ by legal punctuation/case cannot collapse through replacement; supported M1 ID/reference checks still run. Generated names contain only alphanumerics/underscore; no GND synonym or user-selected reserved token. Labels do not influence allocation. Adding/removing/renaming IDs may renumber; new digests/approval/maps are required. Array permutations preserve allocated names/device rows but change the full snapshot hash and therefore invalidate old approval and change its source-hash comment.

`element_map`, `net_map`, `model_map` include every emitted device/net/used profile and the ground pair, sorted by source ID. They are sidecar data, not copied comments. Initially preserve explicit unused net records in net_map; they have no invented device/trace. Adapter RAW availability checks must not promise a trace for an unused net.

## SI Number Policy — Option B

Emit **normalized exact SI**, not `Quantity.literal`. This already agrees with the parent [quantity/export contract](../circuit-json-schema.md). Original literal/grammar remain in source JSON for review. M1 verifies selected literal/SI consistency; M2 independently reparses required SI text with the existing finite SI grammar. No float conversion or context-sensitive `Decimal.normalize()` rounding.

For deterministic emitted numeric text: use exact Decimal tuple digits/exponent, remove insignificant coefficient zeros, normalize all signed zeros to `0`. For nonzero magnitude whose adjusted exponent is -3 through 6 inclusive, emit fixed decimal without `+`, unnecessary leading/trailing zeros or final dot; otherwise emit one leading mantissa digit, optional fractional digits and lowercase `e` followed by an integer exponent without plus/leading zeros. Preserve every significant digit. Respect M1's 128-character token and adjusted-exponent ±300 bounds; reject a representation exceeding them. Required types/sign/dimensions are checked before rendering. No suffix, unit tail, exponent expression or interpolation.

| Validated value | Emitted token |
| --- | --- |
| `1k` (SPICE) → SI 1000 | `1000` |
| `1M` → SI 0.001 | `0.001` |
| `1Meg` → SI 1000000 | `1000000` |
| SI 0.000001 | `1e-6` |
| SI -0.0000000025 | `-2.5e-9` |
| SI -0 or 0.000 | `0` (where zero is legal) |

Trade-off: SI text is less like the original engineering notation, but unambiguous, deterministic and independent of suffix/unit-tail interpretation. The original presentation is still available in review. Arbitrary model coefficients use the same exact formatter on trusted finite decimal strings with template-owned unit definitions; do not extend M1 Quantity units merely for model syntax.

## Passive and Source Rows

```text
R_0001 <a-node> <b-node> <positive-ohm-SI>
C_0001 <a-node> <b-node> <positive-F-SI>
L_0001 <a-node> <b-node> <positive-H-SI> Rser=0
```

Pin roles select endpoints via checked connections; neither `pin_ids` order nor visual orientation decides terminal order. `Rser=0` is a fixed LTspice ideal-inductor setting: the official reference documents a nonzero default series resistance, while M1's L projection is ideal DC short. This exporter-owned constant must have golden and actual-simulator tests. No R/C parasitic or IC option is accepted from source JSON.

Voltage polarity is positive minus negative; current flows positive → negative. For V/I sources:

| WaveformKind | Template after element and two nodes | Required exact keys |
| --- | --- | --- |
| NONE | `DC <dc> [AC <magnitude> <phase>]` | Empty waveform parameters, explicit dc |
| SINE | `SINE(<offset> <amplitude> <frequency> 0 0 0) [AC <magnitude> <phase>]` | offset, amplitude, frequency |
| PULSE | `PULSE(<level1> <level2> <delay> <rise> <fall> <width> <period>) [AC <magnitude> <phase>]` | level1, level2, delay, rise, fall, width, period |

Brackets/angle tokens above are specification notation, never emitted characters. Each actual row uses single spaces. AC is omitted only when ac=null; explicit magnitude 0 is emitted as `AC 0 <phase>`. Magnitude unit is V/A matching the device; phase is deg and is not silently wrapped. SINE has positive Hz and signed finite offset/amplitude; the last three zeros are the profile's nonconfigurable delay/damping/phase, not guessed image settings. PULSE has nonnegative delay, positive rise/fall/width/period and exact `rise+width+fall <= period`; repetition is unbounded within the separately approved transient duration, not a hidden user cycle count.

**Additional M2 restriction:** for SINE, source.dc must exactly equal offset; for PULSE it must equal level1. Do not emit competing DC/waveform operating-point specifications or silently discard a distinct dc value. M1 permits such distinct settings; M2 blocks them as EXPORT_UNSUPPORTED_SOURCE until a later version has proved explicit independent-DC semantics. For matching initial values, the waveform row carries that initial operating-point value without a separate DC token. AC remains independent typed small-signal input. M2F must check DC/AC/transient behavior for both V and I sources and cannot call syntax goldens actual simulator evidence.

No PWL/EXP/file source, arbitrary expression, source resistance or extra waveform key is supported. No `.ac/.tran/.dc` appears in base export.

## MOS and Controlled Model Templates — M2D

```text
M_0001 <drain> <gate> <source> <bulk> mdl_0001 W=<width-SI-m> L=<length-SI-m>
```

NMOS and PMOS use the same four-terminal M syntax; the selected trusted model supplies polarity. Four explicit roles/connections and positive width/length in m are mandatory. Instance parameters must be exactly `width`, `length`; no AD/AS/PD/PS, multiplicity, hidden body tie, D/S swapping, VDMOS or subcircuit fallback.

Initial proposed registry `m2-demo-models-v1` is repository-owned immutable typed data, not arbitrary strings/files. Exact `model_ref` keys `repository_demo_nmos` / `repository_demo_pmos` select reviewed educational Level-1 profiles; unknown/null references block. No filename searching, library scanning or fuzzy/default substitution. The registry must display coefficients/polarity/version/digest during circuit review. M1's symbolic refs do **not** establish these models today.

Proposed frozen `TrustedModelProfile` fields: `profile_id`, `component_type` (existing ComponentType.NMOS/PMOS only), and exact finite SI decimal strings `vto`, `kp`, `lambda_`, `gamma`, `phi`, `cgso`, `cgdo`. LEVEL=1 is fixed by the template, not selectable. Template-owned dimensional/sign checks enforce the table below without adding units to M1 Quantity. The sealed registry is a sorted tuple of these records; source JSON cannot supply or edit them. Its digest covers explicit `{registry_version, profiles}` with each profile's ID/type and all coefficients normalized by the SI formatter, plus fixed level=1, using compact sorted native JSON/UTF-8/SHA-256. Empty context is the same shape with version `m2-no-models-v1` and profiles=[]; no model statements are emitted.

Proposed demo-only coefficients, to be implemented/tested in M2D and validated in M2F (not semiconductor characterization):

| Template field | NMOS | PMOS | Template-owned unit/constraint |
| --- | --- | --- | --- |
| LEVEL | 1 | 1 | Fixed integer |
| VTO | 1 | -1 | V; polarity-consistent nonzero sign |
| KP | 0.0001 | 0.0001 | A/V², positive |
| LAMBDA | 0.02 | 0.02 | 1/V, nonnegative |
| GAMMA | 0 | 0 | V^0.5, nonnegative |
| PHI | 0.6 | 0.6 | V, positive |
| CGSO | 0 | 0 | F/m, nonnegative |
| CGDO | 0 | 0 | F/m, nonnegative |

Emit only used models via fixed field order `LEVEL VTO KP LAMBDA GAMMA PHI CGSO CGDO`:

```text
.model mdl_0001 NMOS (LEVEL=1 VTO=1 KP=1e-4 LAMBDA=0.02 GAMMA=0 PHI=0.6 CGSO=0 CGDO=0)
```

The actual SI formatter above emits `KP=1e-4`; the row is proposed syntax, not a generated/tested artifact. Profile coefficient changes require a registry version/digest change and new approval. No generic user `.model` text or external `.include/.lib` is accepted. This controlled declaration is the sole model-statement exception to the injection ban. Output-capacitance fixtures should use explicit C components for reproducible low-pass tests rather than promise intrinsic bandwidth from this simple model. Model provision does not prove an operating point/convergence or clear M1's nonlinear-reference warning.

## Example Device Body and Adapter Placement

An independently authored divider with V1=1 V, R1=1000 ohm vin→vout, R2=2000 ohm vout→ground and net IDs `n0`, `vin`, `vout` maps to this device body (header digests computed separately, no fake hashes):

```text
R_0001 n_0001 n_0002 1000
R_0002 n_0002 0 2000
V_0001 n_0001 0 DC 1
.end
```

It is an illustrative fragment, not a complete runnable example or saved M2 fixture. M2C goldens must include the fixed title and actual independently reviewed header hashes. M2E inserts exactly one trusted analysis directive before the single `.end` in a run copy. Registry, mapping, validation and approval references remain in [provenance](architecture.md#file-ownership-and-provenance); no local path or user text is embedded in circuit comments.
