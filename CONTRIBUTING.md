# 기여 안내

이 레포의 관리자·기여자용 지침입니다. 에이전트의 런타임 프롬프트로 로드되지 않으며, pl 자체를 개선하거나 점검할 때 참고합니다. 사용·설치는 [루트 README](README.md)와 [pl README](plugins/pl/README.md)를 참조하세요.

## 테스트 매트릭스

`plugins/pl/` 아래를 변경하면 다음 검사를 실행합니다. 일반 테스트·훅은 Python 3.9 이상을 지원하며, Codex 역할 생성기와 생성기 테스트만 Python 3.11 이상이 필요합니다.

```bash
S=plugins/pl/skills/team-pl-orchestrator/scripts
python3 "$S/test_pl_config.py"              # 프롬프트 불변식·manifest·hook
python3 "$S/test_pl_history.py"             # history 헬퍼 동작(git 필요)
python3 "$S/test_hooks.py"                  # memo_capture hook
python3 "$S/test_memo.py"                   # hook 없는 lead memo 저장
python3 -m unittest discover -s tests/pl-codex -p 'test_*.py'
python3.11 "$S/test_build_codex_agents.py"   # 생성기 테스트(tomllib 필요)
python3.11 "$S/build_codex_agents.py" --check
bash tests/pl-guard/run-unit.sh             # 안전 훅 deny/allow 매트릭스
bash tests/pl-e2e/run-unit.sh                # E2E 판정 로직(모델 불필요)
bash tests/pl-codex/run-install-unit.sh     # 선택 설치 스크립트
shellcheck -S warning plugins/pl/install-codex.sh tests/pl-guard/run-unit.sh tests/pl-e2e/*.sh tests/pl-codex/*.sh
claude plugin validate plugins/pl
claude plugin validate .
git diff --check
```

CI는 Python 3.9~3.13, Linux·macOS의 셸 하네스, manifest·생성 파일·버전 증가를 검사합니다. 셸 스크립트는 macOS의 bash 3.2에서도 실행되어야 합니다. `claude plugin validate` 작업은 현재 CI에서 `continue-on-error`로 설정되어 있으므로, CI 전체 상태뿐 아니라 해당 작업의 결과도 확인합니다. 실행할 수 없거나 건너뛴 검사는 이유를 보고합니다.

### 실제 세션 검사

`SKILL.md`·`references/`·`agents/`처럼 모델이 읽는 실행 프롬프트를 변경하면 머지 전에 실제 세션 안전 E2E를 실행합니다. 토큰과 로그인된 CLI가 필요합니다.

```bash
bash tests/pl-e2e/run-safety.sh
# Codex CLI가 설치되어 있으면 함께 실행
PL_E2E_CODEX_AUTH=copy bash tests/pl-e2e/run-safety-codex.sh
```

Codex 역할 실행·history 경로를 변경하면 `python3 tests/pl-codex/run_smoke.py`와 `python3 tests/pl-codex/run_smoke.py --entry team-pl-orchestrator`도 실행합니다. 이 smoke는 임시 레포·`CODEX_HOME`에서 개인 custom agent 설치와 hook 없이 실제 역할 응답·memo·verify·close를 확인합니다.

README·이 문서·GitHub 설명만 바꾸고 실행 프롬프트와 코드가 그대로라면 실제 모델 세션을 반복 실행할 필요는 없습니다. 링크·명령·manifest 일관성과 관련 CI를 확인합니다. 기존 안전 러너는 `tests/pl-e2e/fixtures/`를 재생성하므로 그 아래 보존할 작업을 두지 않습니다. 격리 범위와 `PASS`/`FAIL`/`INVALID`의 의미는 [E2E 안내](tests/pl-e2e/README.md)를 참조하세요.

## 버전·생성 파일·설명 동기화

