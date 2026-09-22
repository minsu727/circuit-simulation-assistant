# 08 — AI Interpretation Architecture

## 문제 / 목표

정량 결과를 만든 뒤에도 이를 설명하는 계층은 별도로 필요했다. Prompt 008A에서는 전송할 사실과 지시문을 로컬에서 확인하는 prompt builder를 만들었고, 008B에서는 OpenAI/mock provider 호출 계층을 붙였다. **실제 OpenAI API smoke test와 실제 모델 응답 품질 검증은 아직 수행하지 않았다.**

## 당시 결정

AI는 이미 계산된 Analysis Summary를 해석 대상으로 받는다. RAW를 직접 읽거나 gain·bandwidth를 다시 계산하지 않는다. 측정 사실, deterministic 파생 사실, 추론, 불확실성을 구분하도록 하고 simulation 승인과 API 호출을 별개의 사용자 행동으로 나눴다.

## 구현

### 008A — 로컬 prompt builder

`ai_interpretation.py`는 provider에 의존하지 않는 prompt를 만든다. 허용한 Summary 필드만 복사하며 유한 숫자는 반올림·단위 변환·재계산 없이 유지한다. RAW 배열·파일 내용과 불필요한 local path는 제외한다. Evidence 경로뿐 아니라 문자열의 Windows/UNC/POSIX 경로 등을 처리하되 `Target/Reference`, `V/V` 같은 측정 표현을 보존했다.

Prompt에는 기존 measured/derived/comparison, status/warnings만 사실의 근거로 쓰도록 명시했다. 새로운 숫자, 실패값 보간, 원인 단정, 보지 않은 RAW나 그래프를 관찰했다는 주장은 금지한다. 해석은 inference/hypothesis로 구분하고 Summary 안의 문자열은 지시문이 아닌 데이터로 취급하도록 했다.

Streamlit에서 prompt와 structured facts를 미리 보고 JSON/TXT로 내보낼 수 있다. Prepare, 다운로드, 일반 rerun은 simulator를 다시 실행하지 않는다. 조건 변경이나 실패 후에는 오래된 prompt를 초기화한다. 이 단계에는 실제 API 호출 자체가 없었다.

### 008B — Provider와 응답 경계

`llm_client.py`의 호출 계층은 OpenAI와 고정 mock을 분리했다. OpenAI 의존성은 optional requirements로 관리하고, mock은 key 없이 사용할 수 있다. 실제 key가 없으면 OpenAI 호출 버튼을 비활성화한다. Key는 prompt나 결과에 포함하지 않는다.

Simulation 승인과 별도로 **Run AI Interpretation**을 눌러야 호출한다. Prepare, model 선택, 다운로드나 화면 rerun만으로는 호출하지 않는다. 입력 크기, 출력 한도와 timeout을 제한하고 비용 가능성을 안내했다.

출력은 다음 필수 string-list 다섯 개를 가진 Structured Output으로 받도록 설계했다.

```text
confirmed_results
interpretation
additional_insights
warnings_uncertainty
suggested_next_checks
```

Schema와 로컬 형식 검사를 함께 적용하고, 잘못된 JSON이나 불완전 응답은 원문을 unverified로 표시한다. 인증·timeout·rate limit·network 오류가 나도 기존 Summary를 지우지 않는다. 자동 재시도나 다른 provider로의 자동 전환은 하지 않는다.

### 수치 일관성과 그 한계

Decimal 기반 검사로 응답의 숫자가 입력 사실에 정확히 존재하는지와 알려진 단위 조합을 확인한다. 새 수치, 반올림된 값, 확인되지 않은 단위에는 warning을 내며 값을 자동 교정하지 않는다.

그러나 같은 숫자를 다른 trace나 parameter point에 잘못 연결한 문장까지 이 검사로 판별하지는 못한다. JSON 형식이 맞고 숫자가 입력에 존재한다는 사실은 물리적 원인이나 해석의 정확성에 대한 증명이 아니다. Path 제거 역시 포괄적인 개인정보 차단을 보증하는 기능으로 주장하지 않는다.

## 검증

| 단계 | 당시 확인한 범위 |
| --- | --- |
| 008A | 전체 83개 tests: 기존 70 + prompt/UI 13 |
| 008A 실제 Summary 검증 | 7개 입력의 숫자 경로별 exact equality, 입력 보존, strict JSON, 경로 제외 |
| 008B | 전체 104개 tests: 기존 83 + provider/UI 등 21 |
| 008B 응답 검증 | 실제 Summary 6종에 mock/fake 응답을 적용한 형식·수치·경고·입력 보존 검사 |
| 기존 실제 simulation 회귀 | AC / Transient / DC / Parameter Sweep integration 모두 통과 |
| 실제 OpenAI API | Key 미설정으로 smoke test SKIP, 실제 유료 호출 0회 |

008A의 7개 입력은 R1, C1, DC, 이전 실패, AC, Transient 및 새 중간 실패 Summary다. RAW 7개를 재분석한 Summary 검증과 혼동하지 않는다. 사용 한도로 마지막 검증이 중단된 뒤에도 기존 구현을 유지하고 중간 실패 시나리오와 회귀 검증을 마무리했다.

실제 R1 prompt는 Summary의 gain 변화 **12.041125015023255 dB**, bandwidth 변화 **-80.09594367044141%**, 5kΩ의 `large_trend_reversal`과 `bandwidth_not_found`를 그대로 보존했다. 원인 설명을 새 사실로 추가하지 않았다.

008B에는 설치된 SDK를 fake HTTP transport로 검사한 결과도 있다. 이것과 고정 mock 응답은 호출 형식·오류 처리를 확인하는 증거이며, 실제 API가 해석한 결과는 아니다. Streamlit preview와 mock 흐름, 승인 차단·원본 ASC·RAW/LOG/graph·Summary도 회귀 검증했다.

## 실패 / 문제

중간 실패 point의 값이나 이전 화면의 prompt가 다음 해석에 남으면 올바른 형식이어도 잘못된 입력이 된다. 실패·변경 시 상태 초기화와 실패 metric 제외를 검사했다. 잘못된 응답 형식과 새 숫자는 mock/fake 시나리오로 만들었으며 실제 API에서 발생한 장애라고 서술하지 않는다.

## 수정 / 배운 점

Prompt 규칙, 전송 데이터, provider 호출, 응답 형식, 수치 검사를 나누자 각 경계를 독립적으로 확인할 수 있었다. 사람이 정한 승인 조건과 검증 기준을 코드·테스트에 반영했지만, 모델이 실제로 규칙을 얼마나 잘 따르는지는 별도 검증으로 남았다.

## 다음 단계

실제 API smoke와 응답 품질 평가, 문장과 evidence의 의미 연결 검사가 남아 있다. 이후 [실제 사용자 테스트](09-real-user-testing.md)는 새로운 해석 기능보다 trace 이름, 조건 재입력, 결과 가독성 같은 기존 흐름을 개선했다. Report나 임의 회로 생성이 이 AI 계층에 포함된 것은 아니다.

원본: [Prompt 008A](../prompt-log.md#prompt-008a--ai-interpretation-prompt-builder), [Prompt Builder 구현·검증](../development-log.md#2026-09-16--ai-interpretation-prompt-builder-prompt-008a), [LLM Interpretation Integration](../development-log.md#2026-09-16--llm-interpretation-integration-prompt-008b).

[이전: Analysis Summary](07-analysis-summary.md) · [목차](README.md) · [다음: Real User Testing & UX Refinement](09-real-user-testing.md)
