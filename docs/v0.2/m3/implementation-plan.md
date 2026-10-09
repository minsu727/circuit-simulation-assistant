# M3 implementation plan

**M3A architecture with the M3B fixture checkpoint recorded below.** Production
observation/topology/review/conversion/UI/admission work remains proposed and
requires its own phase authorization.

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
