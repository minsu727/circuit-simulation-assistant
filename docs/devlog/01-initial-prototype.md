# 01 — Initial Prototype

## 문제 / 목표

첫 구현은 사용자가 회로와 요청을 앱에 전달할 수 있는지 확인하는 단계였다. Prompt 001은 Streamlit 제목, ASC 업로드, 자연어 입력창, **Analyze Request** 버튼으로 범위를 제한했다.

## 당시 결정

초기 화면에서 자연어 조건 해석, LLM API, LTspice 실행, 결과 분석은 제외했다. 버튼 이름이 Analyze Request라고 해서 그 시점에 분석기가 완성된 것은 아니다. 입력을 받고 누락을 안내하는 흐름부터 확인했다.

## 구현

파일이나 요청이 없으면 warning을 표시하고, 입력이 있으면 업로드한 파일명과 요청 내용을 보여줬다. 이후 기능을 붙일 수 있도록 단순한 입력 화면으로 시작했다.

임시 rule-based parser와 Review 화면은 후속 개발에서 사용됐다. 정확한 도입 시점은 원본 로그에 별도로 기록되어 있지 않지만, Prompt 003의 시작 상태에서 분석 종류 정도만 판별하고 주파수에는 기본값을 사용하는 한계가 확인된다. 따라서 이를 Prompt 001의 완료 기능으로 소급하지 않는다.

## 검증

Prompt 001에는 Streamlit 로컬 서버 실행과 브라우저의 UI 표시 확인이 기록되어 있다. 이 단계의 unit test 수나 실제 simulation 성공 기록은 없다. 당시 로컬 UI 증거와 현재 공개 screenshot도 구분하며, 공개되지 않은 초기 이미지를 링크하지 않는다.

## 실패 / 문제

후속 AC 작업에서는 “10 Hz부터 1 MHz까지”라고 요청해도 Review의 Stop Frequency에 기본값 100 MHz가 남았다. 분석 종류를 AC로 분류하는 것과 사용자가 지정한 범위를 추출해 화면에 연결하는 것은 서로 다른 작업이었다.

이 문제는 [AC Directive Generation 기록](../development-log.md#2026-09-14--ac-directive-generation)에 남아 있다. Prompt 001에서 이미 발생·수정된 문제로 서술하지 않는다.

## 수정 / 배운 점

입력 화면의 성공 표시는 요청을 받았다는 확인일 뿐, 요청한 조건을 해석했다는 증거가 아니었다. 이후에는 parser 결과, Review 초기값, 승인된 directive, 실제 RAW 범위를 함께 확인하도록 검증 범위를 넓혔다. 1 MHz 문제의 구체적인 수정과 실제 실행 결과는 [AC Analysis](03-ac-analysis.md)에서 다룬다.

## 다음 단계

먼저 [LTspice Integration](02-ltspice-integration.md)에서 기존 ASC directive를 실행해 파일과 실패 처리를 검증했다. 그다음 승인한 UI 조건을 실제 directive로 바꾸는 작업으로 넘어갔다. LLM을 연결하지 않아도 이 두 경계는 독립적으로 검증할 수 있었다.

원본: [Prompt 001](../prompt-log.md#prompt-001--initial-interface), [Prompt 003](../prompt-log.md#prompt-003--ac-directive-generation).

[이전: Problem Definition & Scope](00-problem-definition-and-scope.md) · [목차](README.md) · [다음: LTspice Integration](02-ltspice-integration.md)
