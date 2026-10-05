# ADR-004 — Human Approval before Generation and Simulation

**Status: Proposed / future v0.2; not implemented.**

## Context

Deterministic checks can reject contradictions but cannot detect every missed symbol or prove image fidelity. v0.1 already requires review and simulation approval. An imported JSON state flag must not act as authorization.

## Decision

Require fresh validation with no ERROR/unresolved AMBIGUOUS, then human circuit review. Only the reviewed revision may generate a preview. Require explicit approval of that exact simulator representation, followed by existing simulation-condition approval. Bind approvals to revision, source/electrical/artifact hashes and model/exporter versions. Invalidate dependent approvals after edits. Keep cloud-image consent and downstream AI approval independent.

## Consequences

Users can inspect original image, terminal/net tables and generated input. Extra review actions are intentional and avoid a guessed-circuit execution path. Warnings require acknowledgement; users cannot override ERROR by clicking approve. Preview generation must not run the simulator. Original images and canonical circuits remain immutable sources for execution copies.

## Alternatives Considered

- Confidence-triggered execution: treats uncertain recognition as permission.
- One boolean in provider JSON: forgeable, stale and unable to distinguish consent types.
- Reuse only v0.1 condition approval: does not demonstrate review of the newly generated circuit representation.

State transitions: [validation rules](../validation-rules.md).
