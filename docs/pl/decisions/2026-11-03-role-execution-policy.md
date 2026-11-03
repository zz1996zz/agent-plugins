---
type: Decision
title: "역할별 고정 턴 제한 제거와 범위별 복수 실행"
status: accepted
date: 2026-11-03
---

# 역할별 고정 턴 제한 제거와 범위별 복수 실행

사용자는 정상 작업 중 발생한 `50-turn limit`의 출처를 확인한 뒤 고정 턴 제한 제거를 승인했다. 이어 독립 기능별로 같은 역할을 여러 명 실행하는 방식도 이번 변경에 포함하도록 승인했다. 작업 브랜치는 `fix/pl-role-execution-policy`다. 초기 구현·검증 후 사용자가 커밋·push·PR 생성과 `main` 머지까지 승인했다. 개인 설치본은 자동으로 변경하지 않는다.

## 출처와 결정

- 기존 `maxTurns` 값은 2026-10-20 설계·계획 커밋 `05e0df3`에서 분석·리뷰 40–60, 구현 120으로 제안됐고, 역할별 값은 구현 계획 Task 9에서 확정됐다. 실제 역할 정의에는 `e51044b`에서 추가됐다. 설계에는 실측으로 조정한다고 되어 있으나 해당 숫자의 적정성을 확인한 기록은 찾지 못했다.
- 역할 Markdown 9개에서 `maxTurns`를 제거한다. 숫자를 높이거나 다른 고정 상한으로 바꾸지 않는다. 정상적으로 진전되는 작업은 배정된 완료 조건까지 수행한다. 동일 실패 반복·정체·외부 의존성은 원인과 다음 조치를 리드에게 보고하고 기존 교정·교체 절차로 처리한다. 외부 호스트의 사용량·실행·동시성 제한은 바꾸지 않는다.
- 외부 중단으로 반환된 부분 결과는 같은 세션으로 재개할 수 있다. 재개 중인 부분 결과는 원장의 진행 상태·근거로 보존하고, 최종 미완료·실패만 lifecycle `Partial`/`Failed`에 기록한다. 메모가 도착했다는 이유만으로 작업을 `done`으로 기록하지 않는다.
- 역할 정의와 실행 인스턴스를 구분한다. backend에 한정하지 않고 모든 역할에 독립 scope별 복수 세션을 허용한다. 역할군·호스트 도구·별도 실행기를 추가하지 않는다. 기능 수만큼 모든 역할을 복제하는 방식은 채택하지 않는다.
- 예를 들어 `pl-backend-orders`와 `pl-backend-search`는 동일한 backend 정의로 실행한다. 각 세션은 고유 라벨, `<label>-memo` task ID, 실제 session ID, memo 경로를 연결한다. 재개는 같은 라벨·ID를 유지하고 교체는 scope 라벨 뒤에 `-r2`를 붙인다.
- 구현은 파일·모듈 독점 소유권과 의존성으로 나눈다. 공통 계약을 먼저 확정하고 공통 파일 수정은 단일 소유자가 순차 통합한다. QA·리뷰·보안·통합은 테스트 범위·요구사항·위협 경계·외부 연동으로, product·architect는 독립 도메인의 질문으로 나눈다. 리드가 공통 결정을 종합한다.
- 분할 리뷰마다 요구사항·결정과 담당 reviewer를 연결한다. reviewer 한 명이 전체 diff의 공통 경로·기능 간 상호작용과 두 gate를 확인하고, 리드가 최종 통합 검증을 수행한다. 범위별 PASS만으로 전체 완료를 선언하지 않는다.
- 버전은 새 역할 배정 정책을 반영해 두 manifest와 README 배지를 0.7.0으로 맞춘다. 과거 설계·결정 문서는 당시 맥락을 보존한다. Codex TOML은 shared preamble 변경을 반영해 재생성한다.

## 공식 문서 확인

확인일은 2026-11-03이다. 다음 문서를 실제 열어 계약을 대조했다.

