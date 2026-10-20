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
KNOWN_TEAM_KEYS = {"historyDir", "verifyCommands", "protectedPaths"}
KNOWN_LOCAL_KEYS = {"verifyCommands", "protectedPaths"}
# 0.4.x per-user config.json keys (Obsidian/Notion backends). History now lives in the repo.
LEGACY_CONFIG_KEYS = ("backend", "obsidian", "notion", "pending")


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
        elif value.startswith("["):
            # Inline JSON arrays are valid YAML; the helper writes `decisions: [...]` this way.
            try:
                parsed = json.loads(value)
                if not isinstance(parsed, list) or not all(isinstance(v, str) for v in parsed):
                    raise ValueError
                data[key] = parsed
            except ValueError:
                warnings.append(f"flow-style value for {key!r} ignored; use a `- item` list or a JSON string array")
            current = None
        elif value.startswith("{"):
            warnings.append(f"nested value for {key!r} ignored")
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
    warnings = [f"{TEAM_CONFIG}: {w}" for w in warnings]
    for key in sorted(set(data) - KNOWN_TEAM_KEYS):
        warnings.append(f"{TEAM_CONFIG}: unknown key {key!r} ignored (known: {', '.join(sorted(KNOWN_TEAM_KEYS))})")
    return data, warnings


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
    for key in sorted(set(data) - KNOWN_LOCAL_KEYS):
        warnings.append(f"{present[0]}: unknown key {key!r} ignored (known: {', '.join(sorted(KNOWN_LOCAL_KEYS))})")
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
    if parts[0].lower() == ".git":
        raise HistoryError(f"historyDir must not be under .git: {value!r}")
    return normalized


def ensure_inside(repo_top: Path, root: Path, value: str) -> None:
    """Refuse a history root that resolves (through symlinks) outside the repository or into .git."""
    resolved_top = repo_top.resolve()
    target = root.resolve()
    try:
        rel = target.relative_to(resolved_top)
    except ValueError as exc:
        raise HistoryError(f"historyDir resolves outside the repository: {value!r} -> {target}") from exc
    if rel.parts and rel.parts[0].lower() == ".git":
        raise HistoryError(f"historyDir resolves under .git: {value!r}")


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
        if root_override is None:
            ensure_inside(repo_top, root, history_dir)
        return Resolved("repo", root.resolve(), repo_top, history_dir, verify, protected, warnings)

    history_root = None
    if config_path is not None and config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            history_root = config.get("historyRoot")
            legacy = [k for k in LEGACY_CONFIG_KEYS if k in config]
            if legacy:
                warnings.append(
                    f"{config_path}: 0.4.x backend keys ignored ({', '.join(legacy)}) — history now lives in the repository"
                    " (docs/pl) or under historyRoot; the old vault/Notion data is untouched"
                )
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


# ---------------------------------------------------------------- notes

FEATURE_TEMPLATE = """---
type: Feature
title: {title}
status: in-progress
date: {date}
owner: PL agent
repo: {repo}
decisions: []
---

# Feature: {plain_title}

## Request

{request}

## Scope

In:
- 

Out:
- 

Size: <solo | light | full> — <why>

## Roles and Opinions

<!-- one subsection per role session that delivered a memo:
### <role> (<label>)
- Position:
- Key evidence:
- Recommendation:
- Open questions:
-->

## Synthesis

- Agreements:
- Conflicts:
- Hidden assumptions:
- Unverifiable statically:

## Challenges

<!-- challenger -> recipient: claim, response, effect on decision | `skipped — no material conflict in synthesis` -->

## PL Decisions

- 

## Implementation Summary

- 

## Changed Files

- 

## Verification

| Command | Exit | Ran at | Note |
|---|---|---|---|

Fresh at close: (not closed)

## Review

<!-- cycle N: Gate 1 PASS|FAIL, Gate 2 PASS|FAIL, unresolved findings -->

## Completion

- Team:
- Residual risk:

## Open Questions

- 
"""

LEDGER_TEMPLATE = """# Ledger: {stem}

Runtime state for the lead. Not committed.

## Execution Ledger

| Task | Owner | Depends on | Deliverable | Status | Evidence |
|---|---|---|---|---|---|

## Team Lifecycle

- Spawned:
- Replaced:
- Partial:
- Failed:
- Not spawned:

## Wave Baselines

"""

DECISION_TEMPLATE = """---
type: Decision
title: {title}
status: accepted
date: {date}
owner: PL agent
feature: {feature}
supersedes: {supersedes}
superseded_by: 
---

# Decision: {plain_title}

## Context

<why this decision was needed>

## Options Considered

1. 
2. 

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
"""


