# Circuit Simulation Assistant

Natural-language-driven LTspice simulation and deterministic circuit analysis.

사용자가 작성한 LTspice schematic의 시뮬레이션과 결과 분석을 돕는 Windows / Streamlit 프로젝트입니다. 자연어 요청은 rule-based parser로 구조화하고, 사용자의 검토·수정·승인 후 LTspice로 실행합니다. RAW 결과의 정량적 측정·비교는 Python의 deterministic analysis가 담당합니다.

## Why I Built It

전자회로 실험에서 directive 문법 확인, waveform 수동 측정, 소자 값 변경에 따른 반복 시뮬레이션, 결과 비교와 보고서 정리에 드는 시간을 줄이고 싶었습니다.

처음에는 임의의 회로를 자동 생성하는 방식도 고려했습니다. current mirror와 feedback 같은 topology의 복잡성을 고려해, **v1에서는 schematic 작성은 사용자에게 맡기고 시뮬레이션·분석 자동화에 집중**하도록 범위를 줄였습니다. [문제 정의](problem-definition.md)와 [SPEC](SPEC.md)에 이 결정과 장기 계획을 기록했습니다. SPEC의 목표 기능이 모두 구현된 것은 아닙니다.

## Workflow

```text
Natural-language Request
  → Review / Edit
  → User Approval
  → LTspice (execution copy)
  → Deterministic Python Analysis
  → Comparison / Analysis Summary
  → AI Interpretation Layer (optional, explicit user action)
```

## Screenshots

<p align="center">
  <a href="docs/screenshots/01_trace_suggestion.png"><img src="docs/screenshots/01_trace_suggestion.png" alt="Trace suggestion for V(out), required-signal warning, and disabled execution approval" width="800"></a><br>
  <em>Trace suggestion and required-signal checks before approval.</em>
</p>

<p align="center">
  <a href="docs/screenshots/02_ac_response.png"><img src="docs/screenshots/02_ac_response.png" alt="AC voltage gain versus frequency with the minus 3 dB level and bandwidth marker" width="800"></a><br>
  <em>AC gain and -3 dB bandwidth analysis.</em>
</p>

<details>
<summary>Parameter Sweep · Transient · DC Sweep 결과 더 보기</summary>

<p align="center">
  <a href="docs/screenshots/03_parameter_sweep_results.png"><img src="docs/screenshots/03_parameter_sweep_results.png" alt="R1 parameter sweep comparison table with gain, bandwidth, and measurement status" width="800"></a><br>
  <em>R1 sweep comparisons, including unavailable bandwidth at 5kΩ.</em>
</p>

<p align="center">
  <a href="docs/screenshots/04_transient_waveform.png"><img src="docs/screenshots/04_transient_waveform.png" alt="Transient voltage waveforms for V(vout) and V(vin)" width="800"></a><br>
  <em>Transient voltage waveforms for V(vout) and V(vin).</em>
</p>

<p align="center">
  <a href="docs/screenshots/05_dc_sweep.png"><img src="docs/screenshots/05_dc_sweep.png" alt="DC sweep of V(vout) against V2 with the selected sweep point marked" width="800"></a><br>
  <em>V(vout) across a V2 sweep, with the selected sweep point marked.</em>
</p>

</details>

## Features

- **AC:** Target / Reference complex transfer function, low-frequency gain, -3 dB bandwidth, frequency graph.
- **Transient:** Input / Output Vpp, voltage gain, output swing; 적용 가능한 step에서 rise / fall time, overshoot, settling time.
- **DC Sweep:** 단일 voltage/current source sweep, min/max, requested-point interpolation, difference / matching error.
- **R/C Parameter Sweep:** 한 소자의 값 목록 또는 start/stop/step 지정, AC/Transient/DC 반복 실행, 비교 표·측정값 그래프·overlay, 실패 지점 기록 후 다음 지점 실행.
- **Analysis Summary:** 측정 사실·파생 사실·경고·비교 결과·증거를 JSON-compatible 구조로 분리.
- **AI Interpretation:** LLM-ready prompt 미리보기·내보내기, OpenAI/mock provider, 수치 일관성 검사. 수치·단위 일치 검사는 물리적 원인이나 해석의 정확성을 증명하지 않습니다.
- **Review UX:** 사용자 승인, 원본 ASC 보존, trace 추천 후 재승인, 같은 회로·분석의 이전 성공 조건 재사용, 전체 RAW/LOG Evidence.

