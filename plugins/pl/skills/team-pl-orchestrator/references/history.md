# History

Single source for where pl's durable history lives, its layout, the helper commands, and what each note section holds. The helper is `<skill-dir>/scripts/pl_history.py`; `<skill-dir>` and `<data-dir>` are defined in SKILL.md Platform Behavior (Host mapping). Run it from the repository (it resolves the location from the current directory).

## Location

- **Repo mode** (current directory is inside a git work tree): `<work tree root>/<historyDir>`, where `historyDir` comes from the committed team file `.agents/pl.md` (frontmatter) and defaults to `docs/pl`. The history is committed by the user together with the code; pl never commits it. `historyDir` must be relative, inside the repository, and not under `.git/`; the helper refuses anything else. A `historyDir` in the personal `pl.local.md` is ignored with a warning — the location is team-owned.
- **Local mode** (not in a git work tree): `<historyRoot>/<work>`, where `historyRoot` is `${XDG_DATA_HOME:-~/.local/share}/pl/history` unless `<data-dir>/config.json` sets `{"historyRoot": "<absolute path>"}`. `<work>` is the slug the user named for the work; without one the helper uses `inbox` and warns — ask the user for a name when you can. The plugin data directory is not used for history because the host deletes it on uninstall.

Run `where` first in every non-solo request; it prints the mode and root, creates the layout when missing, and lists every warning you must relay to the user once.

## Layout

```text
<history root>/
  features/YYYY-MM-DD-<slug>.md     committed
  decisions/YYYY-MM-DD-<slug>.md    committed
  architecture.md                   committed; keep it current when the shape changes
  .runtime/                         git-ignored (self-ignoring .gitignore written by the helper)
    <feature stem>/
      ledger.md                     Execution Ledger, Team Lifecycle, Wave Baselines (written by `ledger`)
      evidence.jsonl                verification runs (written by `verify`)
      memos/<id or hash>.md         role memos (hook는 ID, lead의 memo 명령은 SHA-256 파일명 사용)
      diff.patch                    review diff (written by `diff`)
    current                         stem of the feature the lead is working on (written by `feature`/`current`, cleared by `close`)
```

There is no index file. `list` builds the listing from frontmatter when you need it. Dates plus slugs keep parallel branches from colliding; two notes with the same slug on the same day are refused.

## Helper commands

| Command | What it does |
|---|---|
| `where [--json]` | Resolve mode and root; create the layout; print warnings (ignored keys, duplicate config files, inbox fallback). Also reports `verifyCommands` and `protectedPaths` (team ∪ personal). |
| `feature "<title>" [--request "<text>"]` | Create the feature note and its runtime ledger; print the note path. Idempotent for the same title on the same day. |
| `decision "<title>" --feature <stem> [--supersedes <file>]` | Create a decision note linked both ways (keep the title to a short noun phrase — it becomes the file name); a superseded note gets `status: superseded` and `superseded_by`, never deleted. |
| `list [--type feature\|decision] [--status <s>]` | Listing from frontmatter. |
| `current [--feature <stem>]` | Show or set the current feature. `feature` sets it; `close` clears it. `ledger` and `diff` default to it. |
| `memo --feature <stem> --agent-id <id>` | lead가 수신한 최종 응답 원문을 stdin으로 받아 `.runtime/<stem>/memos/<ID 해시>-<응답 해시>.md`에 저장하고 경로를 출력한다. 첫 줄에 유효한 `Status:`가 필요하다. 같은 응답의 재저장은 동일 경로이고 재개 응답은 새 파일이므로 이전 증거를 보존한다. 반환 ID와 경로를 ledger에 함께 기록한다. hook 실행과 무관하며 `current` 대신 feature를 명시한다. |
| `ledger row <task> [--owner] [--depends] [--deliverable] [--status] [--evidence]` | 단건 행을 삽입·갱신하는 호환 명령이며 생략한 필드는 보존한다. memo task는 고유 라벨 전체인 `<label>-memo`다. 단계별 기록은 batch로 묶고 단건 보정이 필요할 때 사용한다. |
| `ledger [--feature <stem>] batch` | stdin JSON의 `rows`·`lifecycle` 배열을 모두 검증한 뒤 기존 원장에 한 번 저장한다. 같은 단계의 pending 행·반환 ID, 수신 후 완료 행·미완료 lifecycle을 묶는 기본 경로다. 잘못된 입력은 전체 거부하고 같은 lifecycle 항목의 재시도는 중복 추가하지 않는다. 기존 단일 명령도 지원한다. |
| `ledger lifecycle <Spawned\|Replaced\|Partial\|Failed\|Not spawned> "<label (agent id)>"` | Append to a Team Lifecycle field — record every spawn, replacement, final partial, failure, and planned-but-not-spawned role here. 재개 중인 부분 결과는 ledger row의 진행 상태·근거에 기록하고, 최종 미완료가 확정되면 Partial에 남긴다. `close --status done` refuses when Partial or Failed is non-empty. |
| `ledger baseline "<wave label>"` | Snapshot `git status --porcelain` under Wave Baselines before a delegated wave; the change-shape gate compares against it. |
| `diff [--base <sha>]` | Write `.runtime/<stem>/diff.patch` (committed range from `--base` plus uncommitted and untracked changes, history root excluded) for review roles. |
| `verify --feature <stem> -- <command...>` | Run a verification command, stream its output, record exit code, tail, and the working-tree fingerprint after the run; rewrite the note's Verification table. The exit code is the helper's exit code. One argument after `--` is a shell string (run with `sh -c`, recorded verbatim — use this form for `verifyCommands` entries, e.g. `-- "cd web && pnpm test"`); several arguments are an argv. |
| `verify --feature <stem> --withdraw "<command>" --reason "<why>"` | Remove a wrongly chosen command from the required set; the withdrawal and reason stay in the table. `verifyCommands` entries cannot be withdrawn. |
| `close --feature <stem> --status done\|done-with-risks\|blocked` | 완료 검사를 실행하고 성공 시 frontmatter `status`·`Fresh at close`를 쓴다. 기록된 Spawned와 `<label>-memo` 행에서 `Team:`을 생성한다. `done`은 필수 명령의 미실행·실패·stale, Partial/Failed, memo 행의 미완료·근거 누락, 기존 Team의 partial/failed, 선택 placeholder를 거부한다. `done-with-risks`·`blocked`는 문제를 기록하고 닫는다. Spawned가 없는 과거 노트의 Team은 보존한다. |
| `check [--feature <stem>]` | Read-only structural check (links, status vocabulary, placeholders, `done` consistency). Same result on every clone; never looks at runtime evidence. |