def note_title(path: Path) -> str:
    fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
    title = fm.get("title")
    return str(title) if title else path.stem


def runtime_dir(root: Path, stem: str) -> Path:
    return root / ".runtime" / stem


CURRENT_FILE = "current"
LIFECYCLE_FIELDS = ("Spawned", "Replaced", "Partial", "Failed", "Not spawned")


def current_stem(root: Path) -> str | None:
    """The feature the lead is working on now (`.runtime/current`); None when unset or stale."""
    path = root / ".runtime" / CURRENT_FILE
    if not path.is_file():
        return None
    stem = path.read_text(encoding="utf-8").strip()
    return stem if stem and (root / "features" / f"{stem}.md").is_file() else None


def set_current(root: Path, stem: str) -> None:
    stem = feature_stem(root, stem)
    atomic_write(root / ".runtime" / CURRENT_FILE, stem + "\n")


def clear_current(root: Path, stem: str) -> None:
    if current_stem(root) == stem:
        (root / ".runtime" / CURRENT_FILE).unlink(missing_ok=True)


def _ledger_path(root: Path, stem: str) -> Path:
    stem = feature_stem(root, stem)
    path = runtime_dir(root, stem) / "ledger.md"
    if not path.is_file():
        atomic_write(path, LEDGER_TEMPLATE.format(stem=stem))
    return path


def ledger_row(root: Path, stem: str, *, task: str, owner: str | None = None, depends: str | None = None,
               deliverable: str | None = None, status: str | None = None, evidence: str | None = None) -> None:
    """Insert or update one Execution Ledger row keyed by Task; None keeps the existing cell."""
    path = _ledger_path(root, stem)
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^## Execution Ledger\n(.*?)(?=^## |\Z)", text)
    if not match:
        raise HistoryError("ledger has no Execution Ledger section")
    lines = match.group(1).splitlines()
    header = [l for l in lines if l.startswith("|")][:2]
    rows = {}
    order = []
    for line in lines:
        if line.startswith("| ") and line not in header and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6:
                rows[cells[0]] = cells[:6]
                order.append(cells[0])
    task = single_line(task, "task")
    existing = rows.get(task, [task, "", "", "", "pending", ""])
    new = list(existing)
    for index, value in enumerate((task, owner, depends, deliverable, status, evidence)):
        if value is not None:
            new[index] = single_line(value, "ledger cell", allow_empty=True).replace("|", "\\|")
    if task not in rows:
        order.append(task)
    rows[task] = new
    table = ["| Task | Owner | Depends on | Deliverable | Status | Evidence |", "|---|---|---|---|---|---|"]
    table += ["| " + " | ".join(rows[k]) + " |" for k in order]
    atomic_write(path, replace_or_insert_section(text, "Execution Ledger", "\n".join(table), "Team Lifecycle"))


def ledger_lifecycle(root: Path, stem: str, *, field: str, value: str) -> None:
    """Append `value` to one Team Lifecycle field (`; `-separated)."""
    if field not in LIFECYCLE_FIELDS:
        raise HistoryError(f"lifecycle field must be one of {', '.join(LIFECYCLE_FIELDS)}: got {field!r}")
    path = _ledger_path(root, stem)
    text = path.read_text(encoding="utf-8")
    value = single_line(value, "value")
    pattern = re.compile(rf"(?m)^-[ \t]*{re.escape(field)}:[ \t]*(.*)$")
    match = pattern.search(text)
    if not match:
        raise HistoryError(f"ledger has no `- {field}:` line")
    current = match.group(1).strip()
    joined = f"{current}; {value}" if current else value
    atomic_write(path, text[: match.start()] + f"- {field}: {joined}" + text[match.end():])


def ledger_baseline(root: Path, stem: str, *, label: str, porcelain: str | None = None) -> str:
    """Record a `git status --porcelain` snapshot under Wave Baselines; returns the snapshot."""
    path = _ledger_path(root, stem)
    label = single_line(label, "label")
    if porcelain is None:
        top = git_toplevel(root)
        porcelain = _git_out(top, "status", "--porcelain") if top else ""
    text = path.read_text(encoding="utf-8")
    block = f"### {label}\n\n```\n{porcelain.rstrip()}\n```\n"
    match = re.search(r"(?ms)^## Wave Baselines\n(.*?)(?=^## |\Z)", text)
    body = (match.group(1).rstrip() + "\n\n" + block) if match and match.group(1).strip() else block
    atomic_write(path, replace_or_insert_section(text, "Wave Baselines", body))
    return porcelain


