# Debate Protocol

Use this protocol to create productive role-agent discussion without uncontrolled chatter.

## Contents

- Round 0: Brief
- Round 1: Independent Role Memos
- Synthesis
- Round 2: Critique
- Role Session Reset
- Decision
- Implementation
- Review Loop
- Close
- Memory Hygiene

## Round 0: Brief

Create a shared brief:
- User request
- Relevant memory
- Current repo facts
- Constraints
- Proposed role roster
- Predictable role session runtime names
- Expected deliverables
- Acceptance criteria and evidence required

Create one ledger entry per independent memo (a shared task where the host has one; otherwise the same fields go into the spawn brief and the feature note). Each entry must state:
- A subject prefixed with `[<feature-slug>]`
- Task ID and owner
- Dependencies
- Bounded deliverable
- Success criteria
- Files the role session may edit, or `read-only`
- The verification command that decides completion (`Run: <command>`), when the task has a runnable check

## Round 1: Independent Role Memos

Ask each selected role to respond independently. Do not show other role outputs during Round 1.

Each memo leads with its `Status:` line and covers the deliverable items defined in the role's definition body.

The delivery contract in `references/roles.md` governs every memo. Never treat an idle or finished signal alone as a delivered memo: if a role session goes idle without one, run the idle-without-result triage in `references/team-lifecycle.md` (ledger state, host recovery steps, one explicit delivery nudge) before any reset.

## Synthesis

The PL lead summarizes:
- Agreements
- Conflicts
- Hidden assumptions
- Decisions required
- Proposed implementation plan
- Proposed verification plan

Read overlap as signal, not duplication. Lanes are disjoint by design (`references/roles.md` Lane Discipline), so when two roles independently raise the same point it is a defect visible from two directions — it goes to the top of the work list, not into a deduplicated pile. When two roles' advice pulls in opposite directions, carry both sides' evidence into the decision; do not silently pick a winner or average them. Collect every item a role marked as unverifiable from static reading into one list — role sessions cannot check runtime wiring, and that check is the lead's.

## Round 2: Critique

Use the host's peer-challenge channel for material critique instead of sending every message to everyone. Assign one peer challenge per material disagreement or risky untested assumption surfaced in synthesis — not one per role as a quota — and skip Round 2 when synthesis surfaced none. The recipient answers each challenge. Ask for:
- What is wrong or missing?
- Which decision is risky?
- Which simpler option should be considered?
- What must be tested?

Each challenge must name the claim, cite repo or requirement evidence, and state what would change the recommendation. Each response must accept, reject, or narrow the claim with evidence. Both role sessions then deliver the PL a concise revised conclusion. The delivery contract and the idle-without-result triage apply to challenge answers and revised conclusions exactly as to Round 1 memos.

Run more rounds only when there is a material unresolved conflict. Stop when the PL can state the selected option, rejected alternatives, risks, and validation plan without relying on unresolved assumptions.

Record the outcome either way in the feature note's `### Round 2` section: the challenges assigned, or `skipped — no material conflict in synthesis`. Left blank, a correctly skipped round is indistinguishable later from one that ran unrecorded or from conflicts the lead never noticed.

## Role Session Reset

Use reset instead of repeated prompting when a role session gives stale, irrelevant, wrong-role, wrong-model, or obviously low-quality output. Reset targets bad output, not merely undelivered output; for an idle role session with no delivered memo, complete the idle-without-result triage in `references/team-lifecycle.md` first.

Before any reset, save useful facts from the role session's output into the PL synthesis, and settle or reassign its ledger entry without marking abandoned work complete. Then follow the replacement procedure in `references/team-lifecycle.md` under Role Session Health and Restart. Use at most one repair prompt before reset. Do not let one confused role session dominate the discussion.

## Decision

The PL lead decides. Do not average opinions. Choose the option that best fits:
- User goal
- Existing repo patterns
- Maintainability
- Risk
- Testability
- Reversibility

Record durable decisions in memory.

