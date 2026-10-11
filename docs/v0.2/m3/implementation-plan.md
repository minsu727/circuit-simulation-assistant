# M3 implementation plan

**M3A–M3D and M3E domain review, confirmed conversion and image admission are
recorded below.** UI/runner image execution and live inference remain future.
M3 is not closed. [M3E contract](promotion-and-admission.md).

## Dependency order

M3A → M3B → M3C → M3D → M3E → M3F → M3G.
M3E is deliberately split into review, conversion, admission review and minimal
UI checkpoints. This advances necessary review/correction from the historical
M4 plan; it does not broaden M3 into schematic CAD editing.

| Phase | Deliverables | Tests / acceptance gate | Strict dependency |
| --- | --- | --- | --- |
| M3A architecture | Nine mutually linked contracts; actual M1/M2 gap identified | Documentation/scope/privacy/link audit; no implementation claim | Current closed M1/M2 inspected |
| M3B fixtures/evaluation | Owned drawings/rasters, rights records, independent observation/topology/post-review goldens, versioned matching/metrics/budgets | Rights/provenance/hash review; ambiguous and unsupported negatives; no production-generated expected answers | M3A contract review |
| M3C extraction boundary | Separate candidate/observation types and strict wire contract, bounded intake/transforms, deterministic fake/replay provider; chosen real adapter only with reviewed policy | Shape/reference/geometry/consent/injection/retention tests; no network in CI | M3B fixes representative data contract; provider/SDK and numeric limits decided before live adapter |
| M3D connectivity | Local wire/terminal candidates, evidence-linked contacts/separations, bounded alternatives, deterministic preview/reconstruction | Independent partition/role/crossing goldens; unknown/uncertain edges remain unaccepted | M3C validated records plus M3B symbol/style catalog |
| M3E review/conversion | Atomic review engine, confirmation/binding, pure current-M1 adapter; separately reviewed image admission; minimum Streamlit forms/overlay | Manual choices cannot waive M1 issues; exact post-correction conversion; stale image/review blocks; all M2 approvals separate; current ASC UI regression | M3D stable claims, M3B correction goldens; admission design/authorization before any image export |
| M3F actual examples | Actual implemented extraction on held-out owned images, corrections, opt-in actual LTspice through complete chain | Pre/post-review metrics, failures/abstentions, signed mapped data, preserved sources and declared numerical comparisons | M3E review/admission implemented and accepted; explicit live-call opt-ins and simulator prerequisites |
| M3G acceptance/closure | Independent catalog/matrix, evidence inventory, exact tests/CI/libraries, limitations and closure decision | Standard CI green, deterministic acceptance, actual extraction and execution evidence, no gate bypass, original assets preserved | M3F evidence and no unresolved blocking contract defect |

Future filenames should live under a separate candidate namespace, with narrow
modules for observations/provider intake, topology, review and M1 projection.
Do not put geometry/provider state into `circuit_ir` or the existing analyzers.
Tests/fixtures get an explicit M3 image catalog path in M3B; do not freeze an
exported API or add a dependency before its phase review.

## M3E checkpoints and the admission decision

1. Review engine: validated typed operations, atomic changes, revisions and
   explicit snapshot confirmation, tested without a UI/provider.
2. M1 conversion: Origin.IMAGE/source reference retained; actual unchanged M1
   schema/validation results. Current M2 image rejection is an expected negative.
3. **Admission contract review before implementation:** approve a narrow versioned
   image-aware policy and concrete context binding/interface, including asset
   integrity, accepted review and promotion evidence rechecked through M2.
   No relabeling manual, nulling source refs, forging preview or global preflight
   bypass. Preserve manual profile goldens and all warning/approval gates.
4. Minimal Streamlit integration: separate mode/state/forms, original/overlay,
   issue alternatives, explicit correction/confirmation, then distinct M2 reviews.
   Avoid a CAD canvas or changing existing ASC behavior.

The proposed admission extension is not yet an implemented contract or authorization
to modify closed M2. If checkpoint 3 is not approved, conversion-only work can be
accepted but image export, real image E2E and full M3 closure remain blocked.
Document that boundary rather than claiming complete M3E/F execution.

## Checkpoint verification rules