def write_diff(resolved: Resolved, stem: str, *, base: str | None) -> Path:
    """Write the review diff (committed range from `base` plus uncommitted and untracked changes,
    history root excluded) to `.runtime/<stem>/diff.patch`."""
    stem = feature_stem(resolved.root, stem)
    if resolved.repo_top is None:
        raise HistoryError("diff needs a git repository")
    top = resolved.repo_top
    try:
        rel = resolved.root.resolve().relative_to(top.resolve()).as_posix()
        exclude = [f":(exclude){rel}"]
    except ValueError:
        exclude = []
    parts = []
    if base:
        parts.append(_git_out(top, "diff", base, "--", ".", *exclude))
    else:
        parts.append(_git_out(top, "diff", "HEAD", "--", ".", *exclude))
    untracked = _git_out(top, "ls-files", "--others", "--exclude-standard", "--", ".", *exclude)
    for name in sorted(filter(None, untracked.splitlines())):
        # --no-index exits 1 when the files differ (always, against /dev/null); the output is still the patch
        proc = subprocess.run(["git", "-C", str(top), "diff", "--no-index", "--", "/dev/null", name],
                              capture_output=True, text=True, check=False)
        parts.append(proc.stdout)
    patch = runtime_dir(resolved.root, stem) / "diff.patch"
    atomic_write(patch, "".join(p for p in parts if p))
    return patch


def feature_stem(root: Path, ref: str) -> str:
    """Accept a stem, a file name, a history-relative path, or an absolute path."""
    name = Path(ref).name
    stem = name[:-3] if name.endswith(".md") else name
    if not (root / "features" / f"{stem}.md").is_file():
        raise HistoryError(f"feature note not found: {ref!r} (looked for features/{stem}.md)")
    return stem


def _note_path(root: Path, kind: str, date: str, title: str) -> Path:
    path = root / kind / f"{date}-{slugify(title)}.md"
    if path.exists() and note_title(path) != title:
        raise HistoryError(f"slug collision: {title!r} resolves to existing note {path.name!r}")
    return path


def create_feature(root: Path, title: str, *, request: str, repo_name: str, date: str | None) -> Path:
    title = single_line(title, "title")
    date = today(date)
    path = _note_path(root, "features", date, title)
    if not path.exists():
        atomic_write(
            path,
            FEATURE_TEMPLATE.format(
                title=yaml_quote(title), plain_title=title, date=date,
                repo=yaml_quote(repo_name or ""), request=(request or "").strip(),
            ),
        )
    ledger = runtime_dir(root, path.stem) / "ledger.md"
    if not ledger.exists():
        atomic_write(ledger, LEDGER_TEMPLATE.format(stem=path.stem))
    atomic_write(root / ".runtime" / CURRENT_FILE, path.stem + "\n")
    return path


def _set_frontmatter_field(text: str, key: str, value: str | list[str]) -> str:
    """Replace (or append) one frontmatter field. Lists are written inline as JSON (valid YAML)."""
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise HistoryError("note has no frontmatter")
    rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
    block = match.group(1)
    pattern = re.compile(rf"(?m)^{re.escape(key)}:.*$")
    if pattern.search(block):
        block = pattern.sub(lambda _: f"{key}: {rendered}", block, count=1)
    else:
        block = block + f"{key}: {rendered}\n"
    return text[: match.start(1)] + block + text[match.end(1):]


def _frontmatter_list(text: str, key: str) -> list[str]:
    fm = parse_frontmatter(text) or {}
    value = fm.get(key)
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            return [str(v) for v in json.loads(value)]
        except ValueError:
            return []
    return []


def create_decision(root: Path, title: str, *, feature: Path, supersedes: Path | None, date: str | None) -> Path:
    title = single_line(title, "title")
    date = today(date)
    stem = feature_stem(root, str(feature))
    feature_path = root / "features" / f"{stem}.md"
    path = _note_path(root, "decisions", date, title)
    supersedes_rel = f"decisions/{supersedes.name}" if supersedes else ""
    if supersedes and not (root / "decisions" / supersedes.name).is_file():
        raise HistoryError(f"supersedes target not found: {supersedes}")
    if not path.exists():
        atomic_write(
            path,
            DECISION_TEMPLATE.format(
                title=yaml_quote(title), plain_title=title, date=date,
                feature=f"features/{stem}.md", supersedes=supersedes_rel,
            ),
        )
    rel = f"decisions/{path.name}"
    text = feature_path.read_text(encoding="utf-8")
    links = _frontmatter_list(text, "decisions")
    if rel not in links:
        atomic_write(feature_path, _set_frontmatter_field(text, "decisions", links + [rel]))
    if supersedes:
        old_path = root / "decisions" / supersedes.name
        old = old_path.read_text(encoding="utf-8")
        old = _set_frontmatter_field(old, "status", "superseded")
        old = _set_frontmatter_field(old, "superseded_by", rel)
        atomic_write(old_path, old)
    return path


