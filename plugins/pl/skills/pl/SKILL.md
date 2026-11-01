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

명시 호출(`/pl:pl`, `$pl`, `pl:pl`)은 현재 요청에 역할 세션·구현·검증·히스토리 기록을 사용하는 허가다. Codex에서는 frontmatter의 `Skill(...)`, `hooks`, `$ARGUMENTS` 치환을 실행 기능으로 가정하지 않는다. 본문에서 지시한 상대 경로를 직접 읽고 실제 사용자 요청을 전달한다.

## Hard rules (binding even when the orchestrator skill is not loaded)

- 비단순 작업은 orchestrator가 규모와 역할을 정한 뒤 host mapping의 단계 순서를 따른다. `full`은 분석 역할 응답 뒤에 구현하고, `light`는 리드 구현 뒤 reviewer를 실행한다. 역할은 `team-pl-*` 정의를 사용한다. 새 파일·테스트 추가나 `full` 요청은 solo가 아니다.
- Do not commit, push, merge, deploy, publish, or mutate external systems unless the user explicitly requested that action.
- For non-trivial feature work, record the feature note in the repository history and close it with `pl_history.py close` before reporting. A solo pass on a routine change writes no note. Never report `done` without fresh verification evidence.

## Request

$ARGUMENTS

On Claude Code the line above is substituted with the request; on Codex the request is the remainder of the user message after `$pl`.