After each **future executable change**, run focused tests then the existing full
suite; record actual count/failures/skips/exit. Never replace the baseline with an
invented future test total. M1 version/schema/Connection semantics, M2 manual
goldens/approval rules, source preservation and v0.1 ASC/parser/analysis/runtime
remain regression authorities.

Default tests must require no live provider, network, keys or LTspice. Existing
test dependency separation remains; any later imaging/provider dependency must
have a justified isolated installation story. Live extraction and simulator checks
need separate opt-in commands/evidence; do not run them merely to refresh a PASS.

At M3G, close only the explicitly implemented/evaluated profile. Unsupported
styles, model providers/versions, remote retention, handwriting and clean-machine
compatibility remain qualified. If no actual extractor or image-aware admission
exists, mark full M3 NOT CLOSED/conditionally complete with the exact blocker.

## M3A quality review findings

- Actual M1 already carries SourceImageReference/VisualProvenance and image checks;
  no new pixel/provider fields are necessary. Rich candidate data stays a sidecar.
- M1 `Candidate` is not an extraction DTO. Frozen CircuitDocument edits need
  immutable revisions, not in-place Streamlit table mutation.
- Connection-only connectivity and D/G/S/B roles must survive pose/label review;
  a visually plausible net partition can still be electrically wrong.
- M2 manual-only admission is real code, not obsolete proposal wording. The
  current image path must remain blocked until a reviewed extension exists.
- Original high-level plans target LTspice screenshots/M4 review; Prompt 042's
  textbook-first/M3 review scope is recorded without rewriting those documents.
- No unit test rerun is needed for M3A: the documented 848-test baseline is prior
  evidence, not a new run.

## M3A documentation verification

Verified 2026-10-09 (Asia/Seoul): exactly nine new Markdown documents; all 45
relative link/anchor occurrences resolve, code fences are balanced and no trailing
whitespace or missing final newline was found. All 319 pre-existing tracked files
match the starting SHA-256 snapshot, including the already modified root README;
its original working-tree diff is unchanged. Production, tests, schema/version,
existing M1/M2 documents, dependencies, CI, packaging and assets are untouched.

The nine new documents contain no detected secret, email or personal absolute
path. No PDK, image/scan, fixture, executable or generated output was added as a
public file. One-off baseline/audit helpers and reports are ignored under local
runtime output storage, not public validation assets. Staged files: zero.
`git diff --check` passed with exit 0; the existing root README's LF-to-CRLF
notice is not a whitespace error. Final Git status contains that original README
edit plus the new M3 documentation directory.

No full/focused tests, live Vision/API calls, LTspice runs, installation or builds
were performed. The 848-test number above is existing M2 evidence, not a new
M3 test result. No add/commit/push/tag/Release action was performed.

Required commands: `git diff --check` and `git status --short`. Since new
untracked documents are not covered by ordinary diff, inspect their whitespace
and links separately. Preserve initial working-tree edits byte for byte.
Only `docs/v0.2/m3/` should appear as new public files; audit output belongs in
ignored local runtime storage. Do not add/stage, commit, push, tag or release.

## M3B fixtures and evaluation checkpoint

Prompt 043, 2026-10-09: starting M3A commit
`ac86659cd91830fbd69de638b88ba3f7ad145e95` equals remote main. Hosted workflow
`37884948650` is completed/success for that exact SHA. The historical failed M2
workflow is not used as the current CI gate. Existing root README modifications
are preserved; no staging or remote mutation is performed.

Implemented only owned schematic-image assets and fixture integrity. Catalog:
`tests/fixtures/schematic_images/catalog.json`, version `m3-images-1`, 16 cases,
each with original SVG, committed grayscale PNG, separate hand-authored
`m3-fixture-1` truth and provenance. Categories A–N plus ordinary_wire, near_gap,
bulk_unresolved and numeric_mega are all present. Outcomes: 7 RESOLVABLE,
2 NEEDS_REVIEW, 1 UNSUPPORTED, 6 INCOMPLETE; these are not M1 technical states.
Thirteen complete observed topologies, twelve using supported categories.

The authoring agent reviewed the contact sheet and challenging full-size cases.
Connection rows were authored independently of geometry, with no M1 graph,
export, promotion or inferred output. Dot/no-dot/unclear/gap cases have distinct
truth; undecided inner memberships are omitted and both alternatives preserved.
D/G/S/B, missing bulk, source polarity, absent ground/source/value/model/W/L and
printed M versus SPICE M retain their explicit evidence and unknowns. This is not
independent human adjudication or a performance benchmark.

