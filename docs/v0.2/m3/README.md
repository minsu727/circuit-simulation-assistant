# v0.2 M3 — Image-to-Circuit IR plan

**M3A design and M3B owned fixture/evaluation foundation. No M3 extraction,
review UI, conversion or image execution is implemented. M3 is not closed.**
Prepared 2026-10-09 (Asia/Seoul).

Design goal: a clean printed textbook-style schematic image becomes an untrusted,
reviewable candidate; explicit correction/confirmation produces Circuit IR for
existing deterministic validation and separately approved execution. A plausible
but incorrectly connected circuit can be technically VALID and simulate
successfully. That is the central quality risk.

## Inspected baseline and scope differences

- Repository HEAD: `7152c13`, latest M2 evidence commit. [M1](../m1/status.md) and
  [restricted M2](../m2/status.md) are closed in their documented scopes.
- The documented local baseline is **848 passing tests**. This documentation-only
  task does not rerun them or claim new Vision/LTspice/hosted CI results.
- Existing `README.md` working-tree edits are outside this task and preserved.
  Only this new documentation directory is authored.
- M1 already has image references, visual records and ambiguity/confidence fields;
  its wire version remains `0.2-draft1`. Rich observations/review history belong
  in an M3 sidecar, not additional M1 fields.
- **Current M2 explicitly rejects image origin or any image reference.** Reviewed
  image conversion can reach M1 now in principle, but image execution needs a
  separately approved future admission contract. Never erase image provenance or
  relabel the document manual to pass the existing gate.
- Prompt 042 prioritizes printed textbook-style drawings. The older
  [architecture](../architecture.md)/[roadmap](../roadmap.md) started with LTspice
  screenshots and placed textbook examples later; that sequence is historical.
  M3 includes minimum review UI earlier than the older M4 plan because candidate
  extraction cannot safely progress without correction. No existing UI is changed.

## Document ownership

| Document | Single source of detail |
| --- | --- |
| [Architecture](architecture.md) | Boundaries, MVP comparison, current API alignment, future image admission |
| [Candidate Contract](candidate-contract.md) | Proposed typed observations/claims, IDs, evidence, revisions and conversion fields |
| [Vision Boundary](vision-boundary.md) | Provider adapter, intake, consent, privacy and injection handling |
| [Topology and Uncertainty](topology-and-uncertainty.md) | Wire/net hypotheses, symbols, values, MOS/power/ground and fail-closed rules |
| [Review Contract](review-contract.md) | Human actions, snapshot confirmation, M1 conversion and approval invalidation |
| [Test Plan](test-plan.md) | Owned fixtures, independent goldens, metrics and evaluation lanes |
| [Implementation Plan](implementation-plan.md) | M3A–G deliverables, dependencies and acceptance gates |
| [Prompt Breakdown](prompt-breakdown.md) | Small implementation handoffs, protected scope and unresolved decisions |
| [Fixture Annotations](fixture-annotations.md) | Implemented test-truth format, outcome/unknown rules and independent catalog |
| [Evaluation Protocol](evaluation-protocol.md) | Future matching/denominators, topology-first success, resource proposals and report boundary |

## M3B implemented boundary

Prompt 043 starts from pushed M3A commit `ac86659`; its exact-source hosted
[CI run](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37884948650)
completed successfully. Existing root README edits are preserved.

The [owned catalog](../../../tests/fixtures/schematic_images/README.md) contains
16 original SVG/PNG pairs, independently authored connection/role/value goldens,
per-case provenance and CI-safe integrity tests. All A–N categories are covered,
with separate gap, missing bulk and printed-mega cases. No recognition accuracy
or approved CircuitDocument is produced; this is development ground truth,
reviewed by the authoring agent, pending independent human/held-out adjudication.
See [checkpoint verification](implementation-plan.md#m3b-fixtures-and-evaluation-checkpoint).

## Proposed controlled path

Image → local safe intake → untrusted observations → candidate topology/value
claims → explicit correction and snapshot confirmation → image-origin M1 document
→ unchanged M1 validation → **future reviewed image-admission gate** → existing
CIRCUIT_EXPORT → preview → REPRESENTATION → typed request → EXECUTION → M2 runner
→ existing RAW analysis.

Provider confidence, candidate confirmation, technical VALID, export eligibility,
human approvals and simulator/analysis success are different facts. No score
threshold or successful simulation may substitute for image review.

## First-version boundaries

One flat, clean, printed, small analog drawing: R/C/L, independent V/I sources,
NMOS/PMOS, ground, wires and explicit labels. Both zigzag and rectangular
resistors are planned fixture styles. Remote inference is optional and requires
separate explicit opt-in; owned static fixtures/fake responses are the CI default.

BJT/op-amp execution, hierarchy/multiple sheets, complex IC blocks, PCB photos,
guaranteed handwriting, proprietary PDKs, pixel-to-ASC generation, arbitrary
SPICE and new simulation algorithms are deferred. Unsupported content is retained
and blocks conversion; it is never removed automatically to make a partial circuit.

M3A itself added no implementation, dependency, fixture image, production asset,
packaging or release change. Its historical documentation audit results remain in
[Implementation Plan](implementation-plan.md#m3a-documentation-verification).
