#!/usr/bin/env python3
"""pl history helper: in-repo markdown feature/decision notes with verification evidence.

Repo mode: history lives at <repo>/<historyDir> (default docs/pl), committed by the
user with the code. Local mode (outside a git work tree): <historyRoot>/<work>.
Runtime state (ledger, evidence, memos) lives under <root>/.runtime/ and is
git-ignored by a self-ignoring .gitignore the helper writes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import string
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import unquote

DEFAULT_HISTORY_DIR = "docs/pl"
FEATURE_STATUSES = ("in-progress", "done", "done-with-risks", "blocked")
DECISION_STATUSES = ("accepted", "superseded")
TEAM_CONFIG = Path(".agents") / "pl.md"
LOCAL_CONFIGS = (Path(".agents") / "pl.local.md", Path(".claude") / "pl.local.md")


class HistoryError(Exception):
    """A user-facing refusal; the CLI prints the message and exits 2."""


# ---------------------------------------------------------------- low-level utils


def atomic_write(path: Path, text: str) -> None:
    """Replace a file atomically so concurrent readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


_PUNCTUATION_TO_FOLD = "".join(c for c in string.punctuation if c not in "-.")
_PUNCTUATION_PATTERN = re.compile(f"[{re.escape(_PUNCTUATION_TO_FOLD)}]+")


def slugify(value: str) -> str:
    original = value
    value = value.strip().lower()
    value = re.sub(r"[\s_]+", "-", value)
    value = _PUNCTUATION_PATTERN.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-. ")
    if not value:
        return f"item-{hashlib.sha1(original.encode('utf-8')).hexdigest()[:8]}"
    encoded = value.encode("utf-8")
    if len(encoded) > 120:
        digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
        value = encoded[:120].decode("utf-8", errors="ignore").rstrip("-. ")
        return f"{value}-{digest}"
    return value


def today(value: str | None) -> str:
    if value is None:
        return dt.date.today().isoformat()
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HistoryError("date must be a valid YYYY-MM-DD value") from exc


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def single_line(value: str, fieldname: str, *, allow_empty: bool = False) -> str:
    if re.search(r"[\x00-\x1f\x7f]", value):
        raise HistoryError(f"{fieldname} must be a single-line value without control characters")
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise HistoryError(f"{fieldname} must not be empty")
    return normalized


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?\n)---\r?\n", re.S)


def parse_frontmatter_simple(text: str) -> tuple[dict[str, str | list[str]], list[str]]:
    """Parse `key: scalar` lines and `key:` followed by `- item` lists. Nothing else.

    Returns (data, warnings). Unsupported shapes (nested maps, flow lists) are
    skipped with a warning so a typo in a team file never silently changes behavior.
    """
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        return {}, []
    data: dict[str, str | list[str]] = {}
    warnings: list[str] = []
    current: str | None = None
    for raw in match.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", raw)
        if item and current is not None:
            data[current].append(_unquote(item.group(1).strip()))  # type: ignore[union-attr]
            continue
        entry = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if entry is None or raw[0].isspace():
            warnings.append(f"unsupported frontmatter line ignored: {raw.strip()!r}")
            if current is not None:
                # A nested map under `key:` is not a list; drop the half-parsed key.
                data.pop(current, None)
            current = None
            continue
        key, value = entry.group(1), entry.group(2).strip()
        if value == "":
            data[key] = []
            current = key
        elif value.startswith("[") or value.startswith("{"):
            warnings.append(f"flow-style value for {key!r} ignored; use a `- item` list")
            current = None
        else:
            data[key] = _unquote(value)
            current = None
    return data, warnings


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        if value[0] == '"':
            try:
                return json.loads(value)
            except ValueError:
                return value[1:-1]
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, str | list[str]] | None:
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        return None
    return parse_frontmatter_simple(text)[0]


def replace_or_insert_section(text: str, heading: str, body: str, before_heading: str | None = None) -> str:
    pattern = re.compile(rf"(^## {re.escape(heading)}\n)(.*?)(?=^## |\Z)", re.M | re.S)
    replacement = f"## {heading}\n\n{body.rstrip()}\n\n"
    if pattern.search(text):
        return pattern.sub(lambda _: replacement, text)
    if before_heading:
        before = re.search(rf"^## {re.escape(before_heading)}\n", text, re.M)
        if before:
            return text[: before.start()] + replacement + text[before.start() :]
    return text.rstrip() + "\n\n" + replacement


FENCED_CODE_PATTERN = re.compile(
    r"(?ms)^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]{0,3}(?P=fence)[ \t]*$|\Z)"
)
INLINE_CODE_PATTERN = re.compile(r"`+[^`\n]*`+")


def strip_code(text: str) -> str:
    return INLINE_CODE_PATTERN.sub("", FENCED_CODE_PATTERN.sub("", text))


def iter_markdown_links(text: str):
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "[" or (cursor > 0 and text[cursor - 1] in {"!", "\\"}):
            cursor += 1
            continue
        label_end = cursor + 1
        while label_end < len(text):
            if text[label_end] == "\\":
                label_end += 2
                continue
            if text[label_end] in "]\n":
                break
            label_end += 1
        if label_end >= len(text) or text[label_end : label_end + 2] != "](" or label_end == cursor + 1:
            cursor += 1
            continue
        start = label_end + 2
        index = start
        depth = 1
        while index < len(text) and depth:
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    yield text[start:index].strip()
                    break
            index += 1
        cursor = max(index + 1, cursor + 1)


def local_link_target(source: Path, destination: str) -> Path | None:
    destination = destination.strip()
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    if not destination or destination.startswith("#"):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", destination):
        return None
    destination = unquote(destination.split("#", 1)[0])
    if not destination:
        return None
    raw = Path(destination)
    return raw if raw.is_absolute() else (source.parent / raw).resolve()