Before any edit, run an analyze gate: check that the decisions, the implementation plan, and the ledger entries are consistent — every decision maps to at least one entry, every entry traces back to the plan, and no accepted decision or required deliverable is missing an entry. Resolve mismatches before delegating work; a gap here surfaces later as unowned or contradictory implementation.

Before delegated implementation, convert the decision into dependency-aware ledger entries. Assign one owner per task and one owner per file. For complex or risky edits, require plan approval before the implementation role session can edit.

## Implementation

Prefer one final integrator. Role sessions share the working directory, so avoid having multiple agents edit the same files. Delegate implementation edits only when the lead can isolate ownership by file or module. Use separate worktrees only when the PL explicitly provisions and coordinates them.

Run only unblocked tasks in parallel. At every interface handoff, the producing role session delivers the exact contract and evidence to the consumer through the host's peer-challenge channel (via the lead where sessions cannot message each other). Update the feature-note execution ledger after each completed wave so work can resume safely after compaction.

**Change-shape gate.** After each delegated wave, before accepting any deliverable, run `git status --porcelain` (it covers modified and untracked files) and compare every path against the union of the file/module ownership lists on that wave's ledger entries, plus `protectedPaths` from `pl.local.md` (Repo-local config in SKILL.md) when present. A path outside every list is an ownership violation regardless of whether the change looks correct: do not accept the wave, ask the owning role session to revert the path or justify it, and record the incident in the execution ledger. The one-owner-per-file rule above is only as real as this check — without it a violation surfaces later as a conflicting edit or not at all.

Do not coordinate role work through ad hoc messages alone: every active role session must own a visible ledger entry. After the lead accepts a role session's final deliverable and no revision, dependency, or re-review remains, ask that role session to close instead of retaining an idle session.

## Review Loop

After implementation:
1. Summarize the diff.
2. Spawn code-reviewer on the final diff and accepted requirements; do not keep it idle before a diff exists. Brief it with scoped context only — accepted requirements and PL decisions, the `BASE_SHA..HEAD_SHA` range, and the diff summary — and never the lead's session history or reasoning trace, so the review judges the artifact, not the process. Convert the brief into a per-gate rubric: each accepted requirement and PL decision becomes a checkable Gate 1 item, and the Gate 2 quality dimensions become items, so the reviewer returns a verdict per item instead of free-form impressions.
3. Require two ordered review gates, both of which must pass:
   - Gate 1 — spec/decision compliance: the diff satisfies the accepted requirements and PL decisions, with no silent scope drift.
   - Gate 2 — code quality: correctness, maintainability, behavior changes, and missing tests.
   A clean Gate 2 pass does not accept work that fails Gate 1. Rank findings by severity: fix Critical before any progress, Important before closing, and record Minor.
4. Ask QA to verify test coverage.
5. Ask data-engineer, integration-reviewer, or security-reviewer when the changed surface touches those areas.
6. Validate reviewer findings against the repo, fix material issues, rerun relevant tests, and re-review changed risk surfaces.
7. When more than one reviewer ran, merge their reports the way Synthesis does: overlapping findings first (highest confidence — the lanes are disjoint), conflicting advice with both sides' grounds for the user to decide, one merged list of items no reviewer could verify statically, then a fix order by severity and blast radius. Relay each reviewer's findings as given — do not re-tier or reword them, and do not fold your own findings into their sections.

## Close

Close the feature under `SKILL.md`: confirm no required task is pending or merely stale, read fresh verification output instead of trusting role session completion claims, bring feature and decision notes up to date, then follow the completion-or-cancellation checklist in `references/team-lifecycle.md` Team Lifecycle (close, force-close confirmation, lifecycle evidence) and run the memory link/index check. Classify the result under the Standing Completion Contract.

## Memory Hygiene

Write summaries, not transcripts. Do not store secrets, credentials, or raw command logs. Durable notes should help a future LLM answer:
- What did we decide?
- Why?
- What alternatives were considered?
- What changed?
- How was it validated?
- What remains uncertain?
