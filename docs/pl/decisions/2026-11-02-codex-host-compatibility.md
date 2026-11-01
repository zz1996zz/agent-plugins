---
type: Decision
title: "Codex host 계약에 맞춘 PL 실행"
status: accepted
date: 2026-11-02
---

# Codex host 계약에 맞춘 PL 실행

사용자 요청은 PL의 Codex 실사용 개선과 Claude 호환 유지다. [구현 계획](../../superpowers/plans/2026-11-01-pl-codex-compatibility.md)을 기준으로 필요한 호스트 경로와 검증만 수정했다. 시작 시 작업 트리는 깨끗했고 `main`에서 `fix/pl-codex-compatibility`를 만들었다. 로컬 시작 manifest는 0.5.1이었으나, 후속 commit·push·merge 요청에서 fetch한 원격 `main`에는 PL 0.6.0(`f276f89`)이 있었다. 이를 feature branch에 통합해 0.6.0의 Claude 역할별 설정을 보존하고 두 manifest와 배지를 0.6.1로 맞췄다. 초기 구현·검증 단계에서는 commit·push를 하지 않았으며 후속 사용자 지시로 통합한다. marketplace 배포는 하지 않는다.

## 결정

- 역할 Markdown과 shared preamble은 하나로 유지한다. Claude의 plugin agent·Skill·skill hook·SubagentStop 경로는 유지한다. Codex에서는 실제 schema에 `agent_type`이 없거나 등록 역할을 확인할 수 없으면 역할 본문을 일반 subagent brief에 전달한다. 개인 TOML 설치를 필수로 만들지 않는다.
- Codex task 식별자는 label과 분리한다. 예를 들어 `pl-review`는 `task_name: pl_review`로 전달한다. `fork_turns: none` 또는 지원되는 `fork_context: false`로 완결된 brief를 독립 실행한다. 실제 ephemeral CLI 실행에서 이름 제한과 부모 rollout 부재 오류를 확인한 데 따른 수정이다.
- 일반 Codex subagent의 모델·effort는 외부 config에 맡긴다. Claude는 0.6.0의 역할별 `opus`/`sonnet`, `high`/`medium` 설정을 그대로 보존하지만 생성 TOML에는 model·effort·효과 없는 sandbox 키를 넣지 않는다. 예전 TOML의 고정 effort나 본문 차이가 발견되면 정의 전달 경로를 사용한다. 개인 설정을 자동으로 덮어쓰지 않는다.
- command/MCP tool hook도 미신뢰·미지원이면 실행되지 않을 수 있다. lead가 memo 수신·저장·verify·review·close를 직접 수행한다. Codex의 prompt/agent handler, skill-frontmatter hook, SubagentStop 또는 transcript 형식에 핵심 동작을 맡기지 않는다. Codex hook 경로 변수는 네이티브 `PLUGIN_ROOT`를 사용한다. `Bash` matcher는 현재 Codex에서도 유효하다.
- `memo` CLI는 명시적 feature·호스트 반환 ID·수신 응답으로 기록한다. `<ID 해시>-<응답 해시>.md`로 경로 형태 ID를 안전하게 처리하고 재개 전 원문을 보존한다. 동일 응답 재저장은 멱등적이다. hook과 기존 history 상태 판정은 재작성하지 않는다.
- smoke는 artifact와 host 관측을 분리한다. 관측된 위반은 FAIL(1), 필수 host 증거 부족은 INVALID(2), 둘 다 입증됐을 때만 PASS(0)다. V2의 UUID·task_name을 동일 namespace로 가정하지 않는다. 언어는 사용자 지침을 따르고 역할 필드명은 유지한다.

## 공식 계약 근거

2026-11-01 조사, 2026-11-02 실제 실행으로 대조했다.

