# ADR-005 — Vision Inference Separate from Quantitative Analysis

**Status: Proposed / future v0.2; not implemented.**

## Context

v0.1 computes circuit metrics from real RAW data in Python and optionally interprets an Analysis Summary. Adding upstream vision introduces another probabilistic boundary, not a replacement for LTspice or numerical analysis.

## Decision

Vision may propose components, text, geometry and alternatives only. Deterministic reconstruction/validation and human review establish the candidate circuit used for simulation. LTspice and existing Python analyzers remain the quantitative path. Downstream LLM interpretation continues to consume measured/derived facts and warnings after analysis. Keep visual confidence and extraction evidence outside numerical measurement fields; preserve the existing Summary contract.

## Consequences

The core remains useful without cloud vision or interpretation. Each inference boundary has independent consent, failure handling and validation. A correct computation of a wrong circuit remains possible, so provenance and image review are essential. Neither a high vision score nor valid JSON proves model fidelity, convergence or the physical correctness of an interpretation.

## Alternatives Considered

- One multimodal prompt for extraction, simulation and metrics: loses deterministic facts and testable boundaries.
- Attach extraction confidence to gain as a measurement confidence: conflates topology uncertainty and numerical evidence.
- Send original private images with every interpretation request: unnecessary disclosure; downstream Summary remains sufficient for the existing contract.

Existing evidence: [Summary design](../../devlog/07-analysis-summary.md), [AI interpretation boundary](../../devlog/08-ai-interpretation-architecture.md). Actual API smoke and clean-machine validation remain unverified; this proposal does not change those claims.
