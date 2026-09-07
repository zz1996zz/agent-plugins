#!/usr/bin/env python3
"""Static regression tests for the personal Claude Code PL configuration."""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CLAUDE_DIR = SKILL_DIR.parents[1]
AGENTS_DIR = CLAUDE_DIR / "agents"
PL_SKILL = CLAUDE_DIR / "skills" / "pl" / "SKILL.md"
CODEX_MANIFEST = CLAUDE_DIR / ".codex-plugin" / "plugin.json"
ZSHRC = Path.home() / ".zshrc"

# Verified 2026-07-14 (Claude Code 2.1.208): a role `tools` allowlist
# strips the team coordination tools too, despite official docs saying they
# are always available. Every role must therefore list them explicitly or
# the teammate cannot deliver results, settle tasks, or answer shutdown.
TEAM_TOOLS = {"SendMessage", "TaskList", "TaskGet", "TaskUpdate"}

# references/*.md 와 agents/*.md 본문에서 금지되는 호스트 어휘. 대응은 SKILL.md Platform
# Behavior 의 매핑표에만 둔다 (스펙 4.1).
HOST_WORDS = (
    "SendMessage", "TaskList", "TaskGet", "TaskUpdate", "TaskStop",
    "spawn_agent", "send_input", "close_agent",
    "Agent Teams", "Claude Code", "Codex",
)

ROLE_CONFIG = {
    "team-pl-product-analyst": ("sonnet", {"Read", "Grep", "Glob"} | TEAM_TOOLS),
    "team-pl-qa-engineer": ("opus", {"Read", "Bash", "Grep", "Glob"} | TEAM_TOOLS),
    "team-pl-architect": ("opus", {"Read", "Grep", "Glob"} | TEAM_TOOLS),
    "team-pl-backend-engineer": (
        "sonnet",
        {"Read", "Write", "Edit", "Bash", "Grep", "Glob"} | TEAM_TOOLS,
    ),
    "team-pl-frontend-engineer": (
        "sonnet",
        {"Read", "Write", "Edit", "Bash", "Grep", "Glob"} | TEAM_TOOLS,
    ),
    "team-pl-data-engineer": (
        "sonnet",
        {"Read", "Write", "Edit", "Bash", "Grep", "Glob"} | TEAM_TOOLS,
    ),
    "team-pl-integration-reviewer": ("opus", {"Read", "Grep", "Glob"} | TEAM_TOOLS),
    "team-pl-code-reviewer": ("opus", {"Read", "Bash", "Grep", "Glob"} | TEAM_TOOLS),
    "team-pl-security-reviewer": ("opus", {"Read", "Grep", "Glob"} | TEAM_TOOLS),
}

LEGACY_ROLE_NAMES = {name.replace("team-pl-", "team-", 1) for name in ROLE_CONFIG}
IMPLEMENTATION_ROLES = {
    "team-pl-backend-engineer",
    "team-pl-frontend-engineer",
    "team-pl-data-engineer",
}


def read_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"missing frontmatter: {path}")

    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise AssertionError(f"unterminated frontmatter: {path}") from error

    result: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"unsupported frontmatter line in {path}: {line}")
        result[key.strip()] = value.strip()
    return result