[Annotation contract](fixture-annotations.md) defines the test-only format;
[evaluation protocol](evaluation-protocol.md) defines future one-to-one matching,
exact role-aware pin partition and anchored net-name equivalence, pair/merge/split
errors, uncertainty, workflow/cost denominators and proposed M3C intake limits.
No actual scorer, fake recognizer, Vision/OCR API, connectivity inference,
candidate conversion, UI or image admission is added. Current M2 image-origin
rejection remains unchanged. M3 is not closed.

During integrity checks, a duplicated BJT symbol evidence reference was corrected;
the privacy scanner was bounded to avoid interpreting the SVG namespace URL as
a Windows drive. Visual review corrected a rectangle's internal stroke, source
label spacing, legend/ground spacing and PMOS return evidence association.
No production fix was necessary.

Final local verification (full suite executed once after focused checks):

| Check | Actual result |
| --- | --- |
| `python -X utf8 -m unittest tests.test_m3_fixtures -q` | 45 tests; failures 0, errors 0, skips 0; exit 0 |
| `python -X utf8 -m unittest discover -s tests -p "test_*.py"` | 893 tests in 407.804 s; failures 0, errors 0, skips 0; exit 0 |
| `python -m pip check` | No broken requirements found; exit 0 |
| PNG checks | All 16 decode, recorded dimensions/hash agree; 1000×650 L mode; no image metadata; total 236,724 bytes, largest 20,658 bytes |
| Source/reference checks | All 16 SVG/annotation/provenance sets present; category/outcome/ID/connection/evidence integrity passes |
| Preservation audit | 325 of 328 starting tracked files byte-identical; only three authorized M3 documents changed; original root README bytes/diff preserved |
| Public text/link/privacy audit | 81 relative Markdown link/anchor occurrences pass; no detected secret, email or personal absolute path; public text whitespace/fences pass |
| Git hygiene | `git diff --check` exit 0; LF→CRLF notices only; 70 intended new public files, zero staged files; temporary authoring/audit output ignored |

The existing 848-test M1/M2/v0.1 baseline plus 45 M3B integrity tests passes
locally. Hosted CI confirmation above concerns **M3A only**; uncommitted M3B has
not run on GitHub Actions. No live extraction, remote API or LTspice execution
was performed. Integrity does not prove image recognition or visual truth.

Temporary
authoring/audit tools stay ignored in local runtime output; committed SVG/PNG
sources are public fixture assets, not generated simulator results. No new
dependency, existing M1/M2 golden, root README, workflow, packaging or release is
modified. M3C next scope is bounded observation/intake types and fake/static replay;
M3D topology inference and M3E human review/admission remain separate work.
New fixture/doc/test files are prepared for version control but remain untracked
and unstaged in this task. No add/commit/push/tag/Release action is performed.

## M3C intake, observation and replay checkpoint

Prompt 044, 2026-10-11: starting HEAD/remote main
`8388bba05061ba3c6dccdf7009132b4911f5dad6`, M3B commit. Read-only hosted check:
[workflow 37891229541](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37891229541)
completed/success for that exact source. Historical local baseline: 893 tests.
Existing root README bytes/diff are preserved. No Git mutation is performed.

Implemented a separate `circuit_image` package: frozen intake/source/transform
records, bounded PNG/JPEG decode, exact EXIF matrices, tagged observation records,
strict bounded untrusted JSON parsing, explicit serialization, local ID remapping,
provider protocol and static replay only. [Implemented contract](observation-contract.md)
owns exact API/schema/limits/security/uncertainty semantics. Versions:
`m3-intake-1`, `m3-observations-1`; M1 `0.2-draft1` is unchanged.

Ten independently hand-composed replay responses are separate from M3B truth.
They deliberately include omissions/wrong/unknown/ambiguous proposals and invalid
JSON/references; all valid examples report partial coverage. R1/value was checked
visually on the divider PNG, not read from expected.json. Intake tests use ten
representative M3B PNGs; synthetic JPEG/EXIF/corruption images exist only in test
memory. No recognition accuracy, topology, M1 conversion or executable candidate
is claimed. Model metadata remains null; remote/local inference is disabled.

Quality fixes made during development:

