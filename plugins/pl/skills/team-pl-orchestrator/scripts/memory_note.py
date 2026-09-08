#!/usr/bin/env python3
"""Create and validate PL-agent Obsidian memory notes."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import string
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote

def atomic_write(path: Path, text: str) -> None:
    """Replace a note atomically so concurrent readers never see a partial file."""
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


@contextmanager
def memory_lock(root: Path):
    """Serialize helper processes that update shared vault indexes."""
    root.mkdir(parents=True, exist_ok=True)
    lock_id = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"team-pl-memory-{lock_id}.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# Every ASCII punctuation character except `-` and `.` folds into a hyphen, so
# filesystem/URL/Markdown-hostile characters (commas, parens, slashes, quotes,
# ...) never survive into a slug. Non-ASCII characters (e.g. Korean) are left
# untouched.
_PUNCTUATION_TO_FOLD = "".join(c for c in string.punctuation if c not in "-.")
_PUNCTUATION_PATTERN = re.compile(f"[{re.escape(_PUNCTUATION_TO_FOLD)}]+")


def slugify(value: str) -> str:
    original = value
    value = value.strip().lower()
    value = re.sub(r"[\s_]+", "-", value)
    value = _PUNCTUATION_PATTERN.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-. ")
    if not value:
        digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
        return f"item-{digest}"
    # Cap the slug so `YYYY-MM-DD-<slug>.md` stays under filesystem name
    # limits (255 bytes on macOS/Linux); a digest keeps truncated slugs unique.
    encoded = value.encode("utf-8")
    if len(encoded) > 120:
        digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
        value = encoded[:120].decode("utf-8", errors="ignore").rstrip("-. ")
        return f"{value}-{digest}"
    return value


def today(value: str | None) -> str:
    if value is None:
        return dt.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must be a valid YYYY-MM-DD value")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be a valid YYYY-MM-DD value") from exc
    return parsed.isoformat()


def single_line(value: str, field: str, *, allow_empty: bool = False) -> str:
    if re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError(f"{field} must be a single-line value without control characters")
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise ValueError(f"{field} must not be empty")
    return normalized


FEATURE_STATUSES = ("in-progress", "done", "done-with-risks", "blocked")


def status_value(value: str) -> str:
    status = single_line(value, "status")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", status):
        raise ValueError("status must use lowercase letters, numbers, and hyphens")
    return status


def feature_status_value(value: str) -> str:
    status = status_value(value)
    if status not in FEATURE_STATUSES:
        raise ValueError(
            f"feature status must be one of {', '.join(FEATURE_STATUSES)}: got {status!r}"
        )
    return status


def markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def yaml_quote(value: str) -> str:
    """Serialize a scalar as a double-quoted YAML string (JSON is a YAML subset)."""
    return json.dumps(value, ensure_ascii=False)


FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?\n)---\r?\n", re.S)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse the leading YAML frontmatter block into flat scalar fields.

    Only `key: value` scalars are read; list/nested values are ignored so the
    helper stays dependency-free. Returns None when no frontmatter exists.
    """
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        entry = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if entry is None:
            continue
        value = entry.group(2).strip()
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            try:
                value = json.loads(value)
            except ValueError:
                pass
        fields[entry.group(1)] = value
    return fields


def replace_or_insert_section(text: str, heading: str, body: str, before_heading: str | None = None) -> str:
    pattern = re.compile(rf"(^## {re.escape(heading)}\n)(.*?)(?=^## |\Z)", re.M | re.S)
    replacement = f"## {heading}\n\n{body.rstrip()}\n\n"
    if pattern.search(text):
        # repl must be a callable: a plain string is parsed as a re template,
        # so user content containing backslashes would crash or lose escapes.
        return pattern.sub(lambda _: replacement, text)
    if before_heading:
        before = re.search(rf"^## {re.escape(before_heading)}\n", text, re.M)
        if before:
            return text[: before.start()] + replacement + text[before.start() :]
    return text.rstrip() + "\n\n" + replacement


def note_title(path: Path) -> str:
    if path.exists():
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        if frontmatter and frontmatter.get("title"):
            return frontmatter["title"]
        for line in text.splitlines():
            if line.startswith("# Feature: ") or line.startswith("# Decision: "):
                return line.split(":", 1)[1].strip()
            if line.startswith("# "):
                return line[2:].strip()
    return path.stem


