<div align="center">

# agent-plugins

**JeongSu의 개인 플러그인 마켓플레이스 — Claude Code · Codex CLI**

![marketplace](https://img.shields.io/badge/marketplace-zz1996zz-181717?logo=github)
![plugins](https://img.shields.io/badge/plugins-1-blue)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin%20marketplace-d97757)
![Codex CLI](https://img.shields.io/badge/Codex%20CLI-plugin%20marketplace-000000?logo=openai)
![license](https://img.shields.io/badge/license-MIT-green)

역할 에이전트의 토론·구현·검증과 결정 기록을 플러그인으로 배포합니다.
현재 제공하는 `pl`은 Claude Code와 Codex CLI를 지원합니다.

</div>

---

## 플러그인 목록

| 플러그인 | 설명 | 문서 |
|---|---|---|
| **[pl](plugins/pl/README.md)** | PL/테크리드 오케스트레이션 — 작업 규모에 맞게 역할 서브에이전트를 실행하고, 검증 결과와 결정을 레포의 `docs/pl/`에 기록 | [README](plugins/pl/README.md) |

## 설치

| 호스트 | 명령 |
|---|---|
| Claude Code 세션 | `/plugin marketplace add zz1996zz/agent-plugins` → `/plugin install pl@zz1996zz`에서 설치 확인 |
| Codex CLI 터미널 | `codex plugin marketplace add zz1996zz/agent-plugins` → `codex plugin add pl@zz1996zz` |

macOS/Linux, Python 3.9 이상, `git`이 필요합니다. Codex에서는 안전 훅을 사용하려면 세션의 `/hooks`에서 현재 hook 정의를 검토하고 신뢰해야 합니다. 개인 custom agent 설치는 선택 사항입니다. 자세한 요구사항과 호스트별 차이는 [pl 설치 안내](plugins/pl/README.md#설치)를 참조하세요.

설치 후 Claude Code에서는 `/pl:pl <기능 요청>`, Codex CLI에서는 `$pl <기능 요청>`으로 사용합니다. 작은 변경은 리드가 처리하고, 규모가 큰 작업은 역할별 분석·구현·리뷰를 거칩니다.

## 업데이트

Claude Code는 터미널에서 다음 명령을 실행합니다. 세션 안에서는 `/plugin`의 Installed 탭에서 Update now를 선택할 수도 있습니다.

```bash
claude plugin marketplace update zz1996zz
claude plugin update pl@zz1996zz
```

Codex CLI는 해당 마켓플레이스를 갱신한 뒤 플러그인을 다시 설치합니다. 아래 명령은 `codex-cli 0.166.0`에서 확인했습니다.

```bash
codex plugin marketplace upgrade zz1996zz
codex plugin remove pl@zz1996zz && codex plugin add pl@zz1996zz
```

- Claude Code의 타사 마켓플레이스는 자동 업데이트가 기본으로 꺼져 있습니다. 업데이트 후 새 세션을 시작하거나 `/reload-plugins`로 적용합니다. [공식 설치·업데이트 안내](https://code.claude.com/docs/en/plugins/install)
- Codex에서도 새 세션에서 갱신된 스킬을 확인하고, hook 정의가 바뀌어 재검토가 필요하면 `/hooks`에서 확인합니다. [공식 hook 신뢰 안내](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
- pl의 기록은 기본적으로 레포의 `docs/pl/`, 레포 밖에서는 `~/.local/share/pl/history/`에 저장됩니다. 플러그인 캐시와 분리되어 있습니다. Obsidian/Notion 연동은 현재 제공하지 않습니다.
- Claude Code에서 마지막 설치 범위를 제거하면 플러그인 데이터 디렉터리의 로컬 모드 설정(`config.json`)도 기본적으로 삭제됩니다. 보존하려면 `claude plugin uninstall pl@zz1996zz --keep-data`를 사용합니다. [삭제·보존 범위](https://code.claude.com/docs/en/plugins/cli-reference#what-an-uninstall-deletes-and-keeps)

## 레포 구조

```
agent-plugins/
├── .claude-plugin/marketplace.json   # 마켓플레이스 정의
├── .agents/plugins/marketplace.json  # Codex 마켓플레이스 정의
├── plugins/pl/                       # pl 플러그인 (스킬·역할 정의·훅·헬퍼)
├── docs/                            # 이 레포의 설계·결정 이력
└── tests/                            # 플러그인 행동 테스트 (배포물 아님)
```

`tests/`가 `plugins/` 밖에 있는 이유: 아래 version-guard가 `plugins/` 변경마다 버전 범프를 강제하므로, 테스트를 손볼 때마다 설치 캐시 버전이 실제 사용자 변경과 무관하게 올라갑니다. 테스트는 설치 사용자에게 배포될 필요도 없습니다.

- **[`tests/pl-e2e/`](tests/pl-e2e/README.md)** — pl의 안전 경계 행동 회귀. `run-unit.sh`는 판정 로직만 검증해 토큰이 필요 없고, `run-safety.sh`·`run-safety-codex.sh`는 실제 모델 세션을 돌려 Git 부작용으로 판정합니다. pl의 `SKILL.md`·`references/`·`agents/`를 고치면 머지 전에 실행합니다.
- **`tests/pl-guard/`** — pl 안전 훅(`plugins/pl/hooks/guard.py`)의 deny/allow 매트릭스. 페이로드를 직접 주입하므로 토큰이 필요 없고 CI에서 돕니다.
- **`tests/pl-codex/`** — Codex 설치 테스트와 격리된 실제 역할·memo·verify·close smoke. 모델 없는 판정 테스트도 포함합니다.

## 배포 수칙 (관리자)

- **`plugins/` 아래를 변경하면 해당 플러그인의 `version`을 반드시 범프**합니다 — README를 포함한 배포 디렉터리 변경이 대상입니다. 루트 문서나 `tests/`만 고치면 이 조건에 해당하지 않습니다. 설치 캐시가 버전 키라서, 버전이 같으면 콘텐츠가 바뀌어도 사용자에게 전파되지 않습니다(실측).
- 버전 범프 시 해당 플러그인 README의 버전 배지도 함께 갱신합니다.
- `.claude-plugin/plugin.json`과 `.codex-plugin/plugin.json`의 `version`을 함께 범프합니다 (CI가 불일치를 막습니다).
- `agents/team-pl-*.md`나 `references/roles.md`의 preamble 블록을 고쳤으면 `build_codex_agents.py`로 `agents/codex/`를 재생성해 함께 커밋합니다 (CI `--check`).
- 테스트 매트릭스와 운영 모델 변경 수칙은 [`CONTRIBUTING.md`](CONTRIBUTING.md).
- 커밋·문서는 한국어, Conventional Commits를 따릅니다.
