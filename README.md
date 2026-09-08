<div align="center">

# agent-plugins

**JeongSu의 개인 플러그인 마켓플레이스 — Claude Code · Codex CLI**

![marketplace](https://img.shields.io/badge/marketplace-zz1996zz-181717?logo=github)
![plugins](https://img.shields.io/badge/plugins-1-blue)
![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin%20marketplace-d97757)
![Codex CLI](https://img.shields.io/badge/Codex%20CLI-plugin%20marketplace-000000?logo=openai)
![license](https://img.shields.io/badge/license-MIT-green)

팀 워크플로우를 플러그인으로 패키징해 배포합니다.
설치 두 커맨드면 어느 PC에서든 같은 환경이 됩니다.

</div>

---

## 플러그인 목록

| 플러그인 | 설명 | 문서 |
|---|---|---|
| **[pl](plugins/pl/README.md)** | PL/테크리드 팀 오케스트레이션 — 역할 에이전트 토론·구현·검증, Obsidian/Notion 선택형 메모리 | [README](plugins/pl/README.md) |

## 설치

| 호스트 | 명령 |
|---|---|
| Claude Code | `/plugin marketplace add zz1996zz/agent-plugins` → `/plugin install <플러그인 이름>@zz1996zz` |
| Codex CLI | `codex plugin marketplace add zz1996zz/agent-plugins` → `codex plugin add <플러그인 이름>@zz1996zz` → 플러그인 README의 추가 단계 |

각 플러그인의 사용법·요구사항은 해당 플러그인 README를 참조하세요.

## 업데이트

```
/plugin marketplace update zz1996zz
/plugin update <플러그인 이름>@zz1996zz
```

Codex CLI: `codex plugin marketplace upgrade` → `codex plugin remove pl@zz1996zz && codex plugin add pl@zz1996zz` (Codex에는 `plugin update` 커맨드가 없어 remove+add로 갱신합니다).

- 사설 마켓플레이스는 자동 업데이트가 기본으로 꺼져 있습니다 — 위 두 커맨드로 직접 당겨옵니다.
- **⚠️ `plugin uninstall` 주의**: 플러그인의 사용자 데이터 디렉토리(`~/.claude/plugins/data/<플러그인>-zz1996zz/` — 설정·대기 큐)가 함께 삭제됩니다(실측). 갱신은 반드시 위의 update 경로로 하고, 부득이 uninstall 할 때는 데이터 디렉토리를 먼저 백업하세요.

## 레포 구조

```
agent-plugins/
├── .claude-plugin/marketplace.json   # 마켓플레이스 정의
├── .agents/plugins/marketplace.json  # Codex 마켓플레이스 정의
├── plugins/<이름>/                    # 각 플러그인 (자체 README 포함)
└── tests/                            # 플러그인 행동 테스트 (배포물 아님)
```

`tests/`가 `plugins/` 밖에 있는 이유: 아래 version-guard가 `plugins/` 변경마다 버전 범프를 강제하므로, 테스트를 손볼 때마다 설치 캐시 버전이 실제 사용자 변경과 무관하게 올라갑니다. 테스트는 설치 사용자에게 배포될 필요도 없습니다.

- **[`tests/pl-e2e/`](tests/pl-e2e/README.md)** — pl의 안전 경계 행동 회귀. `run-unit.sh`는 판정 로직만 검증해 토큰이 필요 없고, `run-safety.sh`는 실제 `claude -p` 세션을 돌려 git 부작용으로 판정합니다. pl의 `SKILL.md`·`references/`·`agents/`를 고치면 커밋 전에 돌립니다.
- **`tests/pl-guard/`** — pl 안전 훅(`plugins/pl/hooks/guard.sh`)의 deny/allow 매트릭스. 페이로드를 직접 주입하므로 토큰이 필요 없고 CI에서 돕니다.
- **`tests/pl-codex/`** — Codex CLI 설치 스크립트(`install-codex.sh`)의 단위 테스트. 실제 Codex 세션 없이 설치 로직만 검증합니다.

## 배포 수칙 (관리자)

- **배포(push) 전 `plugin.json`의 `version`을 반드시 범프**합니다 — 설치 캐시가 버전 키라서, 버전이 같으면 콘텐츠가 바뀌어도 사용자에게 전파되지 않습니다(실측).
- 버전 범프 시 해당 플러그인 README의 버전 배지도 함께 갱신합니다.
- `.claude-plugin/plugin.json`과 `.codex-plugin/plugin.json`의 `version`을 함께 범프합니다 (CI가 불일치를 막습니다).
- `agents/team-pl-*.md`를 고쳤으면 `build_codex_agents.py`로 `agents/codex/`를 재생성해 함께 커밋합니다 (CI `--check`).
- 커밋·문서는 한국어, Conventional Commits를 따릅니다.
