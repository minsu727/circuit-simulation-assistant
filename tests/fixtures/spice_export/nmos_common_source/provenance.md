# Nmos Common Source

Generic repository-authored M2D topology, not derived from private/coursework material. The expected model/device body and ordinal maps were independently authored from the committed M2 contract; no exporter was imported or run to generate expected text. Transparent stdlib hashing derives header/map/artifact/context hashes from explicit projections retained in expected-export.json. Static expectations are never rewritten by tests.

D/G/S/B use explicit pin roles and connections; the pin list deliberately begins with bulk. Drains have resistive reference paths; selecting a model does not prove an operating point or clear nonlinear-reference warnings. Used logical model IDs exactly equal sealed profile IDs. The full registry digest binds both demo profiles, while model_map binds only used generated tokens. LEVEL=1 coefficients are educational, not process-accurate.

Tests explicitly acknowledge current M1 model warnings and create CIRCUIT_EXPORT envelopes; no approval authority is imported. M1 model_catalog_resolution remains deferred. No analysis/execution approval, LTspice run or numerical/physical validation is claimed.
