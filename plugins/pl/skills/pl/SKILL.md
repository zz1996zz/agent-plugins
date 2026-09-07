---
name: pl
description: Short alias for the team PL orchestrator. Use when the user invokes /pl or asks a PL/tech-lead agent to run feature work. For non-trivial feature work, explicitly spawn Claude Code Agent Teams teammates, not ordinary subagents, before implementation; run role-agent discussion, make decisions, implement, test, and update the user-selected memory backend (Obsidian vault or Notion).
argument-hint: "[feature request]"
disable-model-invocation: true
allowed-tools: Skill(pl:team-pl-orchestrator)
---

# PL

Gate: if you have not yet invoked `pl:team-pl-orchestrator` through the `Skill` tool for this request, do nothing else — no analysis, no clarifying question, no code exploration — invoke it first, then follow it. Re-invoke it whenever its instructions are no longer in context (after auto-compaction or `/resume`). This keeps the orchestrator instructions in the skill lifecycle across turns.

Treat explicit `/pl` invocation as explicit permission to use the team PL orchestration workflow for the current request, including role-agent discussion, implementation, verification, and memory backend updates.

## Hard rules (binding even when the orchestrator skill is not loaded)

- For non-trivial feature work, do not begin implementation until the orchestrator has inspected current tasks and explicitly spawned the required Claude Code Agent Teams teammates using the namespaced `pl:team-pl-*` agent types; never substitute ordinary standalone subagents.
- Do not commit, push, merge, deploy, publish, or mutate external systems unless the user explicitly requested that action.
- Update the memory backend feature note before closing, and never report `done` without fresh verification evidence.

## Request

$ARGUMENTS

If the `Skill` tool or hidden skill is unavailable, read ../team-pl-orchestrator/SKILL.md directly and follow it as the fallback source of truth.