def list_notes(root: Path, *, kind: str | None, status: str | None) -> list[dict]:
    rows: list[dict] = []
    kinds = {"feature": "features", "decision": "decisions"}
    for key, folder in kinds.items():
        if kind and kind != key:
            continue
        for path in sorted((root / folder).glob("*.md")):
            fm = parse_frontmatter(path.read_text(encoding="utf-8")) or {}
            row = {
                "type": str(fm.get("type", key.capitalize())),
                "date": str(fm.get("date", "")),
                "status": str(fm.get("status", "")),
                "title": str(fm.get("title", path.stem)),
                "path": f"{folder}/{path.name}",
            }
            if status and row["status"] != status:
                continue
            rows.append(row)
    return rows


def cmd_feature(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    ensure_layout(resolved.root)
    repo_name = args.repo or (_canonical_repo_name(resolved.repo_top) if resolved.repo_top else "")
    print(create_feature(resolved.root, args.title, request=args.request or "", repo_name=repo_name, date=args.date))
    return 0


def _canonical_repo_name(repo_top: Path) -> str:
    proc = subprocess.run(["git", "-C", str(repo_top), "remote", "get-url", "origin"], capture_output=True, text=True)
    if proc.returncode == 0 and proc.stdout.strip():
        name = proc.stdout.strip().rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        return name[:-4] if name.endswith(".git") else name
    return repo_top.name


def cmd_decision(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    supersedes = Path(args.supersedes) if args.supersedes else None
    print(create_decision(resolved.root, args.title, feature=Path(args.feature), supersedes=supersedes, date=args.date))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    rows = list_notes(resolved.root, kind=args.type, status=args.status)
    if not rows:
        print("(no notes)")
        return 0
    width = max(len(r["title"]) for r in rows)
    for r in rows:
        print(f"{r['type']:<8} {r['date']:<10} {r['status']:<15} {r['title']:<{width}}  {r['path']}")
    return 0


# ---------------------------------------------------------------- verification evidence

TAIL_LINES = 40


def command_string(argv: list[str]) -> str:
    """Identity key of a verification command.

    One argument = a shell string (run through `sh -c`, recorded verbatim so it
    matches `verifyCommands` entries exactly); several = an argv (recorded with
    shlex.join).
    """
    import shlex

    if len(argv) == 1:
        return argv[0]
    return shlex.join(argv)


def command_argv(argv: list[str]) -> list[str]:
    return ["sh", "-c", argv[0]] if len(argv) == 1 else argv


def evidence_path(root: Path, stem: str) -> Path:
    return runtime_dir(root, stem) / "evidence.jsonl"


def _git_out(repo_top: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_top), *args], capture_output=True, text=True, check=False)
    return proc.stdout if proc.returncode == 0 else ""


def fingerprint(repo_top: Path | None, history_root: Path) -> str | None:
    """Hash of HEAD + tracked diff + untracked files, excluding the history root.

    None outside a repository (local mode): freshness is then `unknown`.
    """
    if repo_top is None:
        return None
    try:
        rel = history_root.resolve().relative_to(repo_top.resolve()).as_posix()
    except ValueError:
        rel = None
    exclude = [f":(exclude){rel}"] if rel else []
    digest = hashlib.sha256()
    digest.update(_git_out(repo_top, "rev-parse", "HEAD").encode())
    digest.update(_git_out(repo_top, "diff", "HEAD", "--", ".", *exclude).encode())
    untracked = _git_out(repo_top, "ls-files", "--others", "--exclude-standard", "--", ".", *exclude)
    for name in sorted(filter(None, untracked.splitlines())):
        path = repo_top / name
        digest.update(name.encode())
        try:
            digest.update(path.read_bytes())
        except OSError:
            pass
    return digest.hexdigest()


