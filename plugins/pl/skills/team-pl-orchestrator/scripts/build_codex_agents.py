#!/usr/bin/env python3
"""Generate Codex CLI custom-agent TOML files from the Claude Code agent definitions.

Codex cannot bundle agents inside a plugin (openai/codex#18988), so the generated
files under agents/codex/ are copied into $CODEX_HOME/agents/ by install-codex.sh.
Source of truth stays agents/team-pl-*.md; never edit the TOML by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_AGENTS_DIR = PLUGIN_ROOT / "agents"
DEFAULT_OUT_DIR = DEFAULT_AGENTS_DIR / "codex"

# Role tier -> Codex model. Verified 2026-09-08 at https://learn.chatgpt.com/docs/models
# (redirects from https://developers.openai.com/codex/models).
# opus tier: gpt-6-astra — "our most capable model for complex work across code,
# apps, and research" (top tier). sonnet tier: gpt-5.6-terra — "a balanced GPT-5.6
# model for everyday work" (standard/default tier).
MODEL_MAP: dict[str, str] = {
    "opus": "gpt-6-astra",
    "sonnet": "gpt-5.6-terra",
}
DEFAULT_EFFORT = "high"
# Claude tools that mutate the working tree. Their presence decides sandbox_mode.
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def parse_agent(text: str) -> tuple[dict[str, str], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise ValueError("missing frontmatter")
    end = lines.index("---", 1)
    frontmatter: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"unsupported frontmatter line: {line}")
        frontmatter[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :]).strip("\n") + "\n"
    return frontmatter, body


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_multiline(value: str) -> str:
    # Literal multi-line strings need no escaping unless the body contains '''.
    if "'''" not in value:
        return f"'''\n{value}'''"
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"""')
    return f'"""\n{escaped}"""'


def render_toml(frontmatter: dict[str, str], body: str) -> str:
    name = frontmatter["name"]
    model_tier = frontmatter.get("model", "")
    if model_tier not in MODEL_MAP:
        raise ValueError(f"{name}: unknown model tier {model_tier!r}; expected one of {sorted(MODEL_MAP)}")
    tools = {t.strip() for t in frontmatter.get("tools", "").split(",") if t.strip()}
    sandbox = "workspace-write" if tools & EDIT_TOOLS else "read-only"
    effort = frontmatter.get("effort") or DEFAULT_EFFORT
    return (
        f"# Generated from ../{name}.md by build_codex_agents.py — do not edit; edit the .md and rebuild.\n"
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(frontmatter.get('description', ''))}\n"
        f"model = {_toml_string(MODEL_MAP[model_tier])}\n"
        f"model_reasoning_effort = {_toml_string(effort)}\n"
        f"sandbox_mode = {_toml_string(sandbox)}\n"
        f"developer_instructions = {_toml_multiline(body)}\n"
    )


def build(agents_dir: Path, out_dir: Path, check: bool) -> int:
    sources = sorted(agents_dir.glob("team-pl-*.md"))
    if not sources:
        print(f"no agent sources under {agents_dir}", file=sys.stderr)
        return 2
    expected = {f"{src.stem}.toml": render_toml(*parse_agent(src.read_text(encoding="utf-8"))) for src in sources}
    if check:
        drift = [
            name
            for name, text in expected.items()
            if not (out_dir / name).is_file() or (out_dir / name).read_text(encoding="utf-8") != text
        ]
        drift += [p.name for p in out_dir.glob("*.toml") if p.name not in expected]
        if drift:
            print("codex agents out of date: " + ", ".join(sorted(drift)), file=sys.stderr)
            return 1
        print(f"codex agents up to date ({len(expected)} files)")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in expected.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    for stale in out_dir.glob("*.toml"):
        if stale.name not in expected:
            stale.unlink()
    print(f"wrote {len(expected)} codex agents to {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents-dir", type=Path, default=DEFAULT_AGENTS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", action="store_true", help="exit 1 if the generated files differ")
    args = parser.parse_args(argv)
    return build(args.agents_dir, args.out_dir, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