- [Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents): 일반 subagent 기본값·custom agent의 우선순위·부모 sandbox.
- [Codex Hooks](https://learn.chatgpt.com/docs/hooks), [Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference): hook trust, command/MCP 지원, prompt/agent handler skip, 네이티브 plugin 변수.
- [Plugin packaging](https://developers.openai.com/plugins/build/plugins): 기존 `.codex-plugin`·skills·hooks 경로를 유지할 수 있다.
- [Claude subagents](https://code.claude.com/docs/en/sub-agents), [skills](https://code.claude.com/docs/en/skills), [hooks](https://code.claude.com/docs/en/hooks), [plugin reference](https://code.claude.com/docs/en/plugins-reference): Claude 전용 frontmatter·agent·hook 계약.
- [Codex spawn schema](https://github.com/openai/codex/blob/67f0994b532b8740f14b5b738af7b7b2a915b1d6/codex-rs/core/src/tools/handlers/multi_agents_spec.rs): `agent_type`과 모델 인자의 노출은 조건부다.
- [exec JSONL](https://github.com/openai/codex/blob/67f0994b532b8740f14b5b738af7b7b2a915b1d6/codex-rs/exec/src/exec_events.rs), [V2 spawn](https://github.com/openai/codex/blob/67f0994b532b8740f14b5b738af7b7b2a915b1d6/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs), [V2 wait](https://github.com/openai/codex/blob/67f0994b532b8740f14b5b738af7b7b2a915b1d6/codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs): JSONL의 내부 UUID와 모델에게 반환되는 task 경로가 다르고, 최종 응답이나 model·effort가 모두 공개되지는 않는다.

## 공개 저장소 비교

확인일은 모두 2026-11-01이다. 8개 저장소, 6개 범주를 commit 원문으로 확인했다. 대규모 framework나 역할군은 도입하지 않았다.

| 저장소·범주 | 확인 commit | 읽은 파일 | 채택·제외 판단 |
|---|---|---|---|
| [openai/codex](https://github.com/openai/codex) · 공식 구현 | `67f0994b532b8740f14b5b738af7b7b2a915b1d6` | README, docs/config.md, multi_agents_spec.rs, multi_agents_v2/spawn.rs | 실제 schema 분기 채택. 고정 도구표를 모든 host에 적용하는 방식 제외 |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) · 공식 참조 | `80c6959d28c4c30ecd14fc1cdf172f19d9adad81` | README와 연결 공식 문서 | Claude plugin 경로 유지. Claude tool 이름을 Codex로 전파하는 방식 제외 |
| [anthropics/skills](https://github.com/anthropics/skills) · marketplace | `ca45fc496a3436251f191354091d557da31c15b5` | README, .claude-plugin/marketplace.json | 공유 skill 본문과 packaging 분리 채택. skill 전체 복제 제외 |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) · subagent catalog | `f2e2ea7e0202cc05fa2d469fcb2c57fe08603450` | README, categories/01-core-development/backend-developer.md | 역할 lane·deliverable 유지. 거대 catalog·고정 모델·가상 context-manager protocol 제외 |
| [wshobson/commands](https://github.com/wshobson/commands) · slash-command workflow | `fb091adb62800c7109cdbef47e5d6f55769e99f9` | README, workflows/full-review.md | 역할 review 후 lead 통합 유지. archived Task 호출·고정 모델·무조건 fan-out 제외 |
| [obra/superpowers](https://github.com/obra/superpowers) · cross-tool skills | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | README, .codex-plugin/plugin.json, references/codex-tools.md | 실제 도구 목록·lifecycle 구분·독립 review context 채택. 모델·effort 강제는 사용자 요구와 충돌해 제외 |
| [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow) · multi-agent orchestration | `e580bbc8204874f762d132fe441b18192979211b` | README | host integration 차이 명시만 채택. swarm framework·추가 runtime 제외 |
| [openai/plugins](https://github.com/openai/plugins) · 공식 plugin marketplace | `0722921d5542fc593105c27bd52630babd8b8c2a` | README, plugins/build-web-apps/.codex-plugin/plugin.json | 기존 manifest·공유 skills 유지. README의 agents 언급만으로 자동 custom-agent 등록을 단정하지 않음 |

## 검증 범위와 남은 제한

수정 전 독립 baseline에서 현재 schema에 없는 `agent_type`, 일반 기본값을 덮어쓰는 xhigh, 재개 도구 불일치를 확인했다. generator 기본값 테스트는 4건 실패한 뒤 수정 후 통과했다. 추가 memo·smoke 실패 테스트로 새 동작을 확인했고, 최종 reviewer가 찾은 memo 덮어쓰기와 증거 없는 smoke 성공 가능성을 재현한 뒤 수정했다.

현재 Codex 호스트에서 번들 QA 정의를 `task_name: pl_qa_runtime`, `fork_turns: none`으로 실제 실행해 `/root/pl_qa_runtime`을 받았다. 최종 응답 수신과 `followup_task` 재개를 각각 수행하고 memo CLI 원문 일치·이전 응답 보존·반복 저장 멱등성을 확인했다. model·effort override를 전달하지 않았다. 이 증거는 CLI JSONL 관측과 합산하지 않는다.

실제 Codex CLI 0.166.0의 hook·개인 agent 없는 격리 실행에서 alias와 본체 직접 호출 모두 구현·기존 unittest·memo·verify·close·사용자 fixture 보존 검사를 통과했다. 하지만 해당 CLI가 subagent 이벤트를 출력하지 않아 종합 결과는 `ARTIFACT PASS / HOST UNOBSERVABLE / INVALID`다. 실제 모델·effort 선택은 exec JSONL에서 직접 입증하지 못한다. 최초 네트워크 제한 시도는 `workspace routing discovery failed`로 INVALID였고, 네트워크 허용 후 다시 검증했다.

Claude 실제 S1 안전 E2E는 PASS다. commit·push 없는 케이스만 실행했으며 기존 fixture를 건드리지 않도록 임시 복사본을 사용했다. S3·S4 실제 세션은 사용자 요청의 범위에 맞춰 생략했다. 기존 E2E 판정 20개는 임시 fixture에서 통과했다.

skill-creator 원본 validator는 기존 Claude 확장 키(`hooks`, `user-invocable`, `argument-hint`, `disable-model-invocation`) 때문에 exit 1을 반환한다. 호환성 유지를 위해 키를 제거하지 않았다. 임시 사본에서 이 확장만 제외한 표준 skill 검사는 두 skill 모두 통과했고, 실제 Codex 로드와 Claude plugin validator도 별도로 확인했다. Claude validator의 아이콘 없음 경고는 이번 호환성 범위에서 수정하지 않았다. `PL_MACHINE_TESTS` 환경 의존 검사 1개는 opt-in이므로 건너뛴다.

## 최종 테스트 결과

| 실행 | 결과 |
|---|---|
| Python 3.9 `test_pl_config.py` | 21개, OK, opt-in 1개 skip |
| Python 3.9 `test_pl_history.py` | 63개, OK |
| Python 3.9 `test_hooks.py` | 6개, OK |
| Python 3.9 `test_memo.py` | 6개, OK |
| Python 3.11 `test_build_codex_agents.py` 및 generator `--check` | 14개 OK, 생성본 9개 drift 없음 |
| Python 3.11 전체 skill scripts `unittest discover` | 110개, OK, opt-in 1개 skip |
| Python 3.9 smoke 판정 `unittest discover -s tests/pl-codex` | 15개, OK |
| `tests/pl-guard/run-unit.sh` | PASS=136 FAIL=0 |
| `tests/pl-codex/run-install-unit.sh` | 26개 PASS, FAIL=0 |
| 기존 `tests/pl-e2e/run-unit.sh` 임시 복사본 | PASS=20 FAIL=0 |
| `shellcheck -S warning`, Python compile, `git diff --check` | 통과 |
| `claude plugin validate plugins/pl` | Validation passed, ICON_MISSING 경고 |
| Claude 실제 S1 임시 fixture | PASS, FAIL=0 INVALID=0 |
| Codex 실제 alias / 본체 직접 호출 | 둘 다 ARTIFACT PASS, HOST UNOBSERVABLE, INVALID(exit 2) |
| 현재 host의 PL QA spawn / followup / memo 저장 | 반환 ID·최종 응답 직접 확인, 원문 일치·이전 응답 보존·재저장 멱등성 PASS |
| 독립 최종 review | Gate 1·2 통과, 미해결 Critical/Important 없음 |

최종 전체 수집을 Python 3.9로 추가 시도했을 때 생성기 테스트의 기존 모듈 수준 `sys.exit(0)`가 unittest loader에서 오류가 됐다. 생성기와 그 테스트는 CONTRIBUTING에 명시된 Python 3.11 전용이므로 운영 코드를 넓혀 수정하지 않고, 지정 매트릭스와 Python 3.11 전체 수집으로 다시 확인했다. 해당 실패 출력은 다음과 같다.

```text
ERROR: test_build_codex_agents (unittest.loader._FailedTest)
ImportError: Failed to import test module: test_build_codex_agents
SystemExit: 0
Ran 97 tests in 6.216s
FAILED (errors=1, skipped=1)
skipped: build_codex_agents tests need Python 3.11+ (tomllib)
```

원본 skill validator는 처음 PyYAML 미설치로 `ModuleNotFoundError: No module named 'yaml'`를 반환했다. PyYAML을 새 임시 디렉터리에만 설치한 후 재실행한 출력은 아래와 같다. 표준 검사기의 허용 키 제한과 호스트 호환성 검증을 구분했다.

```text
pl original exit 1 Unexpected key(s) in SKILL.md frontmatter: argument-hint, disable-model-invocation, hooks. Allowed properties are: allowed-tools, description, license, metadata, name
team-pl-orchestrator original exit 1 Unexpected key(s) in SKILL.md frontmatter: hooks, user-invocable. Allowed properties are: allowed-tools, description, license, metadata, name
```

history 테스트가 출력한 unresolved placeholder 경고는 의도적으로 미완성 note를 검사하는 fixture의 예상 출력이다. 안전 E2E의 기존 저장소 fixture·사용자 개인 config는 변경하지 않았다. 임시 테스트 fixture 내부의 git 동작은 실제 작업 브랜치와 외부 원격에 영향을 주지 않는다.

원격 0.6.0 통합 직후에는 이전 upstream 테스트가 Codex effort 복사를 기대해 `KeyError: 'model_reasoning_effort'`로 실패했다. 외부 기본값을 존중하는 이번 요구에 맞춰 기대값을 갱신한 뒤 generator 14개와 전체 매트릭스를 재실행해 통과했다. 통합 리뷰에서도 역할 Markdown 9개가 `origin/main`과 완전히 동일함을 확인했고 새 Critical/Important는 없었다.

PR CI 첫 실행에서는 `ubuntu-latest`가 Ubuntu 26.04로 갱신되어 Python 3.9 설치 단계가 실패했다. 실제 출력은 `The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04.`였다. [공식 Python 배포 manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json)에서 3.9.25의 x64 Linux 지원 목록이 22.04·24.04임을 확인하고 Python 테스트 job만 `ubuntu-24.04`로 고정했다. Python 3.9~3.13 매트릭스는 축소하지 않았다.

## 변경 파일

- 진입점·공유 계약: `plugins/pl/skills/pl/SKILL.md`, `plugins/pl/skills/team-pl-orchestrator/SKILL.md`, 같은 디렉터리의 `references/roles.md`, `references/history.md`, `references/debate-protocol.md`.
- 구현·회귀: 같은 skill의 `scripts/pl_history.py`, `scripts/build_codex_agents.py`, `scripts/test_memo.py`, `scripts/test_pl_config.py`, `scripts/test_build_codex_agents.py`.
- Codex 실행·판정: `tests/pl-codex/run_smoke.py`, `tests/pl-codex/test_smoke.py`.
- packaging: `plugins/pl/.claude-plugin/plugin.json`, `plugins/pl/.codex-plugin/plugin.json`, `plugins/pl/hooks/hooks.codex.json`, `plugins/pl/install-codex.sh`.
- 생성물: `plugins/pl/agents/codex/team-pl-architect.toml`, `team-pl-backend-engineer.toml`, `team-pl-code-reviewer.toml`, `team-pl-data-engineer.toml`, `team-pl-frontend-engineer.toml`, `team-pl-integration-reviewer.toml`, `team-pl-product-analyst.toml`, `team-pl-qa-engineer.toml`, `team-pl-security-reviewer.toml`.
- CI·문서: `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `README.md`, `plugins/pl/README.md`, `tests/pl-e2e/README.md`, 구현 계획과 이 결정 기록.
