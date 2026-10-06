# M1 Validation versus M2 Export Eligibility — Proposed

## Exact Preconditions

M2 export is permitted only when **all** gates pass for the same immutable snapshot:

1. Strict M1 typed loading succeeded (or a typed record passed the same schema/constructor/graph checks). Schema 0.2-draft1; no partial document/coercion.
2. Fresh internal `validate_document(document)` yields TechnicalState.VALID, profile/ruleset `m1-local-v1`, matching current revision and all required local checks complete. Cached/imported reports are not sufficient.
3. Initial profile admission: Origin.MANUAL, source_image_reference=null, flat supported devices/typed fields; no unresolved ambiguity or required pin/connection/model/value/source setting. Every `Ambiguity.state` is RESOLVED with a valid explicit disposition if present.
4. Checked graph supplies exactly one net for each required role, one ground and unambiguous ownership. Temporary exporter views use connections only; there is no geometry/label repair.
5. All M2 number/name/parameter/source constraints pass; waveform DC/initial value compatibility and fixed output grammar are enforced. Unsupported extra fields fail closed.
6. Each MOS has an exact compatible trusted registry model and required W/L. M1 model deferral is not automatic M2 permission.
7. The complete warning/deferral policy below passes; allowed warnings have been explicitly acknowledged. No new issue code is inserted into M1 and no waiver transforms technical state.
8. Current CIRCUIT_EXPORT envelope is approved, correct-scope and bound to snapshot/revision/electrical/report/registry/exporter/warning set. Approval verification is described in [Approval Contract](approval-contract.md).

The result is **eligible to generate a restricted circuit preview**, not to launch LTspice. Execution additionally needs exact representation approval, condition approval, adapter rechecks, an installed LTspice and successful real compatibility checks. An eligible circuit can still fail the simulator or contain bad analog design; those claims are outside deterministic export validation.

## What M1 Already Establishes

M1 checks shape/version/IDs/references/incidence/roles/ground/labels, selected exact quantities, source dimensions/typed waveform timing, MOS body/ref/W/L, narrow linear DC/island/constraint checks and explicit ambiguity/confidence/provenance. ERROR and AMBIGUOUS block; UNVALIDATED is incomplete required checking. Fresh ValidationResult is separate from archival `validation_state`; it has no source content hash and no approval capability.

M1's INVALID/AMBIGUOUS/UNVALIDATED results remain intact. Exporter-specific refusals are separate ExportIssue records; a VALID M1 document can legitimately be BLOCKED by M2. Export eligibility never changes source fields or M1 TechnicalState. Initial M2B/C has no MOS support until the separately reviewed M2D model slice.

## Warning and Deferral Policy

Unknown warning or deferred-check identifiers fail closed under this initial export contract. Do not check only `error_count==0` or permit all WARNING results. Acknowledgement is necessary for eligible warnings, never sufficient for blocked ones.

| Fresh M1 warning / deferral | M2 policy |
| --- | --- |
| LABEL_ALIAS | Nonblocking if labels attach consistently to one canonical net and all alias warning IDs are acknowledged; names still derive from net IDs |
| DANGLING_WIRE | Nonblocking **only** the existing resolved declared unused-stub disposition; every required device pin remains explicitly connected; exact warning acknowledgement required. Unresolved wire-gap ambiguity is already blocked by M1 |
| CHECK_DEFERRED on selected MOS model_ref | Conditional: exact repository-owned typed profile/polarity/version/digest must satisfy M2's narrow model provision. Preserve M1 warning/deferral in original report and acknowledge it; never rewrite it to CONFIRMED or claim external catalog validation |
| DC_REFERENCE_UNPROVEN / nonlinear_dc_reference | Block initial M2 export. Unsolved nonlinear reference cannot be cleared by selecting a model or clicking acknowledge. A later solver-qualified profile would need separate design/evidence |
| SOURCE_CONSTRAINT_CONFLICT as WARNING | Block redundant ideal-source constraints in initial M2; do not presume a warning-only local circuit avoids simulator rank/convergence problems |
| PASSIVE_BYPASSED | Block initial M2; known bypass is not removed or automatically corrected. User edits the canonical circuit and reviews again |
| dynamic_source_constraint_proof | Block; no guessed waveform/ideal-loop proof |
| model_catalog_resolution | Required to supply every used MOS via the controlled M2 registry; not applicable to passive/source-only export. Remains explicitly deferred in the untouched M1 report; no global external-catalog claim |
| image_asset_resolution | No image admission in initial manual M2 profile; future asset integrity/review handling is deferred rather than marked confirmed |
| inference_calibration | Calibration is not permission. Manual input/current M1 item resolutions + explicit circuit review are required; no score-threshold auto-approval or new calibration claim |
| human_approval | Satisfied for this export gate by current circuit envelope, later by representation and condition actions for execution; M1 itself never performs these actions |
| full_export_readiness | Narrow M2 preflight establishes only this supported format/context, not general simulator readiness; remain separate from M1 deferred report and real M2F validation |

Every remaining/new warning is blocked until a specific policy is reviewed in a new exporter contract. Trusted model availability, actual simulator success and physical validity are separate facts. For example M1 V05 NMOS common-source can be M2-eligible after explicit trusted model provision; V06 conditional PMOS drain and V07 conditional tail fixtures stay blocked. M2D/F PMOS success uses a separately authored resistively referenced drain, not weakened M1 warnings.

## Conflicts / Ambiguities Resolved in This Plan

| Existing gap | Explicit decision |
| --- | --- |
| Prompt says approval before export, ADR-004 says approve representation after preview | Two separate scopes: circuit approval before generation; artifact/mapping approval afterward; condition approval before run |
| M1 dump is archival and preserves array order, parent requests normalized electrical hash | Full snapshot binding reuses dump_document; versioned electrical hash is a derived subset projection, never competing full serialization or sole authority |
| M1 report binds revision but not content | Internally recompute for exact input, bind snapshot/electrical/report digests, reject same-revision changed content |
| VALID M1 MOS includes model CHECK_DEFERRED | Conditional restricted export only with explicit exact controlled model; no external resolver or arbitrary identifier-only runnable artifact |
| M1 permits distinct DC and waveform initial values | Initial M2 blocks mismatches rather than silently changing source semantics; actual supported source behavior must be proved in M2F |
| M1 ideal inductor vs LTspice's possible default series resistance | Fixed exporter-owned Rser=0 template and later actual checks; no new arbitrary parameter support |
| Current runner imports SpiceEditor but upload/edit helpers are ASC-specific | New adapter entry point required; reuse low-level editor/runner/readers, not the existing wrapper via a suffix trick |

None requires modifying M1 schema/models/validation, current v0.1 behavior or existing ADRs. This documentation makes narrower export admission explicit instead of changing the meaning of VALID. New architecture ADRs are unnecessary for these decisions because they operationalize ADR-002/004 and the parent hash rules; revisit only if future implementation discovers a genuine contradiction.
