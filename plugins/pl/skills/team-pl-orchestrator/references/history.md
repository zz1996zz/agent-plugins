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
      memos/<agent id>.md           role memos (written by the host's memo-capture hook where it runs; else by the lead)
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
| `ledger row <task> [--owner] [--depends] [--deliverable] [--status] [--evidence]` | Insert or update one Execution Ledger row (keyed by task; omitted fields keep their value). Use it for Round 0 rows, after each wave, and at close. |
| `ledger lifecycle <Spawned\|Replaced\|Partial\|Failed\|Not spawned> "<label (agent id)>"` | Append to a Team Lifecycle field — record every spawn, replacement, partial, failure, and planned-but-not-spawned role here; `close --status done` refuses when Partial or Failed is non-empty. |
| `ledger baseline "<wave label>"` | Snapshot `git status --porcelain` under Wave Baselines before a delegated wave; the change-shape gate compares against it. |
| `diff [--base <sha>]` | Write `.runtime/<stem>/diff.patch` (committed range from `--base` plus uncommitted and untracked changes, history root excluded) for review roles. |
| `verify --feature <stem> -- <command...>` | Run a verification command, stream its output, record exit code, tail, and the working-tree fingerprint after the run; rewrite the note's Verification table. The exit code is the helper's exit code. One argument after `--` is a shell string (run with `sh -c`, recorded verbatim — use this form for `verifyCommands` entries, e.g. `-- "cd web && pnpm test"`); several arguments are an argv. |
| `verify --feature <stem> --withdraw "<command>" --reason "<why>"` | Remove a wrongly chosen command from the required set; the withdrawal and reason stay in the table. `verifyCommands` entries cannot be withdrawn. |
| `close --feature <stem> --status done\|done-with-risks\|blocked` | Run the closing checks; on success write the frontmatter `status` and stamp `Fresh at close`. `done` is refused when any required command's latest run failed, is stale (the working tree changed after it), or never ran; when the runtime ledger's Team Lifecycle lists a partial or failed role; when the Completion `Team:` line says `partial` or `failed`; or when a `<a \| b>` placeholder remains. `done-with-risks` and `blocked` always close (structural problems are printed as warnings) and record the failed/stale commands. |
| `check [--feature <stem>]` | Read-only structural check (links, status vocabulary, placeholders, `done` consistency). Same result on every clone; never looks at runtime evidence. |

Required commands for `done` = every command run through `verify` for this feature (minus withdrawn) ∪ `verifyCommands`. The lead runs `verify`; role sessions never do. Freshness follows the chain of verify runs: a command stays fresh while every later change to the working tree was made by a later `verify` run (test output files, caches); an edit made outside `verify` makes everything before it stale, so re-run the required commands after the last code change. Local mode cannot fingerprint, so `close` stamps `Fresh at close: unknown` and you record the evidence gap under Residual risk.

Never edit a note's frontmatter `status` by hand; `close` is the only writer.

## Note sections

Feature note (`features/`): frontmatter `type, title, status, date, owner, repo, decisions`; sections in this order — **Request** (the user's words) · **Scope** (In / Out / `Size:` with the reason) · **Roles and Opinions** (one `### <role> (<label>)` per delivered memo: Position, Key evidence as repo paths, Recommendation, Open questions — a summary, never the memo verbatim; `not spawned — <reason>` for a planned role that produced no session) · **Synthesis** (Agreements, Conflicts with both sides' grounds, Hidden assumptions, Unverifiable statically) · **Challenges** (`challenger -> recipient: claim, response, effect on decision`, or `skipped — no material conflict in synthesis`) · **PL Decisions** (one line per decision plus rejected alternatives; details in `decisions/`, linked through frontmatter `decisions`) · **Implementation Summary** · **Changed Files** · **Verification** (helper-owned) · **Review** (`cycle N: Gate 1 PASS|FAIL, Gate 2 PASS|FAIL, unresolved findings`) · **Completion** (`Team: <N> role sessions (complete N[, partial N][, failed N][, not spawned N])`, Residual risk) · **Open Questions**.

Decision note (`decisions/`): frontmatter `type, title, status (accepted|superseded), date, owner, feature, supersedes, superseded_by`; sections Context · Options Considered · Decision · Rationale · Consequences · Validation · Open Questions.

Runtime ledger (`.runtime/<stem>/ledger.md`, written only through `ledger`): **Execution Ledger** table (`Task | Owner | Depends on | Deliverable | Status | Evidence`) — the only task state on both hosts; update it after every completed wave so work resumes after compaction. **Team Lifecycle** (`Spawned`, `Replaced`, `Partial`, `Failed`, `Not spawned` — labels with agent IDs). **Wave Baselines** (one `git status --porcelain` snapshot per wave, taken before the wave starts).

## Hygiene

Write summaries, not transcripts. No secrets, credentials, raw command logs, or unbounded output in committed notes (the evidence tail stays in `.runtime/`). Durable notes answer: what did we decide, why, what alternatives, what changed, how was it validated, what remains uncertain. If a helper write fails, tell the user what could not be written and where the content is, and close as `done-with-risks`.
