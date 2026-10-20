#!/usr/bin/env python3
"""pl SubagentStop / SubagentHandback hook: save each role session's memo to
<history-root>/.runtime/<feature>/memos/<agent_id>.md so the lead can summarize
role opinions and merge reviewer findings from files instead of memory.

- Only fires for pl role agents (`agent_type` matching ^pl:team-pl-).
- On SubagentStop the memo is `last_assistant_message`; in auto mode the delivered
  report travels through the SubagentHandback tool instead, so the same script is
  also registered as a PostToolUse hook on that tool and reads `tool_input.message`.
- A memo without a `Status:` line is sent back once (`decision: block`); on the
  retry (`stop_hook_active` true) it is saved as-is so nothing loops.
- Any internal error exits 0 silently: the memo is already in the lead's context,
  so losing the file costs nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROLE_AGENT_PATTERN = re.compile(r"^pl:team-pl-")
STATUS_PATTERN = re.compile(r"(?m)^\s*Status:\s*(DONE|NEEDS_DECISION|BLOCKED)\b")
BLOCK_REASON = "Begin your memo with a Status: line (DONE | NEEDS_DECISION | BLOCKED) and resend it in full."


def load_pl_history():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[1])
    path = Path(root) / "skills" / "team-pl-orchestrator" / "scripts" / "pl_history.py"
    spec = importlib.util.spec_from_file_location("pl_history", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("pl_history.py not found")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules; register before executing.
    sys.modules["pl_history"] = module
    spec.loader.exec_module(module)
    return module


def newest_runtime_dir(root: Path) -> Path | None:
    runtime = root / ".runtime"
    if not runtime.is_dir():
        return None
    candidates = [p for p in runtime.iterdir() if p.is_dir() and (p / "ledger.md").is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p / "ledger.md").stat().st_mtime)


def message_from(payload: dict) -> str | None:
    if payload.get("hook_event_name") == "PostToolUse":
        if payload.get("tool_name") != "SubagentHandback":
            return None
        tool_input = payload.get("tool_input") or {}
        return str(tool_input.get("message") or "") or None
    return str(payload.get("last_assistant_message") or "") or None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        agent_type = str(payload.get("agent_type") or "")
        if not ROLE_AGENT_PATTERN.match(agent_type):
            return 0
        message = message_from(payload)
        if message is None:
            return 0
        if payload.get("hook_event_name") != "PostToolUse" and not STATUS_PATTERN.search(message) and not payload.get("stop_hook_active"):
            print(json.dumps({"decision": "block", "reason": BLOCK_REASON}))
            return 0
        ph = load_pl_history()
        cwd = Path(payload.get("cwd") or os.getcwd())
        resolved = ph.resolve(cwd)
        if not resolved.root.is_dir():
            return 0
        target = newest_runtime_dir(resolved.root)
        if target is None:
            return 0
        agent_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("agent_id") or "unknown"))
        memo = target / "memos" / f"{agent_id}.md"
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        ph.atomic_write(memo, f"# {agent_type} {stamp}\n\n{message.rstrip()}\n")
    except Exception:  # noqa: BLE001 — fail open; see module docstring
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
