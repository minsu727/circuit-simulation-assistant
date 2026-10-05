# v0.2 — Circuit Image to Circuit JSON (Proposed)

**Status: architecture proposal / future work.** Prompt 026은 명세만 작성한다. 이미지 인식, Circuit JSON validator, netlist adapter, review UI는 아직 구현하지 않았으며 현재 v0.1.1 배포 기능을 바꾸지 않는다.

목표는 회로 이미지를 곧바로 실행하는 것이 아니라 **검토 가능한 회로 표현**으로 변환하는 것이다.

```text
Original image (preserved)
  → visual candidates and provenance
  → Circuit JSON / component-pin-net graph
  → deterministic validation
  → human circuit review
  → simulator-neutral model / generated netlist preview
  → explicit representation approval
  → existing request review / simulation approval
  → execution copy / LTspice / existing deterministic result analysis
  → Analysis Summary / optional downstream AI interpretation
```

## Documents

| 문서 | 내용 |
| --- | --- |
| [Architecture](architecture.md) | 범위, graph, vision pipeline, 기존 실행기 연결, failure modes, 기술 선택, privacy |
| [Circuit JSON Schema](circuit-json-schema.md) | 제안 schema와 complete draft 예제, visual/electrical 분리, version·revision 계약 |
| [Validation Rules](validation-rules.md) | deterministic 규칙, 상태 전이, ambiguity와 human review |
| [Roadmap](roadmap.md) | 6 milestones, 8 test levels, fixture/benchmark 전략과 평가 지표 |
| [ADR-001](adr/001-circuit-json.md) | Circuit JSON을 canonical IR로 사용 |
| [ADR-002](adr/002-simulator-output.md) | netlist-first 출력과 ASC-only 실행기 adapter |
| [ADR-003](adr/003-vision-pipeline.md) | hybrid extraction과 deterministic reconstruction |
| [ADR-004](adr/004-human-approval.md) | 회로·생성 표현·simulation 승인 경계 |
| [ADR-005](adr/005-ai-boundaries.md) | vision inference와 정량 분석 분리 |

## First Scope

Phase A는 한 장의 깨끗한 LTspice schematic screenshot과 제한된 symbol catalog를 대상으로 한다. R/C/L, 독립 V/I source, NMOS/PMOS, ground, wire, net label을 지원 후보로 정한다. 모델과 source 설정은 이미지에 보이지 않으면 사용자가 명시한다. Diode, BJT, op amp, dependent source, subcircuit와 hand-drawn input은 첫 milestone 범위에서 제외한다.

Phase B는 직접 작성한 textbook-style diagram, Phase C는 hand-drawn circuit의 별도 후속 연구다. Phase B/C 지원이나 인식 성공률을 현재 기능으로 주장하지 않는다.

## Architectural Invariants — Future Implementation Guardrails

1. Vision 출력은 직접 신뢰하거나 실행하지 않는다. 높은 confidence도 승인 권한이 아니다.
2. Circuit JSON만 canonical 회로 상태다. graph, overlay, netlist는 해당 revision에서 파생한다.
3. deterministic connectivity validation과 human review가 simulator generation보다 먼저다.
4. unresolved `ERROR` / `AMBIGUOUS`가 있으면 generation과 execution을 차단한다.
5. 사용자가 생성된 simulator representation을 명시적으로 승인해야 한다. 기존 simulation 조건 승인도 유지한다.
6. 원본 image/ASC는 보존하고 실행 copy와 임시 전처리 파일을 분리한다.
7. gain/bandwidth/Vpp/DC 값 등 정량 분석은 기존 deterministic Python 경로를 유지한다.
8. 결과 해석 LLM은 측정 이후의 Summary만 대상으로 한다. Vision은 별도 upstream 후보 생성 역할이다.
9. 회로·모델·netlist·simulation 조건 변경은 관련 승인을 무효화한다. 오래된 결과는 새로운 회로 결과로 표시하지 않는다.
10. Cloud vision consent는 simulation 승인이나 결과 해석 승인으로 대체하지 않는다.

## v0.1 Consistency Boundary

현재 [simulation_runner.py](../../simulation_runner.py)는 `.asc` 파일만 받고 AscEditor 기반 directive/component 편집을 수행한다. `.cir` 파일을 확장자만 바꿔 넣거나 현 실행기가 netlist upload를 이미 지원한다고 가정하지 않는다. 미래 M2에서 좁은 adapter를 검증하고, v0.1 ASC 경로·parser·분석기·approval·Summary는 유지한다.

현재 동작 근거: [Root README](../../README.md), [Validation](../validation.md), [Published v0.1.1 record](../releases/v0.1.1.md), [Public example](../../examples/common_source_amplifier/README.md). Clean Windows VM / actual OpenAI API smoke는 여전히 미실시이고 unsigned installer / SmartScreen / 별도 LTspice 설치 제약은 이 제안으로 해소되지 않는다.
