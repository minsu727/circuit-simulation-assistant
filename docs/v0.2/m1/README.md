# v0.2 M1 — Circuit IR / Local Validation Closure

Prompt 027의 계획에 따라 M1A–M1G의 local Circuit IR 범위를 구현·검증했다. 현재 결과와 제한은 [M1 Status](status.md), 계획된 38개 case의 근거는 [Acceptance Matrix](acceptance-matrix.md)에 기록한다. 기존 계획 문서는 당시 결정과 예산을 보존한 자료이며, 통과 test 수는 계획 예산이 아니라 실제 실행 결과를 따른다. v0.1 제품 연결이나 simulator 실행은 M1 범위가 아니다.

## Documents

| 문서 | 구현 전 결정 |
| --- | --- |
| [Implementation Plan](implementation-plan.md) | 범위, 최소 package, primitives, 10-step 구현 순서와 acceptance |
| [Data Model](data-model.md) | 정확한 types/fields/enums, pin/net 계약, 값 parsing와 serialization |
| [Validation Plan](validation-plan.md) | 9 stages, graph/DC algorithm, issue/state, deferred checks |
| [Test Plan](test-plan.md) | 계획 fixture 38개, 약 96 logical test cases, test matrix |
| [Prompt Breakdown](prompt-breakdown.md) | M1A–M1G의 원래 구현 handoff와 경계 |
| [Acceptance Matrix](acceptance-matrix.md) | 38개 계획 case와 보완 unit subcase의 규칙별 근거 |
| [M1 Status](status.md) | 현재 구현 범위, 검증 결과, 한계와 M2 경계 |

## Decisions

- `Circuit JSON`은 canonical IR이며 `connections`만 pin-to-net membership의 기준이다.
- `schema_version="0.2-draft1"`을 유지한다. M1 작업 이름을 이유로 wire version을 `0.2-m1`로 바꾸지 않는다.
- frozen dataclasses + 표준 `json`/`Decimal` + native graph를 사용한다. M1C에서 Draft 2020-12 검증용 `jsonschema` 직접 의존성을 `requirements-circuit-ir.txt`로 분리했고 full test requirements에 포함했다. M1G에서는 새 의존성을 추가하지 않았다.
- ERROR와 AMBIGUOUS는 block이다. confidence는 오류를 덮어쓸 수 없다.
- 기술 상태 `VALID`는 `m1-local-v1` profile에서의 통과다. human approval이나 전체 v0.2 generation-ready 상태가 아니다.
- Image/OCR/Vision/UI/exporter/simulator/API와 model-library resolution은 M1 밖이다.

## Scope Conflicts / Decisions Requiring Explicit Follow-up

| 차이 | 기존 근거 | 이번 계획의 처리 |
| --- | --- | --- |
| Full `MODEL_INVALID`는 catalog 존재·polarity 확인을 요구하지만 M1은 model-library resolution 금지 | [Rules](../validation-rules.md), 이번 M1 요청 | 모델 ref/W/L 형식·누락만 검사하고 catalog lookup은 `CHECK_DEFERRED`. `VALID@m1`을 full validation이나 export 허가로 승격하지 않는다 |
| 기존 M1 roadmap에 manual record editor가 있지만 이번 범위는 UI editing 제외 | [Roadmap](../roadmap.md) | loader와 손으로 작성할 JSON fixtures만 계획. interactive editor는 M4로 남긴다 |
| 기존 M1 acceptance의 “각 blocking rule negative case”에는 image/model/export 단계가 섞여 있다 | [Roadmap](../roadmap.md), [Rules](../validation-rules.md) | M1 적용 규칙은 전부 검사하고 후속 단계 규칙은 coverage/deferred 표로 명시. full-rule completion을 주장하지 않는다 |

이는 상위 architecture를 조용히 변경하지 않기 위한 범위 조정 기록이다. 특히 catalog 확인을 생략하고 full simulator-ready라고 표시하는 설계는 허용하지 않는다. 구현 착수 시 profile/deferred 경계를 유지하고, 후속 full-profile 규칙 확장은 별도 검토한다. 기존 ADR의 canonical IR, netlist-first, human approval, AI boundary를 바꾸는 결정은 없다.

Issue prefix, 내부 상태 이름, enriched diagnostic 정보는 runtime 계획이며 기존 closed JSON 필드를 추가하거나 code를 교체하지 않는다. 세부 호환 계약은 [Data Model](data-model.md)과 [Validation Plan](validation-plan.md)에 있다.

## M1 Completion Boundary

typed loading, deterministic graph/validation, 엄격한 JSON round-trip과 계획된 38개 fixture 계약을 local-only acceptance로 검증했다. 기존 전체 regression도 실행했으며 실제 수는 [M1 Status](status.md)에 기록한다. LTspice 설치, cloud/API, image/model 파일은 M1 acceptance의 조건이 아니다. 기술 상태 `VALID`는 로컬 계약 통과만 뜻하며 export/approval/simulator readiness를 보장하지 않는다.

기존 원칙과 연결: [v0.2 invariants](../README.md), [ADR-001](../adr/001-circuit-json.md), [ADR-004](../adr/004-human-approval.md), [ADR-005](../adr/005-ai-boundaries.md).
