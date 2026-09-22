# 04 — Transient Analysis

## 문제 / 목표

Transient에서는 시간 파형을 읽는 것만으로 측정 정의가 정해지지 않는다. 시작 과도응답을 포함한 전체 swing과 정상상태의 Vpp가 다를 수 있고, sine에 step의 rise time을 적용하면 의미 없는 숫자가 나올 수 있다. Prompt 005는 파형의 종류와 관측 구간을 구분하는 분석을 목표로 했다.

## 당시 결정

사용 한도로 작업이 중단됐을 때 parser, 결과 모듈과 tests가 이미 작성되어 있었다. 재개 시 저장된 코드를 먼저 확인했고, 문법 오류나 중복 구현을 새로 발견한 것은 아니었다. 기존 구현을 유지한 채 unit test와 실제 LTspice 검증을 이어갔다.

정량 계산은 Python으로 수행하고, 적용 조건을 만족하지 않는 metric은 숫자를 만들어내지 않기로 했다. AC의 계산이나 승인 경계도 유지했다.

## 구현

### Directive와 파형

Transient 요청에서 Stop Time, 선택적인 저장 시작 시간과 최대 timestep, Target/Reference 및 측정 항목을 추출했다. 승인한 조건에 따라 `.tran 1m` 또는 `.tran 0 2m 1m 1u` 같은 directive를 실행용 복사본에 적용했다.

RAW에서 time과 voltage trace를 읽고 missing trace를 검증한다. 전체 저장 구간의 Output Swing은 출력 최댓값과 최솟값의 차이다. 주기 입력의 gain은 마지막 안정된 입력 3주기를 공통 측정 구간으로 잡아 Input/Output Vpp를 계산한다. 구간 경계는 시간축에서 보간한다.

```text
Voltage Gain = Output Vpp / Input Vpp
Gain_dB = 20 * log10(Voltage Gain)
```

이는 진폭비이며 부호나 위상 정보까지 표현하는 값은 아니다.

### Step-like waveform의 측정

초기·마지막 구간의 median과 plateau 안정성을 확인한 뒤, 적용 가능한 전이에 rise/fall time을 계산한다. 10%–90% crossing은 실제 시간축에서 선형 보간한다. Overshoot와 settling time은 단일 step에 대한 조건을 확인하며, settling은 기본적으로 step 크기의 2% band를 사용한다.

Settling의 시간 기준은 이상적인 source 명령 시각이 아니라 파형에서 감지한 1% 전이 시작점이다. 주기 sine, flat, ramp 등 부적절한 파형에는 step metric을 억지로 붙이지 않는다.

## 검증

재개 후 추가된 RAW Offset 검사까지 포함해 **전체 25개 tests**가 통과했다. 구성은 기존 AC 14개와 Transient 11개다. 실제 Transient와 AC integration, Streamlit 실행도 통과했다.

실제 MOSFET 회로는 입력 `SINE(3.55 10m 10k)`, Target=`V(vout)`, Reference=`V(vin)`, `.tran 1m` 조건으로 실행했다. 마지막 3주기인 약 0.7–1.0 ms에서 계산한 결과다.

| 측정 | 실제 RAW 계산값 |
| --- | --- |
| Input Vpp | 0.019999742508 V, 약 20 mV |
| Output Vpp | 0.949819087982 V |
| Voltage Gain | 47.491565834178 V/V |
| Gain | 33.532329776956 dB |
| 전체 저장 구간의 Output Swing | 1.024637699127 Vpp |

전체 swing과 정상상태 Output Vpp는 관측 구간이 달라 값이 다르다. 별도의 scalar 계산으로 마지막 0.3 ms 구간을 확인해 상대 오차 0.1% 이내 일치를 검증했다.

Synthetic test에서는 알려진 지수 응답의 rise/fall, 감쇠 2차 응답의 overshoot, settling과 적용 불가 파형을 확인했다. 예를 들어 시정수 0.04 s의 rise/fall 계산은 약 0.087888971564 s로 이론값 `tau * ln(9)`와 1 µs 미만 차이였다. Overshoot는 44.434171077%로 이론값 44.434422509%와 0.001 percentage point 미만 차이였다. 실제 MOSFET sine 검증을 실제 step 응답 검증으로 확대하지 않는다.

## 실패 / 문제

`.tran 0 2m 1m 1u`는 1–2 ms를 저장해야 하는데 처음에는 읽은 시간축이 0–1 ms였다. RAW header에는 `Offset: 1.0000000000000000e-03`가 있고 time trace에는 상대 시간이 저장되어 있었다.

## 수정 / 배운 점

RAW header의 Offset을 더해 절대 시간축으로 복원했다. Offset이 없으면 0을 사용하고 비정상 값은 거절한다. 그래프, marker, 측정 구간이 같은 보정 시간축을 사용하도록 했고 실제 재실행에서 1–2 ms를 확인했다.

파일이 생성되고 gain이 계산되어도 시간축의 의미까지 맞는 것은 아니었다. 저장 시작 시간을 바꾼 실제 실행이 이 오류를 드러냈다. 중단 작업도 새로 작성하기보다 이미 있는 코드와 증거를 검사하는 편이 수정 범위를 명확하게 했다.

현재 공개된 [Transient waveform 화면](../screenshots/04_transient_waveform.png)은 후속 UX 개선 이후의 화면이며, 위 synthetic step test의 증거 이미지는 아니다.

## 다음 단계

DC Sweep으로 확장했다. 실제 step/pulse 회로와 timestep 변화에 대한 검증, 더 다양한 파형의 적용 조건은 후속 과제다. AC 저주파 gain과 10 kHz Transient Vpp gain의 차이만으로 물리적 교차검증을 완료했다고 해석하지 않는다.

원본: [Transient Analysis](../development-log.md#2026-09-15--transient-analysis-prompt-005-중단-작업-재개), [Prompt 005](../prompt-log.md#prompt-005--transient-analysis).

[이전: AC Analysis](03-ac-analysis.md) · [목차](README.md) · [다음: DC Sweep](05-dc-sweep.md)
