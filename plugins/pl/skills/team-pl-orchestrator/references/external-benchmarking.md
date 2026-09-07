# External Benchmarking

Use this checklist only when improving, auditing, or redesigning the PL/team-agent operating system.

## Source Mix

Sample across multiple repo types instead of copying one popular pattern:
- Official references: Claude Code docs for Agent Teams, subagents, dynamic workflows, skills, commands, hooks, and plugins.
- Subagent catalogs: broad role libraries with `name`, `description`, `tools`, and `model` frontmatter.
- Slash-command workflow repos: user-invoked commands for repeatable engineering workflows.
- Skill/plugin marketplaces: `SKILL.md` packages with scripts, references, assets, and progressive disclosure.
- Real project showcases: repos that combine `.claude/agents`, `.claude/skills`, hooks, settings, and workflow docs.
- Multi-agent orchestration repos: planners, dependency graphs, parallel waves, review gates, and memory systems.
- Cross-tool skill repos: projects that keep Agent Skills portable across Claude Code, Codex, Cursor, Gemini, and GitHub Copilot.
- Codex CLI multi-agent setups: `.codex/agents/*.toml` role definitions, `.agents/skills/` skill layouts, and `hooks.json` guards — pl now runs on Codex too, so compare against both ecosystems.

## Minimum Review Standard

Before making a material system change:
1. Check current official Claude Code docs first.
2. Review at least eight public GitHub repositories from at least five source-mix categories.
3. Extract only portable patterns with clear operational value.
4. Reject patterns that increase token cost, coordination cost, or permission risk without a concrete benefit.
5. Prefer small local changes over adopting a large framework.
6. Record each inspected repository URL, commit SHA, inspection date, adopted patterns, and rejected alternatives in the relevant decision note of the configured memory backend.
7. Search community examples for removed or version-sensitive APIs before copying lifecycle instructions. For Claude Code v2.1.178+, `TeamCreate` and `TeamDelete` are stale even when they appear in a recently updated repository.
8. Check agent-name collisions and scope precedence. Managed, CLI, and project subagents override user-level definitions with the same name, so reusable personal roles need a distinctive namespace and a fail-closed collision path.
9. When a search excerpt and current official docs disagree, inspect the current `llms-full.txt` source and the changelog matching the installed release before changing runtime policy. Search indexes can lag versioned tool contracts.

## Seed Repositories

Use current search results rather than treating this list as exhaustive. The full inspected-repository provenance (URL, commit SHA, inspection date, adopted/rejected patterns) lives in the configured memory backend's decision notes for this work.

- `anthropics/claude-code`: authoritative changelog for runtime contracts and removed tools.
- `anthropics/skills`: official Agent Skills examples and marketplace packaging.
- `wshobson/agents`: plugin marketplace including native Agent Teams task, communication, ownership, and shutdown patterns.
- `wshobson/commands`: production slash-command workflows and multi-agent command organization.
- `obra/superpowers`: fresh-context task execution, independent review, and evidence-before-completion gates.
- `aws-samples/sample-claude-code-agent-team`: native shared-task contracts, direct messaging, verification gates, and bounded team sizing.
- `pcliangx/AppGenesisForge`: current implicit-team migration, staged role retirement, file-ownership checks, and runtime-version ADRs.
- `github/spec-kit`: specification, clarification, acceptance checklist, and constitution-driven delivery gates.
- `HumanLayer/12-factor-agents`: owned context, explicit control flow, compact errors, and small focused agents.
- `trailofbits/claude-code-config`: least-privilege role tools plus mechanical guards for dangerous shell operations.

## Adoption Filter

Adopt a pattern only when it improves one of:
- Role selection accuracy
- Teammate lifecycle control
- Model/tool cost control
- Parallel work safety
- Verification discipline
- Durable decision memory
- User command ergonomics

Do not adopt:
- Huge role catalogs without a real use case
- Commands that duplicate existing skills
- Always-on external research for normal coding tasks
- Broad write permissions for review-only roles
- Frameworks that require maintaining generated state by hand
- Community instructions that call removed tools or contradict the installed Claude Code version
- Completion rules that treat an unconfirmed teammate shutdown timeout as successful cleanup
- Generic user-level agent names that can be shadowed silently by repository definitions