## Validation

2026-09-17 Prompt 009A의 **121 tests passed**(기존 104 + UX 17) 및 실제 AC / Transient / DC / Parameter Sweep integration 4종 통과 기록을 보존합니다. 이번 공개 준비에서는 코드를 변경하거나 simulation을 재실행하지 않았습니다.

| 실제 검증 사례 | 결과 |
| --- | --- |
| MOSFET AC, 10 Hz–1 MHz | Low-frequency gain ≈ **38.983 dB**, -3 dB BW ≈ **6.275 kHz** |
| MOSFET Transient, 10 kHz 입력 | 정상상태 Vpp gain ≈ **47.492 V/V** |
| R1 AC sweep, 500Ω / 1kΩ / 2kΩ / 5kΩ | 비교 결과·trend·5kΩ bandwidth 미검출 기록 |
| DC requested point, 분압 fixture | V2=3.55 V에서 **1.775 V**, 원본 보간 정밀도는 Summary에 유지 |

독립 scalar 계산, synthetic response, 승인 차단, 원본 보존, 실패 처리로 검증했습니다. **AC 저주파 소신호 gain과 10 kHz Transient Vpp gain은 서로 다른 지표**입니다. 현재 기록만으로 동일 동작점·조건의 AC–Transient 및 DC–Transient 물리적 교차검증을 완료했다고 주장하지 않습니다. 비교 조건을 맞춘 검증은 [후속 Issue](docs/github-issues.md)로 남겼습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"
```

실제 integration 재현에 필요한 로컬 MOSFET 회로 설정, 공개 fixture 범위와 증거 위치는 [검증 안내](docs/validation.md)를 확인하세요. 개발 기록의 `simulation_output/` 경로는 로컬 증거 참조이며 공개 저장소에는 결과 파일을 포함하지 않습니다.

## AI-Assisted Development

**Problem Definition → SPEC → scoped Codex prompt → implementation → test → real-user validation → refinement** 순서로 진행했습니다. 각 단계에서 범위와 승인 경계를 정하고, 실패 원인을 조사해 실제 LTspice 실행까지 검증했습니다.

정량적인 회로 계산은 LTspice / Python이 담당합니다. AI interpretation은 검증된 Summary를 입력으로 받으며, 측정 사실·파생 사실·추론·불확실성을 구분하도록 설계했습니다.

## Development Log

- [개발 블로그 목차](docs/devlog/README.md) · [실제 사용자 테스트와 UX 개선](docs/devlog/09-real-user-testing.md)
- [원본 Development Log](docs/development-log.md) · [원본 Prompt Log](docs/prompt-log.md)
- [스크린샷 안내](docs/screenshots/README.md) · [GitHub Issue 후보](docs/github-issues.md)
- [공개 전 보안·개인정보 점검](docs/publication-review.md)

## Windows Release

**v0.1.0 공개 준비 중입니다.** 배포 예정 GitHub Release asset은 `CircuitSimulationAssistant-Setup.exe`입니다. [Release notes](docs/releases/v0.1.0.md)와 [검증 체크리스트](docs/release-checklist.md)에 기능·검증 범위·checksum을 기록했습니다. 이 준비 작업에서는 tag 생성이나 Release 업로드를 수행하지 않습니다.

Simulation에는 **LTspice를 별도로 설치**해야 합니다. Installer는 Python runtime을 포함하므로 일반적인 사용에서 별도 Python 설치는 예상하지 않지만, **Python 없는 clean Windows VM 검증은 아직 수행하지 않았습니다**. Unsigned installer; Windows may display a SmartScreen warning.

## Getting Started

검증 환경: Windows, Python 3.13.5, LTspice 26.0.1. LTspice는 별도 설치하며 PyLTSpice가 실행 파일을 찾을 수 있어야 합니다. 설치된 환경의 core 실행 의존성(직접 의존성과 일부 하위 의존성 고정)을 [requirements.txt](requirements.txt)에 기록했습니다. 새 환경에서의 설치 검증은 아직 하지 않았습니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:LLM_PROVIDER = "mock"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`.asc` 업로드 → 요청 입력 → Analyze Request → 조건 수정·승인 → Run 순서입니다. mock에는 API key가 필요 없습니다. OpenAI provider의 선택 의존성은 [requirements-llm.txt](requirements-llm.txt)에 있으며, 실제 API smoke test는 아직 수행하지 않았습니다. `.env` 자동 로더는 없습니다.

OpenAI provider를 사용할 때만 core 설치에 다음을 추가합니다. 설치 자체는 API를 호출하지 않습니다. 기본 simulation / Summary / mock 사용에는 필요하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-llm.txt
```

