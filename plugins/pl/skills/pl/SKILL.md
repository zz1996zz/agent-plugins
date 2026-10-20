---
name: pl
description: Short alias for the team PL orchestrator. Use when the user invokes /pl or asks a PL/tech-lead agent to run feature work. Sizes the work, spawns role subagents through the host mapping for non-trivial features, runs role discussion, decides, implements, verifies with recorded evidence, and keeps the decision history in the repository's docs/pl.
argument-hint: "[feature request]"
disable-model-invocation: true
allowed-tools: Skill(pl:team-pl-orchestrator)
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/guard.py\""
---

# PL

Gate: if you have not yet loaded the orchestrator skill for this request, do nothing else — no analysis, no clarifying question, no code exploration — load it first, then follow it. On Claude Code invoke `pl:team-pl-orchestrator` with the `Skill` tool; on Codex read `../team-pl-orchestrator/SKILL.md` relative to this file and follow it — `<skill-dir>` in the orchestrator means that `team-pl-orchestrator` directory, not this one. Re-load it whenever its instructions are no longer in context (after context compaction or a session restore).

Treat explicit invocation (`/pl:pl` or `$pl`) as explicit permission to use the team PL workflow for the current request, including role-session discussion, implementation, verification, and history updates in the repository.

## Hard rules (binding even when the orchestrator skill is not loaded)

- For non-trivial feature work, do not begin implementation until the orchestrator has sized the work and spawned the required role sessions from the `team-pl-*` definitions through its host mapping; never substitute ordinary standalone helpers.
- Do not commit, push, merge, deploy, publish, or mutate external systems unless the user explicitly requested that action.
- For non-trivial feature work, record the feature note in the repository history and close it with `pl_history.py close` before reporting. A solo pass on a routine change writes no note. Never report `done` without fresh verification evidence.

## Request

$ARGUMENTS

On Claude Code the line above is substituted with the request; on Codex the request is the remainder of the user message after `$pl`.
