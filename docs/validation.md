# Validation & Reproduction

## Recorded validation

Prompt 009A(2026-09-17)에서 121 unit/AppTest, 실제 AC/Transient/DC/Parameter Sweep integration 4종, 실제 Streamlit startup, Edge desktop/mobile graph layout 검증이 통과했습니다. [원본 기록](development-log.md#2026-09-17--core-ux-polish-after-real-user-testing-prompt-009a)에 실패와 수정·재실행도 남아 있습니다. 공개 준비 단계에서는 기존 Python 코드와 tests를 변경하지 않았고 전체 simulation을 다시 실행하지 않았습니다.

단위 테스트에는 PyLTSpice, Streamlit, NumPy/Matplotlib 등이 필요합니다. `requirements.txt`는 core 실행의 직접 의존성과 일부 하위 의존성 버전을 기록하며 새 환경 설치나 모든 전이 의존성의 재현을 보장하는 lockfile은 아닙니다. spicelib는 PyLTSpice, pandas는 Streamlit, Pillow는 Streamlit/Matplotlib의 실행 의존성입니다. OpenAI 및 Playwright는 core 파일에 포함하지 않습니다. 전체 suite에는 OpenAI SDK와 `httpx`를 직접 import하는 fake transport 테스트가 있어 SDK 미설치 시 자동 skip되지 않고 오류가 발생합니다. [requirements-test.txt](../requirements-test.txt)는 core와 선택 LLM requirements를 함께 설치합니다. mock/fake transport 검사는 실제 API를 호출하지 않습니다.

Prompt 019(2026-10-04)의 Windows / Python 3.13.5 fresh-clone 감사에서 core 설치와 `pip check`가 통과했습니다. Core-only suite는 183개 중 SDK 의존성 오류 1개로 exit 1이었고, 선택 LLM requirements 설치 후 **183 tests passed, exit 0**이었습니다. 이 결과는 실제 simulation/API 재검증이나 별도 clean Windows VM 검증이 아닙니다.

프로젝트 root의 `.venv`에서 전체 unit/AppTest suite를 준비하고 실행합니다:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"
```

이 suite는 실제 LTspice 실행이나 API key를 요구하지 않습니다. Windows PowerShell helper 검사는 Windows에서 실행하며, 실제 simulation 및 선택 browser 검증의 외부 도구 요구사항은 아래와 별도 build 안내를 참고하세요.

## Automated CI

[Automated tests workflow](../.github/workflows/test.yml)는 `main` push, `main` 대상 pull request와 수동 실행을 지원합니다. `windows-latest` / Python 3.13에서 `requirements-test.txt`를 설치하고 위와 같은 `python -X utf8 -m unittest discover -s tests -p "test_*.py"`를 실행합니다. Core / optional LLM 의존성 분리는 유지하며, 추가 test skip이나 별도 축소 suite는 없습니다.

Suite 점검 결과:

- Parser·analysis·Summary·UI helper는 synthetic/fixture 데이터와 Streamlit AppTest로 확인합니다. RAW reader와 simulator 실행은 필요한 테스트에서 mock하며, 실제 integration용 `verify_*.py`는 unittest discovery 대상이 아닙니다.
- Launcher 탐지는 임시 디렉터리의 가짜 실행 파일과 mock을 사용합니다. Shutdown helper는 mock process로 확인하므로 실제 설치·종료 검증을 대신하지 않습니다.
- Installer build 테스트는 임시 payload에서 compiler 호출 전 거부 경로를 검사합니다. Release helper는 임시 파일의 hash/preflight와 Windows 기본 OS-version registry 읽기를 사용하지만 기존 앱 설치 registry나 사용자별 설치 상태에 의존하지 않습니다. 이 Windows helper 테스트에는 표준 Windows PowerShell 5.1과 `SYSTEMROOT`가 필요합니다.
- OpenAI SDK 검사는 fake client / `httpx.MockTransport`를 사용합니다. Workflow 기본 provider는 `mock`, API key는 빈 값이며 secret은 사용하지 않습니다. 실제 OpenAI API 호출은 없습니다.

권한은 `contents: read`, checkout credential 저장은 비활성화합니다. 세 requirements 파일을 기준으로 setup-python pip cache를 사용하고, 동일 branch/ref의 이전 실행은 취소합니다. Job timeout은 로컬 약 1분 suite와 의존성 설치 시간을 고려해 15분입니다.

CI는 실제 LTspice, installer build/install, clean Windows VM, SmartScreen/Defender, 실제 OpenAI API 품질을 검증하지 않습니다.

Prompt 024(2026-10-04) 로컬 Windows / Python 3.13.5 검증에서 `requirements-test.txt` 설치와 `pip check`가 통과했고, workflow와 같은 mock/UTF-8 환경의 **183 tests가 63.856초에 통과(exit 0, skip 없음)**했습니다. YAML 구조와 README/validation 상대 링크·헤딩 47개도 통과했습니다. 실제 simulation/API 호출이나 원격 Actions 실행은 없었습니다. 원격 통과는 commit/push 이후 실제 Actions 기록으로 별도 확인해야 합니다.

### Prompt 024B — Windows CI portability

첫 실제 [Actions run 37199913216](https://github.com/minsu727/circuit-simulation-assistant/actions/runs/37199913216)은 Windows / Python 3.13.15에서 **183 tests, failures 6, errors 1, exit 1**이었습니다. 로컬 통과를 원격 통과로 취급하지 않습니다. 테스트 의존성과 harness만 다음처럼 수정했습니다.

- **ASC symbol 의존성:** 실제 `AscEditor`가 설치된 `voltage.asy`를 찾던 테스트에 직접 작성한 [최소 symbol fixture](../tests/fixtures/editor_symbols/README.md)를 제공합니다. 임시 ASC 옆에 복사하고 test 범위에서 외부 library 검색과 cache를 비웁니다. 실제 component 편집·저장·원본 보존 assertion을 유지하며 skip하지 않습니다. LTspice resource를 복제하거나 simulator를 실행하지 않습니다.
- **8.3/long path:** 같은 파일의 경로 표기만 달랐습니다. 네 테스트를 `Path.samefile()` 기반 파일/디렉터리 identity 비교로 바꿨고, 전달 인자는 여전히 단일 `Path`인지 검사합니다. 공백·`&` 포함 실행 파일과 resource/data 분리 검증은 유지합니다.
- **Release helper 환경:** runner는 `pwsh`에서 Python을 시작하고 테스트는 Windows PowerShell 5.1을 child로 실행합니다. [Microsoft의 PSModulePath 설명](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath?view=powershell-7.6)에 따라 child 환경에서 상속된 `PSModulePath`만 제거해 기본 모듈 경로를 구성하게 했습니다. 최초 CI 로그에는 child 모듈 경로/세부 예외가 없어 그 값을 직접 확인할 수 없었습니다. 로컬 진단에서는 PS7 전용 shared-module manifest로 `Get-FileHash` 미검색과 helper의 `CommandNotFoundException` / exit 1을 재현했고, 환경 수정 후 hash 검증 / exit 0을 확인했습니다. 새 회귀 테스트는 이 실패·회복을 모두 검사하며 stdout/stderr 실패 진단도 보완했습니다. Production helper는 변경하지 않았습니다.
- **경고 출력:** AppTest/bare-mode의 `missing ScriptRunContext`와 mock browser-failure/readiness-timeout 테스트의 로그는 예상 경로의 출력입니다. 전역 억제하거나 실패를 skip하지 않습니다.

2026-10-04 로컬 Windows / Python 3.13.5에서 실제 8.3 임시 경로의 targeted **30 tests 통과**, 최종 전체 **184 tests 통과(기존 183 + 모듈 경로 회귀 1), skip 0, failures/errors 0, 63.573초, exit 0**를 확인했습니다. Workflow·requirements·production·packaging은 그대로입니다. Push 후 Windows CI의 기대 결과는 **184 passed, 0 skipped**이나, 수정 후 원격 결과는 아직 확인하지 않았습니다. 실제 simulation/API/installer 실행은 이번 검증에 포함하지 않습니다.

## Local-only circuit configuration

기존 `test_ltspice.py`는 외부 개인 회로의 절대 경로를 포함하는 초기 smoke script입니다. 로컬 파일은 변경하지 않고 공개에서는 명시적으로 제외했습니다. 앱은 이 파일을 import하지 않습니다. MOSFET integration 스크립트들은 AST로 이 파일의 `ASC_FILE` 값을 읽습니다.

새 clone에서 해당 검증을 준비할 때만:

1. `test_ltspice.py.example`을 `test_ltspice.py`로 복사합니다. 기존 로컬 설정을 덮어쓰지 않습니다.
2. 소유권·배포 권한을 확인한 회로를 `local_circuits/Draft3.asc`에 준비합니다. `ASC_FILE`에는 상대 경로를 사용할 수 있습니다.
3. 기존 검증은 FQB55N10 MOSFET, V(vin)/V(vout), R1/C1, SINE(3.55 10m 10k) 등 원래 테스트 회로의 구성과 수치에 의존합니다. 임의 회로로 바꾸면 같은 결과를 기대할 수 없습니다. 원래 MOSFET fixture가 공개되지 않아 이 검증은 fresh clone에서 즉시 재현되지 않습니다.
4. 레거시 `test_ltspice.py`를 원본 회로에 직접 실행하지 않습니다. 기존 integration은 업로드 bytes와 실행용 복사본을 사용합니다.

프로젝트 root에서 한 번에 하나씩 실행합니다. 실행 폴더 전후 비교를 사용하는 검사가 있으므로 병렬 실행하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tests/verify_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_transient_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_dc_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_parameter_sweep_integration.py
```

DC integration은 공개된 `tests/fixtures/dc_divider.asc`, `dc_current_mirror.asc`를 사용합니다. 이 두 작은 ASC에는 개인 include 경로나 외부 모델 파일이 없으며 wildcard로 제외하지 않았습니다. GUI layout 수동 검증은 별도로 Playwright와 설치된 Edge를 필요로 합니다.

## Evidence and interpretation limits

`simulation_input/<run_id>/`는 실행 복사본, `simulation_output/<run_id>/`는 RAW/LOG/netlist/graph이며, 별도 verification 폴더에는 JSON과 감사 로그가 있습니다. 이 데이터는 개인 경로·회로 정보를 포함할 수 있어 모두 공개 제외합니다. 원본 개발 기록의 상대 경로는 증거의 provenance를 보존하기 위한 텍스트이고 공개 다운로드 링크가 아닙니다.

각 분석의 scalar/synthetic 검증과 regression은 직접적인 교차 분석 물리 검증과 구분합니다. AC와 Transient gain 비교에는 같은 frequency/bias/amplitude 조건이 필요하고, DC–Transient 비교에는 같은 topology의 DC bias와 정상상태가 필요합니다. 기존 DC 분압기/current mirror 검증만으로 MOSFET 증폭기의 DC–Transient 일관성을 입증하지 않습니다.
