# M2 end-to-end acceptance catalog

`catalog.json` is a manually selected contract catalog, not an exporter/validator
snapshot. It references existing M1 negative inputs, M2C/D complete SPICE goldens
and M2E execution manifests. No existing fixture or expected byte is rewritten.

| Category | Cases | Reason |
| --- | ---: | --- |
| Export | 12 | All existing passive/source/MOS goldens, including shared and mixed models |
| Execution | 5 | AC/TRAN/DC execution goldens through the complete public chain and fake runner |
| Circuit gate | 3 | INVALID, AMBIGUOUS and controlled fresh UNVALIDATED report |
| Staleness | 45 | Separate reviewed snapshot/report/context, representation and request bindings |
| Explicit decisions | 3 | Circuit, representation and execution decisions cannot be inferred |
| Model rejection | 2 | Unknown profile and wrong polarity, with no partial output |
| Injection | 9 | Unsupported command/path text cannot enter IDs or numeric conditions |
| Runner faults | 8 | Process, output and input-copy failure at the injected runner boundary |
| RAW faults | 7 | Corrupt/wrong-mode/missing/invalid data and unsupported current observation |
| Mapped analysis | 3 | Synthetic AC/TRAN/DC input delegated to existing numerical functions |
| **Total** | **97** | Counts are scenarios, not live simulations |

Each row has an ID, category/stage, existing fixture, scenario, expected outcome
(and code where applicable), CI-safe marker and rationale. Golden cases identify
the existing exact-byte or digest expectation files. No case-count target was
imposed: the 45 negative binding rows make each stale-input rejection inspectable.

[The acceptance module](../../test_m2_acceptance.py) creates one named unittest
per row and three additional integrity/authority checks: **100 tests**.
Run from the repository root:

```powershell
python -X utf8 -m unittest tests.test_m2_acceptance
```

The test controller deliberately grants three separate fixture decisions; it is
not a production approval controller. UNVALIDATED is a controlled validator seam
because ordinary complete M1 validation of these source fixtures returns a final
state. Stale/preflight scenarios assert no composition artifact, no working/output
files and zero calls at both the injected runner and real-entry backend boundary.
Injection rows stop at public model/typed-load boundaries before any valid request
can exist. Post-run faults retain evidence and are FAILED, rather than preflight
BLOCKED.

Opaque fake RAW/LOG files prove file/process contracts only. Reused synthetic
samples prove mapped numerical handoff; they are not LTspice evidence. Existing
M2F unit tests retain discovery, timeout, LOG parsing and binary-reader detail
coverage rather than duplicating every unit test here.

[The evidence inventory](../../../docs/v0.2/m2/real-run-evidence.json) is a
sanitized record of observed local M2F outputs, **not expected values for these
tests**. CI only checks its structure. Actual RAW/LOG files remain ignored and
are unavailable in fresh clones. The [acceptance matrix](../../../docs/v0.2/m2/acceptance-matrix.md)
separates CI mocks from inspected real evidence.
