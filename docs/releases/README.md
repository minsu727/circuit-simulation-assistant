# Manual release process

This is a **local preparation plan**, not an executed publication workflow.
Version/tag: `v0.1.0`. Title: **Circuit Simulation Assistant v0.1.0**.
The [release notes](v0.1.0.md) record artifact identity/provenance, and
[v0.1.0-github-release.md](v0.1.0-github-release.md) is the copy-ready release body.

## Review before committing

- Starting HEAD: `73d952a4fb226895958db89b0c04275a79ad6e07`, branch `main`, clean at task start.
- Artifact built from `d85a76490b5d3fe8b38ad766634a1afd7bf52163`; the later commit
  adds validation assets only. Tag the **new final release-prep commit**, not these
  starting/source commits. No tag is created during this preparation.
- Review [pending validation](../release-checklist.md) and keep the clean Windows,
  Python absence, SmartScreen, Defender and clean-VM LTspice transition unchecked.
  Publication does not turn those limits into completed tests.
- Confirm `origin` is the intended repository and the staged diff contains only
  the seven documentation files prepared here. Keep Setup/dist/build/logs out of Git.
- Compare the installer with the recorded SHA-256 immediately before upload.
  A new binary or application/package change requires a new validation record.

## Commands for the user — not executed by the assistant

From the repository root on `main`, after review:

```powershell
git status --short
git diff --check
Get-FileHash installer_output/CircuitSimulationAssistant-Setup.exe -Algorithm SHA256
git check-ignore installer_output/CircuitSimulationAssistant-Setup.exe
git add README.md docs/releases/README.md docs/releases/v0.1.0.md docs/releases/v0.1.0-github-release.md docs/release-checklist.md docs/development-log.md docs/prompt-log.md
git diff --cached --stat
git diff --cached --check
git diff --cached
```

Stop and review the staged content before continuing. Do not use `git add .` or
force-add the ignored installer.

```powershell
git commit -m "docs: prepare v0.1.0 release"
git rev-parse HEAD
git push origin main
```

Record the displayed SHA as the release-prep/tag target in the release creation
record. Its value cannot be recorded before that commit exists. Confirm the
working tree is clean and that HEAD still points to the reviewed release-prep
commit; do not tag after unrelated work or a failed commit/push.

```powershell
git status --short
git show --no-patch --format=fuller HEAD
git tag --list v0.1.0
git ls-remote --tags origin refs/tags/v0.1.0
```

If either tag check finds an existing `v0.1.0`, inspect it and stop; do not replace
or force-push it. Otherwise, after verifying the target:

```powershell
git tag -a v0.1.0 -m "Circuit Simulation Assistant v0.1.0" HEAD
git rev-parse "v0.1.0^{commit}"
git push origin v0.1.0
```

The resolved tag commit must equal the release-prep SHA you recorded. Only these
explicit commands are proposed; none of them has been run to stage/commit/tag/push
as part of Prompt 015B.

## GitHub web publication — after tag push

1. Open the repository `minsu727/circuit-simulation-assistant`, then **Releases →
   Draft a new release**.
2. Select the **existing `v0.1.0` tag** pushed above; confirm its target commit.
   Do not create a second tag on an arbitrary branch head.
3. Set the title to **Circuit Simulation Assistant v0.1.0**.
4. Paste [the prepared release body](v0.1.0-github-release.md). Preview it and
   confirm that clean-VM/API/security limitations remain visible. No fake asset
   or screenshot URL is needed.
5. Attach only `installer_output/CircuitSimulationAssistant-Setup.exe` as the
   prepared application asset. Check filename, **87,193,866 bytes**, and the
   SHA-256 in the release notes. Do not upload diagnostic logs, private circuits,
   local audit files, VM images or the source `.venv`.
6. Save the draft, review the asset/body/tag, and publish only when the user
   chooses to do so. No draft, upload or publication occurs in this task.
7. After publication, verify a downloaded copy's checksum. Then update README's
   preparation wording with the **actual** release URL/status and record the tag
   target SHA in the publication record. Do not invent the URL beforehand.

No GitHub CLI upload command is needed for this plan. The absence of a locally
available `gh` command does not prevent the manual web workflow.
