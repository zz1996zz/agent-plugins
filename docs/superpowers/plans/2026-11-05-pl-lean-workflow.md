# PL 실행 규모·기록 간소화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 작은 변경의 역할 세션과 수작업 기록을 줄이면서 독립 리뷰·검증 신선도·완료 계약을 유지한다.

**Architecture:** 기존 Markdown ledger·memo·evidence를 그대로 사용한다. `ledger batch`가 기존 행과 lifecycle 변경을 한 번에 적용하고 `close`가 기록된 역할의 완료 상태로 `Team:`을 만든다. Codex 상세 계약은 조건부 reference로 분리한다.

**Tech Stack:** Python 3.9 이상, Markdown skill, Claude Code·Codex CLI.

**Spec:** 사용자가 2026-11-05 승인한 대화의 네 항목과 `docs/pl/decisions/2026-11-05-lean-workflow.md`.

## Global Constraints

- 기본 브랜치 대신 `feat/pl-lean-workflow`에서 구현·검증한다. 초기 범위에는 커밋·푸시가 없었으며, 19:14 KST의 사용자 머지 요청에 따라 커밋·PR·CI 확인 후 main 머지까지 진행한다. 별도 배포는 하지 않는다.
- `solo` 조건, 독립 reviewer, 두 review gate, verify·close의 freshness 판정, guard를 유지한다.
- 새 backend·이벤트 저장소·상태 머신을 만들지 않는다. hook 저장은 보조 수단이다.
- 파일 수만으로 full을 강제하지 않는다. full 기본 discovery는 architect 하나이며 추가 역할은 구체적인 질문으로 정당화한다.
- Codex 모델·effort·sandbox 및 hook 독립 memo 저장 계약을 유지한다.
- 기록의 기존 단일 명령과 과거 노트는 호환한다. 원장이 없는 과거 기록의 Team을 추정해 덮어쓰지 않는다.
- 코드 주석과 새 설명은 한국어로 작성한다. Python 3.9에서 런타임을 유지한다.

## Review Focus

- 잘못된 batch 뒷부분 때문에 앞부분만 원장에 저장되는 부분 갱신을 막는다.
- 같은 기록의 재시도가 spawn 수를 부풀리거나 서로 다른 역할 행을 덮어쓰지 않는다.
- spawn 뒤 memo 미수신·미완료 상태를 complete로 계산하지 않는다.
- 자동 Team 생성이 기존 failed·partial 판정이나 stale verify를 무력화하지 않는다.
- Codex reference로 이동한 정의 전달·재개·memo 저장 경로와 Claude 기본 경로가 모두 도달 가능하다.

### Task 1: 변경 전 행동·공식 자료 비교

**Files:** 결정 노트, 임시 검증 로그.

- [x] 기존 config 21개(환경 검사 1개 skip)와 history 63개 baseline을 확인한다.
- [x] 최소 5개 범주·공개 레포 8개와 현재 공식 문서를 읽고 채택·제외 이유를 결정 노트에 남긴다.
- [x] 기존 정책·무지침 대조·새 정책의 규모 선택을 각각 독립 호출 5회로 비교한다. 이 검사는 실제 실행·비용 절감의 증명이 아닌 wording 검증이다.

### Task 2: 기존 원장의 일괄 갱신과 Team 생성

**Files:** `plugins/pl/skills/team-pl-orchestrator/scripts/pl_history.py`, `test_pl_history.py`.

**Interfaces:** `ledger_batch(root: Path, stem: str, payload: dict) -> None`; stdin JSON의 `rows`와 `lifecycle` 배열을 기존 ledger에 적용한다. `close_feature`는 기록된 Spawned와 `<label>-memo` 완료 행을 집계한다.

- [x] 실제 CLI·파일을 사용하는 테스트를 먼저 작성하고 batch 미지원·Team 미생성·미완료 spawn 미차단 실패를 확인한다.
- [x] 모든 변경을 메모리에서 검증하고 원장을 한 번 atomic write한다. 기존 단일 명령도 같은 변환을 사용한다.
- [x] close 시 Team을 생성한다. 기존 legacy Team의 partial·failed 경고와 freshness 검사는 유지한다.
- [x] history 전체를 실행해 정상·거부·재시도·이전 형식 호환을 확인한다.

### Task 3: 역할 선택·조건부 reference·문서 동기화

**Files:** orchestrator `SKILL.md`, `references/{roles,debate-protocol,history,codex}.md`, config 테스트, plugin manifest 2개·README, 필요 시 Codex 생성본.

- [x] light 기본·위험 발견 시 승격·architect 기본과 QA/product 조건부·추가 세션의 독립 질문 규칙을 반영한다.
- [x] Codex 상세를 `references/codex.md`로 옮기고 본문에 호스트별 읽기 조건을 둔다.
- [x] 단계별 ledger batch 사용과 close의 Team 자동 생성을 안내하고 새 reference의 host 전용 예외를 구조 검사에 반영한다.
- [x] minor 버전 0.8.0으로 두 manifest·README 배지를 동기화한다. 역할 모델·도구·안전 계약은 유지한다.
- [x] config·history·hook·memo·Codex 생성기·smoke 판정·guard·install·E2E 판정·shellcheck·manifest·diff 검사를 실행한다.

### Task 4: 실제 실행과 전체 변경 독립 리뷰

**Files:** 결정 노트의 검증 결과, 임시 로그.

- [x] 임시 복사본에서 Claude·Codex 안전 E2E와 두 Codex smoke 진입점을 실행한다. 실패·INVALID·skip을 그대로 기록한다.
- [x] 독립 whole-diff 리뷰의 Important 4건과 복구 문제를 재현 테스트 후 수정하고 최종 suite를 확인한다. 새 문구의 실제 행동 비교도 15회 수행했다.
- [x] 최종 로컬·실제 모델 검증 결과와 Codex brief 관측 불가·비용 효과 미측정을 구분해 보고한다.

## 실행 기록

- 별도 backend 대신 기존 원장에 batch와 자동 집계만 추가했다. 자동 Team의 소유 표식은 위험 마감 뒤 재개와 legacy 실패 보존을 구분하기 위한 것이다.
- Ruling: 손상된 ledger 때문에 blocked·done-with-risks로 닫지 못하는 리뷰 Minor는 완료 계약 위반이므로 Important로 판단해 수정했다. 회귀 테스트가 실패한 뒤 경고·기존 Team 보존 경로로 통과했다.
- Python 3.9 전체 discovery의 기존 생성기 `SystemExit: 0` import 오류는 실행 방식 문제로 확인했다. 제품 코드를 바꾸지 않고 문서의 개별 실행 및 Python 3.11 전체 실행으로 검증했다.
- 모델 전송은 자동 승인 검토가 구체적인 destination/payload 승인 부재로 거절했다. 사용자에게 범위를 설명한 뒤 19:06 KST의 명시적 승인을 받아 실행했으며, 승인 전에는 다른 경로로 우회하지 않았다.
- 실제 안전 E2E는 두 호스트 각각 4/4 PASS다. Codex 두 smoke는 ARTIFACT PASS, 생성·완료·부모 수신 대조 각 1개다. 정확한 역할 brief가 암호화되어 HOST UNOBSERVABLE·종합 INVALID(exit 2)를 유지한다. 원본 source 무변경·임시 인증 복사본 제거를 확인했다.
- 최종 결과·근거·검증 한계는 위 결정 노트에 기록했다. 초기 검증 보고까지 커밋·푸시하지 않았고, 이후 사용자 머지 요청에 따라 통합한다. 별도 배포는 하지 않는다.
