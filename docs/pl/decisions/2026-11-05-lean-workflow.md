---
type: Decision
title: PL 실행 규모·기록 간소화
status: accepted
date: 2026-11-05
owner: PL agent
---

## Context

사용자는 pl 0.7.0의 규모 판정·역할 수·기록 호출·호스트 지침의 중복을 검토하도록 요청했고, 검토 뒤 제안한 제한된 범위를 승인했다. 기록 호출은 제공된 네 세션에서 합계 840/3955(21.2%)였지만 원본 로그를 확보하지 못해 독립 재현하지 못했다. 이 비율은 Bash 호출 비율이며 API 요청 수·비용 절감률이 아니다. 한 달짜리 세션은 당시 plugin 버전도 분리해야 한다.

## Options Considered

- 기존 full 우선·architect/QA 필수·개별 기록 호출을 유지한다.
- 역할 선택과 기록 호출을 간소화하고 기존 원장·memo·검증 계약을 유지한다(선택).
- lifecycle을 hook에서 전부 추론하거나 별도 이벤트 저장소로 바꾼다(제외). 응답 누락·hook 실패·재개·호스트 차이까지 재설계해야 한다.

## Decision

1. 명시적인 사용자 규모 지시는 유지한다. 그 외 애매하면 light로 시작하고 설계·권한·데이터·외부 계약의 구체적인 위험이나 미해결 의존성이 발견되면 full로 승격한다. 파일 수는 참고값이다. solo 조건은 그대로다.
2. full discovery는 architect 하나를 기본으로 한다. product는 미결정 제품 범위, QA는 설계 전에 정해야 하는 검증 전략이 있을 때 추가한다. 추가 세션마다 독립 질문·산출물·의존성·소유 범위를 명시한다. 고정 인원·턴 상한은 새로 만들지 않는다.
3. 기존 ledger와 memo를 유지한다. `ledger batch`는 행·lifecycle 변경을 stdin JSON으로 받아 모두 검증한 뒤 한 번 저장한다. close는 원장의 Spawned와 memo 완료 행으로 Team을 생성하며, 미완료 세션을 complete로 추정하지 않는다. 자동 Team에 소유 표식을 두어 재개 후 갱신하고, 표식 없는 수기 partial/failed는 위험 마감에서도 보존한다. 기존 단일 명령과 과거 수기 Team은 호환한다.
4. Codex 상세 계약은 `references/codex.md`로 옮긴다. 본문에는 호스트 판별·필수 읽기 조건을 남긴다. hook 독립 memo 저장, 정의 전달, 재개, 모델·effort 외부 설정은 유지한다.
5. reviewer·두 review gate·fresh verify/close·guard·역할별 안전 경계는 유지한다. 이번 분리와 관련 없는 안전 규칙의 대규모 정리는 하지 않는다.

## Rationale

2026-11-05 현재 공식 문서의 방향과 비교했다. 정확한 light/full 기준과 architect 기본은 PL의 설계 선택이며 외부 문서가 그 인원 수를 입증한 것은 아니다.

