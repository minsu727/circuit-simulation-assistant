# v0.1.0 Release Validation

**Clean Windows VM validation not performed.** This checklist separates the
developer-host checks from the still-required clean-machine acceptance test.
Do not mark a VM, SmartScreen, firewall dialog, or antivirus check complete based
on unit tests or a development-machine run.

## Scope and environment

- Target: `installer_output/CircuitSimulationAssistant-Setup.exe`, v0.1.0.
- Source baseline: `d85a76490b5d3fe8b38ad766634a1afd7bf52163` (Prompt 014B).
- Host: Windows 11 Home 25H2, x64, build 26200.9457; non-administrator token.
- Python, project source, `.venv`, Git and LTspice are installed on the host.
  Removing development environment variables does **not** remove those files.
- No Windows Sandbox executable, Hyper-V management command, or VirtualBox/VMware
  executable was found in PATH/common locations. Hypervisor presence alone does
  not establish an available clean guest. No separate machine was available.
- Windows Home is outside the supported [Windows Sandbox editions](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/).
  No Windows feature, edition, VM software, or security setting was changed.
- Bundled Python 3.13 / Streamlit 1.63.0; LTspice remains external. The core
  package omits the optional OpenAI SDK and credentials. No API call is required.

## Build and artifact record

Use a reviewed, clean source revision before changing validation-only files:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_installer.ps1
Get-FileHash installer_output/CircuitSimulationAssistant-Setup.exe -Algorithm SHA256
```

Record build exit codes, UTC timestamp, size, SHA-256, source revision and tool
versions. Logs/manifests belong in ignored `installer_output/release-validation/`.
The installer build only wraps `dist`; it does **not** rebuild stale portable
code. Rebuild portable first when the application revision changes.

- [x] Final full unit/AppTest suite: **174 passed**, 197.240 s, exit 0 (170 existing + 4 helper tests).
- [x] Fresh portable build succeeds, exit 0 (PyInstaller 6.22.3).
- [x] Fresh installer build succeeds, exit 0 (Inno Setup 6.7.3).
- [x] SHA-256, size and UTC timestamp recorded for the exact tested artifact.

| Artifact field | Recorded value |
| --- | --- |
| File | `installer_output/CircuitSimulationAssistant-Setup.exe` |
| Size | 87,193,866 bytes |
| Output last-write time, UTC | 2026-09-30T13:03:34.1785807Z |
| SHA-256 | `fed2fff1f23de2ff279fc132d0bb6f2167a89bd26f480062a64dc25780d408fe` |
| Authenticode | NotSigned |

This record applies only to these exact bytes; a later rebuild needs a new hash
and validation record. The existing 170 tests also passed separately before the
helper tests were added (127.447 s).

## Developer-host isolation checks (not a clean VM)

The existing installer verification refuses to overwrite a pre-existing app or
shortcut identity. It only uninstalls installations it created. Close the app
and use an unused test installation; do not remove a user's installation just
to make the test pass.

```powershell
.\.venv\Scripts\python.exe tests/verify_installer.py --release-checks
```

`--release-checks` explicitly runs one real AC simulation using the public divider
fixture. The helper supplies AC excitation in the upload buffer; this fixture is
test input provided separately, **not** a schematic shipped in Setup.exe.
For a manual guest test, take a copy of `tests/fixtures/dc_divider.asc`, set V1's
small-signal AC amplitude to 1 in LTspice (or add `SYMATTR Value2 AC 1` under V1's
value in that copy), and save it as `ac_divider.asc`. An equivalent validation-only
copy is prepared in ignored `installer_output/release-validation/ac_divider.asc`.
Expected: `.ac dec 100 10 1Meg`, 10 Hz–1 MHz, voltage ratio 0.5,
gain `20*log10(0.5) = -6.020599913... dB`; no -3 dB crossing for this flat divider.
No model downloads, LTspice installation or API calls are performed.

For optional custom-directory validation (spaces included), use an **unused**
subdirectory of `%LOCALAPPDATA%\Programs` with `--install-dir`. Existing
installations/shortcuts cause a safe refusal. This does not validate an elevated
Program Files installation.

- [x] Default current-user install; installed exe starts without development PATH/PYTHONPATH.
- [x] Initial UI/upload/review works; Run requires approval.
- [x] Missing-dependency guidance and no-crash execution block with child-process invalid LTspice override.
- [x] Common-location LTspice discovery without explicit path override.
- [x] Actual approved AC simulation, RAW/LOG, graph, metric and fixture preservation.
- [x] Runtime Python DLL comes from the installed `_internal` folder.
- [x] Actual listener is 127.0.0.1 only; no app LAN listener.
- [x] Start Menu / optional Desktop shortcuts point to the installed executable.
- [x] Running-app uninstall is blocked without forced app termination.
- [x] Uninstall/reinstall/relaunch works, without Windows restart.
- [x] Custom path with spaces works (`%LOCALAPPDATA%\Programs\Circuit Simulation Assistant Release Check`).
- [x] Existing user inputs/results and external LTspice remain intact.

### Recorded host results and limits

- Default installation + reinstall: exit 0; each installed payload matched all
  **2,294** portable files. Start Menu and Desktop task off/on, uninstall registry,
  silent no-launch and post-reinstall UI checks passed. Running uninstall exited
  1 with close-app guidance; subsequent normal uninstall exited 0. Inno logs
  reported `Need to restart Windows? No` for both install/remove cycles.
- A separate custom-path cycle also passed install, installed UI, shortcut
  off/on, running-uninstall guard, uninstall/reinstall/uninstall and preserved
  existing data. It did not repeat simulation or a second post-reinstall UI run;
  those were covered in the default-path cycle. No test installation remains.
- Installed app + headless Edge: initial UI, upload, parsed conditions, approval
  gate, result metrics/graph/Summary and fixture preservation passed. The OS
  accepted the default-browser launch request; this is not manual inspection of
  the desktop browser or the interactive setup wizard's final-launch checkbox.
- Real AC result: 10–1,000,000 Hz, **-6.020599913279624 dB**, displayed -6.021 dB;
  nonempty RAW/LOG and `.ac dec 100 10 1Meg` on the execution copy. The first failed
  verification attempt also completed its AC run; its files remain as local
  evidence, not release payload.
- PowerShell observed only `127.0.0.1:8501`, a non-admin token, and loaded
  `python313.dll` / `python3.DLL` from installed `_internal`. Development PATH,
  PYTHONPATH, PYTHONHOME and VIRTUAL_ENV were removed in the child; the repository
  and Python still existed elsewhere on this PC. Actual absence remains pending.
- A helper default-output expression used `$PSScriptRoot` too early in parameter
  binding on Windows PowerShell. Default path setup was moved into the script
  body; standalone invocation now has a regression test.
- One first-attempt AC shutdown exceeded the verifier's 15-second allowance and
  used its reported termination fallback. A console `ConnectionResetError` was
  also observed; no causal link to the delay is established. The opt-in release
  check now allows 45 seconds and rejects fallback/nonzero exit. The rerun passed
  with CTRL_BREAK / exit 0. Application code was not changed; shutdown timing on
  other machines remains to be checked.
- No block observed in tested environment. **Defender AntivirusEnabled and
  RealTimeProtectionEnabled were false** at inspection: this is not a Defender
  protection test. SmartScreen reputation/download behavior and firewall dialogs
  were not manually tested. Security settings were not changed. Local bind does
  not substitute for a complete offline/outbound-network test.

### Python-free optional smoke helper

After the first manual Setup-only test, the following standalone PowerShell
helper may be copied separately. It needs neither the source tree nor Python,
pip, Git, Streamlit, PyInstaller or Playwright. Supply paths on the test machine:

```powershell
.\verify_release.ps1 -Setup .\CircuitSimulationAssistant-Setup.exe `
  -InstalledExe "$env:LOCALAPPDATA\Programs\Circuit Simulation Assistant\CircuitSimulationAssistant.exe" `
  -Report .\release-smoke.json
