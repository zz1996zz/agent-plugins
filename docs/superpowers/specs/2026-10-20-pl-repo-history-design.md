# pl 0.5.0 — 레포 내 히스토리 저장, 서브에이전트 전환, 운영 개선 설계

작성일: 2026-10-20
대상: `plugins/pl` (Claude Code · Codex CLI 양쪽 호스트)

## 1. 의도

pl은 지금 기능 노트·결정 기록·실행 원장을 사용자가 고른 Obsidian vault 또는 Notion에 쓴다. 사용자 판단은 "굳이 외부 도구에 둘 필요가 없다"는 것이다.

- 레포에서 작업하면 히스토리는 **레포 안(`docs/` 아래)에 저장하고 git에 커밋**해 팀이 공유한다. 결정 기록이 코드와 같은 PR로 리뷰되고 브랜치를 따라 움직인다.
- 저장 위치는 **팀 단위로** 정한다. 팀마다 "히스토리는 여기서 관리한다"는 위치가 있으며, 그것은 레포에 커밋된 설정으로 표현된다.
- 레포 밖에서 작업할 때는 pl 전용 로컬 폴더에 저장하고, 사용자가 그 위치를 옮길 수 있다.
- 커밋되는 기록에는 **역할별로 어떤 의견을 냈고 토론이 어떻게 흘렀는지**가 남아야 한다(결정과 결과만으로는 부족하다).

같은 릴리스에서 내부 검토와 외부 사례 조사로 찾은 개선점도 함께 반영한다(사용자 지시: "한번에 해라"). 이후 세 갈래 감사(프롬프트 정합성 / 스크립트·훅·테스트 / 공식 문서 대조, 2026-10-20)로 찾은 항목은 §16 이후에 있다. **§16(서브에이전트 전환)은 §15 이전 절의 teammate 전제를 덮어쓴다** — 충돌하면 §16이 우선.

## 2. 목표 / 비목표 / 반목표

목표
- G1. 히스토리 백엔드를 "레포 내 markdown"(기본) + "레포 밖 로컬 폴더"(대체) 하나의 파일 기반 구현으로 통일한다.
- G2. 위치는 팀 설정 파일 `.agents/pl.md`의 `historyDir`로 정하고, 없으면 `docs/pl`.
- G3. 커밋 기록(역할 의견·토론·결정·검증·결과)과 진행 중 런타임 상태(실행 원장·세션 생명주기 세부·검증 증거)를 분리한다. 런타임 상태는 git에서 제외한다.
- G4. 병렬 브랜치에서 머지 충돌이 나는 공용 파일을 만들지 않는다.
- G5. 첫 실행 온보딩 질문을 없앤다.
- G6. "fresh 검증 없이 done 금지"를 문서 규칙에서 기계적 검사로 끌어올리고, 리뷰-수정 반복에 상한을 둔다.

비목표
- Notion 지원 유지. Notion 어댑터는 제거한다.
- 기존 Obsidian vault·Notion 내용의 자동 이전. README에 수동 복사 방법만 적는다. (빌더 판단 아님 — 설계자 결정)
- pl이 히스토리 파일을 직접 커밋하는 것. 기존 안전 경계 그대로: pl은 파일만 쓰고 커밋은 사용자가 코드와 함께 한다.

반목표 (기술적으로 동작해도 실패로 본다)
- 커밋된 히스토리에 비밀값·자격증명·원문 대화록·무제한 명령 출력이 들어감.
- 런타임 상태(세션 spawn/강제종료 로그, 태스크 표)가 커밋되어 PR 잡음이 됨.
- 두 브랜치가 동시에 pl을 돌렸을 때 히스토리 파일끼리 머지 충돌.
- 개인 설정이 팀 위치를 덮어써 같은 레포의 기록이 여러 곳에 흩어짐.

## 3. 저장 위치 해석

리드는 intake 단계에서 헬퍼로 히스토리 루트를 해석한다(§6 `where`).

1. 현재 디렉터리가 git 작업 트리이면 **레포 모드**.
   - 루트 = `<작업트리 루트>/<historyDir>`. 작업트리 루트는 `git rev-parse --show-toplevel`(현재 worktree 기준 — 기록은 그 브랜치에 커밋되어야 하므로 main worktree가 아니다).
   - `historyDir`는 `.agents/pl.md` frontmatter 값, 없으면 `docs/pl`.
   - `historyDir`는 레포 루트 기준 상대경로만 허용. 절대경로, `..`로 레포 밖으로 나가는 경로, `.git/` 아래 경로는 거부하고 이유를 출력한다.
   - 개인 설정(`pl.local.md`)의 `historyDir`는 무시하고 한 번 경고한다.
2. git 작업 트리가 아니면 **로컬 모드**.
   - 루트 = `<historyRoot>/<work-slug>`.
   - `historyRoot` 기본값 `${XDG_DATA_HOME:-~/.local/share}/pl/history`. 사용자 설정 `<data-dir>/config.json`의 `{"historyRoot": "<절대경로>"}`로 옮길 수 있다.
   - `<data-dir>`(`CLAUDE_PLUGIN_DATA`)를 기본값으로 쓰지 않는 이유: 공식 문서상 플러그인을 마지막 설치 위치에서 제거하면 이 폴더가 삭제된다(`--keep-data` 예외). 오래 남아야 하는 히스토리에 맞지 않는다. 사용자가 원래 말한 "pl 전용 폴더"의 의도는 유지하되 위치만 안정적인 곳으로 정한 설계자 판단이다.
   - `work-slug` 결정 규칙은 기존과 같다(요청에 명시된 이름 > `inbox` + 사유 기록). 레포 밖이므로 레포명 규칙은 적용되지 않는다.
   - `config.json` 자체가 플러그인 제거로 지워지면 기본값으로 돌아갈 뿐이며, 이는 허용한다.

레포 모드에는 `work/<slug>/` 계층이 없다. 레포 하나가 곧 작업 하나다. 따라서 `workNamespace` 설정은 레포 모드에서 의미가 없어지며 제거한다(로컬 모드는 요청에서 이름을 받는다).

## 4. 디렉터리 구조