- [Claude subagents](https://code.claude.com/docs/en/sub-agents): 빠른 국소 변경·여러 단계가 문맥을 공유하는 작업은 main conversation에 적합하며, 독립된 책임·좁은 brief·요약 반환을 권장한다. fork는 공유 cache를 활용할 수 있으므로 독립 문맥을 무조건 더 저렴하다고 주장하지 않는다.
- [Claude skills](https://code.claude.com/docs/en/skills), [작성 지침](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices): 핵심 지침과 필요한 reference를 나누는 progressive disclosure를 채택한다. compaction의 스킬당 앞 5,000토큰·전체 25,000토큰 보존 한계는 확인했으나 현재 Workflow가 실제로 잘렸다는 증거는 없다.
- [Claude hooks](https://code.claude.com/docs/en/hooks): 응답 종료와 작업 완료를 구분한다. SubagentHandback 보고와 SubagentStop 마지막 문장이 다를 수 있으므로 hook 파일만으로 lifecycle 전체를 판정하지 않는다.
- [Claude plugins](https://code.claude.com/docs/en/plugins-reference), [costs](https://code.claude.com/docs/en/costs): 기존 packaging·namespace를 유지하고 팀 규모·문맥·실행 시간을 줄이는 방향만 참고한다. agent teams의 비용 수치를 PL subagent에 대입하지 않는다.
- [Multi-agent research](https://www.anthropic.com/research/multi-agent-research-system): 복잡도에 맞춘 실행 규모, 명확한 목표·출력·경계, 중복 탐색 방지를 채택한다. 15배는 해당 Research 대 chat 비교이며 PL 단일 실행 대비 배율이 아니다.
- [Codex customization](https://learn.chatgpt.com/docs/customization/overview), [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [hooks](https://learn.chatgpt.com/docs/hooks), [config](https://learn.chatgpt.com/docs/config-file/config-reference): 필요한 reference 로딩·read-heavy 독립 작업·호스트 schema와 외부 model/effort 설정을 유지한다. hook 신뢰와 가용성을 전제로 완료 기록을 맡기지 않는다.

### 공개 저장소 비교

2026-11-05에 다음 8개·6개 이상 범주의 원문을 다시 읽었다. SHA는 기존 조사에서 재사용한 고정 비교점이며 최신 HEAD라는 뜻이 아니다. 과거 maxTurns 조사로 이번 역할 수·기록 변경의 근거를 대신하지 않았다.

| 저장소·범주 | commit SHA·실제로 읽은 파일 | 채택·제외 이유 |
|---|---|---|
| openai/codex · 공식 구현·Codex 설정 | `67f0994b532b8740f14b5b738af7b7b2a915b1d6` · [multi_agents_spec.rs](https://github.com/openai/codex/blob/67f0994b532b8740f14b5b738af7b7b2a915b1d6/codex-rs/core/src/tools/handlers/multi_agents_spec.rs) | task_name·agent_type·fork_turns를 구분하고 실제 schema를 우선한다. V1과 V2 인자를 섞지 않는다. 고정 역할 수 근거는 없다. |
| anthropics/claude-code · 공식 참조 | `80c6959d28c4c30ecd14fc1cdf172f19d9adad81` · [README](https://github.com/anthropics/claude-code/blob/80c6959d28c4c30ecd14fc1cdf172f19d9adad81/README.md) | 현재 공식 문서로 연결하는 진입점만 참고한다. light/full·ledger에 대한 직접 근거는 없다. |
| anthropics/skills · 공식 예제·marketplace | `ca45fc496a3436251f191354091d557da31c15b5` · [README](https://github.com/anthropics/skills/blob/ca45fc496a3436251f191354091d557da31c15b5/README.md), [skill-creator](https://github.com/anthropics/skills/blob/ca45fc496a3436251f191354091d557da31c15b5/skills/skill-creator/SKILL.md) | metadata→본문→필요 reference의 단계적 로딩과 반복 작업 script화를 채택한다. 예제의 전체 평가 절차를 PL runtime에 강제하지 않는다. |
| VoltAgent/awesome-claude-code-subagents · catalog | `f2e2ea7e0202cc05fa2d469fcb2c57fe08603450` · [backend-developer](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/f2e2ea7e0202cc05fa2d469fcb2c57fe08603450/categories/01-core-development/backend-developer.md) | 구체적인 역할 호출 조건·책임만 참고한다. 범용 checklist·보장되지 않은 context manager·여러 역할의 일괄 호출은 제외한다. |
| wshobson/commands · slash workflow | `fb091adb62800c7109cdbef47e5d6f55769e99f9` · [full-review](https://github.com/wshobson/commands/blob/fb091adb62800c7109cdbef47e5d6f55769e99f9/workflows/full-review.md) | 전문 리뷰를 중요도별로 종합하는 패턴을 채택한다. 기본 다섯 리뷰·과거 Task 도구·고정 모델 복제는 제외한다. |
| obra/superpowers · cross-tool skill | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` · [parallel agents](https://github.com/obra/superpowers/blob/2ce8aa15d05bd57213e6f746f953aafb7ded7a8b/skills/dispatching-parallel-agents/SKILL.md), [verification](https://github.com/obra/superpowers/blob/2ce8aa15d05bd57213e6f746f953aafb7ded7a8b/skills/verification-before-completion/SKILL.md) | 독립 scope·수정 경계·통합 충돌 검사·완료 전 fresh 증거를 채택한다. 공유 상태나 관련 실패의 무조건 분산은 제외한다. |
| ruvnet/ruflo(이전 claude-flow) · orchestration | `e580bbc8204874f762d132fe441b18192979211b` · [README](https://github.com/ruvnet/ruflo/blob/e580bbc8204874f762d132fe441b18192979211b/README.md) | plugin과 전체 runtime의 설치·기능 범위를 구분한다. 추가 daemon·대형 역할군·별도 memory/swarm 계층 및 홍보 성능 수치의 전용은 제외한다. |
| openai/plugins · 공식 marketplace | `0722921d5542fc593105c27bd52630babd8b8c2a` · [plugin.json](https://github.com/openai/plugins/blob/0722921d5542fc593105c27bd52630babd8b8c2a/plugins/build-web-apps/.codex-plugin/plugin.json) | 공유 skills 디렉터리의 기존 packaging을 유지한다. 새 실행기·역할 수·ledger 변경의 직접 근거는 없다. |

일부 web cache miss는 GitHub connector의 실제 원문 읽기로 보완했다. claude-flow는 같은 SHA의 이동된 ruflo URL로 읽었다. 셸 DNS 실패는 성공 조회로 계산하지 않았다.

## Consequences

단순 변경의 강제 discovery와 반복 기록 요청을 줄일 수 있는 구조다. 실제 token·시간 절감률과 품질 효과는 아직 측정하지 않았다. hook 누락을 숨기거나 기록 backend를 교체하지 않는다. 지원되는 명령을 추가하고 운영 정책을 바꾸므로 버전은 0.8.0으로 올린다.

## Validation

- 변경 전 config 21개(환경 opt-in 1개 skip), history 63개 통과.
- 새 batch·Team 행동 테스트를 먼저 추가해 batch 미지원, 집계 미생성, 미완료 spawn의 잘못된 done 허용을 확인한 뒤 구현했다. config의 reference 집합도 새 파일이 없는 실패를 확인한 뒤 갱신했다.
- 독립 whole-diff 리뷰는 Important 4건과 손상된 원장의 위험 마감 실패를 재현했다. 자동 Team의 재마감 차단, 위험 마감의 수기 실패 기록 소실, pipe task 중복, 동일 ID의 복수 label 집계, 손상된 ledger 마감 문제다. 마지막 문제도 복구 계약에 영향을 주므로 Important로 판단해 함께 수정했다. 각각 실패를 보인 회귀 테스트가 수정 후 통과했으며 history는 74개다.
- Python 3.9의 전체 discovery 시도는 생성기 테스트가 기존 `SystemExit: 0`을 발생시켜 import 오류 1건으로 실패했다. 생성기에는 Python 3.11이 필요하므로 기여 안내의 Python 3.9 개별 실행과 Python 3.11 전체 실행으로 확인한다. 이 실행 방식 문제를 제품 코드 수정으로 숨기지 않았다.
- 실제 Claude 문구 비교 세션은 처음에 자동 승인 검토가 저장소 내용의 외부 전송에 대한 구체적 승인 부재로 거절했다. 사용자에게 PL 지침·역할 정의·테스트 코드(인증정보 제외)를 Anthropic·OpenAI로 전송하는 문구 비교·안전 E2E·Codex smoke 범위를 설명했고, **2026-11-05 19:06 KST에 명시적 승인을 받은 뒤** 실행했다. 승인 전에는 다른 경로로 실행해 우회하지 않았다.
- 최종 로컬 매트릭스:

| 검사 | 결과 |
|---|---|
| Python 3.11 skill scripts 전체 | 121개, OK, 환경 opt-in 1개 skip |
| Python 3.9 config·history·hook·memo 개별 실행 | 모두 통과, config의 환경 opt-in 1개 skip. 최종 history 74개 재확인 |
| Codex smoke 판정 unittest | 23개 OK |
| Codex 생성본 `--check` | 9개 drift 없음 |
| guard 매트릭스 | PASS=143 FAIL=0 |
| E2E 판정 로직(임시 복사본) | PASS=20 FAIL=0 |
| 선택 설치 | 26개 PASS, FAIL=0 |
| shellcheck·diff whitespace | 통과 |
| Claude plugin·marketplace validator | 둘 다 통과. plugin에는 기존 ICON_MISSING 경고 |
| 실제 문구 비교 | Sonnet 5.5(`claude-sonnet-5-5`), 무지침·기존·새 정책 각 5회, 합계 15회 실행. 아래 결과 참조 |
| Claude 실제 안전 E2E | S1–S4 모두 PASS, FAIL=0 INVALID=0 |
| Codex 실제 안전 E2E | S1–S4 모두 PASS, FAIL=0 INVALID=0 |
| Codex `$pl` smoke | ARTIFACT PASS / HOST UNOBSERVABLE / 종합 INVALID(exit 2). 생성 1개·완료와 부모 수신 대조 1개 |
| Codex orchestrator 직접 호출 smoke | ARTIFACT PASS / HOST UNOBSERVABLE / 종합 INVALID(exit 2). 생성 1개·완료와 부모 수신 대조 1개 |

실제 검증은 Claude Code 2.1.316·Codex CLI 0.166.0과 현재 0.8.0 파일의 임시 복사본에서 수행했다. 두 안전 E2E는 각각 별도 복사본·로컬 bare 원격을 사용했다. Codex smoke는 두 진입점 모두 hook·개인 custom agent 설치 없이 실행했다. 실행 전후 원본 plugin·테스트 소스의 SHA-256에 변경이 없었으며 smoke의 임시 인증 복사본은 제거됐다.

### 규모 선택 행동 비교

각 호출은 도구와 세션 지속성을 끄고 독립 실행했다. 기존·새 `SKILL.md`와 `roles.md`를 같은 형식으로 전달하고, 동일한 세 가지 독립 요청을 판정하게 했다. 새 정책을 쓰기 전 보존한 0.7.0 파일로 기존 정책을 비교했다. 무지침 대조에는 정책 본문을 전달하지 않았다.

| 시나리오 | 무지침 대조 5회 | 기존 0.7.0 정책 5회 | 새 0.8.0 정책 5회 |
|---|---|---|---|
| A: 명확한 수용 조건·기존 테스트가 있는 내부 표시 제거, 기존 6파일 수정, 계약·권한·결제 영향 없음 | light 5회. discovery 0개 2회·1개 3회 | full·architect+QA 5회 | light·discovery 0개·reviewer 필수 5회 |
| B: 사용자가 full을 명시한 문자열 수정 | full 5회, discovery 0–1개 | full 5회. architect+QA 4회, product까지 추가 1회 | full·architect 하나·reviewer 필수 5회 |
| C: 고객 간 권한 경계·스키마 변경, 롤백·데이터 보존·검증 전략 미정 | full 5회, discovery 3–4개 | full·architect+QA+product 5회 | full·architect+QA·reviewer 필수 5회 |

세 요청은 하나의 테스트 입력에 각각 독립된 사례로 제시했다. 실제 feature를 세 개 구현한 검사가 아니다. 기존 정책 응답 일부는 요구한 reviewer JSON 필드를 생략하거나 JSON을 재작성했으므로, 전체 응답 schema 준수까지 5/5 PASS라고 주장하지 않는다. 표의 규모·discovery 판정은 원문을 모두 읽고 확인했다. 새 정책은 5회 모두 reviewer 필드도 true였다. 문구 해석의 분산 감소·명시 full 유지·위험 시 QA 추가를 확인했으나 실제 개발 품질이나 비용 절감률은 측정하지 않았다.

### 실제 기록·역할 실행 경로

두 Codex smoke 모두 분리된 `references/codex.md` 본문을 실제 읽었고 `ledger batch`를 사용했다. reviewer가 실제 생성돼 최종 응답을 전달했고, 저장 memo와 부모 수신 내용이 일치했다. 기존 unittest·직접 호출·keep.txt 보존과 요청하지 않은 commit 부재가 통과했다. feature는 `status: done`, `Fresh at close: yes`, 자동 생성 `Team: 1 role sessions (complete 1)`로 닫혔다.

다만 원본 기록에서 역할 brief 본문이 암호화돼 **정확한 역할 정의 전달은 관측 불가**다. 생성·완료·부모 수신·저장 성공과 정의 전달 가시성을 구분하며, 두 smoke의 종합 INVALID를 PASS로 낮추지 않았다. 이 한계는 이전 0.7.0 조사에서도 확인된 것이다. 실제 full discovery의 모든 역할 조합을 실행한 것은 아니며, 이번 full 규모 비교는 위 문구 검사 범위다.

스킬 본문은 14,761자에서 12,738자로 줄었으며 문자 수 기준이다. tokenizer로 측정한 token 수나 비용 절감률로 주장하지 않는다. 공개 레포 비교에는 읽기 전용 조사 세션 하나, 전체 변경에는 독립 리뷰 세션 하나를 사용했고 역할별 구현 세션은 추가하지 않았다. 독립 리뷰의 Important와 복구 문제는 재현 실패 테스트→수정→전체 suite로 검증했으며 추가 리뷰 세션을 반복하지 않았다.

구현·로컬 검증과 승인된 실제 검증을 수행했으며, 위 관측 한계와 비용 효과 미측정을 함께 보고한다. 임시 fixture와 설치 테스트만 사용했고 개인 plugin·agent 설정은 변경하지 않았다. 작업 브랜치는 `feat/pl-lean-workflow`다. 초기 검증 보고까지 커밋·푸시하지 않았으며, 19:14 KST의 사용자 머지 요청으로 커밋·PR 생성·CI 확인 후 main 머지까지 승인받았다. 별도 배포는 하지 않는다.

## Open Questions

- 원본 queenfish·platy·catshark 로그와 당시 버전별 비용·재작업 지표는 미확보다.
- light 승격·조건부 QA의 품질 효과는 후속 실제 사용에서도 관찰해야 한다.
- Codex 원본 기록의 암호화된 역할 brief는 정확한 정의 전달을 독립 확인할 수 없는 상태다.