- `plugins/` 아래를 변경하면 `plugins/pl/.claude-plugin/plugin.json`과 `plugins/pl/.codex-plugin/plugin.json`의 `version`을 함께 올립니다. 플러그인 README도 배포 디렉터리에 있으므로 대상입니다. 루트 문서·`tests/`만 바꾸면 버전 증가는 필요하지 않습니다.
- `plugins/pl/README.md`의 버전 배지도 맞춥니다.
- 두 plugin manifest와 두 marketplace의 **pl 항목** 설명을 동일하게 유지합니다. marketplace 자체의 설명은 플러그인 목록 전체를 소개하는 별도 필드입니다.
- `agents/team-pl-*.md` 또는 `references/roles.md`의 shared preamble을 변경하면 `python3.11 "$S/build_codex_agents.py"`로 TOML을 재생성하고 함께 커밋합니다. 개인 설치본은 자동으로 덮어쓰지 않습니다.
- GitHub About 설명·토픽과 사용자 README는 현재 지원 호스트·기록 방식을 반영합니다. 과거 설계·결정 노트는 당시 맥락을 보존하며, 현재 사용법은 README에서 안내합니다.
- 커밋·문서는 한국어로 작성하고 Conventional Commits를 따릅니다.

## 운영 모델 변경

작업 규모 판정, 역할 실행, 토론, 검증 또는 기록 방식을 실질적으로 변경하기 전에는 현재 공식 문서와 공개 사례를 비교합니다. 단순한 문서 정정에 이 절차를 적용하지 않습니다.

1. Claude Code의 subagents·skills·hooks·plugins와 Codex의 subagents·hooks·config 공식 문서를 확인합니다. 검색 요약이나 과거 실측과 현재 문서가 다르면 현재 도구 schema·문서와 다시 대조합니다.
2. 다음 범주 중 최소 5개에서 공개 레포 8개 이상을 검토합니다: 공식 예제, subagent 카탈로그, 슬래시 명령 워크플로우, skill/plugin marketplace, 실제 프로젝트, multi-agent orchestration, cross-tool skill, Codex multi-agent 설정.
3. 역할 선택 정확도, 수명 주기, 모델·도구 비용, 병렬 편집 안전성, 검증, 결정 기록, 명령 사용성을 구체적으로 개선하는 패턴만 채택합니다. 이점 없이 토큰·조정·권한 비용을 늘리는 방식은 제외합니다.
4. 방대한 역할 목록, 기존 스킬과 중복되는 명령, 일반 코딩마다 강제하는 외부 조사, 읽기 전용 역할의 광범위한 쓰기 권한, 수작업 생성 상태, 제거된 도구, 레포 정의와 충돌하는 일반 agent 이름은 도입하지 않습니다.
5. 조사 URL·커밋 SHA·날짜·채택 및 제외 이유를 `docs/pl/decisions/`의 결정 노트에 남깁니다.

## 구현 기준과 확인 출처

- 기록은 기본적으로 작업트리의 `docs/pl/`에 저장하고, 레포 밖에서는 로컬 history 경로를 사용합니다. Obsidian/Notion backend는 현재 제공하지 않습니다. 위치·명령의 기준은 `pl_history.py`와 [`references/history.md`](plugins/pl/skills/team-pl-orchestrator/references/history.md)입니다.
- Claude Code는 번들 역할 정의의 `tools`·`model`·`effort`를 사용합니다. 역할에 고정 턴 상한을 설정하지 않으며, 같은 역할도 독립 scope별로 여러 세션을 실행할 수 있습니다. Codex는 실제 도구 schema에 맞춰 역할 본문을 전달하거나 지원되는 custom type을 사용하며, 모델·effort는 외부 config에 맡깁니다. 정확한 호스트별 계약은 [`SKILL.md`](plugins/pl/skills/team-pl-orchestrator/SKILL.md)의 Platform Behavior를 참조합니다.
- Codex plugin hook은 설치만으로 신뢰되지 않습니다. `/hooks`에서 현재 정의를 검토해야 실행됩니다. 신뢰·미지원·실행 실패와 무관하게 완료 기록은 lead가 직접 수행하도록 설계되어 있습니다. [공식 hooks](https://learn.chatgpt.com/docs/hooks), [공식 subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- 설치·업데이트 명령은 2026-11-02에 Claude Code 2.1.316과 Codex CLI 0.166.0의 `--help` 및 공식 문서로 확인했습니다. 이 버전은 확인 환경이며 지원 최소 버전을 뜻하지 않습니다. [Claude Code 설치·관리](https://code.claude.com/docs/en/plugins/install), [Codex plugins](https://learn.chatgpt.com/docs/plugins)