def replace_index_list(text: str, label: str, rows: list[str]) -> str:
    body = "\n".join(rows) if rows else "- (none)"
    replacement = f"{label}:\n{body}"
    pattern = re.compile(rf"(?ms)^{re.escape(label)}:\n.*?(?=\n\n|\Z)")
    if pattern.search(text):
        # Callable repl keeps user content literal (see replace_or_insert_section).
        return pattern.sub(lambda _: replacement, text, count=1)
    marker = "## Notes\n"
    if marker in text:
        return text.replace(marker, f"{marker}\n{replacement}\n", 1)
    return text.rstrip() + f"\n\n## Notes\n\n{replacement}\n"


def has_heading(text: str, heading: str) -> bool:
    return re.search(rf"^## {re.escape(heading)}\n", text, re.M) is not None


def remove_index_list(text: str, label: str) -> str:
    pattern = re.compile(rf"(?ms)^{re.escape(label)}:\n.*?(?=\n\n|\Z)")
    return pattern.sub("", text, count=1)


def remove_empty_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\n[ \t\n]*(?=^## |\Z)")
    return pattern.sub("", text, count=1)


def sync_work_index(work_dir: Path) -> None:
    index = work_dir / "INDEX.md"
    if not index.exists():
        return
    text = index.read_text(encoding="utf-8")
    features = [
        f"- [{markdown_label(note_title(path))}](features/{path.name})"
        for path in sorted((work_dir / "features").glob("*.md"))
        if not path.name.startswith("_")
    ]
    decisions = [
        f"- [{markdown_label(note_title(path))}](decisions/{path.name})"
        for path in sorted((work_dir / "decisions").glob("*.md"))
        if not path.name.startswith("_")
    ]
    if has_heading(text, "Features"):
        text = replace_or_insert_section(text, "Features", "\n".join(features) if features else "- (none)")
        text = remove_index_list(text, "Features")
    else:
        text = replace_index_list(text, "Features", features)
    if has_heading(text, "Decisions"):
        text = replace_or_insert_section(text, "Decisions", "\n".join(decisions) if decisions else "- (none)")
        text = remove_index_list(text, "Decisions")
    else:
        text = replace_index_list(text, "Decisions", decisions)
    text = remove_empty_section(text, "Notes")
    atomic_write(index, text)


def sync_root_index(root: Path) -> None:
    index = root / "INDEX.md"
    if not index.exists():
        atomic_write(index, "# LLM Memory Index\n")
    text = index.read_text(encoding="utf-8")
    rows: list[str] = []
    work_root = root / "work"
    if work_root.exists():
        for work_dir in sorted(
            p
            for p in work_root.iterdir()
            if p.is_dir() and not p.is_symlink() and p.name != "_template"
        ):
            summary = ""
            work_index = work_dir / "INDEX.md"
            if work_index.exists():
                for line in work_index.read_text(encoding="utf-8").splitlines():
                    if line.startswith("Related repos:"):
                        summary = line.split(":", 1)[1].strip()
                        break
            rows.append(f"- `work/{work_dir.name}/`" + (f" - {summary}" if summary else ""))
    body = "\n".join(rows) if rows else "- (none)"
    atomic_write(index, replace_or_insert_section(text, "Workspaces", body, "Sections"))


def ensure_work(root: Path, work: str, repo: str | None = None) -> Path:
    work_slug = slugify(work)
    repo = single_line(repo, "repo", allow_empty=True) if repo is not None else None
    work_root = (root / "work").resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    work_path = work_root / work_slug
    if work_path.is_symlink():
        raise ValueError(f"work namespace must not be a symlink: {work_slug}")
    work_dir = work_path.resolve()
    try:
        work_dir.relative_to(work_root)
    except ValueError as exc:
        raise ValueError(f"work namespace escapes memory root: {work_slug}") from exc
    for subdir in ("features", "decisions", "architecture"):
        subdir_path = work_dir / subdir
        if subdir_path.is_symlink():
            raise ValueError(f"work subdirectory must not be a symlink: {subdir_path}")
        subdir_path.mkdir(parents=True, exist_ok=True)
    index = work_dir / "INDEX.md"
    if not index.exists():
        atomic_write(
            index,
            f"""# Work: {work_slug}

Status: active
Owner: PL agent
Related repos: {repo or ""}

## Scope

Memory for `{work_slug}` only.

## Notes

Features:
- (none)

Decisions:
- (none)

Architecture:
- `architecture/README.md`

## Current Context

## Active Decisions

## Open Questions
""",
        )
    elif repo:
        text = index.read_text(encoding="utf-8")

        def update_related_repos(match: re.Match[str]) -> str:
            existing = match.group(1).strip()
            repos = [item.strip() for item in existing.split(",") if item.strip()]
            if repo not in repos:
                repos.append(repo)
            return "Related repos: " + ", ".join(repos)

        text = re.sub(r"(?m)^Related repos:\s*(.*)$", update_related_repos, text, count=1)
        atomic_write(index, text)
    arch = work_dir / "architecture" / "README.md"
    if not arch.exists():
        atomic_write(
            arch,
            f"""# Architecture: {work_slug}

Status: draft
Owner: PL agent

## Summary

## Current Shape

## Important Constraints

## Common Change Points

## Verification Notes
""",
        )
    sync_work_index(work_dir)
    sync_root_index(root)
    return work_dir


def add_metadata_link(note: Path, label: str, title: str, rel_path: str) -> None:
    text = note.read_text(encoding="utf-8")
    link = f"- [{markdown_label(title)}]({rel_path})"
    if link in text:
        return
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"{label}:"):
            insert_at = index + 1
            while insert_at < len(lines) and lines[insert_at].startswith("- "):
                insert_at += 1
            lines.insert(insert_at, link)
            atomic_write(note, "\n".join(lines) + "\n")
            return
    raise ValueError(f"missing metadata field {label!r}: {note}")


