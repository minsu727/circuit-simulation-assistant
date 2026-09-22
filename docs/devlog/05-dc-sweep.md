# 05 — DC Sweep

## 문제 / 목표

DC Sweep에서는 전압·전류원의 값을 바꾸며 특성을 보고, 특정 입력 지점의 값을 읽거나 두 trace를 비교해야 했다. Prompt 006은 이 작업을 기존 승인·복사본 실행 흐름에 연결했다.

## 당시 결정

한 번에 하나의 독립 voltage/current source를 증가 방향으로 sweep하도록 범위를 정했다. 저항·커패시터 값을 바꾸는 Parameter Sweep과는 구분했다. Sweep source와 관측할 signal도 서로 다른 입력으로 다뤘다.

## 구현

Source, Start/Stop/Step, Target, 선택적인 Comparison 및 requested point를 parsing해 `.dc V1 0 5 10m` 같은 directive를 생성했다. 실제 netlist의 voltage/current source 목록으로 source를 확인한 뒤 승인된 복사본을 실행했다.

RAW의 sweep axis와 trace에서 signed min/max를 계산했다. Requested point는 실제 인접 RAW sample 사이에서 선형 보간하고, 데이터 범위 밖으로 외삽하지 않는다. 초기에는 `V1=3V` 같은 표현을 지원했다. 이후 “3.55 V에서” parsing과 결과 카드가 개선된 과정은 [09 — Real User Testing](09-real-user-testing.md)에서 다룬다.

비교 계산의 정의는 다음과 같다.

```text
Difference = Target - Comparison
Absolute Difference = abs(Target - Comparison)
Matching Error [%] = abs(Target - Comparison) / abs(Target) * 100
```

Matching Error의 분모는 Target이다. 같은 단위끼리 비교하며 분모가 0에 가까운 sample은 유효 matching error에서 제외한다. 이를 0%나 무한대로 표시하지 않는다. 그래프에는 DC curve와 요청한 지점 등을 표시했다.

## 검증

당시 **전체 35개 tests**가 통과했다. 기존 AC 14개, Transient 11개, DC 10개이며, 실제 DC/AC/Transient integration과 Streamlit 실행도 확인했다. Synthetic 데이터로 불균일한 축의 보간, signed difference, matching error와 0에 가까운 분모를 검사했다.

### Divider와 current source fixture

1 kΩ 두 개의 분압 회로에서 `.dc V1 0 5 10m`을 실행했다. 501 samples에서 출력 min=0 V, max=2.5 V였고 **V1=3 V에서 1.5 V**를 확인했다. 별도의 current source fixture에서는 `.dc I1 0 1m 10u`를 실행해 500 µA 지점의 출력 **-0.5 V**를 확인했다.

### Current mirror fixture

단순 LEVEL 1 NMOS 모델을 사용하는 mirror fixture로 trace 비교를 검증했다. VDD=5 V, 기준 저항 10 kΩ이며 출력 drain의 V1을 sweep했다. 이는 검증용 모델의 결과이지 특정 실제 소자의 정밀 모델 검증은 아니다.

| V1=3 V의 측정 | 실제 RAW 계산값 |
| --- | --- |
| Target `Id(M1)` | 321.240600897 µA |
| Comparison `Id(M2)` | 328.761205310 µA |
| Difference | -7.520604413 µA |
| Matching Error | 2.34111267131% |

전체 곡선의 차이와 matching error를 별도 scalar 계산과 비교했다. 분압 결과, mirror 결과, 이후 공개된 MOSFET DC 화면은 서로 다른 사례다.

## 실패 / 문제

Current source 요청에서 Stop의 `1mA`를 Step으로 읽는 parser 오류가 있었다. `step/increment` 앞뒤 표현의 우선순위를 조정해 Stop과 Step을 구분했다.

실제 current source fixture는 simulation이 성공했지만 처음 출력이 0이었다. Netlist를 확인하니 전류원이 의도한 node에 연결되지 않았다. Voltage source와 current source symbol의 pin 위치가 다른데 같은 배치 좌표를 사용한 것이 원인이었다.

MOSFET 전류도 요청한 `I(M1)` 대신 RAW에는 `Id(M1)`으로 나타났다. 없는 이름을 자동 치환하지 않고 누락 trace와 available traces를 표시해 사용자가 실제 이름을 선택하게 했다.

## 수정 / 배운 점

Current source fixture의 symbol 위치를 수정하고 netlist 연결을 검증한 뒤 다시 실행했다. 계산식을 바꿔 0을 원하는 값으로 맞추지 않았다. Simulator 성공 상태와 올바른 회로 연결은 별도로 확인해야 했다.

현재 공개된 [DC Sweep 화면](../screenshots/05_dc_sweep.png)은 V2와 V(vout)의 curve 및 선택 지점을 보여준다. 위 분압·mirror fixture 수치를 그 이미지에서 읽은 값으로 주장하지 않는다.

## 다음 단계

R/C Parameter Sweep에서 이 DC pipeline과 측정을 재사용했다. 다중 source sweep이나 DC–Transient의 직접 물리적 교차검증까지 이 단계에서 완료하지는 않았다.

원본: [DC Sweep Analysis](../development-log.md#2026-09-15--dc-sweep-analysis-prompt-006), [Prompt 006](../prompt-log.md#prompt-006--dc-sweep-analysis).

[이전: Transient Analysis](04-transient-analysis.md) · [목차](README.md) · [다음: Parameter Sweep](06-parameter-sweep.md)