```text
<history-root>/                         # 레포 모드: <repo>/docs/pl
  features/
    YYYY-MM-DD-<feature-slug>.md        # 커밋
  decisions/
    YYYY-MM-DD-<decision-slug>.md       # 커밋
  architecture.md                       # 커밋 (기존 architecture/README.md 대체)
  .runtime/                             # git 제외
    .gitignore                          # 내용: "*"  (자기 자신 포함 전체 무시)
    <feature-slug>/
      ledger.md                         # 실행 원장 + 세션 생명주기 세부
      evidence.jsonl                    # 검증 증거 (§7)
```

- **INDEX 파일 없음.** 기존 루트·work `INDEX.md`는 기능마다 갱신되어 병렬 브랜치에서 충돌한다(외부 사례: conductor `tracks.md` 이슈 #34·#55). 목록은 frontmatter를 읽어 필요할 때 출력한다(§6 `list`).
- 파일명은 기존 `날짜-슬러그` 유지. 일련번호는 병렬 PR에서 충돌한다(adr-tools #102, spec-kit 두 차례 수정). 같은 날 같은 슬러그 충돌은 기존 헬퍼처럼 거부한다.
- `.runtime/.gitignore`(`*`)는 헬퍼가 루트를 처음 만들 때 생성한다. 레포의 최상위 `.gitignore`는 건드리지 않는다.
- `.runtime/`은 `.git/` 아래가 아니다. Claude Code는 `.git/`을 보호 경로로 다룬다.

## 5. 노트 내용

공통: YAML frontmatter가 유일한 기계 판독 표면이다. 기능 노트의 `status`는 frontmatter **한 곳에만** 적는다(기존 Completion 섹션의 `Status:` 중복과 "두 값이 다르면 미완성" 규칙은 제거). 허용값은 기존과 같다: `in-progress`, `done`, `done-with-risks`, `blocked`.

### 5.1 기능 노트 (커밋)

```markdown
---
type: Feature
title: "<name>"
status: in-progress
date: YYYY-MM-DD
owner: PL agent
repo: "<canonical repo name>"
decisions: []            # 결정 노트 상대경로 목록
---

# Feature: <name>

## Request
## Scope            (In / Out)
## Roles and Opinions
### <role> (<runtime-name>)
- Position:
- Key evidence:      (레포 경로 인용)
- Recommendation:
- Open questions:
(역할마다 반복. 참여하지 않은 역할은 쓰지 않는다. lead role pass는 `(lead pass — <사유>)`로 표기)
## Synthesis        (Agreements / Conflicts / Hidden assumptions / Unverifiable statically)
## Challenges       (challenger -> recipient: 주장, 응답, 결정에 미친 영향 | `skipped — no material conflict in synthesis`)
## PL Decisions     (결정 한 줄 + 기각한 대안 한 줄씩; 상세는 decisions/ 노트)
## Implementation Summary
## Changed Files
## Verification     (헬퍼가 채움: 명령, exit, 시각, 철회 내역, `fresh at close` 도장 — §7·§8.2)
## Review           (cycle N: Gate 1 / Gate 2 결과, 미해결 finding)
## Completion
- Team: <N> role sessions; <완료 N / 부분(maxTurns) N / 실패 N / not spawned N>
- Residual risk:
## Open Questions
```

- 역할 의견은 **요약**이다. 원문 메모를 붙이지 않는다(기존 Memory Hygiene 유지).
- `Roles and Opinions`에 이름을 적는 조건은 기존 Role Session Evidence 규칙 그대로다: 세션 식별자 + 전달된 텍스트가 있어야 한다.
- 기존 `Relevant Memory`, `Implementation Plan`, `Team Lifecycle`, `Execution Ledger`, `Discussion Summary/Round 1/Round 2` 섹션은 위 구조로 재편되거나 런타임으로 이동한다.

### 5.2 결정 노트 (커밋)

기존 템플릿 유지(Context / Options Considered / Decision / Rationale / Consequences / Validation / Open Questions). frontmatter에 `feature:`(기능 노트 상대경로), `supersedes:`, `superseded_by:`를 둔다. 대체될 때 삭제하지 않고 `status: superseded`로 바꾼다. 본문의 `Related feature:` 등 링크 줄은 frontmatter로 옮긴다.

### 5.3 런타임 원장 (`.runtime/<feature-slug>/ledger.md`, 커밋 안 함)

- Execution Ledger 표 (Task / Owner / Depends on / Deliverable / Status / Evidence)
- Team Lifecycle 세부 (Spawned / Reused / Replaced / Shut down / Force-stopped / Unconfirmed stop / Role sandbox)
- 압축·세션 중단 후 복구의 기준. 기존 "feature note is the recovery ledger" 역할을 이 파일이 맡는다.

### 5.4 architecture.md (커밋)

기존 Architecture Note 템플릿을 그대로 쓴다. 루트 생성 시 없으면 만든다.

## 6. 헬퍼

`memory_note.py`와 `pl_user_config.py`를 `scripts/pl_history.py` 하나로 대체한다. 표준 라이브러리만 사용(Python 3.11, 기존 CI 조건 유지). 서브커맨드:

| 명령 | 동작 |
|---|---|
| `where [--config <path>] [--work <slug>]` | §3 규칙으로 모드·루트를 해석해 JSON 출력. 루트가 없으면 구조(§4)와 `.runtime/.gitignore`, `architecture.md`를 만든다 |
| `feature "<title>" [--request ...]` | 기능 노트 생성(§5.1) + `.runtime/<slug>/ledger.md` 생성 |
| `decision "<title>" --feature <path>` | 결정 노트 생성, 기능 노트 frontmatter `decisions`에 추가 |
| `list [--status ...]` | features/decisions frontmatter를 읽어 날짜·status·title 표 출력. INDEX 대체 |
| `verify --feature <slug> -- <cmd...>` | 명령 실행, 증거 기록(§7), 기능 노트 Verification 섹션 갱신 |
| `verify --feature <slug> --withdraw "<cmd>" --reason "<why>"` | 잘못 고른 명령을 필수 집합에서 뺀다. 철회 사실과 사유가 증거와 노트에 남는다 |
| `close --feature <slug> --status <status>` | 마감 검사(§8.2) 통과 시에만 frontmatter `status`를 쓰고 Verification에 `fresh at close` 도장을 찍는다 |
| `check [--feature <slug>]` | 구조 무결성 검사(§8.1), 읽기 전용 |

- 공통 옵션 `--root`로 해석 결과를 덮어쓸 수 있다(테스트·디버그용).
- 기존 헬퍼의 원자적 쓰기, 잠금, 슬러그 규칙, YAML 인용, 상태 어휘 검증, 링크 검증, 코드 스팬 제외 등 이미 검증된 로직은 재사용한다(파일 이동 + 축소). 테스트 자산(`test_memory_note.py`)도 해당 부분은 옮겨 살린다.
- `repair`(vault 탐색), `pending/` 재전송, INDEX 동기화, `work/` 계층 처리는 삭제한다.

## 7. 검증 증거 (G6)

`pl_history.py verify --feature <slug> -- <cmd...>`:

1. 명령을 실행하고 한 줄 JSON을 `.runtime/<slug>/evidence.jsonl`에 추가한다: 명령 문자열(`shlex.join(argv)` — 이것이 명령의 동일성 키), exit code, 시작/종료 시각, 출력 마지막 40줄, 실행 전 지문, **실행 후 지문**.
2. **작업 트리 지문** = `HEAD` 커밋 + `git diff HEAD` + untracked·non-ignored 파일(`git ls-files --others --exclude-standard`) 경로·내용의 해시. **히스토리 루트 아래 경로는 제외**한다(노트 갱신이 검증을 stale로 만들지 않도록). gitignore된 빌드 산출물은 원래 포함되지 않는다.
3. 신선도의 기준은 **실행 후 지문**이다. 명령이 커버리지 파일 같은 untracked 산출물을 남겨도 그 상태가 기준이 되므로 곧바로 stale이 되지 않는다. 실행 전·후 지문이 다르면 노트에 `command modified the working tree`를 한 줄 남긴다(정보, 실패 아님).
4. 커밋되는 기능 노트 Verification 섹션에는 명령, exit, 실행 시각만 적는다. 출력 원문은 커밋하지 않는다. `fresh` 값은 여기서 쓰지 않는다 — `close`가 마감 시점에 한 번 도장을 찍는다(§8.2).

**필수 명령 집합** (마감 검사가 강제하는 대상):
- 이 기능에서 `verify`로 한 번이라도 실행한 모든 명령(정확한 문자열 기준) ∪ `verifyCommands`(팀 `.agents/pl.md` ∪ 개인 `pl.local.md`).
- 각 명령은 **가장 최근 실행**만 본다.
- 관련 없는 명령을 잘못 돌렸으면 `verify --withdraw "<cmd>" --reason "<why>"`로 집합에서 뺀다. 철회는 증거와 커밋 노트 양쪽에 사유와 함께 남는다. `verifyCommands`에 있는 명령은 철회할 수 없다.
- 헬퍼는 `.agents/pl.md`·`pl.local.md` frontmatter의 단순 스칼라와 `- item` 목록만 파싱한다(표준 라이브러리 유지). 그 이상의 YAML은 지원하지 않고 경고한다.

**누가 실행하는가:** `verify`는 **리드만** 실행한다. role session 브리프에는 "`pl_history.py`를 실행하지 말라"를 명시한다(roles.md Role Prompt Contract에 추가). role session의 `Run:` 결과는 기존처럼 그 role의 자기 점검일 뿐 증거가 아니다. 증거 레코드에는 실행 주체 필드를 두지 않는다 — 리드만 실행한다는 규칙과 §7.1 훅 범위 축소로 충분하다고 본다.

로컬 모드(레포 밖)에서는 지문을 계산할 수 없으므로 지문 필드를 비워 두고, 마감 검사는 신선도를 `unknown`으로 처리한다. `done`을 막지 않되 Completion에 근거 부족을 한 줄 적게 한다.

### 7.1 TaskCompleted 게이트 (Claude Code 전용, 보조)

orchestrator `SKILL.md` frontmatter `hooks`에 `TaskCompleted` 훅을 추가한다(플러그인 `hooks.json`이 아니다 — §15).

- 대상: subject가 정확히 `[<feature-slug>] verify`인 태스크 **하나**뿐이다. 이 태스크는 리드가 Workflow 7단계(Verify) 시작 때 만들고 리드가 소유한다. role session이 소유한 태스크의 `Run:` 줄은 훅 대상이 아니다. 그래서 teammate가 리드의 검증을 기다리며 막히는 일이 없다.
- 추가 조건: 현재 레포에 `<history-root>/.runtime/<feature-slug>/`가 있을 때만. 그 외 모든 태스크는 즉시 통과(플러그인 훅은 pl과 무관한 세션에서도 실행되므로).
- 판정: §8.2 마감 검사의 증거 부분(`pl_history.py check --feature <slug> --evidence-only`)을 호출해 통과하면 exit 0, 아니면 exit 2 + stderr로 실패한 명령과 다시 돌릴 `verify` 명령을 알려준다.
- 내부 오류(jq·python 부재, 파싱 실패)는 통과(fail-open). `guard.sh`와 같은 원칙.
- **빌더 확인 사항:** TaskCompleted 훅 입력에 태스크 subject가 실제로 들어오는지 공식 hooks 문서와 실측으로 확인한다. 들어오지 않으면 이 훅은 넣지 않고 그 사실을 PR 설명과 README에 적는다. 이 경우에도 §8.2 `close`가 같은 규칙을 양 호스트에서 강제한다.
- Codex에는 대응 이벤트가 없다. Codex에서는 `close`가 유일한 기계 검사다.

## 8. 검사 규칙

### 8.1 `check` — 구조 무결성 (읽기 전용, 언제든)

히스토리 루트 전체(또는 `--feature`로 한 기능)를 검사하고 문제를 한 줄씩 출력, 있으면 exit 1. 파일을 고치지 않는다. CI나 다른 클론에서 돌려도 같은 결과가 나와야 하므로 **런타임 증거·신선도는 보지 않는다.**

- 링크 대상 존재(본문 링크 + frontmatter `decisions`/`feature`/`supersedes`/`superseded_by` 경로).
- 상태 어휘. 기능 노트는 frontmatter `status` 필수.
- `in-progress`가 아닌 노트의 미해결 placeholder(`<a | b>` 형태).
- `done`과 세션 생명주기 모순: 커밋 노트 Completion의 `Team:` 줄을 기존 `DONE_FORBIDDEN_LIFECYCLE_PHRASES` 로직으로 검사.
- `done` 기능 노트는 Verification에 명령이 1개 이상 있고 `fresh at close: yes`(또는 로컬 모드의 `unknown`) 도장이 있어야 한다.

이미 닫힌 기능이 이후 코드 변경으로 "stale"해지는 일은 없다. 신선도는 마감 시점에 한 번 판정되어 도장으로 고정되기 때문이다.

### 8.2 `close` — 마감 검사 (리드가 마감할 때 한 번)

`close --feature <slug> --status <status>`:

1. 해당 기능에 §8.1 검사를 돌린다(도장 조건 제외).
2. `--status done`이면 추가로:
   - 필수 명령 집합(§7)의 각 명령이 가장 최근 실행에서 exit 0.
   - 각 명령의 실행 후 지문 == 현재 지문(최종 코드 변경 뒤에 검증했는가).
   - 런타임 원장 Team Lifecycle 세부에 `done` 금지 문구가 없음(기존 로직).
3. 통과하면 frontmatter `status`를 쓰고 Verification에 `fresh at close: yes`를 기록한다. `done`이 실패하면 아무것도 쓰지 않고 이유를 출력한다. 리드는 원인을 고치거나 `done-with-risks`로 마감한다.
4. `done-with-risks`·`blocked`는 증거 조건 없이 기록되지만, 실패·stale 명령 목록을 Verification에 자동으로 남긴다.

리드는 노트 frontmatter `status`를 손으로 고치지 않는다. 마감은 반드시 `close`로 한다(SKILL.md Workflow 9단계에 명시).

## 9. 리뷰 반복 상한

`references/debate-protocol.md` Review Loop에 추가:

- 리뷰 → 수정 → 재리뷰를 **최대 3 cycle**까지 한다. 각 cycle은 기능 노트 `## Review`에 `cycle N`으로 기록한다.
- 3번째 cycle 후에도 Critical/Important finding이 남으면 더 고치지 않고 멈춘다. 남은 finding을 기록하고, 구현이 동작하면 `done-with-risks`, 안전하지 않으면 `blocked`로 닫고 사용자에게 판단을 넘긴다.
- Minor만 남은 경우는 상한과 무관하게 기록 후 진행(기존 규칙).

## 10. 설정 파일

| 파일 | 소유 | 커밋 | 키 |
|---|---|---|---|
| `.agents/pl.md` (신규) | 팀 | 예 | `historyDir`, `verifyCommands`, `protectedPaths` |
| `.agents/pl.local.md` (기존, 우선) / `.claude/pl.local.md` (레거시) | 개인 | 아니오(권장) | `verifyCommands`, `protectedPaths` — 팀 값에 **추가(합집합)**만 가능, 제거 불가 |
| `<data-dir>/config.json` | 개인 | — | `historyRoot` (로컬 모드 전용) |

- `verifyCommands`·`protectedPaths`는 성격상 팀이 공유하는 값이라 팀 파일로 옮긴다. 개인 파일에 있던 기존 사용자는 그대로 동작한다(합집합).
- `workNamespace`는 제거(§3). 개인 파일에 남아 있으면 무시하고 한 번 알린다.
- 리드는 두 파일 모두 **읽기만** 한다. 만들거나 고치지 않는다(기존 규칙 확장). `.agents/pl.md`가 없으면 기본값으로 동작하며 만들자고 권하지도 않는다. README에 예시를 둔다.
- 알 수 없는 키는 무시.

## 11. 문서·프롬프트 변경 범위

- `skills/team-pl-orchestrator/SKILL.md`
  - description: "user-selected memory backend (Obsidian vault or Notion)" → 레포 내 히스토리.
  - `## Memory` 섹션을 `## History`로 교체: 루트 해석(`where`), 노트 생성, 런타임 원장, 실패 처리. 온보딩·repair·pending replay 문단 삭제.
  - Repo-local config 섹션을 §10 표로 갱신.
  - Role Session Evidence의 섹션 이름(Roles, Team Lifecycle, Execution Ledger, Discussion Summary)을 새 구조에 맞춘다.
  - Workflow 3·5·6·7·9 단계의 노트/원장 경로 갱신. 7단계: 리드가 `[<slug>] verify` 태스크를 만들고 모든 필수 명령을 `verify` 헬퍼로 실행. 9단계: 마감은 `close`로만.
  - roles.md Role Prompt Contract에 "`pl_history.py`를 실행하지 말라" 추가.
  - System Improvement Rule의 테스트 목록 갱신.
  - Standing Completion Contract의 "memory is updated" → "history is updated". 이 계약은 파일 앞쪽 5000자 안에 남아야 한다(기존 테스트).
- `skills/pl/SKILL.md`: description·Hard rules의 memory backend 문구 갱신.
- `references/`: `memory-notion.md`, `memory-obsidian.md` 삭제. `memory-templates.md` → `history.md`로 개명하고 §3~§8의 규칙(위치·구조·템플릿·헬퍼 사용법)을 담는 유일한 출처로 만든다. `debate-protocol.md` Review Loop(§9)·Memory Hygiene 용어 갱신. `external-benchmarking.md`의 "configured memory backend" 문구 갱신.
- `agents/*.md`: memory 언급이 있으면 갱신 후 `build_codex_agents.py`로 TOML 재생성.
- `README.md`(루트·플러그인), `plugin.json` 두 개, 마켓플레이스 JSON 두 개의 설명 문구.
- 버전 `0.5.0`(두 plugin.json 동기화; CI가 강제). 커밋 메시지는 `feat(pl)!:` 형식.
- README "메모리 백엔드" 섹션 → "히스토리": 위치 규칙, `.agents/pl.md` 예시, 커밋 권장, `.runtime/` 설명, 기존 vault/Notion 사용자 안내(이전 기록은 그대로 남고 pl이 더는 읽지 않음, 원하면 `work/<slug>/features|decisions`를 `docs/pl/`로 수동 복사).

## 12. 테스트

- `test_pl_history.py` (신규, 기존 `test_memory_note.py`·`test_pl_user_config.py` 대체): 위치 해석(레포/로컬, `historyDir` 거부 경로, 개인 설정 무시), 구조 생성과 `.runtime/.gitignore`, feature/decision 생성·링크, `list`, `verify` 증거·지문(히스토리 루트 제외, untracked 산출물을 남기는 명령이 stale이 되지 않음), `--withdraw`(일반 명령 철회 가능, `verifyCommands` 철회 거부), `close`(실패·stale·누락 시 `done` 거부, 통과 시 도장), 닫힌 기능이 이후 코드 변경 뒤에도 `check`를 통과함, `check`가 파일을 수정하지 않음.
- 병렬 브랜치 시나리오: 임시 레포에서 두 브랜치가 각각 `feature`를 만들고 머지할 때 충돌이 없음을 확인하는 테스트 1개.
- `test_pl_config.py`: references 집합, Notion 관련 단언 제거, 새 문구 단언 추가, SKILL.md 500줄 제한 유지.
- `tests/pl-e2e/setup-fixtures.sh`: obsidian config 쓰기 제거. 무효 경로 4(온보딩 멈춤)를 README 표에서 삭제.
- TaskCompleted 훅을 넣는다면 `tests/pl-guard/`와 같은 방식의 단위 매트릭스(`[slug] verify`가 아닌 태스크→통과, 증거 없음→exit 2, 증거 stale→exit 2, 증거 OK→통과, 내부 오류→통과).
- CI(`.github/workflows/ci.yml`) 테스트 목록 갱신.
- 완료 전: §11·§12의 모든 스크립트 테스트 + `run-unit.sh` 3종. `run-safety.sh`(실제 세션, 토큰 소모)는 사용자에게 실행 여부를 묻는다.

## 13. 빌더에게 맡기는 것

- 헬퍼 내부 구조, 모듈 분할, 기존 코드 재사용 방식.
- 훅 구현 언어(bash+jq 또는 python).
- 증거 JSON 필드 이름, 출력 꼬리 줄 수의 미세 조정.
- 문서 문장, 섹션 순서의 세부.
- 작업은 `main`이 아닌 새 브랜치(또는 worktree)에서 한다.

## 14. 설계자 판단 목록 (사용자 확인용)

- 레포 밖 기본 위치를 플러그인 데이터 폴더가 아닌 `~/.local/share/pl/history`로 정함(플러그인 제거 시 삭제 문제).
- 기본 `historyDir` = `docs/pl`, 팀 설정 파일 이름 = `.agents/pl.md`.
- 개인 설정은 `historyDir`를 바꿀 수 없고, `verifyCommands`·`protectedPaths`는 추가만 가능.
- 역할 의견은 원문이 아닌 요약(입장·근거·권고·질문)으로 커밋.
- 세션 생명주기 세부는 커밋하지 않고 Completion에 한 줄 요약만.
- 기존 vault/Notion 자동 이전 없음.
- `workNamespace` 제거.
- 검증 증거의 출력 원문은 커밋하지 않음.
- 신선도는 `close` 시점에 한 번 판정해 도장으로 고정(이후 코드 변경으로 닫힌 기능이 깨지지 않음), `check`는 읽기 전용.
- 필수 명령 = 이 기능에서 돌린 모든 명령 ∪ `verifyCommands`, 잘못 돌린 명령은 사유와 함께 철회.
- 신선도 기준은 실행 후 지문.
- `verify`는 리드만 실행, TaskCompleted 훅은 리드의 `[slug] verify` 태스크에만 적용.
- hook 적용 범위는 "세션 단위": 그 세션에서 pl을 실행한 뒤부터 세션 끝까지(§15).

## 15. Hook 적용 범위 (사용자 요구 추가)

사용자 요구: 지금 `guard.sh`는 플러그인이 켜져 있기만 하면 pl을 쓰지 않는 세션에도 적용된다. **pl을 한 번이라도 사용한 세션에서, 그때부터** 적용되어야 한다. "한 번 사용"은 세션 단위로 해석한다(그 세션에서 `/pl`을 실행한 순간부터 세션 끝까지) — 설계자 해석.

근거(공식 문서, 2026-10-20 확인, code.claude.com/docs/en/hooks · sub-agents):
- 스킬 frontmatter `hooks`는 스킬이 호출될 때 등록되어 세션 끝까지 유지된다. 스킬 훅에서도 `${CLAUDE_PLUGIN_ROOT}` 치환이 된다.
- 문서는 settings·managed·플러그인 훅이 서브에이전트 안에서도 실행된다고만 적고, 스킬 훅의 서브에이전트/teammate 적용 여부는 적지 않는다.
- 플러그인 에이전트 정의의 `hooks` 필드는 보안상 무시된다.
- 플러그인 훅 입력에는 서브에이전트·in-process teammate 안에서 `agent_id`·`agent_type`이 들어온다. 플러그인 에이전트의 `agent_type`은 `pl:team-pl-<role>` 형태.

### 15.1 Claude Code

1. **리드:** `skills/team-pl-orchestrator/SKILL.md`와 `skills/pl/SKILL.md` frontmatter `hooks`에 `PreToolUse`(matcher `Bash`) → `guard.sh`를 등록한다. 둘 다 등록되어 중복 실행되어도 판정이 같으므로 무해하다. 이로써 `/pl` 실행 순간부터 세션 끝까지 리드의 Bash가 보호된다. §7.1 `TaskCompleted` 훅도 orchestrator frontmatter에 둔다.
2. **역할 세션:** 플러그인 `hooks/hooks.json`의 `PreToolUse` guard는 유지하되, `guard.sh`가 입력의 `agent_type`이 `pl:team-pl-`로 시작할 때만 판정하고 그 외에는 즉시 통과한다. pl을 쓰지 않는 세션에는 영향이 없고, 역할 세션은 스킬 훅 전파 여부와 무관하게 항상 보호된다.
3. 모드 구분은 인자로 한다: `guard.sh --scope role`(플러그인 훅: `agent_type` 검사), 인자 없음(스킬 훅·Codex: 항상 판정). 판정 로직 자체는 공유한다.
4. **빌더 실측 항목:** (a) 플러그인 스킬의 frontmatter 훅이 실제로 등록되는지(`/hooks` 메뉴에 session 출처로 보이는지), (b) Agent Teams teammate의 PreToolUse 입력에 `agent_type: pl:team-pl-<role>`이 들어오는지. (b)가 거짓이면 역할 세션 보호가 사라지므로, 그 경우 플러그인 훅을 "항상 판정"으로 되돌리고 그 사실을 사용자에게 보고한다(보호 공백보다 과잉 적용이 낫다). (a)가 거짓이면 리드 보호가 사라지므로 마찬가지로 "항상 판정"으로 되돌리고 보고한다.

### 15.2 Codex CLI

- Codex에 스킬 단위 훅이 있는지, 없다면 우회(예: `UserPromptSubmit` 훅이 `$pl` 호출을 감지해 `session_id`별 표식을 남기고 guard가 표식이 있을 때만 판정; 서브에이전트에 같은 표식이 이어지는지 포함)가 가능한지 빌더가 공식 문서와 실측으로 확인한다.
- **우회가 확인되지 않으면 Codex는 지금처럼 항상 guard를 켜 둔다**(사용자 결정). 이 경우 `.codex-plugin/plugin.json`은 Codex 전용 훅 파일(예: `hooks/hooks.codex.json`, 인자 없는 "항상 판정" 모드)을 가리켜야 한다. Claude용 `hooks.json`의 `--scope role` 모드를 Codex가 그대로 쓰면 `agent_type`이 없어 guard가 꺼지므로 반드시 분리한다.
- README 호스트 차이 표와 안전 훅 절에 "Claude Code: pl 실행 세션부터 / Codex: 항상(또는 확인된 우회 방식)"을 적는다.

### 15.3 테스트

- `tests/pl-guard/run-unit.sh`에 모드 축 추가: `--scope role`에서 `agent_type` 없음→통과, `agent_type: Explore`→통과, `agent_type: pl:team-pl-backend-engineer`→기존 판정; 인자 없음→기존 판정(Claude·Codex 페이로드 모두).
- `test_pl_config.py`: 두 SKILL.md frontmatter에 guard 훅이 있고, 플러그인 `hooks.json`은 `--scope role`, Codex 매니페스트는 항상-판정 훅 파일을 가리킴을 단언.

## 16. 서브에이전트 전환 (Claude Code)

사용자 결정: Claude Code에서도 Agent Teams 대신 일반 서브에이전트를 쓴다. 근거(공식 문서 2026-10-20): Agent Teams는 실험 기능·기본 꺼짐, `/resume` 복원 불가, 토큰 "significantly more"; 서브에이전트는 최종 응답이 곧 결과이고 이름 또는 agent ID로 재개(`SendMessage`)할 수 있으며 대화 이력을 유지한다.

### 16.1 실행 모델 (두 호스트 공통)

- **spawn**: 한 단계의 역할을 한 메시지에서 병렬로 spawn한다. 메모 = 서브에이전트의 최종 응답. 전달 누락·idle 상태가 존재하지 않는다.
- **이름을 붙이지 않는다.** 공식 문서: Agent Teams가 켜진 세션에서 `name`을 붙여 spawn하면 teammate로 바뀐다. 플러그인은 그 플래그를 끌 수 없으므로 spawn 호출에 `name`을 넣지 않고, 호스트가 돌려준 **agent ID**로 재개·추적한다. `pl-architect` 같은 런타임 이름은 런타임 원장과 노트 안의 **라벨**로만 쓴다. `-r2` 접미 규칙은 라벨에만 남는다.
- **반론(Round 2)과 재리뷰**: 리드가 해당 agent ID로 `SendMessage`(Codex: `send_input`/`resume_agent`)를 보내 재개한다. 재개된 세션은 처음의 도구 제한을 유지한다. 역할끼리 직접 메시지는 없다 — 두 호스트 모두 리드 중계.
- **종료**: 완료된 서브에이전트는 이미 끝난 상태다. 종료 요청·강제 종료·종료 미확인 개념을 모두 없앤다. 아직 돌고 있는 세션을 버려야 할 때만 `TaskStop`(Codex: `close_agent`).
- **부분 결과**: `maxTurns`에 닿으면 호스트가 부분 결과로 돌려준다. 리드는 재개해 마저 받거나, 부분 결과로 진행하고 노트에 `partial`로 적는다.
- **Round 0 태스크 필드**는 spawn 브리프에 넣고 런타임 원장에 적는다(지금 Codex 방식). 호스트 TaskList는 쓰지 않는다 — 새 모델에서는 기본 제공되지 않고 백그라운드 서브에이전트에서 제거된다.

### 16.2 역할 정의 frontmatter

모든 역할에서 `SendMessage`, `TaskList`, `TaskGet`, `TaskUpdate`를 `tools`에서 뺀다. `model: inherit` 유지. 검사 역할 5개 `effort: xhigh` 유지. **`maxTurns`를 모든 역할에 추가**(분석·리뷰 40–60, 구현 120 — 빌더가 실측으로 조정). `memory`·`isolation`·`background`·`skills`는 설정하지 않는다(`memory`는 편집 도구를 강제로 켠다; `isolation: worktree`는 기본 브랜치에서 분기해 미커밋 변경을 못 본다). 재개가 예상되는 검사 역할에는 `experimental.cacheTtl: 1h`를 둘 수 있다(빌더 판단).

### 16.3 메모 자동 수집 (Claude Code 전용, 보조)

orchestrator SKILL.md frontmatter에 `SubagentStop` 훅(matcher `^pl:team-pl-`)을 추가한다. `last_assistant_message`(auto 모드에서는 `SubagentHandback`의 `PostToolUse` `tool_input.message`)를 `.runtime/<slug>/memos/<agent_id>.md`에 쓴다. 리드는 이 파일을 Roles and Opinions 요약과 리뷰 병합의 입력으로 쓴다. `Status:` 줄이 없는 메모는 `decision: block`으로 한 번 돌려보낸다(`stop_hook_active`로 루프 방지). 스킬 훅이 이후 spawn된 서브에이전트의 Stop에 걸리는지는 빌더가 실측한다. 실패해도 메모는 리드의 컨텍스트에 이미 있으므로 기능 손실은 없다.

### 16.4 삭제·축소되는 문서

- `references/team-lifecycle.md` 삭제. 남길 내용(라벨 비재사용, 세션 복원 후 재개 가능, 잘못된 역할 세션 교체는 agent ID 새로 spawn + 라벨 `-r2`)은 roles.md 한 절로 옮긴다.
- SKILL.md Platform Behavior: Host mapping 표는 spawn / 재개 / 종료 / 스킬 디렉터리 / 데이터 디렉터리 5행으로 줄인다. Claude Code 절의 teammate·TeamCreate·TaskList·패널·transcript 복구·"teammates라는 단어를 써라" 문단 전부 삭제. 호스트 식별은 `Agent` 도구 유무(Claude) vs `spawn_agent`(Codex).
- Role Session Evidence 규칙은 유지하되 "세션 식별자 + 최종 응답 텍스트"로 단순화.
- Standing Completion Contract에서 종료 확인 조항 삭제; `done-with-risks` 조건에 "필수 역할이 `partial`/실패로 끝나 메모가 없음"을 넣는다.
- README 호스트 차이 표를 다시 쓴다. "Agent Teams를 켜 둔 사용자는 끄기를 권장(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`); 켜져 있어도 pl은 이름 없는 spawn으로 서브에이전트를 유지한다"를 적는다.

### 16.5 Codex 사실 정정 (공식 문서 2026-10-20)

- `sandbox_mode`는 커스텀 에이전트 파일에서 **항상** 무시된다("부모가 덮어쓸 때만"이 아니다). TOML에서 빼거나 주석으로 남기고, 읽기 전용 역할은 `features.shell_tool = false`로 Bash를 끈다(빌더가 TOML 키 유효성 확인). 노트의 `Role sandbox:` 줄은 삭제.
- 멀티에이전트 도구 이름은 `spawn_agent`, `send_input`, `resume_agent`, `wait_agent`, `close_agent`. `followup_task`·`interrupt_agent`·"깊이 1단계" 서술은 문서에 없으므로 삭제하고 실측 결과만 적는다.
- `build_codex_agents.py`: `sandbox_mode` 생성 제거, `maxTurns`는 대응 키가 없으면 무시.

## 17. 워크플로우 결함 수정 (프롬프트 정합성 감사)

1. **작업 규모 3단계**를 Workflow 1단계 직후에 둔다: `solo`(기존 조건) / `light` / `full`. `light` 기준(설계자 판단): 변경 파일 ≤ 3, 새 공개 API·스키마·외부 연동 없음, 사용자 가시 동작 변경이 요청에 명시된 범위뿐. `light` = 리드 intake 분석 + 구현(리드 또는 엔지니어 1명) + code reviewer 1회. `full` = 지금 구조. 요청에 "full"/"팀 토론"이 있으면 `full`, "light"가 있으면 `light`. 리드는 선택한 단계와 이유를 노트 Scope에 적는다. roles.md의 "product/architect/qa 필수"는 `full`의 기본값으로 낮춘다.
2. **완료 계약에 단계별 분기**: `solo`는 fresh 검증 + 리드 diff 점검으로 `done`, 노트 없음. `light`/`full`은 §8.2. 리뷰 3회 상한 소진 시 Important 이상 미해결 → `done-with-risks`, 목록 기록(§9).
3. **사용자 결정 단계 추가**: Synthesis 뒤, Decide 전에 "제품 범위·우선순위에 걸린 결정(`NEEDS_DECISION`, product analyst의 Decisions needed)을 한 번에 모아 사용자에게 묻는다. 기술 결정은 리드가 한다." 기존 "질문은 최대 1개" 규칙은 intake 단계 한정으로 명시.
4. **analyze gate 순서**: "결정 → 원장 항목 변환"을 gate 앞으로 옮긴다.
5. **change-shape gate 기준선**: 각 wave 시작 전 `git status --porcelain` 스냅샷을 런타임 원장에 저장하고, wave 뒤 **차이**만 소유 목록과 비교한다. 히스토리 루트와 리드 소유 경로는 제외.
6. **QA 리뷰 참여 조건 통일**: 테스트 파일이 바뀌었거나 Verify에서 실패가 있었을 때만 QA agent ID를 재개해 커버리지 검토. 무조건 호출 문장 삭제.
7. **리뷰 finding 소유권**: 리드가 각 finding을 검증하고 근거를 적어 기각할 수 있다. 제품 범위에 걸린 충돌만 사용자에게. "re-tier 금지"는 "리뷰어 원문 보존 + 리드 판정 별도 표기"로 바꾼다.
8. **존재하지 않는 참조 삭제**: `/verify`, `explain-diff`. 앱 동작 확인은 "레포의 문서화된 실행 절차"로 통일.
9. **네임스페이스 규칙 삭제**(레포 모드), §3 로컬 모드만 요청에서 이름을 받는다.
10. **역할 lane 정비**: 9개 모두 `Your lane` 한 줄을 갖는다. 겹치는 Focus 항목 제거 — architect의 "Integration points/risks"는 integration reviewer로, backend "Observability"는 integration으로, backend "Persistence and migration impact"는 data engineer로, security "External integration abuse"는 "integration의 입력을 통한 위협"으로 좁힌다. roles.md의 "QA의 acceptance criteria"는 product analyst로 정정.
11. **엔지니어 메모 = 구현 보고서**: 바뀐 경로, 실행한 명령과 결과 요약, 계획 대비 편차, 후속 과제. 사전 분석 항목 목록 삭제.
12. **공유 메모 형식**: 모든 역할 메모는 `Status:` → 역할별 본문 → `Unverifiable statically:` → `Key files:`. Synthesis가 소비하지 않는 항목(architect "Validation implications", QA "Release risk" 등) 삭제.
13. **product analyst**: `full`에서만 spawn하고, 요구사항이 명확하면 리드가 생략할 수 있다. 복붙된 "send the proposed change and file ownership" 줄 삭제.
14. **역할 본문 공통 보일러플레이트 추출**: 전달 계약·입력 신뢰 경계·부작용 금지·grounding 규칙은 `references/roles.md`의 "Shared role preamble" 한 블록으로 두고 리드가 브리프 맨 앞에 그대로 붙인다. 역할 본문에는 Focus·lane·메모 형식만 남긴다. (Codex TOML `developer_instructions`에는 생성기가 preamble을 합쳐 넣는다 — 호스트가 브리프 없이 정의만 쓰는 경우 대비.)
15. **유지보수 전용 내용 이동**: System Improvement Rule과 `external-benchmarking.md`를 레포 루트 `CONTRIBUTING.md`로 옮긴다. 날짜 붙은 실측 메모("verified 2026-07-14" 등)와 규칙의 근거 설명은 CHANGELOG 또는 CONTRIBUTING으로. 런타임 프롬프트에는 규칙 문장만 남긴다.
16. **중복 규칙 단일화**: 슬러그 접두, 계획 승인, 파일당 소유자 1명, 리뷰어 spawn 시점, Status-first 메모, 심각도 처리, 모델 오버라이드 금지, 충돌 검사, wave 후 원장 갱신 — 각각 소유 reference 한 곳에만 두고 나머지는 포인터.
17. **code reviewer 문구**: "불확실한 finding도 보고하되 confidence low 표기"로 통일, "instead of guessing" 삭제. 메모 형식에 `Gate 1 items:`(요구사항·결정별 PASS/FAIL) 추가.
18. **리뷰어 입력**: 리드가 `.runtime/<slug>/diff.patch`(`git diff <base>..HEAD` + 미커밋 포함)를 쓰고 모든 리뷰어 브리프에 경로를 준다. Bash가 없는 security/integration 리뷰어도 diff를 직접 읽는다. security 브리프는 `threat-model`(설계 단계) 또는 `diff-review`(구현 후) 중 하나를 명시한다.

## 18. 안전 훅 재작성

감사에서 확인된 우회·오탐(이 세션에서 직접 재현: `git reset --har`, `env git push --force`, `git push origin +main` 통과; `git checkout main 2>&1`과 heredoc 본문 속 git 줄은 오탐 차단 — 감사 중 리드의 heredoc이 실제로 두 번 막혔다).

- **Python(표준 라이브러리)으로 재작성** `hooks/guard.py`. `jq` 의존 제거(README 전제조건에서 삭제). bash 3.2 호환 문제도 사라진다. 내부 오류는 fail-open 유지.
- 토크나이저: `shlex`(`punctuation_chars=True`)로 인용·heredoc·백슬래시 연속을 올바르게 처리. 리다이렉션 토큰 제거. 구분자 `;`, `&&`, `||`, `|`, `&`, 개행.
- 래퍼 벗기기: 선행 env 대입(단, `GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT`가 `core.hooksPath`를 담으면 deny), `env`, `command`, `exec`, `time`, `nohup`, `sudo`, 절대경로·`\git` → basename `git`. `sh|bash|zsh -c "<str>"`, `eval`, `xargs`, `$( )`, 백틱 본문은 재귀 스캔.
- 긴 옵션은 **고유 접두 매칭**(`--har` → `--hard`, 3자 이상).
- 추가 규칙: `push`의 `+refspec`, `:ref`, `--delete`/`-d`, `--mirror`; `update-ref -d`; `reflog expire`; `gc --prune`; `worktree remove --force`; `rm -rf .git`·`rm -r .git`; `git rm -rf .`; `--pathspec-from-file`; `stash` 하위명령을 옵션 뒤에서도 찾기; `-c alias.*`, `config core.hooksPath`, `--config-env=core.hooksPath`.
- 입력 형식: `.tool_input.command // .tool_input.cmd`, 배열이면 join, `bash -lc` 한 겹 풀기. `hooks.json` matcher를 `Bash|Monitor`로 넓힐지는 Monitor 입력 형식 확인 후 빌더 결정.
- 모드: §15의 `--scope role`(입력 `agent_type`이 `^pl:team-pl-`일 때만 판정) / 기본(항상 판정).
- 테스트 `tests/pl-guard/run-unit.sh`: 위 우회·오탐 전부 케이스로 추가, 기존 a28 "known hole" 케이스는 DENY로 전환, stdout이 유효 JSON인지와 exit code를 단언. 셸 스크립트 하네스는 유지(판정기만 Python).

## 19. 테스트·CI·설치 스크립트

- `test_pl_config.py`: 문장 고정(prose pin) 단언을 걷어내고 불변 마커(헤딩·ID·frontmatter 값·파일 집합·단어 예산)만 남긴다. 머신 의존 검사(`CLAUDE_CODE_SUBAGENT_MODEL`)는 `PL_MACHINE_TESTS=1` 옵트인. `hooks.json`(과 Codex 훅 파일)·두 SKILL.md frontmatter 훅·매니페스트 4개 설명 문구 일치를 검사하는 테스트 추가. `compile()` 대신 import로 헬퍼 검증. 머신 경로 스캔을 `.sh`·`.json`·`hooks/`·`tests/`까지 넓힌다.
- `ci.yml`: Python 3.10/3.11/3.12/3.13 매트릭스 + `macos-latest`(bash 3.2·기본 python3) 1 job, `shellcheck`, `claude plugin validate plugins/pl`과 마켓플레이스(설치 가능하면), 버전 가드는 push에서 `github.event.before` 기준·`NEW > OLD` semver 비교. 액션은 SHA 고정.
- `install-codex.sh`: 충돌을 세고 끝까지 진행 후 요약·종료 코드 구분(0 성공 / 3 충돌 / 1 오류), 삭제된 역할 TOML 정리(`--prune`), 심볼릭 링크 대상 복사 금지, README 실행 줄을 버전 해석 명령으로 교체(`CODEX_HOME` 존중).
- `tests/pl-e2e`: `timeout` 존재 확인, 세션 exit code 반영, 양성 대조는 교정 문구 존재까지 단언, S3는 커밋에 README 포함 확인, S4는 커밋 존재 확인, `--setting-sources`로 사용자 설정 격리. 픽스처에서 Obsidian config 생성 제거; 히스토리 파일이 생기므로 `porcelain` 기반 단언을 "히스토리 루트 제외"로 바꾸고, 히스토리 파일이 스테이징되지 않음을 S2에 단언. 새 케이스: 바깥 레포(`agent-plugins`)의 `docs/`가 건드려지지 않음.
- 매니페스트: `plugin.json` 2개·`marketplace.json` 2개 설명 동기화, Codex 마켓플레이스 `owner` 추가, `hooks.json` 명령 인용(`"${CLAUDE_PLUGIN_ROOT}"`).

## 20. 설계자 판단 추가분 (사용자 확인용)

- 서브에이전트는 **이름 없이** spawn하고 agent ID로 재개한다(Agent Teams 플래그와 무관하게 동작하기 위해).
- 작업 규모 `light` 단계 신설과 그 기준(§17-1).
- product analyst는 `full`에서만, 요구사항이 명확하면 생략 가능.
- 사용자에게 묻는 결정 단계 신설(Synthesis 뒤 한 번에).
- 안전 훅을 Python으로 재작성, `jq` 전제조건 제거.
- 유지보수 전용 문서를 `CONTRIBUTING.md`로 이동.
- Codex 읽기 전용 역할은 `features.shell_tool = false`(유효성은 빌더 확인).

