# Debate Protocol

The discussion-to-close loop for `full` work. `light` work runs only Implementation, Review Loop (one cycle), and Close.

## Round 0: Brief

Before spawning, add one Execution Ledger row per planned memo with `pl_history.py ledger row` (`history.md`): task `<role>-memo`, owner label, dependencies, deliverable (the memo plus `read-only` or the editable files, and `Run: <command>` when a runnable check decides completion), status `pending`. Then build each brief from the Role brief contract in `roles.md` and spawn the stage's roles in one message (host mapping in SKILL.md Platform Behavior).

## Round 1: Independent memos

Each role answers independently; do not show other roles' memos during Round 1. A memo is the session's final response (where the host's memo-capture hook runs, it is also saved under `.runtime/<stem>/memos/`; read those files when present). A session that returns a partial result (`maxTurns`) is resumed once to finish, or recorded as `partial`.

After each spawn, `ledger lifecycle Spawned "<label> (<agent id>)"`; a partial or failed session goes under `Partial`/`Failed`. Record every delivered memo as a summary under Roles and Opinions in the feature note, and set its ledger row to `done` with the evidence (`ledger row <task> --status done --evidence "<memo id>"`).

## Synthesis

The lead writes the Synthesis section: agreements; conflicts with both sides' evidence (never average them or silently pick a winner); hidden assumptions; decisions required; the proposed implementation plan; the proposed verification plan; and one merged list of everything the roles marked `Unverifiable statically` — role sessions cannot check runtime wiring, and that check is the lead's in Verify.

Overlap is signal: lanes are disjoint (`roles.md`), so the same finding from two roles is a defect visible from two directions and goes to the top of the work list.

## User decisions

Collect every `Status: NEEDS_DECISION` and every item under the product analyst's `Decisions needed` that concerns product scope, priority, or user-visible behavior, and ask the user once, in one batched message. The lead decides technical questions itself. Do not proceed to Decide while a user-facing decision is open; if the user cannot answer now, close as `blocked` with the questions listed.

## Round 2: Challenge

Assign one challenge per material disagreement or risky untested assumption surfaced in synthesis — not one per role as a quota — and skip Round 2 when synthesis surfaced none. A challenge names the claim, cites repo or requirement evidence, and states what would change the recommendation. Deliver it by resuming the target session (agent ID) on either host; the answer accepts, rejects, or narrows the claim with evidence and restates the revised conclusion. Run more rounds only for a material unresolved conflict; stop when the lead can state the selected option, rejected alternatives, risks, and validation plan without unresolved assumptions.

Record the outcome in the feature note's Challenges section either way: the challenges and their effect, or `skipped — no material conflict in synthesis`.

## Decide

The lead decides; do not average opinions. Choose by user goal, existing repo patterns, maintainability, risk, testability, reversibility. Record each durable decision with `pl_history.py decision` and one line under PL Decisions; a decision that replaces an earlier note supersedes it instead of deleting it.

Then convert the decisions into dependency-aware Execution Ledger rows with one owner per task and one owner per file, and only then run the analyze gate: every decision maps to at least one row, every row traces back to the plan, and no accepted decision or required deliverable lacks a row. Resolve mismatches before any edit. For complex or risky delegated edits, require the role's plan (its intended paths and approach) before it edits.

## Implementation

Prefer one final integrator: the lead owns integration and prevents same-file overlap. Delegate edits only with isolated file or module ownership; role sessions share the working directory, so never let two sessions edit the same file. Run only unblocked rows in parallel. At every interface handoff the producing session's memo carries the exact contract and evidence; the lead forwards it to the consumer when it resumes or spawns that session.

**Wave baseline and change-shape gate.** Before each delegated wave, run `pl_history.py ledger baseline "<wave label>"` (it saves `git status --porcelain` under Wave Baselines). After the wave, before accepting any deliverable, diff the new `git status --porcelain` against that baseline; every path that appeared or changed must fall inside the union of the wave's ownership lists, excluding the history root and paths the lead itself edited, and must not touch `protectedPaths`. A path outside every list is an ownership violation regardless of whether the change looks correct: do not accept the wave, ask the owning session to revert or justify it, and record the incident in the ledger. Update the Execution Ledger after each completed wave.

## Review Loop

1. Run `pl_history.py diff [--base <sha>]` (writes `.runtime/<stem>/diff.patch`) and summarize the diff.
2. Spawn `team-pl-code-reviewer` only now, with scoped context: accepted requirements, PL decisions, the `BASE..HEAD` range, the diff summary, and the diff path — never the lead's session history or reasoning, so the review judges the artifact. Each accepted requirement and decision becomes a `Gate 1 items` entry the reviewer answers individually.
3. Both gates must pass: Gate 1 (spec/decision compliance) outranks Gate 2 (quality). Fix Critical before any progress and Important before closing; record Minor. After every fix, re-run the required verification commands through `verify` before re-review — evidence older than the fix is stale.
4. Resume `pl-qa` for a coverage review only when test files changed or Verify found a failure (in `light` work, where no QA session exists, the lead does this check itself). Add `team-pl-security-reviewer` (`diff-review` mode) or `team-pl-integration-reviewer` when the changed surface touches their lanes.
5. The lead validates every finding against the repo and may drop one with written grounds; relay each reviewer's findings as given, with the lead's verdict beside them. Only conflicts that touch product scope go to the user. With several reviewers, merge like Synthesis: overlapping findings first, conflicting advice with both sides' grounds, then one list of items no reviewer could verify statically, then a fix order by severity and blast radius.
6. **At most three cycles.** A cycle is review → fix → re-review, recorded in the feature note's Review section as `cycle N`. Re-review only when the fix changed the risk surface. If Critical or Important findings remain after cycle 3, stop fixing: list them under Review, close as `done-with-risks` when the implementation works and `blocked` when it is unsafe, and hand the decision to the user.

## Close

Settle every ledger row (never mark abandoned work complete; record abandonment). Fill Completion's `Team:` line from the runtime ledger's Team Lifecycle. Bring feature and decision notes up to date, then run `pl_history.py close` with the status the Standing Completion Contract in SKILL.md yields. Stop any role session still running; completed sessions need nothing.
