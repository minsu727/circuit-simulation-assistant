# Release history and process

## Published releases

### v0.1.0

**[Circuit Simulation Assistant v0.1.0](https://github.com/minsu727/circuit-simulation-assistant/releases/tag/v0.1.0)**
was published on **2026-10-01 at 04:49:34 UTC** and is the latest release.
It is neither a draft nor a prerelease.

**[Download the Windows installer](https://github.com/minsu727/circuit-simulation-assistant/releases/download/v0.1.0/CircuitSimulationAssistant-Setup.exe)**.
LTspice must be installed separately. The installer is unsigned; Windows may
show a SmartScreen warning. Clean Windows VM validation and actual OpenAI API
smoke testing remain unperformed.

| Item | Verified result |
| --- | --- |
| Tag / local and remote target | `v0.1.0` / `75f6db47f722b20241190275ce01611ac00f2d1c`; existing tag preserved |
| Release status | Published / latest; draft=false, prerelease=false |
| Asset | `CircuitSimulationAssistant-Setup.exe`, uploaded |
| Local and downloaded size | **87,193,866 bytes** each |
| Local and downloaded SHA-256 | `fed2fff1f23de2ff279fc132d0bb6f2167a89bd26f480062a64dc25780d408fe` |
| Public access | Release page and anonymous direct download both HTTP 200 |
| Release description | [Release body source](v0.1.0-github-release.md) updated for published availability and synchronized with GitHub |

See the [detailed release notes](v0.1.0.md) for validated functionality, installation,
checksum instructions, build provenance and limitations. Automatic source ZIP/TAR
archives are not the compiled Windows installer; no portable ZIP is attached.

## v0.1.0 publication verification

The initial Prompt 016 public check at **04:06 UTC** found the existing tag but
no published Release or Setup asset. After the user explicitly authorized
publication and completed GitHub CLI login, authenticated checks confirmed that
no v0.1.0 Release existed. GitHub CLI 2.102.0, authenticated as `minsu727` with
repository ADMIN permission, created the Release with the existing notes and
checksum-matched installer using `--verify-tag --latest`.

Post-publication API checks confirmed the tag/title, uploaded asset, published
state and matching latest-release ID. The public installer was independently
downloaded without authentication; its byte count and SHA-256 matched the local
artifact. The downloaded installer was **not executed**. No rebuild, simulation
or application test was needed for these publication checks. Local audit files
and the verification download remain in ignored `installer_output/release-publish/`.

After publication, the user authorized replacing the pre-publication wording
with current download availability and actual Release/installer links. The local
body source was updated and synchronized through `gh release edit --notes-file`;
the published body was retrieved again for comparison. Validation claims and
limitations remain unchanged. Publication and a matching checksum do not establish
clean-machine compatibility, publisher identity or antivirus approval.

## Future releases

1. Choose a new version, review changes and update installer metadata and notes.
   Do not reuse or move an already published tag.
2. Build portable and installer from reviewed source; record source commit,
   filename, size, timestamp and SHA-256. Follow the [validation checklist](../release-checklist.md).
3. Review documentation and limitations, then create the release-prep commit.
   Tag that exact commit only after review; never an unrelated branch head.
4. Push the intended commit/tag manually. In GitHub, select that tag, create a
   draft with the reviewed title/body, and attach only the intended release asset.
5. Review before publishing. Keep source environments, private circuits, audit
   files, logs and generated binaries out of Git; binaries belong in Release assets.
6. Verify the published page and downloaded checksum, synchronize the release
   body source, then update README links and the release history.

Publication does not complete previously unperformed clean-machine/security tests.