# ---------------------------------------------------------------- resolution


@dataclass
class Resolved:
    mode: str
    root: Path
    repo_top: Path | None
    history_dir: str
    verify_commands: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self, **extra) -> str:
        data = asdict(self)
        data["root"] = str(self.root)
        data["repo_top"] = str(self.repo_top) if self.repo_top else None
        data.update(extra)
        return json.dumps(data, ensure_ascii=False, indent=2)


def git_toplevel(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip()).resolve()


def _as_list(value, key: str, warnings: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    warnings.append(f"{key} must be a `- item` list; scalar ignored")
    return []


def load_team_config(repo_top: Path) -> tuple[dict, list[str]]:
    path = repo_top / TEAM_CONFIG
    if not path.is_file():
        return {}, []
    data, warnings = parse_frontmatter_simple(path.read_text(encoding="utf-8"))
    return data, [f"{TEAM_CONFIG}: {w}" for w in warnings]


def load_local_config(repo_top: Path) -> tuple[dict, list[str]]:
    present = [p for p in LOCAL_CONFIGS if (repo_top / p).is_file()]
    if not present:
        return {}, []
    warnings: list[str] = []
    if len(present) > 1:
        warnings.append(f"both {present[0]} and {present[1]} exist; using {present[0]} (the other is ignored)")
    data, parse_warnings = parse_frontmatter_simple((repo_top / present[0]).read_text(encoding="utf-8"))
    warnings += [f"{present[0]}: {w}" for w in parse_warnings]
    for key in ("historyDir", "workNamespace"):
        if key in data:
            reason = "history location is team-owned (.agents/pl.md)" if key == "historyDir" else "no longer used"
            warnings.append(f"{present[0]}: {key} ignored — {reason}")
            del data[key]
    return data, warnings


def validate_history_dir(value: str) -> str:
    value = value.strip()
    if not value:
        raise HistoryError("historyDir must not be empty")
    if Path(value).is_absolute():
        raise HistoryError(f"historyDir must be relative to the repository root: {value!r}")
    normalized = os.path.normpath(value)
    parts = Path(normalized).parts
    if not parts or parts[0] == ".." or normalized.startswith(".."):
        raise HistoryError(f"historyDir must stay inside the repository: {value!r}")
    if parts[0] == ".git":
        raise HistoryError(f"historyDir must not be under .git: {value!r}")
    return normalized


def resolve(
    cwd: Path, *, config_path: Path | None = None, work: str | None = None, root_override: Path | None = None
) -> Resolved:
    warnings: list[str] = []
    repo_top = git_toplevel(cwd)
    if repo_top is not None:
        team, team_warnings = load_team_config(repo_top)
        local, local_warnings = load_local_config(repo_top)
        warnings += team_warnings + local_warnings
        history_dir = validate_history_dir(str(team.get("historyDir") or DEFAULT_HISTORY_DIR))
        verify = _dedup(_as_list(team.get("verifyCommands"), "verifyCommands", warnings)
                        + _as_list(local.get("verifyCommands"), "verifyCommands", warnings))
        protected = _dedup(_as_list(team.get("protectedPaths"), "protectedPaths", warnings)
                           + _as_list(local.get("protectedPaths"), "protectedPaths", warnings))
        root = root_override or (repo_top / history_dir)
        return Resolved("repo", root.resolve(), repo_top, history_dir, verify, protected, warnings)

    history_root = None
    if config_path is not None and config_path.is_file():
        try:
            history_root = json.loads(config_path.read_text(encoding="utf-8")).get("historyRoot")
        except ValueError:
            warnings.append(f"{config_path}: invalid JSON ignored")
    if history_root:
        base = Path(str(history_root)).expanduser()
    else:
        xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        base = Path(xdg) / "pl" / "history"
    slug = slugify(work) if work else "inbox"
    if not work:
        warnings.append("work namespace unclear; using inbox")
    root = root_override or (base / slug)
    return Resolved("local", root.resolve(), None, "", [], [], warnings)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


ARCHITECTURE_TEMPLATE = """# Architecture

Status: draft
Owner: PL agent

## Summary

## Current Shape

## Important Constraints

## Common Change Points

## Verification Notes
"""


def ensure_layout(root: Path) -> bool:
    """Create the history layout. Returns True when anything was created."""
    created = False
    for sub in ("features", "decisions", ".runtime"):
        path = root / sub
        if not path.exists():
            path.mkdir(parents=True)
            created = True
    gitignore = root / ".runtime" / ".gitignore"
    if not gitignore.exists():
        atomic_write(gitignore, "*\n")
        created = True
    architecture = root / "architecture.md"
    if not architecture.exists():
        atomic_write(architecture, ARCHITECTURE_TEMPLATE)
        created = True
    return created


# ---------------------------------------------------------------- CLI


def _resolved_from_args(args: argparse.Namespace) -> Resolved:
    config = Path(args.config).expanduser() if args.config else None
    override = Path(args.root).expanduser() if args.root else None
    return resolve(Path.cwd(), config_path=config, work=getattr(args, "work", None), root_override=override)


def cmd_where(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    created = ensure_layout(resolved.root)
    for warning in resolved.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.json:
        print(resolved.to_json(created=created))
    else:
        print(f"{resolved.mode} {resolved.root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="override the resolved history root (tests/debug)")
    parser.add_argument("--config", help="per-user config JSON (local mode: historyRoot)")
    sub = parser.add_subparsers(dest="command", required=True)

    where = sub.add_parser("where", help="resolve the history root and create its layout")
    where.add_argument("--work", help="work namespace for local mode")
    where.add_argument("--json", action="store_true")
    where.set_defaults(func=cmd_where)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HistoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