Required commands for `done` = every command run through `verify` for this feature (minus withdrawn) ∪ `verifyCommands`. The lead runs `verify`; role sessions never do. Freshness follows the chain of verify runs: a command stays fresh while every later change to the working tree was made by a later `verify` run (test output files, caches); an edit made outside `verify` makes everything before it stale, so re-run the required commands after the last code change. Local mode cannot fingerprint, so `close` stamps `Fresh at close: unknown` and you record the evidence gap under Residual risk.

### 단계별 일괄 기록

spawn 전에 brief에 task·의존성·편집 경계·산출물을 정한다. 같은 단계의 반환 ID를 받은 즉시 pending 행과 lifecycle을 함께 기록한다.

```bash
python3 "<skill-dir>/scripts/pl_history.py" ledger --feature <stem> batch <<'JSON'
{"rows":[{"task":"pl-review-memo","owner":"pl-review","depends":"implementation","deliverable":"read-only review memo","status":"pending"}],"lifecycle":[{"field":"Spawned","value":"pl-review (returned-id)"}]}
JSON
```

`rows`의 필수 필드는 `task`이며 나머지 필드는 기존 row 명령과 같다. 생략하거나 null인 필드는 기존 값을 유지한다. `lifecycle` 항목은 `field`·`value`가 필요하다. 두 배열 중 하나는 생략할 수 있다. 여러 역할의 항목을 각 배열에 추가한다. 실제 응답을 받고 완료 조건을 확인한 뒤 같은 명령에 `{"rows":[{"task":"pl-review-memo","status":"done","evidence":"memo 경로 또는 수신 ID"}]}`를 전달한다. 최종 미완료는 해당 행과 lifecycle `Partial`/`Failed`로 남긴다. memo 저장·리뷰 판정은 lead의 책임이며 hook 종료만으로 완료를 추정하지 않는다.

자동 생성한 Team에는 `<!-- pl:team-summary -->` 표식이 붙는다. 이 줄은 close가 관리하며, 미완료 작업을 재개해 완료하면 새 집계로 검사·갱신한다. 표식이 없는 기존 수기 Team의 partial/failed는 위험 마감에서도 보존하므로 기록된 위험을 먼저 해결해야 한다. 동일 session ID를 다른 label에 중복 배정하면 done을 거부한다. 원장이 손상돼 집계할 수 없으면 done은 거부하고, blocked·done-with-risks는 경고와 기존 Team을 보존해 닫는다.

Never edit a note's frontmatter `status` by hand; `close` is the only writer.

## Note sections

Feature note (`features/`): frontmatter `type, title, status, date, owner, repo, decisions`; sections in this order — **Request** (the user's words) · **Scope** (In / Out / `Size:` with the reason) · **Roles and Opinions** (one `### <role> (<label>)` per delivered memo: Position, Key evidence as repo paths, Recommendation, Open questions — a summary, never the memo verbatim; `not spawned — <reason>` for a planned role that produced no session) · **Synthesis** (Agreements, Conflicts with both sides' grounds, Hidden assumptions, Unverifiable statically) · **Challenges** (`challenger -> recipient: claim, response, effect on decision`, or `skipped — no material conflict in synthesis`) · **PL Decisions** (one line per decision plus rejected alternatives; details in `decisions/`, linked through frontmatter `decisions`) · **Implementation Summary** · **Changed Files** · **Verification** (helper-owned) · **Review** (`cycle N: Gate 1 PASS|FAIL, Gate 2 PASS|FAIL, unresolved findings`) · **Completion** (close가 생성하는 `Team: <N> role sessions (complete N[, partial N][, failed N][, not spawned N])`, lead가 작성하는 Residual risk) · **Open Questions**.

Decision note (`decisions/`): frontmatter `type, title, status (accepted|superseded), date, owner, feature, supersedes, superseded_by`; sections Context · Options Considered · Decision · Rationale · Consequences · Validation · Open Questions.

Runtime ledger (`.runtime/<stem>/ledger.md`, written only through `ledger`): **Execution Ledger** table (`Task | Owner | Depends on | Deliverable | Status | Evidence`) — the only task state on both hosts; update it after every completed wave so work resumes after compaction. **Team Lifecycle** (`Spawned`, `Replaced`, `Partial`, `Failed`, `Not spawned` — labels with agent IDs). **Wave Baselines** (one `git status --porcelain` snapshot per wave, taken before the wave starts).

## Hygiene

Write summaries, not transcripts. No secrets, credentials, raw command logs, or unbounded output in committed notes (the evidence tail stays in `.runtime/`). Durable notes answer: what did we decide, why, what alternatives, what changed, how was it validated, what remains uncertain. If a helper write fails, tell the user what could not be written and where the content is, and close as `done-with-risks`.
