---
name: pl
description: Short alias for the team PL orchestrator. Use when the user invokes /pl or asks a PL/tech-lead agent to run feature work. For non-trivial feature work, explicitly spawn role sessions through the host mapping, not ordinary helpers, before implementation; run role-agent discussion, make decisions, implement, test, and update the user-selected memory backend (Obsidian vault or Notion).
argument-hint: "[feature request]"
disable-model-invocation: true
allowed-tools: Skill(pl:team-pl-orchestrator)
---

# PL

Gate: if you have not yet loaded the orchestrator skill for this request, do nothing else — no analysis, no clarifying question, no code exploration — load it first, then follow it. On Claude Code invoke `pl:team-pl-orchestrator` with the `Skill` tool; on Codex read `../team-pl-orchestrator/SKILL.md` relative to this file and follow it. Re-load it whenever its instructions are no longer in context (after context compaction or a session restore). This keeps the orchestrator instructions in the skill lifecycle across turns.

Treat explicit invocation (`/pl:pl` or `$pl`) as explicit permission to use the team PL orchestration workflow for the current request, including role-session discussion, implementation, verification, and memory backend updates.

## Hard rules (binding even when the orchestrator skill is not loaded)

- For non-trivial feature work, do not begin implementation until the orchestrator has inspected the task ledger and explicitly spawned the required role sessions from the `team-pl-*` role definitions through the host mapping in its Platform Behavior; never substitute ordinary standalone helpers.
- Do not commit, push, merge, deploy, publish, or mutate external systems unless the user explicitly requested that action.
- For non-trivial feature work, update the memory backend feature note before closing. A solo pass on a routine change writes no note. Never report `done` without fresh verification evidence.

## Request

$ARGUMENTS

On Claude Code the line above is substituted with the request; on Codex the request is the remainder of the user message after `$pl`.

If the `Skill` tool or hidden skill is unavailable, read `../team-pl-orchestrator/SKILL.md` relative to this file directly and follow it as the fallback source of truth.
