# Memory Adapter: Notion (official MCP)

Use this adapter only when the user config says `backend: notion`. Notion is the source of truth — do not silently fall back to local files. All calls go through the official Notion MCP server (`notion`, `https://mcp.notion.com/mcp`); the plugin does not bundle it — onboarding step 1 connects it. Load its tools through the host's tool discovery (SKILL.md Host mapping). `<root-page>` is the `notion.rootPage` value from `pl_user_config.py show`.

## Onboarding (first run)

1. Check for Notion MCP tools. If the server is not connected, ask the user to add it once at user scope and authenticate, then retry:

   | Host | Add the server | Authenticate |
   |---|---|---|
   | Claude Code | `claude mcp add --scope user --transport http notion https://mcp.notion.com/mcp` | run `/mcp` and complete the Notion OAuth |
   | Codex CLI | `codex mcp add notion --url https://mcp.notion.com/mcp` | `codex mcp login notion` |

   If the server exists but is unauthenticated, only the authenticate step is needed. Verify the connection by calling search.
2. Ask the user for the root page URL (they create or pick one page in the shared workspace).
3. Fetch the root page to confirm access.
4. Create two databases under the root page (skip any that already exist):
   - **Features** — properties: `Title` (title), `Status` (select: `in-progress`, `done`, `done-with-risks`, `blocked`), `Date` (date), `Owner` (text), `Work` (select), `Repo` (text), `Decisions` (relation → Decisions).
   - **Decisions** — properties: `Title` (title), `Status` (select: `accepted`, `superseded`), `Date` (date), `Owner` (text), `Work` (select), `Feature` (relation → Features), `Supersedes` (relation → Decisions, self).
   If the MCP tools cannot create a property type (e.g. relation), create what is possible, then give the user exact manual steps for the rest and wait.
5. Create a `Works` child page under the root page (holds one architecture subpage per work namespace).
6. Save: `python3 "<skill-dir>/scripts/pl_user_config.py" --config "<data-dir>/config.json" init --backend notion --notion-root-page <url>`

## Contract Operations

- **Recall**: query the Features and Decisions databases filtered by `Work = <work-slug>` (recent first); fetch pages relevant to the request plus the `Works/<work-slug>` architecture page. Use Notion search scoped to the root page for free-form recall.
- **Ensure work**: confirm the `Work` select option and the `Works/<work-slug>` architecture page exist; create the architecture page from the `memory-templates.md` architecture template if missing.
- **Create feature note**: create a page in Features with all properties set and the body sections from `memory-templates.md` (same headings, same order). Title = feature title; `Date` = today; `Status` = `in-progress`.
- **Update ledger**: update the feature page content by replacing whole sections (`## Execution Ledger`, `## PL Decisions`, …). Never append duplicate section headings — replace in place.
- **Record decision**: create a page in Decisions with properties set, body from the decision template, and the `Feature` relation pointing at the feature page. When superseding, set `Supersedes` and update the old page's `Status` to `superseded` instead of deleting it.
- **Integrity check**: before closing, confirm on every touched page — `Status` uses the allowed vocabulary, each decision has its `Feature` relation, and the feature's `Decisions` relation lists every decision created this run. Report any mismatch instead of guessing.

## Failure handling

If any write fails or the MCP is unreachable mid-work, save the complete intended note content under `<data-dir>/pending/<date>-<slug>.md` with a frontmatter line `target: notion:<database>/<title>`, report it, and close as `done-with-risks` per SKILL.md. On replay, search the target database for a page with the same title and `Work`; update it if found (upsert), create it otherwise.