def parse_tools(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def read_body(path: Path) -> str:
    # Frontmatter `tools:` legitimately names host tool APIs (SendMessage,
    # TaskList, ...); host-neutrality checks apply only to the body.
    _, _, body = path.read_text(encoding="utf-8").split("---", 2)
    return body


def read_agent_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    frontmatter = text.split("---", 2)
    if len(frontmatter) < 3 or frontmatter[0] != "":
        return None
    for line in frontmatter[1].splitlines():
        if line.startswith("name:"):
            return line.partition(":")[2].split("#", 1)[0].strip().strip("\"'") or None
    return None


class PlConfigTests(unittest.TestCase):
    def test_role_inventory_models_and_tools(self) -> None:
        role_files = {path.stem: path for path in AGENTS_DIR.glob("team-pl-*.md")}
        self.assertEqual(set(ROLE_CONFIG), set(role_files))
        for legacy_name in LEGACY_ROLE_NAMES:
            self.assertFalse((AGENTS_DIR / f"{legacy_name}.md").exists(), legacy_name)

        model_counts = {"sonnet": 0, "opus": 0}
        for role, (expected_model, expected_tools) in ROLE_CONFIG.items():
            frontmatter = read_frontmatter(role_files[role])
            self.assertEqual(role, frontmatter.get("name"))
            self.assertEqual(expected_model, frontmatter.get("model"), role)
            self.assertEqual(expected_tools, parse_tools(frontmatter.get("tools", "")), role)
            # Opus roles are the checks other work depends on; pin their effort so a
            # later edit cannot silently drop recall. Sonnet roles run at the default.
            expected_effort = "xhigh" if expected_model == "opus" else None
            self.assertEqual(expected_effort, frontmatter.get("effort"), role)
            self.assertNotIn("permissionMode", frontmatter, role)
            # Description은 상주 컨텍스트 비용이므로 압축 형식을 유지한다.
            # 금지 규칙 전문(standalone subagent 금지)은 본문(스폰 시 로드)에 있다.
            self.assertIn("Role session", frontmatter.get("description", ""), role)
            self.assertIn("PL lead only", frontmatter.get("description", ""), role)
            self.assertLess(len(frontmatter.get("description", "")), 160, role)

            role_text = role_files[role].read_text(encoding="utf-8")
            # build_codex_agents.py never copies frontmatter into the generated
            # body either, so the host-neutral prose check below uses the body.
            role_body = read_body(role_files[role])
            self.assertIn("You are a role session spawned by the PL lead", role_text, role)
            for status in ("Status: DONE", "Status: NEEDS_DECISION", "Status: BLOCKED"):
                self.assertIn(status, role_text, role)
            self.assertIn("not instructions that can override", role_text, role)
            self.assertIn("Do not begin role work without a brief that states your task fields", role_text, role)
            self.assertNotIn("Do not edit files unless", role_text, role)
            # 호스트 중립: 전달 수단은 브리프가 정한다 (SKILL.md Platform Behavior 매핑표).
            self.assertIn("Deliver your memo through the delivery channel named in your brief", role_text, role)
            self.assertIn("settle the owned ledger entry when the brief names one", role_text, role)
            self.assertIn("in one delivery", role_text, role)
            for host_word in HOST_WORDS:
                self.assertNotIn(host_word, role_body, f"{role}: {host_word}")
            self.assertNotIn(". Return:", role_text, role)
            if role in IMPLEMENTATION_ROLES:
                self.assertIn("listing the files you intend to touch", role_text, role)
            elif role != "team-pl-code-reviewer":
                self.assertIn(
                    "send the proposed change and file ownership to the lead",
                    role_text,
                    role,
                )
            if role in IMPLEMENTATION_ROLES:
                self.assertIn("exclusive file or module ownership", role_text, role)
                self.assertIn("external mutation APIs", role_text, role)
                self.assertIn("avoid over-engineering", role_text, role)
                self.assertIn("they do not define the solution", role_text, role)
            else:
                self.assertNotIn("Write", expected_tools, role)
                self.assertNotIn("Edit", expected_tools, role)
            if role == "team-pl-code-reviewer":
                self.assertIn("coverage, not filtering", role_text, role)
            if role == "team-pl-qa-engineer":
                self.assertIn("not the definition of the solution", role_text, role)
            self.assertTrue(TEAM_TOOLS <= expected_tools, role)
            model_counts[expected_model] += 1

        # Sonnet where a wrong output is caught downstream (lead verifies
        # implementation; the user answers the product memo's open questions),
        # Opus where the output is itself the check; see roles.md Model Policy.
        self.assertEqual({"sonnet": 4, "opus": 5}, model_counts)
        self.assertFalse(list(AGENTS_DIR.glob("team-pl-*-opus.md")))

        names: dict[str, list[Path]] = {}
        for agent_file in AGENTS_DIR.rglob("*.md"):
            name = read_agent_name(agent_file)
            if name:
                names.setdefault(name, []).append(agent_file)
        duplicates = {name: paths for name, paths in names.items() if len(paths) > 1}
        self.assertFalse(duplicates, duplicates)

    def test_references_and_roles_are_host_neutral(self) -> None:
        # 스펙 4.1: 호스트 이름·도구 이름은 SKILL.md Platform Behavior 에만 산다.
        # 예외: 사용자가 직접 치는 설정 명령(memory-notion 온보딩), 시스템 개선 전용 문서.
        exempt = {"memory-notion.md", "external-benchmarking.md"}
        files = [p for p in (SKILL_DIR / "references").glob("*.md") if p.name not in exempt]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for host_word in HOST_WORDS:
                self.assertNotIn(host_word, text, f"{path.name}: {host_word}")
        for path in sorted(AGENTS_DIR.glob("team-pl-*.md")):
            # Frontmatter `tools:` legitimately names host tool APIs; only the
            # post-frontmatter body is checked here.
            body = read_body(path)
            for host_word in HOST_WORDS:
                self.assertNotIn(host_word, body, f"{path.name}: {host_word}")
        notion = (SKILL_DIR / "references" / "memory-notion.md").read_text(encoding="utf-8")
        self.assertIn("codex mcp add notion --url https://mcp.notion.com/mcp", notion)
        self.assertIn("claude mcp add --scope user --transport http notion https://mcp.notion.com/mcp", notion)
        self.assertNotIn("ToolSearch", notion)

    def test_skill_entrypoints_and_references(self) -> None:
        pl_frontmatter = read_frontmatter(PL_SKILL)
        orchestrator = SKILL_DIR / "SKILL.md"
        orchestrator_frontmatter = read_frontmatter(orchestrator)

        self.assertEqual("pl", pl_frontmatter.get("name"))
        self.assertEqual("true", pl_frontmatter.get("disable-model-invocation"))
        self.assertEqual(
            "Skill(pl:team-pl-orchestrator)",
            pl_frontmatter.get("allowed-tools"),
        )
        self.assertEqual("team-pl-orchestrator", orchestrator_frontmatter.get("name"))
        self.assertEqual("false", orchestrator_frontmatter.get("user-invocable"))
        self.assertNotIn("model", pl_frontmatter)
        self.assertNotIn("model", orchestrator_frontmatter)

        pl_text = PL_SKILL.read_text(encoding="utf-8")
        orchestrator_text = orchestrator.read_text(encoding="utf-8")
        self.assertIn("$ARGUMENTS", pl_text)
        self.assertNotIn("`$ARGUMENTS`", pl_text)
        self.assertIn("\n$ARGUMENTS\n", pl_text)
        self.assertIn("on Codex the request is the remainder of the user message after `$pl`", pl_text)
        self.assertIn("read `../team-pl-orchestrator/SKILL.md` relative to this file", pl_text)
        self.assertIn("invoke `pl:team-pl-orchestrator` with the `Skill` tool", pl_text)
        self.assertLess(len(pl_text.splitlines()), 40)
        self.assertLess(len(pl_frontmatter.get("description", "")), 1536)
        self.assertLess(len(orchestrator_frontmatter.get("description", "")), 1536)
        for required in (
            "### Host mapping",
            "### Claude Code (Agent Teams)",
            "### Codex CLI (subagents)",
            "| role session |",
            "| delivery channel |",
            "| task ledger |",
            "| peer challenge |",
            "| close session |",
            "| skill dir (`<skill-dir>`) |",
            "| data dir (`<data-dir>`) |",
            "| repo-local config |",
            "every enabled session already has one implicit team",
            "`TeamCreate` and `TeamDelete` no longer exist",
            "allowlist strips the team coordination tools",
            "read the matching session file under `~/.claude/projects/`",
            "`install-codex.sh`",
            "become required fields of the spawn brief",
            "actual app, CLI, or service path",
            "done-with-risks",
            "Never ask a role session to spawn further sessions",
            "Do not substitute a dynamic `Workflow`",
            "do not silently downgrade to ordinary subagents",
            "`.agents/pl.local.md`",
            "`.claude/pl.local.md`",
        ):
            self.assertIn(required, pl_text + "\n" + orchestrator_text, required)
        # 호스트 변수는 hooks.json 밖에서 쓰지 않는다 (스펙 4.2 <skill-dir>/<data-dir>).
        # 유일한 허용 정의 지점은 SKILL.md 의 Host mapping 표 Claude 열이다.
        for path in sorted(SKILL_DIR.rglob("*.md")) + [PL_SKILL]:
            if path == SKILL_DIR / "SKILL.md":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("CLAUDE_PLUGIN_ROOT", text, path)
            self.assertNotIn("CLAUDE_PLUGIN_DATA", text, path)
        self.assertEqual(1, orchestrator_text.count("CLAUDE_PLUGIN_ROOT"))
        self.assertEqual(1, orchestrator_text.count("CLAUDE_PLUGIN_DATA"))

        # Single-source layout: catalog/model/spawn policy lives only in
        # roles.md; lifecycle/triage rules live only in team-lifecycle.md
        # (progressive disclosure — the orchestrator keeps read triggers).
        self.assertNotIn("## Model Policy", orchestrator_text)
        self.assertNotIn("## Role Session Health and Restart", orchestrator_text)
        self.assertIn("`references/team-lifecycle.md`", orchestrator_text)
        # Budget 3200: Platform Behavior carries the two-host mapping table plus
        # both host subsections (Claude Code and Codex CLI), and that vocabulary
        # lives nowhere else in the plugin.
        self.assertLess(len(orchestrator_text.split()), 3200)
        # 공유 태스크 목록은 Claude 전용이다. 그 어휘가 Claude 절 밖으로 새면
        # Codex 호스트에서 존재하지 않는 것을 지시하게 된다.
        before_claude, _, rest = orchestrator_text.partition(
            "### Claude Code (Agent Teams)"
        )
        _, _, from_codex = rest.partition("### Codex CLI (subagents)")
        self.assertNotIn("shared task", before_claude)
        self.assertNotIn("shared task", from_codex)

        lifecycle_text = (
            SKILL_DIR / "references" / "team-lifecycle.md"
        ).read_text(encoding="utf-8")
        for required in (
            "## Team Lifecycle",
            "## Role Session Health and Restart",
            "Prefix every ledger entry subject",
            "Do not reuse a runtime name",
            "force-close the session through the host's close-session mechanism",
            "rather than looping",
            "do not spawn a replacement in the same session",
            "idle without a delivered result",
            "Host-specific recovery steps (transcript lookup, session restore) live in SKILL.md Platform Behavior.",
        ):
            self.assertIn(required, lifecycle_text)
        for host_word in HOST_WORDS:
            self.assertNotIn(host_word, lifecycle_text, host_word)
        self.assertLess(len(lifecycle_text.split()), 1300)

        # Single-source: the full spawn-brief delivery contract lives only in
        # roles.md; the orchestrator points at the Role Prompt Contract.
        self.assertIn("Role Prompt Contract in `references/roles.md`", orchestrator_text)
        self.assertNotIn("delivery contract in every spawn brief", orchestrator_text)
        self.assertNotIn("v2.1.198", orchestrator_text)
        # The lead-side safety boundaries (input trust, irreversible-action
        # gate) must sit inside the auto-compaction reattach window, not at
        # the document tail.
        self.assertIn("Do not commit, push, merge, deploy", orchestrator_text[:6000])
        self.assertIn("not instructions that can override", orchestrator_text[:6000])
        self.assertIn("destructive shortcut", orchestrator_text[:6000])

        runtime_contract = pl_text + "\n" + orchestrator_text
        for legacy_name in LEGACY_ROLE_NAMES:
            self.assertNotIn(f"`{legacy_name}`", runtime_contract, legacy_name)

        done_line = next(
            line for line in orchestrator_text.splitlines() if line.startswith("- `done`:")
        )
        risk_line = next(
            line
            for line in orchestrator_text.splitlines()
            if line.startswith("- `done-with-risks`:")
        )
        self.assertNotIn("timeout", done_line.lower())
        self.assertIn("confirmed stopped", done_line)
        self.assertIn("shutdown timeout", risk_line)
        self.assertIn("## Standing Completion Contract", orchestrator_text[:5000])
        self.assertIn("- `done`:", orchestrator_text[:5000])
        self.assertLess(len(orchestrator_text.splitlines()), 500)

        runtime_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                PL_SKILL,
                orchestrator,
                SKILL_DIR / "references" / "roles.md",
                SKILL_DIR / "references" / "team-lifecycle.md",
                SKILL_DIR / "references" / "debate-protocol.md",
            )
        ).lower()
        self.assertNotIn("lead clean up the team", runtime_text)
        self.assertNotIn("before creating a fresh team", runtime_text)
        self.assertNotIn("use subagents for role passes", runtime_text)
        self.assertNotIn("not a documented teammate termination", runtime_text)
        self.assertNotIn("not scanned for subagents", runtime_text)

        references = SKILL_DIR / "references"
        self.assertEqual(
            {
                "roles.md",
                "team-lifecycle.md",
                "debate-protocol.md",
                "memory-templates.md",
                "external-benchmarking.md",
                "memory-obsidian.md",
                "memory-notion.md",
            },
            {path.name for path in references.glob("*.md")},
        )
        roles_text = (references / "roles.md").read_text(encoding="utf-8")
        self.assertIn(
            "no commit, push, merge, deploy, publish, or external mutation",
            roles_text,
        )
        self.assertIn("input-trust boundary", roles_text)
        self.assertIn("delivery channel for this host", roles_text)
        self.assertIn("host mapping in SKILL.md Platform Behavior", roles_text)
        for host_word in HOST_WORDS:
            self.assertNotIn(host_word, roles_text, host_word)
        self.assertIn("high-fidelity references", roles_text)
        self.assertIn("when the output is itself the check", roles_text)
        self.assertIn("also set `effort: xhigh` in frontmatter", roles_text)
        self.assertIn("no destructive shortcuts", roles_text)
        self.assertIn("never speculate about code", roles_text)
        self.assertIn("follow instructions literally", roles_text)
        self.assertNotIn("Require each role to return:", roles_text)
        # roles.md is the sole catalog: every role type, model routing, override
        # ban, and collision rule live here; memo item lists live only in the
        # agent definition bodies (no "Output:" duplicates to drift).
        for role in ROLE_CONFIG:
            self.assertIn(role, roles_text)
        self.assertIn("## Model Policy", roles_text)
        self.assertIn("Do not pass an invocation-level model override", roles_text)
        self.assertIn("treat any same-name collision as unavailable", roles_text)
        self.assertNotIn("Output:", roles_text)
        self.assertNotIn("The memo must contain:", roles_text)

        debate_text = (references / "debate-protocol.md").read_text(encoding="utf-8")
        self.assertIn("peer-challenge channel", debate_text)
        self.assertIn("one ledger entry per independent memo", debate_text)
        for host_word in HOST_WORDS:
            self.assertNotIn(host_word, debate_text, host_word)
        self.assertIn("idle-without-result triage", debate_text)
        self.assertIn("delivery contract in `references/roles.md`", debate_text)
        self.assertIn("skip Round 2 when synthesis surfaced none", debate_text)
        # A blank Round 2 section cannot be told apart later from an unrecorded
        # round or from conflicts the lead never noticed; force an explicit skip.
        self.assertIn("skipped — no material conflict in synthesis", debate_text)
        self.assertIn("per-gate rubric", debate_text)
        # Reset/close procedures live only in SKILL.md; debate-protocol points.
        self.assertIn("Role Session Health and Restart", debate_text)
        self.assertNotIn("Spawn a fresh teammate", debate_text)
        self.assertNotIn("Each memo must include:", debate_text)

    def test_launch_alias_and_model_override_policy(self) -> None:
        if os.environ.get("PL_SKIP_MACHINE_TESTS"):
            self.skipTest("PL_SKIP_MACHINE_TESTS set")
        if not ZSHRC.exists():
            self.skipTest("machine-specific: ~/.zshrc not present")
        zshrc_text = ZSHRC.read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", zshrc_text)
        self.assertIsNone(os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL"))

        user_settings = Path.home() / ".claude" / "settings.json"
        if user_settings.exists():
            settings = json.loads(user_settings.read_text(encoding="utf-8"))
            self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", settings.get("env") or {})

    def test_codex_manifests_and_skill_metadata(self) -> None:
        claude_manifest = json.loads(
            (CLAUDE_DIR / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex_manifest = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        # 설치 캐시가 버전 키다. 두 호스트의 버전이 갈리면 한쪽 사용자에게만 변경이 전파된다.
        self.assertEqual(claude_manifest["version"], codex_manifest["version"])
        self.assertEqual("pl", codex_manifest["name"])
        self.assertEqual("./skills/", codex_manifest["skills"])
        self.assertEqual("./hooks/hooks.json", codex_manifest["hooks"])
        # Notion MCP 는 번들하지 않는다 (README 정책).
        self.assertNotIn("mcpServers", codex_manifest)

        marketplace = json.loads(
            (CLAUDE_DIR.parents[1] / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("zz1996zz", marketplace["name"])
        entry = next(p for p in marketplace["plugins"] if p["name"] == "pl")
        self.assertEqual({"source": "local", "path": "./plugins/pl"}, entry["source"])

        # Claude 의 disable-model-invocation: true 에 대응하는 Codex 메타데이터.
        pl_meta = (CLAUDE_DIR / "skills" / "pl" / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("allow_implicit_invocation: false", pl_meta)
        orch_meta = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", orch_meta)

    def test_python_helpers_compile(self) -> None:
        for script in SCRIPT_DIR.glob("*.py"):
            compile(script.read_text(encoding="utf-8"), str(script), "exec")

    def test_no_machine_specific_paths(self) -> None:
        # Exclude this test file itself: its own assertion below necessarily
        # embeds the literal marker string it checks for in every other file.
        # Any user home path (macOS/Linux) is machine-specific; also catch the
        # current runner's home for exotic layouts.
        machine_path = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")
        home = str(Path.home())
        self_path = Path(__file__).resolve()
        for path in sorted(SKILL_DIR.rglob("*")) + sorted(AGENTS_DIR.glob("*.md")) + [PL_SKILL]:
            if path.is_file() and path.suffix in {".md", ".py"} and path.resolve() != self_path:
                text = path.read_text(encoding="utf-8")
                found = machine_path.search(text)
                self.assertIsNone(found, f"{path}: {found.group(0) if found else ''}")
                self.assertNotIn(home, text, path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
