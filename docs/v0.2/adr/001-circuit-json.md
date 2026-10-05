# ADR-001 — Circuit JSON as the Canonical Intermediate Representation

**Status: Proposed / future v0.2; not implemented.**

## Context

Image inference can miss symbols, guess text or misread crossings. A raw model response or simulator file loses alternatives and provenance. The current ASC workflow must remain intact.

## Decision

Use versioned [Circuit JSON](../circuit-json-schema.md) as the single canonical circuit state. Separate visual evidence from electrical components, terminal roles, nets and connections. Derive the typed graph, overlay and exporter views from the same revision. Keep only one pin-to-net membership table and recompute imported validation state.

## Consequences

Schema and semantic rules can be tested without vision or LTspice. User corrections are revisioned and exporters remain simulator-specific. There is additional reference-integrity, migration and provenance work. JSON validity does not prove visual fidelity or circuit physics.

## Alternatives Considered

- Direct image-to-ASC/netlist: fast demo but no reliable correction or ambiguity boundary.
- Provider-specific JSON: couples domain state to one model and permits unreviewed fields.
- Flat netlist only: simple export but poor visual provenance and review support.