- Pillow PNG verification must immediately follow opening/header inspection;
  reading EXIF before verify had moved the stream. Verification now precedes the
  separate bounded decode/EXIF pass; all eight orientation tests pass.
- Provider payload is excluded from repr; exception diagnostics do not echo
  secrets/paths/recognized text. Invalid callback options fail before invocation.
- Unit proposals require an explicit recognized unit token, preventing fabricated
  volts for missing units. Numeric checks reuse M1 scalar parsing, not electrical
  validation. Printed M versus SPICE m retains its explicit notation.
- Alternatives are distinct after typed numeric normalization: 1000 and 1e3
  cannot masquerade as different readings of the same literal.
- The first M2 boundary test omitted mandatory approval arguments; the test was
  corrected to use the existing API and assert the unchanged image-origin gate.
  No M1/M2 production change was required.

Focused final run: **82 tests** (22 intake, 42 observations, 18 adapter),
failures/errors/skips 0, exit 0, 9.094 s. `python -m pip check`: no broken
requirements, exit 0. No dependency added; existing pinned Pillow 12.3.0 reused.
Final local verification (full suite executed once after final focused checks):

| Check | Actual result |
| --- | --- |
| Focused M3C command in Test Plan | 82 tests in 9.094 s; failures 0, errors 0, skips 0; exit 0 |
| `python -X utf8 -m unittest discover -s tests -p "test_*.py"` | 975 tests in 238.268 s; failures 0, errors 0, skips 0; exit 0 |
| `python -m pip check` | No broken requirements found; exit 0 |
| Preservation audit | 392/398 starting tracked files byte-identical; only six authorized M3 Markdown documents changed; root README bytes/diff unchanged |
| M3B preservation | All 66 catalog/README/image/SVG/truth/provenance files byte-identical; no M1/M2 golden/schema/production change |
| Public text/link audit | 76 relative link/anchor occurrences resolve; no detected personal absolute path/email/API-key pattern or trailing whitespace; Markdown fences balanced |
| Git hygiene | `git diff --check` exit 0; LF→CRLF notices only; 24 new intended public files, zero staged files; diagnostic authoring/log/cache outputs ignored |

The full run retains the historical 893-test baseline plus 82 new M3C cases;
existing v0.1 ASC/UI, M1/M2 and M3B tests pass. Hosted CI evidence above concerns
committed **M3B only**, not these uncommitted M3C changes. No real Vision/API/OCR
or LTspice run, simulation, build, installation or release was performed.

New public scope: seven `circuit_image` modules; three focused tests and their
hand-composed helper; ten replay payloads plus catalog/README; the implemented
observation document. Six existing M3 documents link/record the boundary. Root
README remains the original unrelated user modification. Requirements, CI,
packaging, installer, assets, M1/M2/v0.1 logic and existing fixtures are untouched.
One-off audit/authoring tools and logs remain ignored under local simulation
output; no public generated image/simulator result is added. No add/commit/push/
tag/Release action is performed.

Known limits: shape-valid/reported-complete is not recognition fidelity or human
confirmation; callback timeout is cooperative, not arbitrary-code preemption;
normalized hashes assume the same codec/settings. No live SDK/API/OCR, retained
bundle/remote-consent policy, graph/review/conversion/UI or image admission.
M3D requires validated original-frame records/artifact, separate evidence-linked
claims/constraints, resource bounds and independent partition/role/abstention
tests. It must not merge by distance/confidence or invent body/ground/source/value.
M2 image restrictions stay intact; M3 is not closed.

## M3D topology reconstruction checkpoint

Prompt 045, 2026-10-11: starting source
`b6878d0c3ad2bf70164e07e049491f0c59ee1912`, historical local baseline 975 tests.
The user supplied successful hosted run 38115371769 for that committed baseline;
this task makes no network call and claims no new hosted validation. The existing
root README modification is preserved byte-for-byte, with no staging.

Implemented four modules: immutable unapproved topology records, conservative
reconstruction, explicit serialization/digest and independent bounded evaluation.
The [Topology Contract](topology-contract.md) fixes exact API/state/coordinate/
evidence/limit semantics and M3E prerequisites. One narrow `circuit_image` export
extension exposes only the reconstruction surface; evaluation reference records
stay in their comparison module, never become final M1 Circuit IR.

