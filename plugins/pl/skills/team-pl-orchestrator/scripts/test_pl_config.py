#!/usr/bin/env python3
"""Invariant tests for the pl plugin's prompt documents, manifests, and hook wiring.

These pin structure (frontmatter values, file sets, headings, budgets, forbidden
references) rather than sentences, so wording can change without touching tests.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PLUGIN_DIR = SKILL_DIR.parents[1]
REPO_DIR = PLUGIN_DIR.parents[1]
AGENTS_DIR = PLUGIN_DIR / "agents"
HOOKS_DIR = PLUGIN_DIR / "hooks"
PL_SKILL = PLUGIN_DIR / "skills" / "pl" / "SKILL.md"
ORCHESTRATOR = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
CLAUDE_MANIFEST = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = PLUGIN_DIR / ".codex-plugin" / "plugin.json"
MARKETPLACES = (REPO_DIR / ".claude-plugin" / "marketplace.json", REPO_DIR / ".agents" / "plugins" / "marketplace.json")

TEAM_TOOLS = {"SendMessage", "TaskList", "TaskGet", "TaskUpdate", "Agent"}
ROLE_TOOLS = {
    "team-pl-product-analyst": {"Read", "Grep", "Glob"},
    "team-pl-architect": {"Read", "Grep", "Glob"},
    "team-pl-qa-engineer": {"Read", "Bash", "Grep", "Glob"},
    "team-pl-backend-engineer": {"Read", "Write", "Edit", "Bash", "Grep", "Glob"},
    "team-pl-frontend-engineer": {"Read", "Write", "Edit", "Bash", "Grep", "Glob"},
    "team-pl-data-engineer": {"Read", "Write", "Edit", "Bash", "Grep", "Glob"},
    "team-pl-code-reviewer": {"Read", "Bash", "Grep", "Glob"},
    "team-pl-security-reviewer": {"Read", "Grep", "Glob"},
    "team-pl-integration-reviewer": {"Read", "Grep", "Glob"},
}
CHECK_ROLES = {
    "team-pl-architect", "team-pl-qa-engineer", "team-pl-code-reviewer",
    "team-pl-security-reviewer", "team-pl-integration-reviewer",
}
# Host vocabulary stays in SKILL.md's Platform Behavior; references and agent bodies are host-neutral.
HOST_WORDS = ("SendMessage", "TaskList", "TaskStop", "spawn_agent", "send_input", "close_agent", "Agent Teams", "Claude Code", "Codex")
# Things the 0.5.0 redesign removed; none may come back into a runtime prompt.
FORBIDDEN_RUNTIME_REFERENCES = (
    "memory_note", "pl_user_config", "TeamCreate", "TeamDelete", "explain-diff", "`/verify`",
    "Obsidian", "Notion", "memory-templates", "memory-obsidian", "memory-notion", "team-lifecycle.md",
    "external-benchmarking", "TaskUpdate", "TeammateIdle",
)
GUARD_COMMAND = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"'


def read_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"missing frontmatter: {path}"
    end = lines.index("---", 1)
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#") or line.startswith(" ") or line.startswith("-"):
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


def read_frontmatter_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # YAML double-quoted scalars escape inner quotes; compare against the decoded command.
    return text.split("---", 2)[1].replace('\\"', '"')


def read_body(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[2]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


class RoleDefinitionTests(unittest.TestCase):
    def test_role_inventory_and_frontmatter(self) -> None:
        names = {p.stem for p in AGENTS_DIR.glob("team-pl-*.md")}
        self.assertEqual(set(ROLE_TOOLS), names)
        seen: set[str] = set()
        for path in sorted(AGENTS_DIR.glob("team-pl-*.md")):
            fm = read_frontmatter(path)
            self.assertEqual(path.stem, fm["name"], path.name)
            self.assertNotIn(fm["name"], seen, "duplicate agent name")
            seen.add(fm["name"])
            tools = {t.strip() for t in fm["tools"].split(",")}
            self.assertEqual(ROLE_TOOLS[path.stem], tools, path.name)
            self.assertFalse(tools & TEAM_TOOLS, path.name)
            self.assertEqual("inherit", fm["model"], path.name)
            self.assertTrue(int(fm["maxTurns"]) > 0, path.name)
            if path.stem in CHECK_ROLES:
                self.assertEqual("xhigh", fm.get("effort"), path.name)
            else:
                self.assertNotIn("effort", fm, path.name)
            self.assertNotIn("hooks", fm, f"{path.name}: plugin agents ignore hooks frontmatter")

    def test_role_bodies_are_host_neutral_and_carry_contract(self) -> None:
        for path in sorted(AGENTS_DIR.glob("team-pl-*.md")):
            body = read_body(path)
            self.assertTrue(body.strip(), path.name)
            for word in HOST_WORDS:
                self.assertNotIn(word, body, f"{path.name}: {word}")
            self.assertIn("Your lane:", body, path.name)
            self.assertIn("Status: DONE | NEEDS_DECISION | BLOCKED", body, path.name)
            self.assertIn("Unverifiable statically:", body, path.name)
            self.assertIn("Key files:", body, path.name)
            self.assertIn("Do not run pl_history.py", body, path.name)

    def test_agents_directory_has_no_stray_markdown(self) -> None:
        stray = [p.name for p in AGENTS_DIR.glob("*.md") if not p.name.startswith("team-pl-")]
        self.assertEqual([], stray)


class ReferenceTests(unittest.TestCase):
    def test_reference_set(self) -> None:
        self.assertEqual({"roles.md", "debate-protocol.md", "history.md"}, {p.name for p in REFERENCES.glob("*.md")})

    def test_references_are_host_neutral(self) -> None:
        for path in sorted(REFERENCES.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.strip(), path.name)
            for word in HOST_WORDS:
                self.assertNotIn(word, text, f"{path.name}: {word}")

    def test_roles_md_markers(self) -> None:
        text = (REFERENCES / "roles.md").read_text(encoding="utf-8")
        self.assertIn("<!-- preamble:start -->", text)
        self.assertIn("<!-- preamble:end -->", text)
        for heading in ("## Work sizing", "## Role menu", "## Labels", "## Role brief contract", "## Replacement"):
            self.assertIn(heading, text, heading)
        for size in ("`solo`", "`light`", "`full`"):
            self.assertIn(size, text)
        self.assertIn("never pass a `name`", text)

    def test_debate_protocol_markers(self) -> None:
        text = (REFERENCES / "debate-protocol.md").read_text(encoding="utf-8")
        for heading in ("## Round 0", "## Round 1", "## Synthesis", "## User decisions", "## Round 2", "## Decide", "## Implementation", "## Review Loop", "## Close"):
            self.assertIn(heading, text, heading)
        self.assertIn("skipped — no material conflict in synthesis", text)
        self.assertIn("three cycles", text)
        self.assertIn("Wave Baselines", text)
        self.assertIn("diff.patch", text)

    def test_history_md_documents_every_helper_command(self) -> None:
        text = (REFERENCES / "history.md").read_text(encoding="utf-8")
        for command in ("where", "feature", "decision", "list", "current", "ledger", "diff", "verify", "close", "check"):
            self.assertRegex(text, rf"`{command}\b", command)
        self.assertIn("docs/pl", text)
        self.assertIn(".runtime/", text)
        self.assertIn("Fresh at close", text)


class SkillTests(unittest.TestCase):
    def test_orchestrator_budgets_and_contract_position(self) -> None:
        text = ORCHESTRATOR.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 500)
        self.assertLessEqual(len(text.split()), 2600)
        head = text[:5000]
        self.assertIn("## Standing Completion Contract", head)
        self.assertIn("- `done`:", head)
        self.assertIn("## Safety Boundaries", head)

    def test_orchestrator_workflow_and_references(self) -> None:
        text = ORCHESTRATOR.read_text(encoding="utf-8")
        for ref in ("references/roles.md", "references/debate-protocol.md", "references/history.md"):
            self.assertIn(ref, text, ref)
        for marker in ("pl_history.py", "where --json", "verify --feature", "close --feature", "## Platform Behavior", "## Workflow", ".agents/pl.md"):
            self.assertIn(marker, text, marker)
        self.assertIn("never pass a `name`", text)
        # sizing lives inline in the workflow: a lead that skips the references must still size correctly
        for marker in ("`solo` only when ALL hold", "never `solo`", "`full` otherwise", "First look for a size word",
                       "`full` never goes straight to implementation", "ledger baseline"):
            self.assertIn(marker, text, marker)

    def test_runtime_prompts_have_no_removed_references(self) -> None:
        runtime = [PL_SKILL, ORCHESTRATOR, *REFERENCES.glob("*.md"), *AGENTS_DIR.glob("team-pl-*.md")]
        for path in runtime:
            text = path.read_text(encoding="utf-8")
            for word in FORBIDDEN_RUNTIME_REFERENCES:
                self.assertNotIn(word, text, f"{path.name}: {word}")
        # the one allowed mention of teammates explains why spawns carry no name
        orch = ORCHESTRATOR.read_text(encoding="utf-8").lower()
        self.assertLessEqual(orch.count("teammate"), 1)

    def test_skill_frontmatter_hooks(self) -> None:
        pl_fm = read_frontmatter(PL_SKILL)
        self.assertEqual("true", pl_fm["disable-model-invocation"])
        self.assertEqual("Skill(pl:team-pl-orchestrator)", pl_fm["allowed-tools"])
        for path in (PL_SKILL, ORCHESTRATOR):
            block = read_frontmatter_block(path)
            self.assertIn("hooks:", block, path.name)
            self.assertIn("PreToolUse:", block, path.name)
            self.assertIn(GUARD_COMMAND, block, path.name)
            self.assertNotIn("--scope role", block, f"{path.name}: skill hooks judge the lead unconditionally")
        # memo capture lives in the plugin hooks: skill-frontmatter SubagentStop hooks did not fire
        # for role subagents in the 2026-10-20 live run, plugin hooks did.
        orch_block = read_frontmatter_block(ORCHESTRATOR)
        self.assertNotIn("SubagentStop:", orch_block)

    def test_pl_alias_gate(self) -> None:
        text = PL_SKILL.read_text(encoding="utf-8")
        self.assertIn("pl:team-pl-orchestrator", text)
        self.assertIn("$ARGUMENTS", text)
        self.assertIn("## Hard rules", text)


class HookTests(unittest.TestCase):
    def test_hook_files_and_modes(self) -> None:
        claude = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
        codex = json.loads((HOOKS_DIR / "hooks.codex.json").read_text(encoding="utf-8"))
        claude_cmd = claude["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        codex_cmd = codex["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertEqual(f"{GUARD_COMMAND} --scope role", claude_cmd)
        self.assertEqual(GUARD_COMMAND, codex_cmd)
        self.assertEqual("Bash", claude["hooks"]["PreToolUse"][0]["matcher"])
        self.assertEqual("^pl:team-pl-", claude["hooks"]["SubagentStop"][0]["matcher"])
        self.assertIn("memo_capture.py", claude["hooks"]["SubagentStop"][0]["hooks"][0]["command"])
        self.assertEqual("SubagentHandback", claude["hooks"]["PostToolUse"][0]["matcher"])
        self.assertNotIn("SubagentStop", codex["hooks"])
        self.assertFalse((HOOKS_DIR / "guard.sh").exists())
        for script in ("guard.py", "memo_capture.py"):
            self.assertTrue(os.access(HOOKS_DIR / script, os.X_OK), script)

    def test_python_helpers_import_on_this_interpreter(self) -> None:
        for path in (SCRIPT_DIR / "pl_history.py", HOOKS_DIR / "guard.py", HOOKS_DIR / "memo_capture.py"):
            module = load_module(path)
            self.assertTrue(callable(getattr(module, "main")), path.name)

    def test_no_jq_dependency_in_plugin(self) -> None:
        for path in list(HOOKS_DIR.glob("*")) + [PLUGIN_DIR / "install-codex.sh"]:
            if path.is_file():
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"\bjq\b", path.name)


class ManifestTests(unittest.TestCase):
    def test_manifests_agree(self) -> None:
        claude = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
        codex = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual(claude["description"], codex["description"])
        self.assertEqual("pl", codex["name"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual("./hooks/hooks.codex.json", codex["hooks"])
        self.assertNotIn("mcpServers", codex)
        for marketplace in MARKETPLACES:
            data = json.loads(marketplace.read_text(encoding="utf-8"))
            self.assertEqual("zz1996zz", data["name"])
            entry = next(p for p in data["plugins"] if p["name"] == "pl")
            self.assertEqual(claude["description"], entry["description"], marketplace)
            # Claude marketplaces use a path string; Codex marketplaces use the object form.
            self.assertIn(entry["source"], ("./plugins/pl", {"source": "local", "path": "./plugins/pl"}), marketplace)

    def test_openai_skill_metadata(self) -> None:
        for path in (PLUGIN_DIR / "skills" / "pl" / "agents" / "openai.yaml", SKILL_DIR / "agents" / "openai.yaml"):
            self.assertIn("allow_implicit_invocation: true", path.read_text(encoding="utf-8"), path)

    def test_no_machine_specific_paths(self) -> None:
        machine_path = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")
        home = str(Path.home())
        self_path = Path(__file__).resolve()
        roots = [PLUGIN_DIR, REPO_DIR / "tests", REPO_DIR / ".github"]
        for root in roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix not in {".md", ".py", ".sh", ".json", ".yml", ".toml"}:
                    continue
                if path.resolve() == self_path or ".git" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                found = machine_path.search(text)
                self.assertIsNone(found, f"{path}: {found.group(0) if found else ''}")
                self.assertNotIn(home, text, path)


class MachineTests(unittest.TestCase):
    def test_no_subagent_model_override_on_this_machine(self) -> None:
        if not os.environ.get("PL_MACHINE_TESTS"):
            self.skipTest("opt-in: set PL_MACHINE_TESTS=1")
        self.assertIsNone(os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL"))
        user_settings = Path.home() / ".claude" / "settings.json"
        if user_settings.exists():
            settings = json.loads(user_settings.read_text(encoding="utf-8"))
            self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", settings.get("env") or {})


if __name__ == "__main__":
    unittest.main(verbosity=1)