def create_feature(args: argparse.Namespace) -> Path:
    root = Path(args.root).expanduser()
    date = today(args.date)
    title = single_line(args.title, "title")
    status = feature_status_value(args.status)
    repo = single_line(args.repo, "repo", allow_empty=True) if args.repo is not None else None
    work_dir = ensure_work(root, args.work, repo)
    path = work_dir / "features" / f"{date}-{slugify(title)}.md"
    if path.exists() and note_title(path) != title:
        raise ValueError(
            f"feature slug collision: {title!r} resolves to existing note {path.name!r}"
        )
    if not path.exists():
        atomic_write(
            path,
            f"""---
type: Feature
title: {yaml_quote(title)}
status: {status}
date: {date}
owner: PL agent
work: {work_dir.name}
repo: {yaml_quote(repo or "")}
---

# Feature: {title}

Related decisions:
Related PR/commit:

## Request

{args.request or ""}

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
- Runtime cleanup: <host-owned | not applicable>

## Discussion Summary

### Round 1

### Synthesis

### Round 2

### Direct Challenges

- 

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
- Fresh after final code change: no
- Notes:

## Completion

- Status: in-progress
- Residual risk:

## Open Questions

- 
""",
        )
    sync_work_index(work_dir)
    print(path)
    return path


def create_decision(args: argparse.Namespace) -> Path:
    root = Path(args.root).expanduser()
    date = today(args.date)
    title = single_line(args.title, "title")
    status = status_value(args.status)
    repo = single_line(args.repo, "repo", allow_empty=True) if args.repo is not None else None
    work_dir = ensure_work(root, args.work, repo)
    path = work_dir / "decisions" / f"{date}-{slugify(title)}.md"
    if path.exists() and note_title(path) != title:
        raise ValueError(
            f"decision slug collision: {title!r} resolves to existing note {path.name!r}"
        )
    feature_path: Path | None = None
    feature_reference = ""
    if args.feature:
        feature_path = (work_dir / args.feature).resolve()
        try:
            feature_path.relative_to(work_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"feature path escapes work namespace: {args.feature}") from exc
        if not feature_path.is_file():
            raise FileNotFoundError(f"related feature does not exist: {feature_path}")
        rel_feature = Path(os.path.relpath(feature_path, path.parent)).as_posix()
        feature_reference = f"[{markdown_label(note_title(feature_path))}]({rel_feature})"
    if not path.exists():
        atomic_write(
            path,
            f"""---
type: Decision
title: {yaml_quote(title)}
status: {status}
date: {date}
owner: PL agent
work: {work_dir.name}
---

# Decision: {title}

Related feature: {feature_reference}
Related files:
Related sources:
Supersedes:
Superseded by:

## Context

{args.context or ""}

## Options Considered

1. 
2. 
3. 

## Decision

{args.decision or ""}

## Rationale

## Consequences

Positive:
- 

Negative:
- 

## Validation

- 

## Open Questions

- 
""",
        )
    if feature_path:
        rel_decision = Path(os.path.relpath(path, feature_path.parent)).as_posix()
        add_metadata_link(feature_path, "Related decisions", title, rel_decision)
    sync_work_index(work_dir)
    print(path)
    return path


