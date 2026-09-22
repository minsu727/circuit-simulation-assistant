# 03 — AC Analysis

## 문제 / 목표

AC 작업은 두 단계였다. Prompt 003은 **자연어 조건 → 검토·승인 → 실제 `.ac` directive → LTspice**를 연결했고, Prompt 004는 생성된 RAW에서 gain과 bandwidth를 계산했다. Directive 생성 단계에 결과 계산까지 완료됐다고 섞어 쓰지 않는다.

## 당시 결정

자연어 해석에는 LLM API를 사용하지 않고 정규식과 규칙을 적용했다. 주파수 범위, Target, 요청 measurement를 추출하고 사용자가 Review에서 수정하게 했다. Gain 계산에는 AC source가 1 V라는 가정을 두지 않고 Reference를 별도로 받았다.

첫 bandwidth 계산은 low-pass response와 초기의 평탄한 통과대역을 우선 가정했다. 모든 필터 형태에 같은 정의를 적용하는 범용 bandwidth 분석기로 만들지는 않았다.

## 구현

### 요청에서 실행 조건까지

“V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘”에서 범위와 signal, 측정 항목을 추출했다. `Hz/kHz/MHz/GHz`, 한국어 범위 표현과 `from/to`, `~` 등을 처리하고 parser 값을 Review widget에 연결했다.

Decade, Points=100, Start=10 Hz, Stop=1 MHz를 승인하면 다음 directive를 생성한다.

```spice
.ac dec 100 10 1Meg
```

SPICE의 단위 해석을 고려해 1 MHz를 `1Meg`로 표기했다. Directive를 미리 보여주고 승인 이후 실행용 ASC 복사본에만 반영했다. `AscEditor`의 편집 기능을 사용해 기존 analysis directive를 정리하면서 `.param`과 주석 등은 보존했다.

### RAW에서 측정값까지

Target과 Reference가 실제 RAW에 있는지 확인하고 complex 데이터를 읽었다. 없는 trace를 비슷한 이름으로 대체하지 않으며, 누락 이름과 available traces를 표시했다. 다음 식을 NumPy로 계산했다.

```text
H(f) = Target(f) / Reference(f)
Gain_dB(f) = 20 * log10(abs(H(f)))
```

Reference가 0에 가깝거나 결과가 non-finite인 sample은 유효 측정에 쓰지 않았다. Low-frequency gain `G0`는 첫 최대 10개 sample 구간의 유효 gain median으로 정하며, 유효 sample이 최소 3개 필요하다. 단일 첫 sample에 의존하지 않고 초기 구간의 변화나 peaking에는 주의를 표시했다.

Threshold는 `G0 - 3 dB`다. 주파수가 증가하면서 처음 아래로 내려가는 인접 유효 sample을 찾고, gain을 log-frequency 축에서 보간했다.

```text
a = (threshold - g1) / (g2 - g1)
log10(f_bw) = log10(f1) + a * (log10(f2) - log10(f1))
```

유효하지 않은 구간을 건너뛰어 crossing을 만들거나 sweep 밖으로 외삽하지 않는다. Crossing이 없으면 `Not found within sweep range`로 남긴다. 결과에는 low-frequency gain, -3 dB level, bandwidth와 log-frequency graph를 표시했다.

## 검증

Prompt 003은 관련 6개 unit test와 실제 AC 실행을 확인했다. 승인한 `.ac dec 100 10 1Meg`의 RAW는 **10 Hz–1 MHz, 501 samples**였다. Review를 수정한 조건도 별도로 실행해 UI 기본값이 아닌 승인값이 적용되는지 확인했다.

Prompt 004에서는 기존 6개에 결과 분석 8개를 더한 **14개 tests**가 통과했다. 실제 MOSFET 회로의 조건과 결과는 다음과 같다.

| 항목 | 기록된 값 |
| --- | --- |
| Target / Reference | `V(vout)` / `V(vin)` |
| Directive | `.ac dec 100 10 1Meg` |
| Low-frequency gain | 38.983432121 dB |
| -3 dB level | 35.983432121 dB |
| -3 dB bandwidth | 6274.787804816 Hz, 약 6.275 kHz |

별도의 scalar complex/math 계산과 비교해 gain 오차는 1e-10 dB 미만, bandwidth 상대 오차는 1e-10 미만이었다. 이 검증은 같은 RAW의 계산을 독립적으로 확인한 것이며 AC–Transient 물리적 교차검증을 뜻하지 않는다.

Synthetic response `H(f) = 4 / (1 + j*f/1000)`에서는 주파수에 따라 변하는 complex Reference를 사용해도 transfer function을 복원했다. 정확히 -3 dB인 crossing 997.628345111 Hz에 대해 997.603603208 Hz를 계산했으며 상대 오차는 약 0.00248007%였다. Pole인 1 kHz와 정확한 -3 dB 지점을 구분했다. No crossing, peaking, 비정상 sample, missing trace도 검사했다.

## 실패 / 문제

초기에는 “1 MHz까지”라는 요청이 Review의 기본값 100 MHz를 바꾸지 못했다. 범위 parsing뿐 아니라 추출값을 widget 초기값에 연결해야 해결되는 문제였다. 누락·잘못된 값을 임의의 정상 기본값으로 확정하지 않고 검토하게 했다.

기존 directive를 추가 명령만으로 교체하면 여러 analysis가 남을 수 있어 충돌 제거를 보완했다. Prompt 003의 실제 RAW 검증 테스트에서는 `get_axis()` 사용 시 지연 로딩 오류가 발생해 `frequency` trace의 `get_wave().real`을 읽도록 수정했다. 이때 앱에 결과 계산 기능을 추가한 것은 아니었다.

## 수정 / 배운 점

Parser 결과만 검사하면 실제 LTspice에 1 MHz가 적용됐는지 알 수 없다. 요청, Review, directive, RAW의 첫·끝 주파수를 한 흐름으로 검사했다. 계산도 보기 좋은 숫자보다 정의와 적용 조건을 먼저 정했다.

현재 공개된 [AC response 화면](../screenshots/02_ac_response.png)은 후속 UX 개선 이후 제공된 이미지다. Prompt 004 당시 화면의 시점 증거로 사용하지 않는다. Trace 추천 UX는 이후 [사용자 테스트](09-real-user-testing.md)에서 보완했다.

## 다음 단계

Transient 분석으로 범위를 확장했다. AC에는 초기 통과대역 가정, sweep 해상도, peaking과 비정상 데이터의 한계가 남아 있다. High-pass/band-pass의 일반화나 stepped RAW 분석까지 완료한 것은 아니다.

원본: [AC Directive Generation](../development-log.md#2026-09-14--ac-directive-generation), [AC Result Analysis](../development-log.md#2026-09-14--ac-result-analysis), [Prompt 004](../prompt-log.md#prompt-004--ac-result-analysis).

[이전: LTspice Integration](02-ltspice-integration.md) · [목차](README.md) · [다음: Transient Analysis](04-transient-analysis.md)
