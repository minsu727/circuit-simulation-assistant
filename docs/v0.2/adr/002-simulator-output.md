# ADR-002 — Netlist First, ASC Export Later

**Status: Proposed / future v0.2; not implemented.**

## Context

Electrical connectivity can be serialized without recreating symbol placement. ASC generation also needs catalog-specific geometry and correct wire/label coordinates. Current [simulation_runner.py](../../../simulation_runner.py) accepts ASC only and cannot be assumed to run a generated netlist unchanged.

## Decision

Start with reviewed Circuit JSON → simulator-neutral device model → allowlisted LTspice/SPICE netlist preview. Add a narrow, separately tested future netlist execution adapter in M2; preserve the existing ASC branch. Reuse directive builders and deterministic RAW analyzers. Keep trace/device name mappings and approved model/source settings explicit.

## Consequences

Export is reproducible and testable with terminal/value/model goldens. No automatic graphical schematic is available initially. Adapter/source validation, safe serialization and node-to-RAW mapping are real implementation tasks; renaming a netlist to ASC is not integration. Both export formats may be supported later from the same neutral model.

## Alternatives Considered

- ASC-first: fits current UI but adds a layout/wiring generation problem.
- Both immediately: duplicates exporter and round-trip work too early.
- Replace the v0.1 engine: unnecessary risk to proven approval/execution/analysis paths.
