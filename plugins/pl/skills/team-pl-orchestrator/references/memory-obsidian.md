# Memory Adapter: Obsidian Vault

Use this adapter only when the user config says `backend: obsidian`. `<vault-root>` below is the `obsidian.root` value from `pl_user_config.py show`. `<skill-dir>` and `<data-dir>` are defined in SKILL.md Platform Behavior (Host mapping).

## Onboarding (first run)

1. Ask for the vault path (suggest `~/Documents/obsidian/memory`). The path may be a fresh directory.
2. Save: `python3 "<skill-dir>/scripts/pl_user_config.py" --config "<data-dir>/config.json" init --backend obsidian --obsidian-root <answer>`
3. Verify: `python3 "<skill-dir>/scripts/memory_note.py" --root <vault-root> check` — a fresh vault reports `memory check ok`.

## Contract Operations

- **Recall**: read `<vault-root>/INDEX.md`, then only relevant notes from `work/<work-slug>/` plus global notes.
- **Ensure work**: `python3 "<skill-dir>/scripts/memory_note.py" --root <vault-root> init-work <work-slug> --repo <repo-path>`
- **Create feature note**: `python3 "<skill-dir>/scripts/memory_note.py" --root <vault-root> feature <work-slug> "<feature title>" --repo <repo-path>`
- **Update ledger**: edit the feature note file directly, replacing whole sections (`## Execution Ledger`, `## PL Decisions`, …) per `memory-templates.md`.
- **Record decision**: `python3 "<skill-dir>/scripts/memory_note.py" --root <vault-root> decision <work-slug> "<decision title>" --feature features/<feature-file>.md`
- **Integrity check**: `python3 "<skill-dir>/scripts/memory_note.py" --root <vault-root> check` whenever links or indexes changed. If the helper is not found at `<skill-dir>/scripts/`, search the plugin tree for it first; a missing helper may be recorded as an evidence gap only after that search fails.

The helper enforces the status vocabulary, slug rules, index sync, and link validation; prefer it over hand-writing new notes. After changing the helper itself, run `python3 "<skill-dir>/scripts/test_memory_note.py"` first.

## Pending replay

When writing a pending file for this backend, set its frontmatter target line to the vault-relative path, e.g. `target: obsidian:work/<work-slug>/features/<file>.md`.
When replaying `<data-dir>/pending/*.md` into this backend, write each note to its target path (recorded in the pending file's frontmatter `target:` line) only after comparing content; if the target already exists, merge section-by-section instead of overwriting newer content.
