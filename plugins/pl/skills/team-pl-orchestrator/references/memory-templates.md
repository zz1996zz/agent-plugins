# Memory Templates

Use these templates in the configured memory backend (see the adapter references).

## Contents

- Note Format
- Workspace Layout
- Feature Note
- Decision Note
- Architecture Note

## Note Format

Feature and decision notes start with YAML frontmatter (OKF-compatible: `type`, `title`, `status`, `date`, `owner`, `work`, plus `repo`/`status_note`/`tags` when relevant). Frontmatter is the single machine-read surface: Obsidian indexes it natively (property search, Bases/Dataview) and agents can read only the first lines of a file to know its state without parsing the body. Relational links (`Related decisions:`, `Related feature:`, etc.) stay in the body under the H1 so link validation and backlink insertion keep working. Do not duplicate frontmatter fields as plain body lines; legacy unmigrated notes with a plain `Status:` line are still accepted by `check` as a fallback only. A feature note's `status` is one of `in-progress`, `done`, `done-with-risks`, or `blocked`; the Completion section's `Status:` line carries the same value, optionally followed by a short reason.

## Workspace Layout

Store new work under a 업무/project namespace (path shown for the Obsidian backend; the Notion adapter maps the same structure to databases):

```text
<vault-root>/
  INDEX.md
  work/
    <work-slug>/
      INDEX.md
      features/
        YYYY-MM-DD-feature-slug.md
      decisions/
        YYYY-MM-DD-decision-slug.md
      architecture/
        README.md
```

Selection rule:
- If the user names a 업무/project/product, slugify that name.
- Otherwise, if the repository has `pl.local.md` with `workNamespace` in its frontmatter (see SKILL.md, Repo-local config), use that slug.
- Otherwise use the canonical repository name: the basename of `git remote get-url origin` with any `.git` suffix removed. With no remote, use the main repository directory name (resolve `git rev-parse --git-common-dir` to the repository root) — never the worktree or workspace directory name; some launchers run sessions in renamed worktrees. Outside a git repository, treat the namespace as unclear.
- If neither is clear, ask the user one concise question to name the namespace; only when that is not possible, use `inbox` as a temporary namespace and record why.

Never put unrelated 업무 A and 업무 B in the same feature note or decision folder.

Use relative Markdown links between feature and decision notes. The feature note links to every durable decision, and each decision links back to its feature. Keep superseded notes; mark their status and successor instead of deleting history.

## Feature Note

Path: `work/<work-slug>/features/YYYY-MM-DD-feature-slug.md`

```markdown
---
type: Feature
title: "<name>"
status: in-progress
date: <YYYY-MM-DD>
owner: PL agent
work: <work-slug>
repo: "<path or repo name>"
---

# Feature: <name>

Related decisions:
Related PR/commit:

## Request

<user request>

## Scope

In:
- 

Out:
- 

## Relevant Memory

- 

## Roles

- product-analyst:
- architect:
- qa-engineer:
- code-reviewer:
- selected conditional roles:

## Team Lifecycle

- Spawned:
- Reused:
- Replaced:
- Shut down:
- Force-stopped:
- Unconfirmed stop:
- Runtime cleanup: host-owned
- Role sandbox: <inherited from lead session | read-only enforced>

## Discussion Summary

### Round 1

### Synthesis

### Round 2

### Direct Challenges

- <challenger> -> <recipient>: <claim, response, effect on decision>

## PL Decisions

- 

## Implementation Plan

1. 

## Execution Ledger

| Task | Owner | Depends on | Deliverable | Status | Evidence |
|---|---|---|---|---|---|
| T1 |  |  |  | pending |  |

## Implementation Summary

- 

## Changed Files

- 

## Verification

- Command:
- Result:
- Fresh after final code change: yes/no
- Notes:

## Completion

- Status: in-progress
- Residual risk:

## Open Questions

- 
```

In the feature note's `## PL Decisions` section, refer to a decision note only through the `Related decisions:` wikilink at the top of the feature note; never spell a decision note's filename in prose — a filename written twice will diverge.

## Decision Note

Path: `work/<work-slug>/decisions/YYYY-MM-DD-decision-slug.md`

```markdown
---
type: Decision
title: "<name>"
status: accepted
date: <YYYY-MM-DD>
owner: PL agent
work: <work-slug>
---

# Decision: <name>

Related feature:
Related files:
Related sources:
Supersedes:
Superseded by:

## Context

<why this decision was needed>

## Options Considered

1. 
2. 
3. 

## Decision

<selected option>

## Rationale

<evidence and reasoning summary>

## Consequences

Positive:
- 

Negative:
- 

## Validation

- 

## Open Questions

- 
```

## Architecture Note

Path (Obsidian): `work/<work-slug>/architecture/README.md` — `memory_note.py init-work` creates it automatically, embedding this same structure. Notion: the `Works/<work-slug>` page content.

```markdown
# Architecture: <work-slug>

Status: draft
Owner: PL agent

## Summary

## Current Shape

## Important Constraints

## Common Change Points

## Verification Notes
```
