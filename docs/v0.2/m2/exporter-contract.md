# Restricted Exporter Contract — Proposed / Not Implemented

## Admission and Device Subset

Target `m2-spice-v1`: flat manual-origin CircuitDocument with `source_image_reference=null`, fresh complete `VALID@m1-local-v1`, explicit roles/incidence, export preflight and current CIRCUIT_EXPORT approval. No image-derived generation claim. Every component and required field must have a supported meaning; one unsupported item blocks the whole artifact.

| M1 ComponentType | M2 support | Ordered terminals / restriction |
| --- | --- | --- |
| RESISTOR | M2C | a, b; positive ohm quantity; no extra parameters |
| CAPACITOR | M2C | a, b; positive F quantity; no initial condition or parasitic fields |
| INDUCTOR | M2C | a, b; positive H quantity; fixed LTspice `Rser=0` preserves the ideal primitive; no coupling/initial-current fields |
| VOLTAGE_SOURCE | M2C | positive, negative; typed DC, optional AC, NONE/SINE/PULSE only |
| CURRENT_SOURCE | M2C | positive, negative; same source subset in A |
| NMOS / PMOS | Conditional M2D | drain, gate, source, bulk; exact W/L; exact selected trusted Level-1 profile required |
| UNKNOWN | Unsupported | Never drop, infer or substitute |

Diode/BJT/op amp/dependent or behavioral sources/subcircuits/transformers are outside M1's closed enum and M2 scope. Ground/label/wire/visual records are not component statements. Arbitrary instance parameters, multiplicity, temperature, initial conditions, hierarchy and expressions are unsupported. The generated inductor option is a fixed exporter template constant, not an opening for user parameters. [Format](netlist-format.md) owns exact tokens.

## Proposed Pure API

Future module `circuit_ir/exporter.py`:

```text
check_export_eligibility(document, *, model_context) -> tuple[ExportIssue, ...]
export_document(document, circuit_approval, *, model_context) -> ExportResult
```

Names/signatures are proposed, not currently importable. `model_context` is an immutable `(registry_version, registry_sha256)` pair selected from exporter-owned known contexts, initially the explicit empty profile context. The exporter verifies the digest against its sealed in-memory registry; the pair cannot inject profile objects, model parameters or SPICE strings. It is not a dictionary or filesystem resolver. The exporter recomputes `validate_document` and a checked graph for the exact document, then M2 checks and approval verification; it never trusts caller-cached results. Preflight is diagnostic-only, emits no SPICE text and grants no authority. Wrong Python argument types are programming errors (`TypeError`); admitted typed but noneligible circuits/approvals return BLOCKED deterministically.

`export_document` performs no filesystem/network/subprocess/simulator access or output writes. It returns complete circuit text only after **all** gates pass. It does not accept directives, filenames, analysis conditions, raw model declarations or uploaded netlist text. Export results never contain RAW/LOG paths or simulator return codes.

## Minimal Proposed Runtime Records

Frozen records with tuple collections, explicit nulls and native string/bool/enum values; no mutable defaults, source mutation or duplicate canonical graph:

| Record | Proposed fields / purpose |
| --- | --- |
| ExportStatus | SUCCESS, BLOCKED; not TechnicalState |
| ExportIssue | code, severity (existing IssueSeverity, restricted to ERROR/WARNING), target_refs, field?, message; blocking is derived, not editable |
| ExportResult | status, spice_text?, issues, provenance?, element_map, net_map, model_map; each map is a sorted tuple of `(source_id, emitted_name)` pairs |
| ExportProvenance | document_id/revision, document/electrical/validation/circuit-approval SHA-256, validation profile/ruleset, exporter contract, registry version/digest, base-netlist digest, mapping digest |

SUCCESS requires complete text/provenance/maps and no blocking ExportIssue. BLOCKED requires `spice_text=None`, `provenance=None`, empty generated maps; diagnostics refer only to relevant source IDs/fields. Never return a usable partial circuit alongside errors. Export-specific records live in the new exporter module; `ValidationIssue` remains M1 technical diagnosis. Source/report/approval binding is specified in [Approval Contract](approval-contract.md); no generic artifact abstraction or new serialization framework is required.

