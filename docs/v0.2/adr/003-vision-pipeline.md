# ADR-003 — Hybrid Extraction with Deterministic Graph Reconstruction

**Status: Proposed / future v0.2; not implemented.**

## Context

A multimodal call can propose symbols and values but may invent missing information or misread connections. Fixed CV operations also infer uncertain geometry and are not a proof of electrical topology.

## Decision

Use a finite Phase A symbol catalog, local image/wire/pin processing and optional OCR/multimodal candidate providers. Preserve observations, alternatives and original-pixel coordinates. Perform union-find reconstruction only over accepted connection constraints, then run independent deterministic validation and human review. Start with a local/manual path before making any cloud provider necessary.

## Consequences

Failures are localizable and candidate-provider contracts can be replayed. The pipeline needs catalog maintenance, geometry testing and a small owned benchmark. Cloud extraction requires separate consent. Model scores are not calibrated accuracy, and unresolved crossings/body/pin assignments block generation.

## Alternatives Considered

- LLM-first trusted JSON: lower prototype effort, weaker reproducibility/topology assurance.
- Fully classical CV/OCR for every style: too broad and brittle for the first scope.
- Train a detector immediately: data/annotation/deployment cost is not justified before a baseline.

Details: [vision comparison](../architecture.md), [future fixtures](../roadmap.md).
