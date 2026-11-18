---
type: Decision
title: PL 호출·light 기록·reviewer 보고의 제한적 간소화
status: accepted
date: 2026-11-13
owner: PL agent
---

## Context

사용자는 최신 공식 글과 현재 pl의 과도한 절차를 검토한 뒤 Codex·Claude의 독립 재검토를 요청했다. 두 검토는 solo 확대와 최종 freshness 완화의 근거가 부족하다고 판단했다. 두 결과를 대조한 제한적 권고에 사용자가 `진행해`라고 승인했다. 비용·오탐·개발 품질 개선은 미측정이며 이번 변경의 확정 효과로 주장하지 않는다.

## Options Considered

- 원래 다섯 제안을 함께 적용: 독립 리뷰·영구 증거 생략과 fingerprint 계약 변경이 포함되어 제외한다.
- light 템플릿 헤딩 삭제: 기존 도구·테스트·노트와의 호환 변경이 필요해 제외한다.
- 호출 의도와 조건부 서술만 정리하고 기존 증거·헤딩·helper를 유지한다(선택).

## Decision

1. description은 PL/tech-lead 또는 역할 에이전트에 기능 분석·구현을 맡기는 요청을 대상으로 좁힌다. 사용법·설명·읽기 전용 감사는 기능 workflow와 구분한다. 명시 alias로 로드되어도 요청 의도와 제한을 먼저 적용한다. PL 자체 변경·감사는 CONTRIBUTING을 따른다.
2. light에서 실제 수행하지 않았고 남은 쟁점도 없는 Synthesis·Challenges에만 기존 헤딩 아래 `n/a — light`를 허용한다. 실제 역할 결과·Scope와 규모 사유·핵심 결정·검증·리뷰·Team·잔여 위험은 보존한다. 실제 충돌은 n/a로 덮지 않는다.
3. reviewer는 위치·근거·영향이 있는 결함을 Findings에, 근거가 부족한 우려를 Unconfirmed concerns에 구분한다. 중요한 미확인 위험에는 확인 방법을 남기고 리드가 처리한다. 낮은 confidence나 P4/P5 분류만으로 중요도를 낮추지 않는다. 두 gate·중요 결함 처리·리드의 판정 책임은 유지한다.
4. solo 경계·역할 수·모델 정책·안전 hook·verify/close freshness·노트 템플릿과 helper는 변경하지 않는다. 2026-11-05 결정의 나머지 정책은 유지한다. 이번 선택은 해당 결정 전체를 대체하지 않는다.

## Rationale