실제 provider 사용 시에는 `LLM_PROVIDER=openai`와 `OPENAI_API_KEY`를 환경변수 또는 로컬 `.streamlit/secrets.toml`로 설정합니다. 실제 키는 저장소에 넣지 않습니다. 앞서 설정한 mock provider는 자동으로 변경되지 않습니다.

## Windows Portable Build

개발 환경 실행은 기존처럼 `streamlit run app.py`를 사용합니다. Windows x64 portable build는 Python runtime을 포함한 **폴더 전체**를 복사해 실행하며, **LTspice는 별도로 설치해야 합니다**. GitHub Release binary는 아직 업로드하지 않았습니다.

빌드 개발 환경에 기존 core requirements와 build-only 도구를 설치한 뒤 실행합니다:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

```text
dist/CircuitSimulationAssistant/
  CircuitSimulationAssistant.exe
  _internal/                     Python runtime, libraries, app resources
```

- `CircuitSimulationAssistant.exe`를 실행하면 사용 가능한 localhost 포트(8501 우선)를 선택하고 서버 준비 후 기본 브라우저를 엽니다. 자동 열기가 실패하면 console의 URL을 직접 엽니다.
- Console launcher를 열어 두고 사용합니다. 종료는 `Ctrl+C` 또는 launcher 창 닫기이며, browser tab만 닫으면 서버는 유지됩니다. `--no-browser` 옵션으로 자동 열기를 생략할 수 있습니다.
- LTspice는 사용자별/Program Files의 일반 설치 위치와 PATH에서 탐지합니다. 비표준 설치는 `LTSPICE_EXECUTABLE` 환경 변수에 exe 전체 경로를 지정하고 재시작합니다. 잘못된 명시 경로는 다른 binary로 자동 대체하지 않습니다.
- 입력 복사본·결과·launcher 로그는 `%LOCALAPPDATA%/CircuitSimulationAssistant/`의 `simulation_input/`, `simulation_output/`, `logs/`에 저장합니다. 실행 폴더나 원본 회로를 덮어쓰지 않습니다. Developer run의 프로젝트 내부 저장 방식은 유지합니다.
- 이 core portable build에는 OpenAI SDK와 LTspice를 포함하지 않습니다. Mock은 유지하며 실제 OpenAI provider는 기존 optional `requirements-llm.txt`를 설치한 개발 환경에서 사용합니다. API key를 배포 파일에 넣지 않습니다.
- PyInstaller 6.22.3 onedir / Streamlit 1.63.0 bootstrap을 사용합니다. Bootstrap은 내부 API이므로 버전 변경 시 재검증해야 합니다. Portable 폴더에는 signing·자동 업데이트를 포함하지 않으며, installer는 아래 절차로 별도 빌드합니다.
- 빌드 후 선택적 Playwright/Edge 검증은 `python tests/verify_portable.py`로 수행합니다. `--simulate`는 공개 저항 분압 fixture를 실제 LTspice로 실행하고, `--open-browser`는 기본 browser 자동 열기를 확인합니다. `--missing-ltspice`는 누락 안내와 review를 검증합니다. 검증 로그는 Git에서 제외됩니다.

## Windows Installer