Sixteen separately hand-transcribed M3C responses, catalog and provenance README
are distinct from independent M3B annotation targets. Predictions are constructed
before truth loading. No expected.json data is used to author engine inputs.
The original M3B fixtures and earlier M3C replay files remain byte-identical.

Quality findings and fixes:

- Exact contact tolerance is zero; nearby gaps and unexplained intersections
  retain alternatives rather than joining. A certain dot cannot authorize an
  uncertain conductor. An ambiguous pin/contact cannot attach through a second
  nearby wire. No component body supplies an implicit conductive edge.
- Contradictory contact evidence quarantines the whole affected positive group.
  Conflicting physical-group labels cannot propagate equivalence to other wires.
  Ground needs an observed lead endpoint; rail names do not invent sources.
- Missing bulk, unsupported content, values and model/W/L stay unrepaired.
  Topology resolution remains separate from conversion completeness and approval.
- Initial divider/RC-family replay preparation omitted visibly drawn corner
  dots. Independent junction comparison correctly rejected exact matches. The
  missing observations were transcribed from public SVGs without golden edits.
- The first 74-test focused run had one test setup failure: M3C correctly rejects
  empty observations claiming complete coverage. The empty-set test now uses
  partial coverage, asserts incomplete/review state, and its focused rerun passed.

Final prepared-observation comparison:

| Profile | Result |
| --- | --- |
| Unique supported exact topology | 12/12: divider, rc, missing_value, unreadable_value, rlc, nmos, pmos, cross_open, cross_dot, shared_labels, rotated_sources, supply_unknown |
| Required pin assignments / joined pairs | 82/82 pins; 46/46 required joined pairs |
| False added / missing primary joins | 0 / 0 across 16 prepared cases |
| Authored required-review issues | 12/12, kind and localized target checked |
| Ambiguous crossing / gap | Both local choices retained, correct abstention; excluded from unique exact denominator |
| Missing bulk | 9 visible terminals, bulk unresolved; no inferred tie; excluded from exact denominator |
| Unsupported BJT | Symbol and three unknown-role terminal records retained; unsupported and reviewed; role/anchor errors reported, excluded from supported exact denominator |
| Corrupted predictions | Wrong joins/splits, D/S/polarity swaps, missed/duplicate objects, wrong labels/ground and wrong-target review are detected |

These are scores for reconstruction **given prepared observations**, not actual
AI extraction accuracy, held-out generalization, human adjudication or simulation
success. Review precision and full alternative-circuit materialization are not
claimed. M3D never calls M1 validation to establish image fidelity.

Final local verification:

| Check | Actual result |
| --- | --- |
| `python -X utf8 -m unittest discover -s tests -p "test_*.py"` | 1,049 tests in 501.015 s; failures 0, errors 0, skips 0; exit 0 |
| M3D cases included in final suite | 74: 45 reconstruction/fail-closed + 29 evaluation; all pass |
| Existing regression | Historical 975 tests retained, including M1/M2 and v0.1 behavior; all pass |
| `python -m pip check` | No broken requirements found; exit 0; no dependencies added |
| Tracked-file preservation | 414/422 starting files byte-identical; only package exports and seven authorized M3 documents changed |
| Protected fixtures/source | All 66 M3B files and 12 prior M3C replay files byte-identical; no M1/M2/v0.1/packaging/requirements/CI change; root README bytes unchanged |
| Public text/link audit | 69 local link/anchor occurrences resolve; no detected secret/email/personal absolute-path pattern; balanced fences; no trailing whitespace |
| Git hygiene | `git diff --check` exit 0; LF→CRLF notices only; 26 new intended public files, zero staged; audit helpers/logs/temporary outputs ignored |

Streamlit's existing bare-mode ScriptRunContext warnings appear in the unit/AppTest
run, without failures. No actual LTspice or live extraction/API was invoked by
this task. Local uncommitted verification is distinct from the supplied baseline
hosted CI result.

M3E remains next: exact-source-bound review/correction revisions, explicit choices,
atomic stale-safe human confirmation, pure image-origin M1 conversion, unchanged
M1 validation, and a separately specified/authorized image-aware admission gate.
Current M2 restrictions and all export/representation/execution approvals remain
unchanged. No UI, Vision/OCR/API, LTspice, generated image/netlist, build/release,
dependency change or Git add/commit/push/tag operation is performed. M3 is open.

## M3E review, promotion and image-admission checkpoint

