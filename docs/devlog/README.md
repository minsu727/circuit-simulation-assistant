# Development Blog Index

회로 실습의 반복 작업을 줄이기 위해 범위를 정하고, 입력 화면에서 실제 LTspice 실행·분석·비교로 확장한 과정을 정리했습니다. 각 글은 [원본 Development Log](../development-log.md)와 [Prompt Log](../prompt-log.md)를 바탕으로 당시 결정, 실패와 수정, 검증 근거를 설명합니다.

Problem Definition → SPEC → 범위를 정한 prompt → 구현 → test → 실제 LTspice 검증 → 사용자 테스트 → 개선 순서로 진행했습니다. Codex에 구현을 요청할 때도 기능 범위, architecture, 승인 경계, 검증 기준과 다음 단계는 사람이 정했습니다.

- [00 — Problem Definition & Scope](00-problem-definition-and-scope.md): 임의 schematic 생성 대신 사용자가 작성한 회로의 simulation·분석 자동화에 집중한 이유를 다룹니다.
- [01 — Initial Prototype](01-initial-prototype.md): 최초 Streamlit 입력 화면과 후속 임시 parser에서 드러난 기본값 문제를 시점별로 구분합니다.
- [02 — LTspice Integration](02-ltspice-integration.md): 실행용 복사본, 사용자 승인, RAW/LOG 생성과 실제 실패 처리를 연결합니다.
- [03 — AC Analysis](03-ac-analysis.md): 자연어 범위를 실제 directive로 반영하고 complex gain과 -3 dB bandwidth를 검증합니다.
- [04 — Transient Analysis](04-transient-analysis.md): 정상상태 Vpp와 step metric의 적용 조건, RAW 시간 Offset 오류를 다룹니다.
- [05 — DC Sweep](05-dc-sweep.md): source sweep, 지점 보간, matching error와 divider/current mirror fixture 검증을 설명합니다.
- [06 — Parameter Sweep](06-parameter-sweep.md): parser → component 검증 → R/C 실행·비교로 나누어 확장한 과정을 다룹니다.
- [07 — Analysis Summary](07-analysis-summary.md): 측정 사실·파생 사실·경고·증거를 JSON 구조로 분리하고 추세 판단의 한계를 기록합니다.
- [08 — AI Interpretation Architecture](08-ai-interpretation-architecture.md): prompt preview, OpenAI/mock 계층과 수치 검사, 실제 API 미검증 경계를 설명합니다.
- [09 — Real User Testing & UX Refinement](09-real-user-testing.md): trace 불일치, 조건 재입력, graph/table 크기와 DC point 가시성을 사용자 테스트로 개선합니다.

## 기록을 읽는 기준

각 글의 test 수와 측정값은 **해당 단계의 원본 검증 기록**입니다. 이번 문서 재구성에서 simulation이나 tests를 다시 실행한 결과가 아닙니다. 초기 기능에 나중의 UX 개선을 소급하지 않았으며, 현재 구현·재현 조건은 [프로젝트 README](../../README.md)와 [Validation](../validation.md)을 함께 확인하세요.

[SPEC](../../SPEC.md)은 장기 목표도 포함하며 전체 구현 완료 목록이 아닙니다. 실제 OpenAI API smoke와 AC–Transient/DC–Transient 직접 물리적 교차검증은 완료로 주장하지 않습니다. 로컬 `simulation_output/` 증거와 개인 MOSFET 회로는 공개 저장소에 포함되지 않으므로 원본 기록의 경로를 공개 다운로드 링크로 만들지 않았습니다.

관련 글에는 [공개 screenshot](../screenshots/README.md)을 원본 이미지 링크로 연결했습니다. 후속 UX 개선 이후의 화면이며 초기 단계의 당시 screenshot으로 취급하지 않습니다. 새 이미지를 생성하지 않았습니다.

[후속 Issue 후보](../github-issues.md) · [공개 전 점검](../publication-review.md)