개발자는 먼저 위 portable 폴더를 만들고, 외부 빌드 도구인 [Inno Setup 6](https://jrsoftware.org/isdl.php)를 설치한 뒤 실행합니다. 실제 검증 버전은 **6.7.3**입니다. Inno Setup은 Python requirements나 최종 앱에 포함하지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1
```

결과: `installer_output/CircuitSimulationAssistant-Setup.exe`. GitHub Release에는 아직 업로드하지 않았습니다. Compiler는 PATH와 일반 설치 위치에서 찾으며 비표준 위치는 `-ISCC` 인자 또는 `ISCC_EXE` 환경 변수로 지정합니다. Portable 출력이 없으면 먼저 빌드하라는 안내와 함께 중단합니다.

- Setup에서 설치 범위와 경로를 선택합니다. 전체 사용자 기본 경로는 Program Files이며 관리자 권한이 필요합니다. 현재 사용자 모드도 제공하며 기본 경로는 사용자 Programs 폴더입니다.
- 시작 메뉴 바로가기를 만들고, 바탕화면 바로가기는 선택한 경우에만 만듭니다. 마지막 화면에 앱 실행 옵션을 제공하며 silent 설치에서는 실행하지 않습니다.
- **LTspice는 별도로 설치해야 합니다.** Installer가 다운로드하거나 라이선스 동의를 대신 처리하지 않습니다. Python runtime을 함께 설치하므로 일반적인 사용에서 별도 Python 설치는 예상하지 않습니다. Python 없는 clean Windows VM은 아직 검증하지 않았습니다.
- 제거는 Windows 설치된 앱 목록에서 합니다. 먼저 launcher를 `Ctrl+C`로 종료하세요. 실행 중인 앱 파일이 잠겨 있으면 종료 안내 후 제거를 중단하며 강제 종료하지 않습니다. 기존 LocalAppData의 회로 복사본·결과·로그와 LTspice는 보존합니다.
- Prompt 015A에서 **174 tests passed** 및 개발 PC의 현재 사용자 모드 설치/설치된 앱 UI·LTspice 탐지/실제 AC/제거/재설치를 확인했습니다. 기본·공백 포함 custom 경로, 바로가기 선택, 실행 중 제거 차단도 검증했습니다. 관리자 Program Files 설치, 대화형 완료 화면의 실행 체크박스, 별도 clean Windows VM은 미검증입니다. [상세 검증 범위](docs/release-checklist.md)를 확인하세요.
- Installer is currently unsigned and Windows may show a SmartScreen warning. 코드 서명과 경고 우회는 수행하지 않았습니다.

재현 가능한 설치 검증은 `python tests/verify_installer.py`를 사용합니다(선택적 Playwright/Edge 필요). 기존 설치·바로가기가 있으면 중단하며, 테스트에서 새로 설치한 앱만 제거합니다. 생성된 installer·검증 로그는 Git에서 제외됩니다.

## Project Structure

```text
app.py                         Streamlit review / approval / results
*_analysis.py                  Analysis-specific parsing and directives
*_result_analysis.py           RAW measurements and graphs
simulation_runner.py           Approved execution on circuit copies
parameter_sweep*.py            R/C sweep parsing, execution, comparison
analysis_summary.py            Deterministic structured facts and evidence
ai_interpretation.py            LLM-ready prompt builder
llm_client.py                  Optional OpenAI / mock interpretation
ui_helpers.py                  Display formatting and review defaults
tests/                         Unit, AppTest, integration; small ASC fixtures
docs/                          Original logs, devlog, publication guidance
```

## Current Limitations / Future Work

- Actual API smoke test not yet performed; 실제 응답 품질은 검증하지 않았습니다.
- 한 번에 **하나의 R/C** sweep만 지원하며 nested sweep / cancel-resume는 지원하지 않습니다.
- AC bandwidth는 low-pass 우선, Transient step 측정은 waveform 적용 조건이 있습니다.
- 외부 model/include 업로드, 결과 저장·재분석, 긴 legend·좁은 화면 UX는 후속 과제입니다.
- Image-to-circuit와 보고서 생성은 향후 구현할 기능입니다.
- 개인 MOSFET 회로와 로컬 증거는 배포하지 않습니다. 라이선스와 공개할 회로·이미지 권리는 소유자가 공개 전에 결정해야 합니다.