Prompt 046, 2026-10-11 (Asia/Seoul). Baseline M3D HEAD `4e8ef04`;
required hosted [CI run 38118695850](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/38118695850)
was read with `gh run view`: status completed, conclusion success. This mandatory
read-only precondition was the only external network action. Implementation/tests
use prepared local observations, not Vision/OCR/network or LTspice.

Implemented [contract and public APIs](promotion-and-admission.md): immutable
exact-source review sessions, 18 typed corrections, atomic deterministic revisions,
explicit complete-claim confirmation, strict archival replay without restored
confirmation, existing M1 promotion/schema/validation, immutable provenance/maps
and separately verified image admission. The optional M2 context and image-bound
approval hash are the narrow authorized boundary change; manual digest projection,
M1 rules, model policy and all three explicit approvals remain unchanged.

| Prepared cases after explicit test-review actions | Actual outcome |
| --- | --- |
| divider, rc, rlc, cross_dot, rotated_sources | Confirmed → complete existing M1 document → VALID → admission eligible |
| nmos, pmos | Reviewer selects matching sealed profile and explicit W/L → confirmed/VALID/eligible |
| cross_ambiguous | Explicit connected choice → confirmed/VALID/eligible; separated choice also review-tested without convenient automatic selection |
| near_gap | Gap stays separate initially; explicit touching choice and corrected label attachment → confirmed/VALID/eligible |
| nmos_bulk_unknown | Initially blocks; reviewer explicitly assigns already-observed bulk pin → confirmed/VALID/eligible, no invented bulk/tie |
| missing_value, unreadable_value | Reviewer explicitly supplies C1 quantity → confirmed/VALID/eligible; original visible text untouched |
| cross_open | Confirmed but M1 INVALID (`ISOLATED_SUBNETWORK`); admission blocked |
| shared_labels | Confirmed but M1 INVALID (`FLOATING_DC_NODE`); admission blocked |
| supply_unknown | Review blocked by missing ground; no ground/source invention |
| unsupported_bjt | Unsupported acknowledgment retained; full confirmation/promotion blocked, no fake supported substitute |

The additional negative-resistor test confirms review-confirmed but INVALID
behavior. An independent divider check verifies supply/resistor pin groups and
ground/polarity after M1 projection. These are replay-domain results, not image
recognition accuracy, independent human adjudication or physical simulation.

| Verification | Actual result |
| --- | --- |
| Focused M3E group | 94 tests: 47 review + 22 promotion + 25 admission; exit 0 |
| Full suite | 1,143 tests in 493.195 s; failures 0, errors 0, skips 0; exit 0; historical 1,049 tests retained |
| Final catalog-provenance correction | Subsequent complete M3E group: 94 tests in 65.138 s; exit 0; preserves original observation catalog version |
| `python -m pip check` | No broken requirements found; exit 0; dependencies added: none |
| Protected inputs | 66 M3B files, 12 prior M3C replay files and 18 M3D replay/catalog files byte-identical; M3D engine/evaluation and M1 schema/models/validation unchanged |
| Existing app | v0.1 simulation/parser/analysis/UI, launcher, packaging, requirements, CI and unrelated root README bytes preserved |
| Final preservation/public audit | 432/448 starting tracked files byte-identical; only 16 intended existing files changed and 10 intended files added; existing log prefixes preserved |
| Markdown/privacy | 96 relative link/anchor occurrences resolve; no detected secret/email/personal absolute-path pattern in intended changed/new text |
| Git hygiene | `git diff --check` exit 0; LF→CRLF notices only; zero staged files and zero tracked generated/audit outputs |

Quality fixes: use the actual uncertainty enum contract and retain uncertain
values for explicit correction; reject conflicting writes/choices and stale
confirmation; archive numeric booleans cannot impersonate revision integers;
unsupported devices cannot be reclassified into fake supported devices. One
synthetic ownership test initially violated the minimum-two-alternatives M3C
contract; its hand-authored input was corrected without changing source fixtures.

Limitations: UI, live recognition/consent/provider evaluation, broad missing
component authoring, pose/CAD editing and actual image→LTspice execution are not
implemented. M3F must integrate current context into the existing runner; no
alternate runner path exists. Review/admission hashes provide integrity/staleness,
not authenticated user identity or image fidelity. M3G closure remains future.
No add/commit/push/tag/release action is performed.
