# 06 — Parameter Sweep

## 문제 / 목표

단일 분석이 가능해진 뒤에도 R/C 값을 바꾸고 다시 실행해 결과를 비교하는 작업은 남았다. Parameter Sweep은 반복을 자동화하되 각 point의 조건, 성공 여부, 측정값을 추적할 수 있어야 했다.

## 당시 결정

작업은 Prompt 007A의 parser/UI, 007A-1의 component 존재 검증, 007B의 실제 실행으로 나눴다. 자연어 목록이 올바르게 해석되는지, 해당 소자가 회로에 있는지, 승인한 값으로 실행되는지를 각각 확인할 수 있는 범위였다. 초기 두 단계의 승인 버튼은 실제 실행으로 연결하지 않았다.

## 구현

### 007A — Parser와 Review만

`R1을 1k, 2k, 5k, 10k로 바꿔가며 AC simulation` 같은 목록과 `R1을 1k부터 10k까지 1k 간격으로 sweep` 같은 범위를 구조화했다. 별도 `parameter_sweep.py`에서 값을 parsing하고 Review에서 편집하게 했다. 분석 종류가 없으면 사용자가 선택해야 했다.

승인해도 실행은 다음 단계에 구현된다는 안내만 표시했다. Component 변경, 파일 생성, LTspice 호출은 하지 않았다.

### 007A-1 — Component 존재 확인

업로드한 ASC의 `SYMBOL` / `SYMATTR InstName`에서 최상위 component 이름을 확인했다. 대소문자와 주변 공백은 처리하되 다른 이름을 유사하다는 이유로 확정하지 않았다. 있으면 `Component found`, 없으면 누락 이름과 확인된 목록을 보여주고 승인을 막았다. 이 단계도 실제 실행은 없었다.

### 007B — 복사본별 실행과 비교

최종 검토·승인 뒤 **Run Parameter Sweep**을 눌러 실행하도록 연결했다. Point마다 독립 실행용 복사본을 만들고 `AscEditor.set_component_value()`로 R/C 값만 변경했다. 단일 실행 경로를 `simulation_runner.py`로 분리해 AC/Transient/DC directive와 RAW 분석을 재사용했다.

명시적 목록의 순서는 유지하고 범위는 Decimal로 `Start + n * Step`을 생성한다. 간격에 맞지 않는 Stop을 임의로 덧붙이지 않는다. 한 번에 하나의 R/C, 양수 값, 최대 100 points의 순차 실행으로 제한했다. Parser가 인식하던 L은 실제 실행에서는 차단했다.

Point마다 `OK`, `Partial Measurements`, `Simulation Failed`, `Analysis Failed`를 구분하고 RAW/LOG/directive를 보존했다. 한 point가 실패해도 다음 point를 실행한다. 비교 표에는 모든 point를, extrema와 변화량에는 유효 측정만 사용했다. 결측 지점에서 metric graph를 끊고 overlay는 분석 가능한 처음 8개 curve까지 표시했다.

## 검증

007A에서는 전체 43개 tests, 007A-1에서는 관련 13개 tests를 확인했다. 이 두 단계에서 실제 sweep을 실행했다고 주장하지 않는다. 007B에서는 **전체 56개 tests**와 실제 AC/Transient/DC/Parameter Sweep integration이 통과했다.

### 실제 R1 AC sweep

기존 MOSFET amplifier의 drain resistor R1을 바꾸고 Target=`V(vout)`, Reference=`V(vin)`, `.ac dec 100 10 1Meg`로 실행했다.

| R1 | Low-frequency Gain [dB] | -3 dB BW [Hz] | 상태 |
| --- | ---: | ---: | --- |
| 500Ω | 32.9628426354 | 13129.4689675 | OK |
| 1kΩ | 38.9834321205 | 6274.78780482 | OK |
| 2kΩ | 45.0039676504 | 2613.29689907 | OK |
| 5kΩ | -38.2161724208 | 미검출 | Partial Measurements |

네 point 모두 simulation과 RAW/LOG 생성에 성공했다. 5kΩ는 simulation 실패가 아니라 bandwidth crossing 미검출이다. 500Ω→2kΩ에서는 gain 증가와 bandwidth 감소가 보이고, 5kΩ의 gain은 앞선 경향에서 크게 벗어난다. 이 관측만으로 회로의 물리적 원인을 확정하지 않았다. 자동 `large_trend_reversal` 경고는 다음 [Analysis Summary](07-analysis-summary.md) 단계에서 추가됐다.

### C1 Transient와 DC 재사용

C1을 10n/20n/30n으로 바꾸고 `.tran 0 2m 1m 1u`에서 측정한 Vpp gain은 각각 **68.3652692468 / 50.3016041505 / 38.4969407836 V/V**였다. 기존의 마지막 안정된 3주기 측정 정의를 사용했다.

분압 fixture의 R1=1k/2k DC sweep에서도 출력 maximum **2.5 / 1.66666662693 V**를 확인했다. 실제 Parameter 검증은 AC 4점, Transient 3점, DC 2점, 별도 실패 시나리오 3점으로 **총 12점: 정상 simulation 11회와 의도한 실패 1회**였다. 승인 차단과 원본 bytes 보존도 확인했다.

## 실패 / 문제

별도 R1=1k/2k/5k 테스트에서는 가운데 2k 복사본에만 없는 모델명을 넣었다. 1k 성공, 2k의 실제 LTspice 실패, 5k 실행·분석 순서를 확인했다. 위 정상 sweep의 2k 결과와 이 오류 주입 테스트를 구분해야 한다.

매우 큰 범위에서는 point 상한을 검사하기 전에 Decimal 정수 나눗셈이 예외를 낼 수 있었다. 먼저 비율을 100-point 상한과 비교하도록 수정해 잘못된 입력을 사용자용 오류로 처리했다.

## 수정 / 배운 점

실패와 부분 측정을 구분해야 비교가 성립한다. 미검출 bandwidth를 0으로 채우거나 실패 point의 수치를 보간하면 실제 실행 결과와 다른 그래프가 된다. 공통 분석기를 재사용하면서 point별 상태와 evidence를 함께 보존했다.

[공개 Parameter Sweep 화면](../screenshots/03_parameter_sweep_results.png)은 후속 UX 개선 뒤의 비교 표다. 긴 RAW/LOG 경로를 별도 Evidence로 옮긴 내용은 [09번 글](09-real-user-testing.md)에 기록되어 있다.

## 다음 단계

비교 결과를 사람이 읽는 표뿐 아니라 향후 AI 입력으로 사용할 구조화 Summary로 정리했다. Nested sweep, 다중 component, 취소·재개, optimization은 이 단계의 구현 범위가 아니었다.

원본: [Prompt 007A](../prompt-log.md#prompt-007a--parameter-sweep-request-parsing), [Prompt 007A-1](../prompt-log.md#prompt-007a-1--parameter-sweep-component-validation), [007B 실행·검증](../development-log.md#2026-09-15--parameter-sweep-execution--comparative-analysis-prompt-007b).

[이전: DC Sweep](05-dc-sweep.md) · [목차](README.md) · [다음: Analysis Summary](07-analysis-summary.md)
