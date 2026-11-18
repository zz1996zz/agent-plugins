# PL 프롬프트 제한적 간소화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 승인한 범위를 현재 세션에서 구현하고 마지막에 독립 리뷰를 받는다.

**Goal:** PL의 호출·light 작성·reviewer 보고를 명확히 하면서 완료 증거를 보존한다.

**Architecture:** helper와 노트 헤딩은 그대로 두고 프롬프트의 요청 분기·조건부 작성 규칙만 바꾼다. 역할 Markdown에서 Codex TOML을 재생성한다.

**Tech Stack:** Markdown, JSON, 기존 Python unittest와 shell E2E.

**Spec:** `docs/superpowers/specs/2026-11-13-pl-prompt-simplification-design.md`

## Global Constraints

- solo 경계·최종 verify/close freshness·안전 hook·설치본은 변경하지 않는다.
- Python 3.9 이상, 생성기는 Python 3.11 이상, bash 3.2 호환을 유지한다.
- 최초 구현 범위에서는 커밋·푸시·배포를 하지 않는다. 2026-11-19 사용자의 명시적인 머지 요청으로 이 작업의 커밋·브랜치 push·PR 생성·main 머지는 허가됐다. 별도 설치·배포는 포함하지 않는다. 작업 브랜치는 `feat/pl-prompt-simplification`이다.
- 기존 사용자 요청과 독립 검토로 범위가 승인되어 추가 설계 승인을 반복하지 않는다. 작업은 현재 Orca checkout의 별도 브랜치에서 수행한다.

## Review Focus

- 명시 alias로 들어온 사용법·읽기 전용 감사도 기능 실행으로 오인하지 않는다.
- 일반 언어의 PL/tech-lead 기능 요청을 놓치지 않는다.
- light에서 실제 수신한 역할 의견·핵심 결정·미해결 충돌을 n/a로 덮지 않는다.
- 낮은 confidence의 중요 결함이나 P4/P5의 실질 결함을 보고에서 지우지 않는다.
- 기존 노트 헤딩·두 gate·freshness·Codex 생성본의 호환성을 유지한다.

## Task 1: 동작 사례와 변경 전 관측

- [x] `tests/pl-prompts/cases.json`과 안내에 호출 양성·음성, alias 감사, light 기록, reviewer 사례를 작성한다.
- [x] 기존 config 테스트를 실행하고, PL 본문 미제공·기존 지침을 적용한 평가를 두 호스트에서 반복한다. 문구 평가와 실제 로드를 구분하고 원문을 읽는다.
- [x] 기여 안내에 따라 공식 자료와 공개 레포 8개·5범주 이상을 확인하고 결정 노트에 기록한다.

## Task 2: 승인된 프롬프트 변경

- [x] 두 SKILL.md에 호출 조건·메타 요청 분기를 적용한다.
- [x] history.md에 light n/a 조건과 필수 증거 보존을 명시한다.
- [x] reviewer와 debate-protocol의 우려 처리 규칙을 일치시킨다.
- [x] Codex reviewer TOML을 재생성하고 양쪽 manifest·README를 0.8.1로 맞춘다.
- [x] 같은 동작 사례를 수정안으로 평가하고 결과·오판을 기록한다.

## Task 3: 검증·독립 리뷰·보고

- [x] CONTRIBUTING.md의 전체 로컬 매트릭스를 실행한다.
- [x] 임시 복사본에서 Claude·Codex 안전 E2E와 두 Codex 역할 smoke를 실행한다. smoke의 HOST UNOBSERVABLE·종합 INVALID는 PASS로 세지 않고 기록한다.
- [x] 전체 diff를 독립 reviewer에게 전달하고 Important 이상을 해결한다. 지적 사항은 없었고, 추가 관측의 정보 과장은 독립 판정 후 residual로 남긴다.
- [x] 결정 노트에 실제 결과·한계·미실행 검사를 기록하고 사용자에게 변경·검증 결과를 보고한다.

## 마감 기록

2026-11-18 로컬 매트릭스를 재확인했다. 11월 13일 모델 원문은 임시 디렉터리 정리로 현재 없으며 당시 실행 기록과 오늘의 로컬 검사를 구분한다. 최종 근거와 남은 한계는 `docs/pl/decisions/2026-11-13-prompt-simplification.md`의 Validation에 기록했다. 커밋·푸시·설치본 갱신은 하지 않았다.
