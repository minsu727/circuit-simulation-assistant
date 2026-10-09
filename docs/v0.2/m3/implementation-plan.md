# M3 implementation plan

**M3A specification only.** No proposed module/test/UI/admission change below is
implemented or authorized by this documentation task.

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
