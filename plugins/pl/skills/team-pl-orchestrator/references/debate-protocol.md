# Debate Protocol

The discussion-to-close loop for `full` work. `light`는 Implementation·리뷰 1회·Close를 수행한다. 리뷰에서 수정이 필요하면 같은 reviewer를 재개해 확인하며 아래 three cycles 상한을 따른다.

## Round 0: Brief

Before spawning, add one Execution Ledger row per planned memo with `pl_history.py ledger row` (`history.md`): task `<label>-memo` (고유 인스턴스 라벨 전체), owner label, dependencies, deliverable (the memo plus `read-only` or the editable files, and `Run: <command>` when a runnable check decides completion), status `pending`. 같은 역할의 복수 세션은 `roles.md`의 Role instances·Labels 규칙으로 scope와 task ID를 분리한다. Then build each brief from the Role brief contract in `roles.md` and spawn the stage's roles in one message (host mapping in SKILL.md Platform Behavior).

## Round 1: Independent memos

Each role answers independently; do not show other roles' memos during Round 1. A memo is the session's final response (where the host's memo-capture hook runs, it is also saved under `.runtime/<stem>/memos/`; read those files when present). 부분 결과는 남은 작업·장애 원인을 확인해 진행 가능하면 같은 세션을 재개한다. 완료하지 못한 결과는 `partial`로 기록하고, 반복 실패·정체는 `roles.md`의 Replacement 규칙을 따른다.

After each spawn, `ledger lifecycle Spawned "<label> (<agent id>)"`. Record every delivered memo as a summary under Roles and Opinions in the feature note. 배정된 완료 조건을 충족한 최종 응답을 실제 수신했을 때만 해당 ledger row를 `done`으로 기록한다(`ledger row <task> --status done --evidence "<memo id>"`). 재개 중인 부분 결과는 행에 진행 상태와 근거를 남긴다. 최종 미완료·실패 세션만 Team Lifecycle의 `Partial`/`Failed`에 기록하고, `BLOCKED` 또는 부분 응답을 받았다는 이유만으로 행을 완료하지 않는다.

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
   분할 리뷰에서는 모든 요구사항·결정에 담당 reviewer label을 연결하고 누락이 없는지 확인한다. 각 reviewer의 두 gate 결과를 개별 기록한 뒤, reviewer 한 명을 재개하거나 통합 reviewer를 배정해 전체 diff의 공통 경로·기능 간 상호작용과 두 gate를 검토한다. 범위별 PASS만으로 전체 PASS를 선언하지 않는다.
3. Both gates must pass: Gate 1 (spec/decision compliance) outranks Gate 2 (quality). Fix Critical before any progress and Important before closing; record Minor. After every fix, re-run the required verification commands through `verify` before re-review — evidence older than the fix is stale.
4. 테스트 파일이 바뀌거나 Verify가 실패했을 때만 해당 scope의 QA 세션을 실제 ID로 재개해 coverage review를 받는다(`light`에서 QA 세션이 없으면 리드가 점검한다). 분할 QA 세션 중 변경에 해당하는 범위를 선택한다. Add `team-pl-security-reviewer` (`diff-review` mode) or `team-pl-integration-reviewer` when the changed surface touches their lanes.
5. The lead validates every finding against the repo and may drop one with written grounds; relay each reviewer's findings as given, with the lead's verdict beside them. Only conflicts that touch product scope go to the user. With several reviewers, merge like Synthesis: overlapping findings first, conflicting advice with both sides' grounds, then one list of items no reviewer could verify statically, then a fix order by severity and blast radius.
6. **At most three cycles.** A cycle is review → fix → re-review, recorded in the feature note's Review section as `cycle N`. Re-review only when the fix changed the risk surface. If Critical or Important findings remain after cycle 3, stop fixing: list them under Review, close as `done-with-risks` when the implementation works and `blocked` when it is unsafe, and hand the decision to the user.

## Close

Settle every ledger row (never mark abandoned work complete; record abandonment). Fill Completion's `Team:` line from the runtime ledger's Team Lifecycle. Bring feature and decision notes up to date, then run `pl_history.py close` with the status the Standing Completion Contract in SKILL.md yields. Stop any role session still running; completed sessions need nothing.
