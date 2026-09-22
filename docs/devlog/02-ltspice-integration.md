# 02 — LTspice Integration

## 문제 / 목표

화면에서 요청을 받는 것과 회로를 실제로 실행하는 것은 별개다. Prompt 002에서는 이미 로컬 smoke script에서 성공한 방식을 앱에 연결하고, 성공뿐 아니라 승인 차단·원본 보존·실패 처리까지 확인했다.

## 당시 결정

실행 흐름은 **Streamlit → Python / PyLTSpice → LTspice → RAW / LOG**다. 회로 simulation은 LTspice가 수행한다. 앱은 실행 조건과 파일을 관리하고 결과를 확인하며, AI가 simulation 숫자를 대신 계산하지 않는다.

이 단계에서는 UI에서 선택한 AC/DC/Transient 조건을 ASC에 반영하지 않았다. 업로드 회로 내부에 이미 있는 directive를 실행한다는 점을 화면에 알렸다. 실행 연결과 directive 편집을 별도 단계로 검증하기 위한 범위였다.

## 구현

기존 성공 방식인 `SpiceEditor`와 `SimRunner(simulator=LTspice).run_now()`를 사용했다. 업로드 bytes는 실행별 `simulation_input/<run_id>/`에 저장하고, 결과는 `simulation_output/<run_id>/`로 분리했다. 같은 파일명을 올려도 실행을 구분하며, 사용자의 원본 ASC를 직접 수정하지 않는다.

조건을 검토하고 승인한 다음 **Run Simulation**을 눌러야 실행한다. 승인 체크만으로 실행하지 않고, 파일·요청·조건 변경 시 승인을 초기화한다. 비활성 버튼 외에도 실행 처리부에서 승인을 검사했다.

성공은 경로가 반환됐다는 사실만으로 판정하지 않았다. Runner 성공 상태와 비어 있지 않은 RAW/LOG를 확인한 뒤 완료 메시지와 경로를 표시했다. 실패하면 오류와 로그 내용을 보여주고 앱의 나머지 화면은 유지했다.

## 검증

2026-09-14의 실제 검증 기록은 다음과 같다.

| 확인 항목 | 당시 결과 |
| --- | --- |
| `python -m py_compile app.py` | 통과 |
| Streamlit health / 홈페이지 | HTTP 200 |
| `verify_integration.py --real-ltspice` | 종료 코드 0 |
| 실제 회로 directive | 기존 `.tran 1m` 유지 |
| 생성 파일 | RAW 51,168 bytes, LOG 528 bytes |
| 승인·원본 경계 | 승인 전 실행 차단, 원본 bytes 보존 |

UI에 AC가 선택되어 있어도 이 단계에서는 `.tran 1m`을 실행했다. 이는 AC 조건 적용 성공의 증거가 아니며, 다음 단계에서 해결할 제한이었다.

## 실패 / 문제

검증 준비 중 로컬 script를 기본 CP949로 읽어 `UnicodeDecodeError`가 발생했다. 읽기 encoding을 UTF-8로 명시해 해결했다.

또한 AppTest에서 비활성 버튼을 강제로 누르는 방식만으로는 실행부의 승인 검사를 확인할 수 없었다. 버튼 이벤트를 패치해도 승인되지 않은 상태에서는 editor와 runner가 호출되지 않는지 확인하도록 검증을 보완했다.

실제 simulator 실패는 업로드 테스트 복사본의 모델명을 존재하지 않는 이름으로 바꾸어 만들었다. LTspice가 오류로 종료하고 `.fail` 로그를 남겼을 때도 앱은 crash하지 않고 오류를 표시했다. 이 오류 주입은 원본 회로에 적용하지 않았다.

## 수정 / 배운 점

실행 가능한 앱이라는 판단에는 정상 회로 한 번의 성공보다 더 많은 근거가 필요했다. 승인 없이 실행되지 않는지, 잘못된 모델에서도 사용자가 원인을 볼 수 있는지, 재실행 파일이 섞이지 않는지를 함께 검사했다.

## 다음 단계

승인한 조건을 실제 directive로 반영하고 RAW 범위까지 비교하는 AC 단계로 진행했다. 외부 model/include 파일 처리와 결과 분석은 이 단계에서 완료하지 않았다.

원본: [Streamlit-LTspice Integration](../development-log.md#2026-09-14--streamlit-ltspice-integration), [Prompt 002](../prompt-log.md#prompt-002--streamlit-ltspice-integration).

[이전: Initial Prototype](01-initial-prototype.md) · [목차](README.md) · [다음: AC Analysis](03-ac-analysis.md)