- [Claude subagents](https://code.claude.com/docs/en/sub-agents): `maxTurns`는 선택 필드이며 partial 반환·재개를 설명한다. 특정 역할에 50턴을 권장하지 않는다. 필드 제거는 프로젝트의 선택이며 공식 문서가 무제한 실행을 권고한 것으로 해석하지 않는다.
- [Claude skills](https://code.claude.com/docs/en/skills): forked skill 호출과 직접 subagent 실행을 구분한다. 같은 skill의 후속 호출 대기를 역할당 한 세션 제한으로 일반화하지 않는다.
- [Claude hooks](https://code.claude.com/docs/en/hooks): `agent_id`와 `agent_type`을 구분한다. [Plugin reference](https://code.claude.com/docs/en/plugins-reference)의 기존 agent·skills·hooks 배포 구조를 유지한다.
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents): 독립 작업의 병렬 실행과 쓰기 작업의 충돌·조정 비용을 고려한다. [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)의 호스트 동시 thread 제한을 따르며 역할별 인스턴스 수 제한을 만들지 않는다.
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)의 신뢰 경계를 유지하고 lead 직접 기록을 사용한다. [Plugin packaging](https://developers.openai.com/plugins/build/plugins)의 기존 공유 skills·manifest 경로를 유지한다.

## 공개 저장소 비교

2026-11-03에 다음 pinned 원문 8개 저장소·6개 이상 범주를 다시 확인했다. SHA는 이전 호스트 호환성 조사와 같으며 최신 HEAD라는 의미는 아니다.

| 저장소·범주 | 확인 commit | 읽은 파일 | 채택·제외 판단 |
|---|---|---|---|
| [openai/codex](https://github.com/openai/codex) · 공식 구현·Codex 설정 | `67f0994b532b8740f14b5b738af7b7b2a915b1d6` | `codex-rs/core/src/tools/handlers/multi_agents_spec.rs` | 역할 type과 task 이름·반환 ID 분리 채택. 고정 턴 값의 근거로 사용하지 않음 |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) · 공식 참조 | `80c6959d28c4c30ecd14fc1cdf172f19d9adad81` | README와 연결 공식 문서 | frontmatter 계약은 현재 공식 문서로 대조. README를 50턴 권장의 근거로 사용하지 않음 |
| [anthropics/skills](https://github.com/anthropics/skills) · marketplace | `ca45fc496a3436251f191354091d557da31c15b5` | README, `.claude-plugin/marketplace.json` | 공유 skill·배포 구조 유지. 인스턴스 수·턴 정책의 직접 근거는 없음 |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) · subagent catalog | `f2e2ea7e0202cc05fa2d469fcb2c57fe08603450` | `categories/01-core-development/backend-developer.md` | 전문 책임·산출물 분리 참고. 고정 모델·가상 context-manager·광범위 checklist 제외. 읽은 파일에 maxTurns 없음 |
| [wshobson/commands](https://github.com/wshobson/commands) · slash-command workflow | `fb091adb62800c7109cdbef47e5d6f55769e99f9` | `workflows/full-review.md` | 여러 리뷰 결과의 리드 통합 채택. 과거 Task 호출 복제 제외. 읽은 파일에 maxTurns 없음 |
| [obra/superpowers](https://github.com/obra/superpowers) · cross-tool skill | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | README, `skills/dispatching-parallel-agents/SKILL.md` | 동일 general-purpose 유형 3개를 독립 test 파일별로 실행하는 예시 확인. scope 분리·수정 경계·통합 충돌 검사 채택. 공유 상태의 무조건 병렬화 제외 |
| [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow) · multi-agent orchestration | `e580bbc8204874f762d132fe441b18192979211b` | README | 호스트 계약 분리만 참고. 추가 swarm runtime·daemon·대형 역할군 제외. README의 maxTurns 부재를 제거 권고로 해석하지 않음 |
| [openai/plugins](https://github.com/openai/plugins) · 공식 plugin marketplace | `0722921d5542fc593105c27bd52630babd8b8c2a` | `plugins/build-web-apps/.codex-plugin/plugin.json` | 기존 공유 skills 배포 유지. 역할 수·턴 정책의 직접 근거는 없음 |

이전 조사 노트에 적힌 superpowers `references/codex-tools.md`는 해당 SHA에서 404였다. 이번에는 실제 존재하는 dispatch skill을 읽었다. 일부 web 조회의 cache miss는 읽기 전용 네트워크 조회로 보완했다.

## 검증

변경 전 독립 행동 검증은 같은 역할의 scope별 label·task ID 규칙 부재와 `<role>-memo` 충돌 가능성을 확인했다. 주문·검색 시나리오에서 backend 한 세션으로 두 기능을 순차 처리하는 계획이 나왔다. 변경 후 같은 시나리오는 두 backend 세션, 독점 파일 소유권, 공통 router의 순차 통합, 분할 리뷰 뒤 전체 diff 검토로 계획됐다. 정상 50턴 진행·외부 partial·반복 실패와 auth/payments의 역할 분할 기준도 별도로 검토했다.

독립 리뷰가 발견한 Important 1건은 메모 도착만으로 ledger를 done으로 기록하는 기존 문구의 모순이다. 완료 조건을 충족한 최종 응답에만 done을 허용하고 일시적 partial과 최종 미완료 기록을 구분한 뒤 재검토에서 Gate 1·2 PASS를 받았다. 이 검증은 실제 모델의 정책 적용 계획 검증이며, 모든 역할 조합의 병렬 구현을 실제 실행했다는 뜻은 아니다.

설정 불변식 테스트 2개는 먼저 `maxTurns` 부재를 기대하도록 바꿔 기존 설정에서 실패하는 것을 확인했다.

```text
FAIL: test_role_inventory_and_frontmatter
AssertionError: 'maxTurns' unexpectedly found ... team-pl-architect.md
FAIL: test_committed_agents_frontmatter_is_subagent_contract
AssertionError: 'maxTurns' unexpectedly found ... team-pl-architect.md
```

설정 제거·Codex 생성본 갱신 후 두 테스트를 포함한 설정 21개(환경 opt-in 1개 skip)와 생성기 14개는 통과했다.

| 검사 | 결과 |
|---|---|
| Python 3.11 skill scripts 전체 unittest | 110개, OK, 환경 opt-in 1개 skip |
| Python 3.11 Codex smoke 판정 unittest | 15개, OK |
| Codex 생성본 `--check` | 9개 drift 없음 |
| 안전 훅 매트릭스 | PASS=143 FAIL=0 |
| 선택 설치 스크립트 | 26개 PASS, FAIL=0 |
| E2E 판정 로직(임시 복사본) | PASS=20 FAIL=0 |
| shellcheck, diff whitespace 검사 | 통과 |
| Claude plugin·marketplace validator | 둘 다 통과, plugin에는 기존 ICON_MISSING 경고 |
| Claude 실제 S1(임시 복사본) | 재실행 PASS, FAIL=0 INVALID=0 |
| Codex 실제 S1(임시 복사본·임시 인증 홈) | 재실행 PASS, FAIL=0 INVALID=0 |
| Codex 오케스트레이터 직접 호출 smoke | ARTIFACT PASS / HOST UNOBSERVABLE / INVALID(exit 2) |
| Codex `$pl` alias smoke | 사용자 승인 후 재실행: ARTIFACT PASS / HOST UNOBSERVABLE / INVALID(exit 2) |

최초 샌드박스 안의 실제 CLI 실행은 아래 오류로 INVALID였다. 이를 성공으로 세지 않았다. 네트워크·인증 접근을 허용한 S1 재실행은 위와 같이 통과했다.

```text
Claude: Not logged in · Please run /login
Codex: workspace routing discovery failed
```

S2–S4 실제 모델 세션은 실행하지 않았다. 이번에는 변경된 역할 정책을 별도 행동 시나리오로 검증하고, 기존 안전 경계는 S1과 전체 단위 매트릭스로 점검했다. 기존 사용자 E2E fixture 대신 임시 복사본에서 실행했고, 개인 설치본과 config는 갱신하지 않았다.

직접 호출 smoke에서는 코드 변경·memo·verify·close 결과가 통과했지만, 공개 CLI JSONL에서 실제 spawn 성공 이벤트를 관측할 수 없어 종합 성공으로 세지 않았다. 별도 행동 검증과 CLI 관측 결과를 합쳐 host PASS라고 주장하지 않는다. `$pl` alias 재검증은 임시 테스트·플러그인 내용을 Codex API로 전송할 구체적 사용자 승인이 없다는 자동 승인 검토 사유로 한 번 중단됐다. 사용자가 해당 검증 실행을 명시적으로 승인한 뒤 최신 플러그인을 새 임시 복사본에서 재실행했다. alias 경로도 코드 변경·기존 unittest·keep.txt 보존·memo·verify·close 결과는 통과했으며, 동일하게 실제 spawn 성공 이벤트가 관측되지 않아 `ARTIFACT PASS / HOST UNOBSERVABLE / INVALID(exit 2)`로 기록한다. 실행 후 임시 인증 복사본이 제거됐음을 확인했다.

## 추가 진단: 생성 누락과 이벤트 누락 구분

위 두 기존 실행은 `--ephemeral`이어서 원본 세션 기록이 남지 않았다. 해당 실행들이 실제로 생성했는지는 사후 입증할 수 없으며, 아래 새 재현의 증거를 기존 실행의 증거로 소급하지 않는다.

설치된 Codex CLI 0.166.0의 릴리스 소스 commit은 `6ff1e1ca3b30fc8b914720681fcf5fe62e95f856`이다. [V2 spawn](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs)은 생성 성공을 `SubAgentActivity`로 알리지만 [exec JSONL 변환기](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/exec/src/event_processor_with_jsonl_output.rs)는 이 유형을 출력하지 않는다. 반면 [V2 wait](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs)는 빈 대상 목록의 `CollabAgentToolCall`을 출력한다. 따라서 `wait`만 보인다는 이유로 생성 누락을 단정할 수 없다.

동일한 `$pl` 시나리오에서 `--ephemeral`만 제거해 재현했다. 새 원본 기록에서는 부모의 실제 spawn 호출과 `/root/pl_review` 반환, 부모 UUID에 연결된 별도 자식 UUID, 자식의 Important 지적, 같은 세션 재개 후 `Status: DONE`, 부모의 구조화된 FINAL_ANSWER 수신과 저장 memo가 확인됐다. 파일 마지막 개행 1개를 제외한 응답 내용이 일치했다. 이 재현에서는 실제 reviewer 생성·재개·완료·수신이 입증됐다.

검증기는 JSONL에 생성이 없으면 해당 실행의 임시 홈 원본 기록으로 위 관계를 교차 확인하도록 수정했다. 관련 실패 테스트를 먼저 확인한 뒤 23개 smoke 판정 테스트가 통과했다. 독립 리뷰에서 발견한 Important 1건(두 번째 성공 spawn의 자식 증거가 없을 때 첫 번째만 보고 PASS 가능)은 두 세션 실패 테스트로 재현한 뒤 수정했고 재검토에서 추가 Critical/Important가 없었다.

역할 brief 본문은 새 원본 기록에서도 암호화돼 있어 정확한 정의 전달까지 입증하지는 못했다. 이를 정의 누락 FAIL로 오판하지 않고 별도 `관측 불가`로 기록한다. 새 재현을 보완된 검증기로 재판정한 결과는 **실제 생성 1개·최신 완료와 부모 수신 대조 1개, ARTIFACT PASS, 역할 brief 비공개로 종합 INVALID**다. 전체 성공 기준을 낮추거나 역할 실행 여부와 brief 가시성을 혼동하지 않는다. 이 원본 기록 처리는 테스트만의 관측 보완이며 PL의 runtime 계약을 바꾸지 않는다.

후속 최종 검증은 Python 3.11 skill scripts 110개(환경 opt-in 1개 skip), smoke 판정 23개 모두 통과했다. 기본 Python에서도 smoke 판정 23개를 재확인했고 `git diff --check`가 통과했다. 실제 보존 기록을 수정된 판정 함수로 다시 읽어 생성·완료·수신 대조와 암호화 brief의 별도 미확인 판정을 확인했다. 임시 인증 복사본도 제거된 상태다.