def _append_evidence(root: Path, stem: str, record: dict) -> None:
    path = evidence_path(root, stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_evidence(root: Path, stem: str) -> list[dict]:
    path = evidence_path(root, stem)
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def latest_evidence(root: Path, stem: str) -> dict[str, dict]:
    """Command → last record. A withdrawal record replaces the run record."""
    latest: dict[str, dict] = {}
    for record in read_evidence(root, stem):
        command = record.get("command")
        if isinstance(command, str):
            latest[command] = record
    return latest


def required_commands(resolved: Resolved, stem: str) -> list[str]:
    """Everything run through `verify` (minus withdrawn) ∪ verifyCommands."""
    commands: list[str] = []
    for command, record in latest_evidence(resolved.root, stem).items():
        if not record.get("withdrawn"):
            commands.append(command)
    return _dedup(commands + list(resolved.verify_commands))


def _render_verification(resolved: Resolved, stem: str, closing: str | None = None) -> str:
    rows = ["| Command | Exit | Ran at | Note |", "|---|---|---|---|"]
    for command, record in latest_evidence(resolved.root, stem).items():
        cell = "`" + command.replace("|", "\\|") + "`"
        if record.get("withdrawn"):
            rows.append(f"| {cell} | — | — | withdrawn: {record.get('reason', '')} |")
            continue
        notes = []
        if record.get("fp_before") != record.get("fp_after"):
            notes.append("command modified the working tree")
        if record.get("note"):
            notes.append(record["note"])
        rows.append(f"| {cell} | {record['exit']} | {record['ts_end']} | {'; '.join(notes)} |")
    for command in resolved.verify_commands:
        if command not in latest_evidence(resolved.root, stem):
            rows.append(f"| `{command}` | — | — | required by verifyCommands; not run |")
    stamp = closing if closing is not None else _current_stamp(resolved.root, stem)
    return "\n".join(rows) + f"\n\nFresh at close: {stamp}"


def _current_stamp(root: Path, stem: str) -> str:
    path = root / "features" / f"{stem}.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    match = re.search(r"(?m)^Fresh at close: (.+)$", text)
    return match.group(1).strip() if match else "(not closed)"


def _write_verification(resolved: Resolved, stem: str, closing: str | None = None) -> None:
    path = resolved.root / "features" / f"{stem}.md"
    text = path.read_text(encoding="utf-8")
    atomic_write(path, replace_or_insert_section(text, "Verification", _render_verification(resolved, stem, closing), "Review"))


def run_verify(resolved: Resolved, stem: str, argv: list[str]) -> int:
    if not argv:
        raise HistoryError("verify needs a command after `--`")
    stem = feature_stem(resolved.root, stem)
    command = command_string(argv)
    ts_start = now_iso()
    fp_before = fingerprint(resolved.repo_top, resolved.root)
    tail: list[str] = []
    try:
        proc = subprocess.Popen(
            command_argv(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=resolved.repo_top or Path.cwd(),
        )
    except OSError as exc:
        raise HistoryError(f"cannot run {command!r}: {exc}") from exc
    assert proc.stdout is not None
    with proc.stdout:
        for line in proc.stdout:
            sys.stdout.write(line)
            tail.append(line.rstrip("\n"))
            if len(tail) > TAIL_LINES:
                del tail[0]
    exit_code = proc.wait()
    record = {
        "ts_start": ts_start,
        "ts_end": now_iso(),
        "command": command,
        "exit": exit_code,
        "tail": tail,
        "fp_before": fp_before,
        "fp_after": fingerprint(resolved.repo_top, resolved.root),
    }
    _append_evidence(resolved.root, stem, record)
    _write_verification(resolved, stem)
    return exit_code


def withdraw(resolved: Resolved, stem: str, command: str, reason: str) -> None:
    stem = feature_stem(resolved.root, stem)
    reason = single_line(reason, "reason")
    if command in resolved.verify_commands:
        raise HistoryError("cannot withdraw a verifyCommands entry")
    if command not in latest_evidence(resolved.root, stem):
        raise HistoryError(f"no evidence for command {command!r}")
    _append_evidence(resolved.root, stem, {"ts": now_iso(), "command": command, "withdrawn": True, "reason": reason})
    _write_verification(resolved, stem)


def cmd_current(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    if args.feature:
        set_current(resolved.root, args.feature)
    stem = current_stem(resolved.root)
    print(stem or "(none)")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    stem = args.feature or current_stem(resolved.root)
    if not stem:
        raise HistoryError("no feature given and no current feature")
    if args.ledger_command == "row":
        ledger_row(resolved.root, stem, task=args.task, owner=args.owner, depends=args.depends,
                   deliverable=args.deliverable, status=args.status, evidence=args.evidence)
    elif args.ledger_command == "lifecycle":
        ledger_lifecycle(resolved.root, stem, field=args.field, value=args.value)
    elif args.ledger_command == "baseline":
        snapshot = ledger_baseline(resolved.root, stem, label=args.label)
        print(snapshot.rstrip())
    print(runtime_dir(resolved.root, feature_stem(resolved.root, stem)) / "ledger.md")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    stem = args.feature or current_stem(resolved.root)
    if not stem:
        raise HistoryError("no feature given and no current feature")
    print(write_diff(resolved, stem, base=args.base))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    if args.withdraw:
        withdraw(resolved, args.feature, args.withdraw, args.reason or "")
        print(f"withdrawn: {args.withdraw}")
        return 0
    argv = list(args.argv)
    if argv and argv[0] == "--":
        argv = argv[1:]
    return run_verify(resolved, args.feature, argv)


# ---------------------------------------------------------------- check / close

CHOICE_PLACEHOLDER_PATTERN = re.compile(r"<[^<>\n]*\|[^<>\n]*>")
COMPLETION_SECTION_PATTERN = re.compile(r"(?ms)^## Completion\n(.*?)(?=^## |\Z)")
VERIFICATION_SECTION_PATTERN = re.compile(r"(?ms)^## Verification\n(.*?)(?=^## |\Z)")
TEAM_LINE_PATTERN = re.compile(r"(?m)^-[ \t]*Team:[ \t]*(.*)$")
DONE_FORBIDDEN_TEAM_TOKENS = ("partial", "failed")
# `partial 0` / `failed 0` are fine; `partial 1`, `failed: 2`, or a bare word count as gaps.
_TEAM_GAP_PATTERN = re.compile(r"\b(partial|failed)\b(?!\s*:?\s*(?:0|none|no)\b)", re.I)


def team_line_gaps(team_text: str) -> list[str]:
    return sorted({m.group(1).lower() for m in _TEAM_GAP_PATTERN.finditer(team_text)})
HTML_COMMENT_PATTERN = re.compile(r"(?s)<!--.*?-->")


def _note_files(root: Path, stem: str | None) -> list[Path]:
    if stem:
        return [root / "features" / f"{stem}.md"]
    files = sorted((root / "features").glob("*.md")) + sorted((root / "decisions").glob("*.md"))
    arch = root / "architecture.md"
    return files + ([arch] if arch.is_file() else [])


def _verification_rows(text: str) -> int:
    match = VERIFICATION_SECTION_PATTERN.search(text)
    if not match:
        return 0
    rows = [l for l in match.group(1).splitlines() if l.startswith("| `")]
    return len([r for r in rows if "| — | — |" not in r])


def check(root: Path, *, stem: str | None, assume_status: str | None = None) -> list[str]:
    """Structural integrity of committed notes. Read-only; identical on every clone.

    `assume_status` evaluates a single feature as if its status were already that
    value — `close` uses it so placeholder rules apply before the status is written.
    """
    problems: list[str] = []
    for note in _note_files(root, stem):
        if not note.is_file():
            problems.append(f"missing note: {note}")
            continue
        text = note.read_text(encoding="utf-8")
        fm = parse_frontmatter(text) or {}
        for destination in iter_markdown_links(text):
            target = local_link_target(note, destination)
            if target is not None and not target.exists():
                problems.append(f"missing local link: {note} -> {destination}")
        for key in ("decisions", "feature", "supersedes", "superseded_by"):
            value = fm.get(key)
            refs = value if isinstance(value, list) else ([value] if value else [])
            for ref in refs:
                if not (root / str(ref)).is_file():
                    problems.append(f"missing frontmatter link: {note} -> {key}: {ref}")
        kind = fm.get("type")
        status = assume_status if (assume_status and stem and kind == "Feature") else fm.get("status")
        if kind == "Feature":
            if status not in FEATURE_STATUSES:
                problems.append(f"nonstandard feature status: {note} -> {status!r} (allowed: {', '.join(FEATURE_STATUSES)})")
        elif kind == "Decision":
            if status not in DECISION_STATUSES:
                problems.append(f"nonstandard decision status: {note} -> {status!r} (allowed: {', '.join(DECISION_STATUSES)})")
        prose = strip_code(HTML_COMMENT_PATTERN.sub("", text))
        if status != "in-progress" and kind in ("Feature", "Decision"):
            for placeholder in dict.fromkeys(CHOICE_PLACEHOLDER_PATTERN.findall(prose)):
                problems.append(f"unresolved placeholder: {note} -> {placeholder}")
        if kind == "Feature" and status == "done":
            completion = COMPLETION_SECTION_PATTERN.search(prose)
            team = TEAM_LINE_PATTERN.search(completion.group(1)) if completion else None
            for token in team_line_gaps(team.group(1) if team else ""):
                problems.append(f"done status contradicts Team line: {note} -> {token!r}")
            if _verification_rows(text) == 0:
                problems.append(f"done status with no verification rows: {note}")
            stamp = re.search(r"(?m)^Fresh at close: (.+)$", text)
            if not stamp or stamp.group(1).strip() not in ("yes", "unknown"):
                problems.append(f"done status without `Fresh at close: yes|unknown` stamp: {note}")
    return problems


def _lifecycle_problems(root: Path, stem: str) -> list[str]:
    ledger = runtime_dir(root, stem) / "ledger.md"
    if not ledger.is_file():
        return []
    problems = []
    text = ledger.read_text(encoding="utf-8")
    for label in ("Partial", "Failed"):
        match = re.search(rf"(?m)^-[ \t]*{label}:[ \t]*(.*)$", text)
        value = match.group(1).strip() if match else ""
        if value and value.lower() not in ("0", "none", "-", "—"):
            problems.append(f"Team Lifecycle {label}: {value} (runtime ledger) — cannot close as done")
    return problems


def _evidence_problems(resolved: Resolved, stem: str) -> tuple[list[str], bool]:
    """(problems, fresh). fresh is False when any required command is stale/failed/missing."""
    problems: list[str] = []
    latest = latest_evidence(resolved.root, stem)
    required = required_commands(resolved, stem)
    if not [c for c in required if c in latest and not latest[c].get("withdrawn")]:
        problems.append("no verification evidence recorded (run `pl_history.py verify --feature <stem> -- <command>`)")
    current = fingerprint(resolved.repo_top, resolved.root)
    runs = [r for r in read_evidence(resolved.root, stem) if not r.get("withdrawn") and isinstance(r.get("command"), str)]
    for command in required:
        record = latest.get(command)
        if record is None or record.get("withdrawn"):
            problems.append(f"required command not run: {command!r}")
            continue
        if record.get("exit") != 0:
            problems.append(f"required command failed (exit {record.get('exit')}): {command!r}")
        if current is not None and not _fresh_through_chain(runs, record, current):
            problems.append(f"evidence is stale (working tree changed after it ran): {command!r}")
    return problems, not problems


def _fresh_through_chain(runs: list[dict], record: dict, current: str) -> bool:
    """A run is fresh when only later verify runs changed the tree: each later run
    started from the previous run's end state and the last one ends at `current`."""
    try:
        index = runs.index(record)
    except ValueError:
        return record.get("fp_after") == current
    state = record.get("fp_after")
    for later in runs[index + 1:]:
        if later.get("fp_before") != state:
            return False
        state = later.get("fp_after")
    return state == current


def close_feature(resolved: Resolved, stem: str, status: str) -> list[str]:
    if status not in FEATURE_STATUSES or status == "in-progress":
        raise HistoryError(f"close status must be one of {', '.join(s for s in FEATURE_STATUSES if s != 'in-progress')}")
    stem = feature_stem(resolved.root, stem)
    path = resolved.root / "features" / f"{stem}.md"
    evidence_problems, fresh = _evidence_problems(resolved, stem)
    problems = [
        p for p in check(resolved.root, stem=stem, assume_status=status)
        if "Fresh at close" not in p and "no verification rows" not in p
    ]
    if status == "done":
        problems += evidence_problems + _lifecycle_problems(resolved.root, stem)
        text = path.read_text(encoding="utf-8")
        completion = COMPLETION_SECTION_PATTERN.search(strip_code(text))
        team = TEAM_LINE_PATTERN.search(completion.group(1)) if completion else None
        problems += [f"Team line contains {t!r}; close as done-with-risks instead" for t in team_line_gaps(team.group(1) if team else "")]
    else:
        # done-with-risks / blocked always close: placeholders and links become warnings, not refusals
        for problem in problems:
            print(f"warning: {problem}", file=sys.stderr)
        problems = []
    if problems:
        return problems
    if resolved.repo_top is None:
        stamp = "unknown"
    else:
        stamp = "yes" if fresh else "no"
    if status != "done":
        latest = latest_evidence(resolved.root, stem)
        for problem in evidence_problems:
            for command, record in latest.items():
                if repr(command) in problem and not record.get("withdrawn"):
                    record["note"] = "failed at close" if "failed" in problem else "stale at close"
                    _append_evidence(resolved.root, stem, record)
    _write_verification(resolved, stem, closing=stamp)
    text = path.read_text(encoding="utf-8")
    atomic_write(path, _set_frontmatter_field(text, "status", status))
    clear_current(resolved.root, stem)
    return []


def cmd_check(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    stem = feature_stem(resolved.root, args.feature) if args.feature else None
    problems = check(resolved.root, stem=stem)
    if args.evidence_only and stem:
        problems = _evidence_problems(resolved, stem)[0]
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("history check ok")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    resolved = _resolved_from_args(args)
    problems = close_feature(resolved, args.feature, args.status)
    for problem in problems:
        print(problem)
    if problems:
        print(f"not closed: fix the problems above or close as done-with-risks/blocked", file=sys.stderr)
        return 1
    print(f"closed {args.feature} as {args.status}")
    return 0


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

    feature = sub.add_parser("feature", help="create a feature note and its runtime ledger")
    feature.add_argument("title")
    feature.add_argument("--request", default="")
    feature.add_argument("--repo", help="repository name for the frontmatter (default: origin basename)")
    feature.add_argument("--date")
    feature.add_argument("--work")
    feature.set_defaults(func=cmd_feature)

    decision = sub.add_parser("decision", help="create a decision note linked to a feature")
    decision.add_argument("title")
    decision.add_argument("--feature", required=True, help="feature stem, file name, or path")
    decision.add_argument("--supersedes", help="decision file name or path being superseded")
    decision.add_argument("--date")
    decision.add_argument("--work")
    decision.set_defaults(func=cmd_decision)

    current = sub.add_parser("current", help="show or set the feature the lead is working on")
    current.add_argument("--feature", help="set the current feature (stem, file name, or path)")
    current.add_argument("--work")
    current.set_defaults(func=cmd_current)

    ledger = sub.add_parser("ledger", help="update the runtime ledger (rows, lifecycle, wave baselines)")
    ledger.add_argument("--feature", help="defaults to the current feature")
    ledger.add_argument("--work")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    row = ledger_sub.add_parser("row", help="insert or update an Execution Ledger row")
    row.add_argument("task")
    row.add_argument("--owner")
    row.add_argument("--depends")
    row.add_argument("--deliverable")
    row.add_argument("--status")
    row.add_argument("--evidence")
    life = ledger_sub.add_parser("lifecycle", help="append to a Team Lifecycle field")
    life.add_argument("field", choices=LIFECYCLE_FIELDS)
    life.add_argument("value")
    base = ledger_sub.add_parser("baseline", help="record git status --porcelain under Wave Baselines")
    base.add_argument("label")
    ledger.set_defaults(func=cmd_ledger)

    diff = sub.add_parser("diff", help="write .runtime/<stem>/diff.patch for review roles")
    diff.add_argument("--feature", help="defaults to the current feature")
    diff.add_argument("--base", help="commit to diff from (default: HEAD + uncommitted + untracked)")
    diff.add_argument("--work")
    diff.set_defaults(func=cmd_diff)

    lst = sub.add_parser("list", help="list notes from frontmatter (no index file)")
    lst.add_argument("--type", choices=("feature", "decision"))
    lst.add_argument("--status")
    lst.add_argument("--work")
    lst.set_defaults(func=cmd_list)

    verify = sub.add_parser("verify", help="run a verification command and record its evidence")
    verify.add_argument("--feature", required=True)
    verify.add_argument("--withdraw", metavar="COMMAND", help="remove a previously run command from the required set")
    verify.add_argument("--reason")
    verify.add_argument("--work")
    verify.add_argument("argv", nargs=argparse.REMAINDER)
    verify.set_defaults(func=cmd_verify)

    close = sub.add_parser("close", help="run the closing checks and write the feature status")
    close.add_argument("--feature", required=True)
    close.add_argument("--status", required=True, choices=[s for s in FEATURE_STATUSES if s != "in-progress"])
    close.add_argument("--work")
    close.set_defaults(func=cmd_close)

    chk = sub.add_parser("check", help="read-only structural check of the history root")
    chk.add_argument("--feature")
    chk.add_argument("--evidence-only", action="store_true", help="with --feature: report only evidence problems")
    chk.add_argument("--work")
    chk.set_defaults(func=cmd_check)
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