2026-11-13에 Claude의 [subagents](https://code.claude.com/docs/en/sub-agents)·[skills](https://code.claude.com/docs/en/skills)·[hooks](https://code.claude.com/docs/en/hooks)·[plugins](https://code.claude.com/docs/en/plugins), Codex의 [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)·[hooks](https://learn.chatgpt.com/docs/hooks)·[config](https://learn.chatgpt.com/docs/config-file/config-reference) 원문을 확인했다. 기존 호스트별 정의 전달·hook 독립 증거 경로는 유지한다.

[OpenAI 2026-09-11 글](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)은 짧고 구체적인 호출 조건과 필요한 자료만 읽는 구조를 권한다. [OpenAI 2026-10-14 글](https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family)과 [Anthropic 2026-03-24 실험](https://www.anthropic.com/research/harness-design-long-running-apps)은 모델별·요소별 관찰과 측정을 뒷받침한다. 이 자료들이 PL의 solo 기준이나 검증 생략의 안전성을 입증하는 것은 아니다.

### 공개 저장소 비교

독립 조사 에이전트가 2026-11-13에 공식 GitHub connector로 default branch의 HEAD를 조회하고 아래 SHA에 고정된 실제 파일을 읽었다. 여덟 저장소는 공식 구현·예제, 역할 catalog, slash workflow, cross-tool skill, orchestration runtime, marketplace 범주를 포함한다. 날짜는 commit UTC 날짜이며 조사일과 구분한다.

| 저장소·범주 | commit SHA·UTC 날짜·확인한 원문 | 채택·제외 이유 |
|---|---|---|
| openai/codex · 공식 구현·review | `69231e119bfca0b14453515e97d99688ce1c47c9` · 2026-11-13 · [rubric](https://github.com/openai/codex/blob/69231e119bfca0b14453515e97d99688ce1c47c9/codex-rs/prompts/templates/review/rubric.md), [review-agent](https://github.com/openai/codex/blob/69231e119bfca0b14453515e97d99688ce1c47c9/codex-rs/skills/src/assets/samples/review-agent/SKILL.md) | 조치 가능한 결함·입증된 영향·confidence·중요 검증 공백과 잔여 위험 분리를 채택한다. JSON schema와 P0–P3 체계는 이식하지 않는다. |
| anthropics/claude-code · 공식 제품 | `e17972353b00440bf432e46cb601b2fbe5f0e524` · 2026-11-13 · [README](https://github.com/anthropics/claude-code/blob/e17972353b00440bf432e46cb601b2fbe5f0e524/README.md) | 공식 문서·plugin 구현의 진입점만 참고한다. PL의 n/a·review 규칙의 직접 근거로는 제외한다. |
| anthropics/skills · 공식 skill 예제 | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` · 2026-11-06 · [skill-creator](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/skill-creator/SKILL.md) | 의도·trigger·출력 구분, 양성·음성 및 키워드가 겹치는 near-miss 평가를 채택한다. n/a 자체의 근거로 확대하지 않는다. |
| VoltAgent/awesome-claude-code-subagents · catalog | `ed74d115b7fb7026a22a4f816a8e3250f425e3b4` · 2026-11-02 · [code-reviewer](https://github.com/VoltAgent/awesome-claude-code-subagents/blob/ed74d115b7fb7026a22a4f816a8e3250f425e3b4/categories/04-quality-security/code-reviewer.md) | 구체적 조치·중요 문제 우선 보고만 참고한다. context manager 전제·보편 coverage 수치·범용 checklist는 제외한다. |
| wshobson/commands · slash workflow | `fb091adb62800c7109cdbef47e5d6f55769e99f9` · 2026-09-30 · [full-review](https://github.com/wshobson/commands/blob/fb091adb62800c7109cdbef47e5d6f55769e99f9/workflows/full-review.md) | 필수 수정·권고·제안을 나누는 패턴만 참고한다. archive된 고정 5리뷰·과거 Task·고정 모델은 제외한다. |
| obra/superpowers · cross-tool skill | `22f0b463e7a5e579904dd6211a520321035526f7` · 2026-11-03 · [brainstorming](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/SKILL.md), [reviewer](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/code-reviewer.md), [verification](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion/SKILL.md) | 규모에 맞춘 서술·위치/이유/중요도·리드 판단·fresh 증거를 유지한다. n/a 규칙은 PL 자체 선택이다. |
| ruvnet/ruflo · orchestration runtime | `002d8c1ac031871fc14220e964f4dbb35b60428f` · 2026-11-12 · [README](https://github.com/ruvnet/ruflo/blob/002d8c1ac031871fc14220e964f4dbb35b60428f/README.md) | 개념/demo와 실제 실행 증거를 구분하는 원칙만 참고한다. daemon·memory·swarm 계층과 홍보 성능 수치는 제외한다. |
| openai/plugins · 공식 marketplace | `d420d13051bffe4543ed39e30fa46b87148e47dd` · 2026-11-06 · [plugin.json](https://github.com/openai/plugins/blob/d420d13051bffe4543ed39e30fa46b87148e47dd/plugins/build-web-apps/.codex-plugin/plugin.json) | 기존 공유 skills packaging을 유지한다. manifest로 runtime·리뷰·완료 계약을 입증하지 않는다. |

## Consequences

실행 의도가 없는 요청의 기록 부작용과 불필요한 서술을 줄이는 것이 목적이다. 핵심 증거를 버리거나 새로운 상태·의존성 추적기를 추가하지 않는다. 프롬프트 동작을 바꾸므로 버전은 0.8.1로 올린다. 설치본 자동 업데이트는 하지 않는다.

## Validation

- 변경 전 config 테스트: 21개 OK, 환경 opt-in 1개 skip.
- 동작 사례는 `tests/pl-prompts/cases.json`, 평가 범위와 한계는 같은 디렉터리 README에 둔다.
- 최초 Claude baseline 실행은 자동 승인 검토가 외부 payload 승인 부족으로 거절했다. 실행을 우회하지 않고 payload·provider·합성 사례·fixture 동작 범위를 명시해 승인을 요청했고, 사용자가 `이 범위의 평가·E2E 실행 승인`이라고 답한 뒤 실행했다. 승인 전 모델 평가는 실행하지 않았다.
- 추가 확인: GitHub connector에서 이 저장소의 `visibility: public`을 확인했고, 전송 대상 기존 지침 5개가 공개 commit `3edd173cff6731c05acbe01b1081a329328b0084`의 원문과 모두 일치했다. 이 확인은 외부 실행 승인이나 동작 평가의 성공을 대신하지 않는다.
- 변경 전 helper 전체 baseline: Python 3.11 unittest 121개 OK, 환경 opt-in 1개 skip. 임시 복사본에서 실행했다. 출력의 placeholder·누락 memo 경고는 해당 거부 동작을 검증하는 fixture에서 발생했으며 실패는 없었다.
- 임시 평가 스크립트의 초기 구문 오류로 두 CLI 호출 전에 실패했다. 괄호를 수정하고 `py_compile` 통과 후 실행했다. 이 시도를 모델 평가 성공으로 세지 않는다.

### 로컬 검사와 실제 실행

Claude Code 2.1.316·Codex CLI 0.166.0에서 확인했다. 합성 평가 모델은 Claude Sonnet 5.5(`sonnet`, medium)와 `gpt-6.1-sol`(low)이며 실제 안전 E2E에는 각각 `claude-sonnet-5-5`와 `gpt-6.1-sol`을 지정했다. 이 모델·설정의 결과를 다른 모델 전체로 일반화하지 않는다.

| 검사 | 결과 |
|---|---|
| Python 3.9 config/history/hooks/memo, Codex smoke 판정 unittest, Python 3.11 생성기 테스트 | 합계 144개 OK, 환경 opt-in 1개 skip |
| Codex 생성본 `--check` | 9개 drift 없음 |
| guard 매트릭스 | PASS=143, FAIL=0 |
| E2E 판정 로직 | PASS=20, FAIL=0 |
| 선택 설치 | PASS=26, FAIL=0 |
| shellcheck·diff whitespace | 통과 |
| plugin·marketplace validator | 통과. plugin의 기존 `ICON_MISSING` 경고 유지 |
| Claude 실제 안전 E2E | S1–S4 PASS, FAIL=0, INVALID=0 |
| Codex 실제 안전 E2E | S1–S4 PASS, FAIL=0, INVALID=0 |
| Codex `$pl` 역할·기록 smoke | ARTIFACT PASS / HOST UNOBSERVABLE / 종합 INVALID(exit 2) |
| Codex orchestrator 직접 진입 smoke | ARTIFACT PASS / HOST UNOBSERVABLE / 종합 INVALID(exit 2) |
| 독립 구현 리뷰 | Critical·Important·Minor 지적 없음. 전체 diff·untracked 문서·사례·TOML 일치·버전 확인 |

안전 E2E는 각기 별도 임시 복사본·일회용 fixture·로컬 bare 원격에서 실행했다. 두 역할 smoke는 개인 agent 설치·hook 없이 실행했고 실제 역할 생성 1개·완료 응답과 부모 수신 대조 1개·memo 저장·unittest·freshness check·`status: done`·자동 Team 집계가 확인됐다. 두 smoke의 실제 feature에도 Synthesis·Challenges가 `n/a — light`로 기록됐다. 다만 원본 기록의 brief가 암호화되어 정확한 역할 정의 전달을 독립 확인할 수 없어 **종합 INVALID를 유지**했다. 이는 0.8.0 결정에도 기록된 관측 한계다. 임시 인증 복사본은 두 smoke 모두 제거된 것을 확인했다.

최종 plugin 변경 파일 9개가 E2E 복사본과 byte 단위로 일치함을 확인했다. 사용자 저장소 HEAD는 `3edd173cff6731c05acbe01b1081a329328b0084`로 유지했으며 커밋·푸시·개인 설치본 갱신은 하지 않았다.

### 프롬프트 동작 평가

합성 사례는 양성 5개·음성 5개·명시 alias 감사 2개, light 기록, 결함/테스트 공백/미확인 캐시 위험의 reviewer 보고를 포함한다. PL 본문 미제공 대조·baseline·수정안 각 5회씩 두 호스트에서 합계 30회 실행했다. 각 호출에 12개 요청과 기록·리뷰 사례를 함께 제시했으며 **60개의 독립 모델 실행이 아니다**. 독립 평가자가 30개 응답 원문을 읽고 선택과 workflow를 따로 판정했다.

| 호스트 | 군 | 스킬 선택 정답 /60 | 기능 workflow 정답 /60 |
|---|---|---:|---:|
| Claude | PL 본문 미제공 | 60 | 60 |
| Claude | baseline | 60 | 60 |
| Claude | 수정안 | 60 | 60 |
| Codex | PL 본문 미제공 | 42 | 51 |
| Codex | baseline | 50 | 60 |
| Codex | 수정안 | 60 | 60 |

Codex baseline은 매번 `decision history`와 `team agents` 용어 설명을 과잉 선택했지만 기능 workflow는 실행하지 않았다. 수정안은 이 선택 오답을 제거했다. Claude의 호출 판정은 baseline과 대조도 이미 맞았으므로 개선 효과로 계산하지 않는다. 이 평가는 전체 PL 본문을 함께 제공한 문구 모의 평가이며, 실제 호스트의 자동 선택·로드를 입증하지 않는다. Claude는 safe-mode, Codex는 ignore-user-config/read-only로 실행했으나 기본 harness 문맥과 Codex global catalog의 완전 격리를 입증하지 않았다. 대조를 순수 무지침이나 모델 간 우열로 해석하지 않는다.

수정안의 두 호스트 각 5개 응답은 실제 reviewer·CSV 결정·두 gate·검증·Team·잔여 위험을 유지하면서 두 분석·반론 절만 `n/a — light`로 썼고, 캐시 우려를 확인 방법과 함께 Unconfirmed concerns로 분리했다. limit=0 결함·테스트 공백·캐시 우려 보존과 해결 전 PASS 금지는 대조군도 이미 잘했으므로 새 효과로 주장하지 않는다. baseline도 import 취향 지적을 제외했다.

혼합 입력에서 Claude 일부 응답이 trigger 사례의 CSV 기능 요청을 light의 사용자 원문으로 가져왔다. light만 분리해 두 호스트 각 5회, 총 10회를 추가 실행하고 독립 평가자가 모두 읽었다. 원문 혼입은 0/10, 핵심 절 보존과 두 절 n/a는 10/10이었다. 실제 테스트 실행·통과 증거를 꾸며 낸 응답은 관찰하지 못했다. 다만 Claude는 5/5에서 두 gate PASS만으로 `unresolved findings: none`을 단정했고, 일부에는 규모 사유·기각 대안·원장 집계의 정보 과장이 남았다. Codex는 이 항목을 미확인으로 구분했다. 따라서 응답 전부가 사실 정확성까지 통과했다고 주장하지 않는다.

11월 13일에는 원문·CLI usage·판정 자료를 임시 디렉터리에 보존하고 커밋하지 않았다. 11월 18일 재개 시 해당 임시 디렉터리는 정리되어 원문을 다시 확인할 수 없었다. 위 모델 평가·안전 E2E·역할 smoke 결과는 당시 직접 확인한 실행 기록이며 11월 18일에 재실행한 결과가 아니다. cold/warm cache·출력 분량·실행 설정이 섞인 이 평가로 시간·토큰·개발 품질의 절감률을 주장하지 않는다.

### 2026-11-18 재개와 최종 확인

- runtime 파일은 추가 수정하지 않았다. 별도 스냅샷에서 기여 안내의 로컬 매트릭스를 다시 실행했다. Python 144개 중 1개 opt-in skip, 나머지 통과. guard 143개·E2E 판정 20개·설치 26개, 생성본 drift·shellcheck·plugin/marketplace validator도 통과했다. 기존 `ICON_MISSING` 경고는 남아 있다.
- 이번 로컬 실행의 전체 명령·종료 코드·출력은 채팅 scratch의 `pl-final-20261118-uzeyka4f/logs/`에, 입력 파일 SHA-256과 도구 버전은 같은 작업 디렉터리에 보존했다. 이는 사라진 11월 13일 모델 원문을 복원한 자료가 아니다.
- Claude의 `unresolved findings: none` 과잉 추론에 대한 추가 독립 판정을 완료했다. 첫 요청은 사용량 제한으로 실패했으므로 검토 완료로 세지 않았고, 재개 후 reviewer가 현재 runtime diff와 이 노트를 읽고 판정했다. reviewer도 사라진 평가 원문을 재확인했다고 주장하지 않았다.
- 해당 추론은 baseline에서도 관찰됐고, 수정안은 Review·실제 memo·잔여 위험 보존을 명시한다. 명시된 Minor가 실제 기록에서 사라지거나 Important가 닫히거나 실행 증거가 조작된 사례는 확인하지 못했다. 따라서 새 Important 회귀로 보지 않고 기존 모델 한계로 기록한다. 이번 범위에 지침·완료 계약·helper 수정을 추가하지 않는다.
- 후속 보강이 필요하면 `PASS+Minor 명시`·`PASS+findings 없음 명시`·`PASS만 제공`을 나누어 비교한다. 이 보강 효과는 이번 결과로 입증하지 않는다. Codex smoke 두 건의 HOST UNOBSERVABLE·종합 INVALID도 그대로 유지한다.

### 2026-11-19 머지 요청과 사전 검증

- 사용자가 `머지까지 해라`라고 요청해 이 변경의 커밋·브랜치 push·PR 생성·main 머지를 진행하도록 허가했다. 개인 설치본 갱신·별도 배포는 포함하지 않는다.
- 원격 main을 fetch하고 기준 commit `3edd173cff6731c05acbe01b1081a329328b0084`와 추가 차이가 없음을 확인했다. 작업 브랜치의 기존 PR은 없었다.
- runtime은 추가 수정하지 않고 별도 스냅샷에서 로컬 매트릭스 전체를 다시 실행했다. 13개 검사 명령이 모두 exit 0이었다. Python 합계 144개 중 환경 opt-in 1개 skip, guard 143개·E2E 판정 20개·설치 26개와 생성본 drift·shellcheck·양쪽 validator가 통과했다. 기존 `ICON_MISSING` 경고는 유지한다.
- 새 실행 기록은 채팅 scratch의 `pl-merge-20261119-qx1r3d4t/logs/`에 보존했다. 모델 평가·실제 안전 E2E·역할 smoke는 11월 13일 실행 기록을 사용하며 이번 머지 단계에서 반복하지 않았다. smoke 두 건의 INVALID와 모델의 정보 과장 한계는 PR에도 명시한다.

## Open Questions

- 시간·토큰·재작업·실제 개발 품질의 개선 효과는 별도 측정이 필요하다.
- 호출 모의 평가만으로 호스트의 실제 카탈로그 선택·로드를 입증할 수 없다.
- Codex 역할 brief의 정확한 전달은 암호화 때문에 관측하지 못했다. 두 smoke의 종합 판정은 INVALID다.
- 불완전한 입력에서 모델이 `미확인`을 `없음`으로 단정하는 한계가 남는다. 실제 memo·원장·검증 자료와 대조해야 한다.
