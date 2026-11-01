# PL Codex 호환성 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 직접 진단·수정·검증을 요청했으므로 현재 세션에서 연속 실행한다.

**Goal:** Claude 경로를 보존하면서 현재 Codex의 skill·subagent·hook 계약으로 PL을 실행한다.

**Architecture:** 역할 Markdown과 shared preamble은 공유한다. Codex는 노출된 spawn schema에 따라 custom agent 또는 정의를 담은 일반 subagent를 사용한다. 모델·effort는 외부 설정에 맡기고, memo·verify·close는 lead가 명시적으로 실행한다.

**Tech Stack:** Python 3.9 런타임, Python 3.11 TOML 생성기, bash 3.2, Codex CLI 0.166.0.

**Spec:** 현재 사용자 요청의 목표 및 필수 작업 1–9.

## 제약 및 검토 초점

- 사용자 변경·기존 fixture·개인 Codex 설정을 보존한다. commit·push·publish는 하지 않는다.
- Claude agent frontmatter와 plugin hook은 유지한다. Codex에만 적용되는 차이를 host mapping에 둔다.
- `agent_type`이 없는 schema, 필수 `task_name`, 완료 알림과 `wait_agent` 차이, 세션 복구 시 ID 유효성, 신뢰되지 않은 hook을 검증한다.
- 저장소 manifest 기준 버전은 0.5.1이다. 요청의 0.6.0과 다르므로 원본을 재작성하지 않고 다음 패치 버전 0.6.1로 맞춘다.

## 작업

- [x] 실패 재현: 독립 baseline 평가 및 generator 기본값·hook 없는 memo 저장 테스트를 먼저 실행한다.
- [x] host mapping과 alias를 수정한다. Codex schema에 맞는 spawn·재개·중단, 설치 선택화, memo 저장과 복구를 명시한다.
- [x] generator에서 Claude effort·무효 sandbox 설정 변환을 제거하고 TOML을 재생성한다. memo CLI와 안전한 경로 검증을 추가한다.
- [x] Codex smoke의 세션 실행·실제 subagent·memo·검증 증거를 점검하는 테스트를 추가한다. 격리된 환경에서 실행한다.
- [x] CONTRIBUTING 테스트 매트릭스, skill validator, 안전한 실제 Codex 실행과 독립 최종 검토를 수행한다. 실제 S3·S4는 실행하지 않고 CLI host 관측 불가는 INVALID로 기록한다.
- [x] 공식 문서 및 공개 저장소 비교를 docs/pl/decisions에 기록하고 최종 결과·제약을 보고한다.

## 진단 근거

수정 전 독립 baseline: `agent_type` 없는 현재 spawn schema에서 첫 역할 실행 불가, 재개·중단 도구 이름 불일치, `wait_agent` 반환을 memo로 오인, 생성된 검사 역할의 `model_reasoning_effort=xhigh` 고정. 기존 Codex hook은 command handler만 사용하며 verify·close는 이미 lead 실행이다. 이 경로는 보존한다.

## 최종 확인

2026-11-02 기준: Python 3.11 전체 skill 테스트 109개(1개 opt-in skip), smoke 판정 15개, guard 136개, installer 26개, 기존 E2E 판정 20개 통과. Python 3.9 런타임 개별 테스트도 통과했다. 독립 최종 리뷰 Gate 1·2 통과, 미해결 Critical/Important 없음. 실제 CLI의 alias·본체 artifact PASS와 host trace 미관측을 구분하고, 현재 host 도구의 실제 spawn·재개·memo 전달은 별도 검증했다. [설계·검증 기록](../../pl/decisions/2026-11-02-codex-host-compatibility.md)에 실패 출력·생략 범위를 남겼다.
