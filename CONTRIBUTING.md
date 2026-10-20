# Contributing

Maintainer rules for this repository. They are not loaded into any agent's runtime prompt; `pl`'s orchestrator points here when a user asks to improve or audit pl itself.

## Test matrix

Run after any change under `plugins/pl/`:

```bash
S=plugins/pl/skills/team-pl-orchestrator/scripts
python3 "$S/test_pl_config.py"          # prompt-document invariants, manifests, hooks
python3 "$S/test_pl_history.py"         # history helper behavior (needs git)
python3 "$S/test_hooks.py"              # memo_capture hook
python3.11 "$S/test_build_codex_agents.py"   # Codex agent generator (tomllib → 3.11+)
python3.11 "$S/build_codex_agents.py" --check   # after editing agents/team-pl-*.md or the preamble in references/roles.md; drop --check to regenerate
bash tests/pl-guard/run-unit.sh         # safety hook deny/allow matrix
bash tests/pl-e2e/run-unit.sh           # E2E verdict logic (no model)
bash tests/pl-codex/run-install-unit.sh # install-codex.sh
claude plugin validate plugins/pl       # manifest + hook quoting
```

Runtime helpers (`pl_history.py`, `hooks/guard.py`, `hooks/memo_capture.py`) must run on Python 3.9 (macOS default `python3`); only the generator and its test need 3.11. Shell scripts must run on bash 3.2.

After changing `SKILL.md`, `references/`, or `agents/`, run the real-session safety E2E before merging (costs tokens): `bash tests/pl-e2e/run-safety.sh`, and `bash tests/pl-e2e/run-safety-codex.sh` when `codex` is installed. See `tests/pl-e2e/README.md`.

Bump `version` in both `plugins/pl/.claude-plugin/plugin.json` and `plugins/pl/.codex-plugin/plugin.json` for any change under `plugins/` (CI enforces it). Keep the four manifest descriptions identical.

## Changing the operating model

Before a material change to how pl sizes work, spawns roles, debates, verifies, or records history, compare against current official docs and public examples:

1. Read the current Claude Code docs for subagents, skills, hooks, and plugins, and the Codex CLI docs for custom agents, subagent tools, and hooks. Search indexes lag versioned tool contracts; when a search excerpt and the current docs disagree, the docs win.
2. Review at least eight public repositories from at least five of these categories: official references, subagent catalogs, slash-command workflow repos, skill/plugin marketplaces, real project showcases, multi-agent orchestration repos, cross-tool skill repos, Codex CLI multi-agent setups.
3. Adopt a pattern only when it improves role-selection accuracy, lifecycle control, model/tool cost, parallel-work safety, verification discipline, durable decision history, or command ergonomics — and reject anything that adds token, coordination, or permission cost without a concrete benefit. Prefer small local changes over adopting a framework.
4. Do not adopt: huge role catalogs, commands that duplicate existing skills, always-on external research for ordinary coding, broad write permissions for review-only roles, frameworks that require hand-maintained generated state, community instructions that call removed tools, generic agent names that a repository definition can shadow.
5. Record inspected repositories (URL, commit SHA, date, adopted and rejected patterns) in the pl decision note for the change (`docs/pl/decisions/`).

## Facts verified against official docs (keep current)

- Claude Code: plugin agents honor `tools`, `model`, `effort`, `maxTurns`; they ignore `hooks`, `mcpServers`, `permissionMode`. A named spawn becomes a teammate while Agent Teams is enabled; pl therefore spawns without `name`. Skill-frontmatter hooks register when the skill loads and stay for the session. Plugin hooks run inside subagents with `agent_type` = `pl:team-pl-<role>`. `${CLAUDE_PLUGIN_DATA}` is deleted on uninstall, so history never lives there.
- Codex CLI: custom-agent TOML `sandbox_mode` is never applied (the parent session's sandbox is). Multi-agent tools: `spawn_agent`, `send_input`, `resume_agent`, `wait_agent`, `close_agent`. No skill-scoped hooks; plugin hooks need a one-time trust review in `/hooks`.
- Default `python3` on macOS is 3.9.