def iter_markdown_links(text: str):
    """Yield Markdown destinations with escaped labels and balanced path parentheses."""
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
            if text[label_end] == "]":
                break
            if text[label_end] == "\n":
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


def check_memory(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser()
    problems: list[str] = []
    for work_dir in sorted((root / "work").glob("*")):
        if work_dir.is_symlink():
            problems.append(f"symlinked work namespace is not allowed: {work_dir}")
        elif work_dir.is_dir() and work_dir.name != "_template":
            sync_work_index(work_dir)
    sync_root_index(root)
    markdown_files = sorted(root.rglob("*.md"))
    for note in markdown_files:
        text = note.read_text(encoding="utf-8")
        for destination in iter_markdown_links(text):
            target = local_link_target(note, destination)
            if target is not None and not target.exists():
                problems.append(f"missing local link: {note} -> {destination}")

    for decision in (root / "work").glob("*/decisions/*.md"):
        text = decision.read_text(encoding="utf-8")
        match = re.search(r"(?m)^Related feature:\s*(features/\S+\.md)\s*$", text)
        if match:
            target = (decision.parent.parent / match.group(1)).resolve()
            if not target.exists():
                problems.append(f"missing legacy feature link: {decision} -> {match.group(1)}")

    # Feature notes must use the completion-contract vocabulary so the PL can
    # trust status at a glance; free-text detail belongs in the note body.
    # Status lives in the YAML frontmatter (`status:`); plain `Status:` body
    # lines are accepted only as a legacy fallback for unmigrated notes.
    for feature in (root / "work").glob("*/features/*.md"):
        if feature.parent.parent.name == "_template" or feature.name.startswith("_"):
            continue
        text = feature.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        status = (frontmatter or {}).get("status")
        if status is None:
            match = re.search(r"(?m)^Status:\s*(.+)$", text)
            status = match.group(1).strip() if match else None
        if status is None:
            problems.append(f"missing feature status: {feature}")
        elif status not in FEATURE_STATUSES:
            problems.append(
                f"nonstandard feature status: {feature} -> {status!r}"
                f" (allowed: {', '.join(FEATURE_STATUSES)})"
            )

    if problems:
        for problem in problems:
            print(problem)
        return 1
    print(f"memory check ok ({len(markdown_files)} markdown files, 0 broken local links)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-work")
    init.add_argument("work")
    init.add_argument("--repo")
    init.set_defaults(func=lambda args: print(ensure_work(Path(args.root).expanduser(), args.work, args.repo)))

    feature = sub.add_parser("feature")
    feature.add_argument("work")
    feature.add_argument("title")
    feature.add_argument("--repo")
    feature.add_argument("--request")
    feature.add_argument("--status", default="in-progress")
    feature.add_argument("--date")
    feature.set_defaults(func=create_feature)

    decision = sub.add_parser("decision")
    decision.add_argument("work")
    decision.add_argument("title")
    decision.add_argument("--repo")
    decision.add_argument("--feature")
    decision.add_argument("--context")
    decision.add_argument("--decision")
    decision.add_argument("--status", default="accepted")
    decision.add_argument("--date")
    decision.set_defaults(func=create_decision)

    check = sub.add_parser("check")
    check.set_defaults(func=check_memory)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).expanduser()
    try:
        with memory_lock(root):
            result = args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
