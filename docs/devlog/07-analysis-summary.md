# 07 — Analysis Summary

## 문제 / 목표

분석 결과가 화면과 Python 객체에만 있으면 향후 AI에 무엇을 전달했는지 확인하기 어렵다. Prompt 007C는 LTspice/Python이 확인한 결과와 나중의 해석을 분리하는 구조화 계층을 만들었다. LLM에 RAW를 읽고 숫자를 계산하게 하는 방식은 선택하지 않았다.

## 당시 결정

`analysis_summary.py`는 기존 결과 객체를 소비한다. AC bandwidth나 Transient gain을 다시 구현하지 않고, 이미 계산된 값·측정 정의·상태·증거를 JSON-compatible 구조로 옮긴다. 추세와 변화량도 Python으로 결정하며 회로 원인은 설명하지 않는다.

## 구현

Schema v1.0의 공통 필드는 다음과 같다. 분석에 불필요한 derived/comparison은 비워둘 수 있다.

| 필드 | 담는 내용 |
| --- | --- |
| `schema_version`, `analysis_type`, `status` | 형식 버전, 분석 종류, 실행·분석 상태 |
| `simulation_conditions` | 검토한 조건, signal, 실제 측정 구간과 방법 |
| `measured_facts` | 기존 RAW 분석기의 값·단위·사용 가능 상태, sweep의 point별 결과 |
| `derived_facts` | 유효 구간의 추세, 변화량과 변화율, 판단 규칙 |
| `warnings` | 미검출·실패·비정상 값 등과 해당 point/measurement |
| `comparison_results` | 극값과 parameter, 요청 순서의 마지막–첫 유효 값 차이 |
| `evidence` | RAW/LOG/graph 경로, 적용 directive, parameter 값의 참조 |

Evidence에는 파일 자체나 전체 waveform 배열을 넣지 않는다. NumPy 값·배열, Decimal, Path 등은 JSON native 값으로 변환하고, NaN/Inf는 `null`과 위치 경고로 남긴다. `json.dumps(..., allow_nan=False)`로 직렬화를 확인했다. 실패 point에 이전 metric이 남아 있어도 유효 사실로 포함하지 않는다.

화면에는 읽기 쉬운 고정 형식의 Summary와 JSON expander를 추가했다. 해석 문장을 생성하는 LLM 호출은 이 단계에 없었다.

### 추세를 판단하는 규칙

Trend는 parameter 숫자 오름차순으로 판단한다. 반면 기존 비교 함수의 last–first 차이는 요청 순서 기준이므로 둘을 구분해 기록한다. 동등성 허용오차는 `max(1e-15, max(abs(a), abs(b))*1e-9)`이며 increasing/decreasing/constant와 plateau가 있는 경우를 구분한다.

실패나 누락 사이를 연결하지 않고 유효 연속 구간만 설명한다. 전체에 결측이 있으면 `incomplete`, 유효 값이 두 개 미만이면 `insufficient_data`다. 변화율은 `100 * (last-first) / abs(first)`이며 기준값이 0이면 만들지 않는다. dB 값에는 백분율 대신 dB 차이만 기록한다.

큰 반전은 연속 유효 4점 이상에서 앞선 두 변화가 같은 방향이고, 다음 변화가 반대이며, 크기가 앞선 두 절대 변화 median의 3배보다 클 때 기록한다. 경고 이름은 `large_trend_reversal`이다. 이는 고정된 관측 규칙이며 원인 진단이나 일반적인 통계적 outlier 판정이 아니다.

## 검증

당시 전체 **70개 tests**가 통과했다. 기존 56개에 Summary 14개를 추가했으며, 이후 단계의 83/104/121개 수치를 이 단계에 소급하지 않는다.

기존 실제 RAW **7개(R1 AC 4개, C1 Transient 3개)**를 다시 분석해 이전 측정값과 rtol/atol=1e-12 이내 일치를 확인하고 두 sweep의 strict JSON 예시를 저장했다. 이는 7종 prompt 검증과는 별개의 작업이다.

| 실제 sweep | Summary에 기록된 사실 |
| --- | --- |
| R1 500→2000Ω Gain | increasing, +12.0411250150 dB |
| R1 500→2000Ω BW | decreasing, -10516.1720684 Hz, -80.0959436704% |
| R1 5000Ω Gain | 앞선 증가 후 큰 반전, 전체 gain은 `non_monotonic` |
| R1 5000Ω BW | `null`, `bandwidth_not_found`; 전체 BW는 `incomplete` |
| C1 10n→20n→30n Gain | 68.3652692468 / 50.3016041505 / 38.4969407836 V/V, `decreasing` |
| C1 전체 Gain 변화 | -29.8683284632 V/V, -43.6893305509% |

R1의 2000→5000Ω gain 변화 -83.2201400712 dB는 앞선 두 변화 median 6.02056250751 dB와 비교해 규칙을 만족한다. 5kΩ에서 왜 그런 응답이 나왔는지는 Summary에 넣지 않았다.

실제 AC/Transient/DC와 Parameter Sweep integration도 통과했다. Parameter 검증은 12점 중 정상 simulation 11회와 의도한 중간 실패 1회였으며, 실패 이후 실행·원본 보존·승인 차단·화면 Summary와 graph reference를 확인했다.

## 실패 / 문제

원본 기록에는 이 단계의 새 테스트 실패나 계산값 변경은 없다고 명시되어 있다. 대신 설계 검토에서 실패 point의 stale metric, JSON의 NaN/Inf, 부분 구간과 전체 trend를 혼동할 위험을 다뤘다.

BW crossing 미검출은 `bandwidth_not_found`, 비정상 sample 때문에 판단할 수 없으면 `bandwidth_undetermined`로 구분한다. `trace_missing`, `simulation_failed`, `analysis_failed`, `measurement_missing`, `measurement_not_applicable`, `non_finite_result`도 구분해 남긴다. 경고를 지우거나 결측을 0으로 바꾸지 않는다.

## 수정 / 배운 점

Summary는 숫자를 모으는 작업과 함께 그 숫자가 유효한 조건을 보존하는 작업이었다. 어느 구간에서 계산했는지, 실패인지 부분 측정인지, 비교 순서가 무엇인지가 빠지면 다음 계층이 사실을 잘못 해석할 수 있다.

## 다음 단계

이 Summary만 입력으로 받는 prompt builder로 이어졌다. 고정 trend 임계값, 불균일 parameter 간격, 분석기별 적용 조건은 여전히 한계다. Schema 소비자 계약·버전 관리와 조건이 다른 결과의 비교 적합성도 후속 과제로 남겼다.

원본: [Analysis Summary Builder](../development-log.md#2026-09-16--analysis-summary-builder-prompt-007c), [Prompt 007C](../prompt-log.md#prompt-007c--analysis-summary-builder).

[이전: Parameter Sweep](06-parameter-sweep.md) · [목차](README.md) · [다음: AI Interpretation Architecture](08-ai-interpretation-architecture.md)