## Failure Categories — Future M2 Codes Only

| Proposed code | Gate / meaning |
| --- | --- |
| EXPORT_DOCUMENT_NOT_VALID | Current M1 report is INVALID, AMBIGUOUS or UNVALIDATED / incomplete |
| EXPORT_APPROVAL_MISSING | No approved circuit envelope |
| EXPORT_APPROVAL_STALE | Snapshot/revision/report/warnings/registry/exporter mismatch, wrong scope or malformed binding |
| EXPORT_UNSUPPORTED_COMPONENT | Device not in the current slice's supported subset |
| EXPORT_UNSUPPORTED_SOURCE | Unknown mode/parameter shape or unavailable source semantics |
| EXPORT_UNSAFE_FIELD | Control characters/raw syntax or malformed trusted identifier reached a token-bearing boundary |
| EXPORT_VALUE_INVALID | Missing/inconsistent/non-finite/unrepresentable SI token or unsupported quantity dimension |
| EXPORT_MODEL_UNRESOLVED | No exact trusted profile for a MOS reference; no external library fallback |
| EXPORT_MODEL_INCOMPATIBLE | Registry/profile shape, polarity or coefficient contract does not match the MOS selection |
| EXPORT_PREREQUISITE_UNRESOLVED | Blocking warning/deferral, unavailable trusted model/reference proof |
| EXPORT_UNSUPPORTED_FEATURE | Image-origin, arbitrary parameters, raw statements, hierarchy or other excluded feature |

These are proposals, **not new M1 issue codes**. Preserve original M1 report separately; `EXPORT_DOCUMENT_NOT_VALID` does not relabel AMBIGUOUS as an electrical ERROR in M1. Order gates as load/type → fresh technical validity → M2 structural/value/model restrictions → warning/deferral decision → approval match → rendering. A prerequisite failure suppresses dependent/cascading failures; missing approval cannot mask known technical problems. Within one gate sort/deduplicate issues by `(severity rank, code, target_refs, field)`; do not freeze prose or expose random/timestamp IDs.

No filename/path APIs are part of export. Later file/representation/execution mismatches are adapter errors, not technical state mutations. [Validation Boundary](validation-boundary.md) defines permitted warnings and discharged requirements; users cannot override a blocked export by acknowledgement.

## Text-Generation Threat Model

Untrusted Circuit JSON may contain prompt-like text, executable-looking labels, malicious model references, renamed devices, contradictory literal/SI data or forged reviewed state. An attacker may replace saved artifacts or reuse old approvals. The exporter must not turn any such text into additional simulator statements.

| Input | Protection |
| --- | --- |
| Component/net IDs | Recheck M1 ID shape/reference uniqueness, then allocate safe ordinal names; never interpolate source IDs into SPICE tokens, comments or filenames |
| Labels / visual text / candidate descriptions / imported messages | Display metadata only; omit from SPICE entirely. No comment escaping mechanism and no evaluator |
| Quantity.literal | Never emit it; M1 checks selected literal/SI agreement, M2 parses/reformats bounded exact SI and rejects unresolved grammar |
| model_ref | Exact registry lookup only; never paste it into a model token, path, include or declaration. Generated model names and controlled template parameters only |
| Source/waveform parameters | Fixed enum/key sets and numeric tokens; no PWL/file data, functions, braces or arbitrary waveform text |
| Templates/comments | Fixed ASCII title/version and lowercase 64-hex digests only; no usernames, timestamps, paths or untrusted text |
| Output tampering | Digest + deterministic regeneration/map checks before representation approval and run; verify exact base bytes again before deriving execution copy |

Reject raw `.include`, `.lib`, `.model`, `.tran`, `.ac`, `.dc`, `.step`, `.param`, `.options`, `.save`, expressions, file paths and shell-like fragments from Circuit JSON. The only base dot statements are a **controlled M2D model template** and terminal `.end`. The later adapter may add exactly one analysis statement from existing builders. Those individually modeled exceptions do not permit raw user text. Extra keys reject at strict load or exporter allowlists, never disappear silently. No shell invocation, eval/exec, filesystem model search or remote resolver is allowed.
