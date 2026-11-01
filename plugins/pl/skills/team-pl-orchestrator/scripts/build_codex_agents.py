#!/usr/bin/env python3
"""공유 역할 정의로부터 선택 설치용 Codex custom-agent TOML을 생성한다.

원본은 agents/team-pl-*.md와 references/roles.md의 shared preamble이다.
Claude의 model·effort·tools·maxTurns를 Codex 설정으로 변환하지 않는다.
Codex의 일반 subagent 기본값은 외부 config가 결정하고, sandbox는 부모의
설정을 따른다. 역할의 편집 범위는 공유 본문과 lead brief에 명시한다.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_AGENTS_DIR = PLUGIN_ROOT / "agents"
DEFAULT_OUT_DIR = DEFAULT_AGENTS_DIR / "codex"
ROLES_MD = SCRIPT_DIR.parent / "references" / "roles.md"
PREAMBLE_START = "<!-- preamble:start -->"
PREAMBLE_END = "<!-- preamble:end -->"

def load_preamble(roles_md: Path = ROLES_MD) -> str:
    text = roles_md.read_text(encoding="utf-8")
    start = text.index(PREAMBLE_START) + len(PREAMBLE_START)
    end = text.index(PREAMBLE_END)
    return text[start:end].strip() + "\n"


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
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"""\n{escaped}"""'


def render_toml(frontmatter: dict[str, str], body: str, preamble: str = "") -> str:
    name = frontmatter["name"]
    if preamble:
        body = preamble.rstrip("\n") + "\n\n" + body
    lines = [
        f"# Generated from ../{name}.md by build_codex_agents.py — do not edit; edit the .md and rebuild.\n",
        f"name = {_toml_string(name)}\n",
        f"description = {_toml_string(frontmatter.get('description', ''))}\n",
    ]
    lines.append(f"developer_instructions = {_toml_multiline(body)}\n")
    return "".join(lines)


def build(agents_dir: Path, out_dir: Path, check: bool) -> int:
    sources = sorted(agents_dir.glob("team-pl-*.md"))
    if not sources:
        print(f"no agent sources under {agents_dir}", file=sys.stderr)
        return 2
    expected: dict[str, str] = {}
    preamble = load_preamble()
    for src in sources:
        text = render_toml(*parse_agent(src.read_text(encoding="utf-8")), preamble=preamble)
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"{src.name}: generated invalid TOML: {exc}") from exc
        expected[f"{src.stem}.toml"] = text
    if check:
        drift = [
            name
            for name, text in expected.items()
            if not (out_dir / name).is_file() or (out_dir / name).read_text(encoding="utf-8") != text
        ]
        drift += [p.name for p in out_dir.glob("team-pl-*.toml") if p.name not in expected]
        if drift:
            print("codex agents out of date: " + ", ".join(sorted(drift)), file=sys.stderr)
            return 1
        print(f"codex agents up to date ({len(expected)} files)")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in expected.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    for stale in out_dir.glob("team-pl-*.toml"):
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