```

Without `-InstalledExe`, it records artifact integrity only. With that argument,
it starts **its own** hidden `--no-browser` child from an unrelated working
directory, strips development environment variables and explicit LTspice override,
checks HTTP health, netstat listeners and loaded Python DLLs, then terminates only
that owned smoke process. Normal Ctrl+C shutdown is checked by the separate UI
verifier; this helper is not a graceful-shutdown or browser/graph test. No existing
user process is stopped. Reports omit machine-specific paths. The script never
certifies Python absence or a clean VM automatically.

The simulation console can include the current user's LocalAppData result paths
from LTspice runner diagnostics. These are local runtime data paths, not fixed
development-source dependencies, but the raw logs must be redacted before sharing.
Ignored local logs are not release attachments.

## Clean Windows acceptance — pending

Use an existing clean, licensed Windows VM/Sandbox or separate machine. Do not
enable Windows features or install tools without authorization. Transfer **only
Setup.exe** for the first test, verify its hash, and keep host source/venv folders
unshared. Copy this checklist/helper/fixture only later, recording each addition.

### Setup-only and LTspice absent

- [ ] Record guest Windows edition/build/architecture and VM type.
- [ ] Confirm Python/pip are absent (Windows Store aliases are not Python), and source/Git/venv are absent.
- [ ] Launch Setup normally; record actual SmartScreen/Defender observations without bypassing protection.
- [ ] Install to default location; record chosen per-user/all-users mode and elevation.
- [ ] Use the final launch option; browser opens and initial Streamlit UI renders.
- [ ] LTspice absent: app remains usable, missing-dependency guidance is clear, execution fails safely without traceback.
- [ ] No developer path appears in UI/errors/logs; no repository or external Python dependency.
- [ ] Launch via Start Menu and optional Desktop shortcut; targets are installed exe.
- [ ] Test an unused custom path containing spaces.

### LTspice present and simulation

- [ ] User installs official LTspice normally; record version, no automatic license acceptance/download.
- [ ] Restart app without reinstalling it; discover LTspice without a manual path override.
- [ ] Separately provide the public divider fixture with AC source excitation; preserve its original hash.
- [ ] Upload → request → Analyze → Review → Approve → Run.
- [ ] RAW/LOG exist and parse; 10 Hz–1 MHz and gain -6.020599913... dB; graph/result render.
- [ ] Original ASC bytes preserved; no source folder mounted or development dependency introduced.
- [ ] App/simulation run under an ordinary user token, without write access to Program Files.
- [ ] Logs/caches/input/output go under `%LOCALAPPDATA%\CircuitSimulationAssistant` (`logs`, `matplotlib`, `simulation_input`, `simulation_output`); inspect other temporary writes if present.

### Network / security / cleanup

- [ ] Confirm app PID listens only on 127.0.0.1, not 0.0.0.0/LAN/IPv6 wildcard.
- [ ] Check browser and app behavior without external network access; no API calls.
- [ ] Record whether an inbound firewall dialog actually appears; do not instruct blanket permission.
- [ ] Record actual SmartScreen result (unsigned artifact; do not bypass/hide warnings).
- [ ] Record active antivirus product/protection state and actual block/quarantine observations.
- [ ] Close launcher normally; localhost server stops.
- [ ] Attempt removal while app runs: close-app guidance, no forced termination.
- [ ] Uninstall completes; owned executable/shortcuts/registry removed; preserve user schematics/results/LTspice/unrelated files.
- [ ] Reinstall → launch again; no stale state/broken shortcut.
- [ ] No Windows restart is required; otherwise record cause/exit codes.

Unsigned development release; Windows may display a SmartScreen warning.
An absence of blocking in one environment is not an antivirus safety guarantee.

## Publication gate

- [ ] Complete the outstanding clean-machine cases before claiming clean Windows validation.
- [x] Review diff and secret/privacy scan; `git diff --check` passes. Seven public text files reviewed; no credential/personal-path patterns found.
- [x] Keep generated Setup, dist/build, logs and installer_output out of Git; no VM image was created. Staged files: 0.
- [x] Prompt 015B: recompute the existing installer hash and size; exact match with Prompt 015A, no rebuild.
- [x] Prepare [v0.1.0 notes](releases/v0.1.0.md), [GitHub release body](releases/v0.1.0-github-release.md) and [manual publication plan](releases/README.md), including checksum and limitations.
- [x] Keep version/title/tag consistent: AppVersion `0.1.0`, title `Circuit Simulation Assistant v0.1.0`, planned tag `v0.1.0`.
- [ ] User review and commit the release-prep documents; record that final commit SHA.
- [ ] Create/push `v0.1.0` on that final release-prep commit, after verifying no existing tag conflict.
- [ ] User creates the GitHub Release and uploads the checksum-matched Setup asset.
- [ ] Verify the published download hash and update README with the actual release URL/status.

Prompt 015B started on clean `main` at
`73d952a4fb226895958db89b0c04275a79ad6e07`. The artifact source remains
`d85a76490b5d3fe8b38ad766634a1afd7bf52163`; changes between those commits affect
only validation scripts/tests/docs, not the application or build recipes. The
tag target will be the **future final release-prep commit**, not either of these
existing commits. Its SHA cannot be known before the user commits. No application
tests, simulation or build were rerun during this documentation-only preparation.
All clean-machine/security cases above remain unchecked.

This task does not commit, push, upload a GitHub Release, sign binaries or change
SmartScreen/firewall/security settings.
