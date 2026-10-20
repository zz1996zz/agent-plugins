#!/usr/bin/env python3
"""Behavior tests for the plugin hooks that depend on pl_history (memo_capture.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
MEMO_CAPTURE = PLUGIN_ROOT / "hooks" / "memo_capture.py"
sys.path.insert(0, str(SCRIPT_DIR))

import pl_history as ph  # noqa: E402
from test_pl_history import make_repo  # noqa: E402


class MemoCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.repo = make_repo(self.base)
        self.resolved = ph.resolve(self.repo)
        ph.ensure_layout(self.resolved.root)
        self.feature = ph.create_feature(self.resolved.root, "Feat", request="", repo_name="x", date="2026-10-20")
        self.memos = ph.runtime_dir(self.resolved.root, self.feature.stem) / "memos"

    def run_hook(self, payload: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT))
        return subprocess.run(
            [sys.executable, str(MEMO_CAPTURE)], input=json.dumps(payload), cwd=self.repo,
            capture_output=True, text=True, env=env,
        )

    def stop_payload(self, message: str, *, agent_type: str = "pl:team-pl-architect", active: bool = False) -> dict:
        return {
            "hook_event_name": "SubagentStop", "cwd": str(self.repo), "agent_id": "abc123",
            "agent_type": agent_type, "stop_hook_active": active, "last_assistant_message": message,
        }

    def test_memo_capture_writes_file(self) -> None:
        proc = self.run_hook(self.stop_payload("Status: DONE\nProposed design: x"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")
        memo = self.memos / "abc123.md"
        self.assertTrue(memo.is_file())
        text = memo.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# pl:team-pl-architect "), text[:60])
        self.assertIn("Proposed design: x", text)

    def test_memo_capture_blocks_once_without_status(self) -> None:
        proc = self.run_hook(self.stop_payload("no status line here"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("Status:", out["reason"])
        # second stop with stop_hook_active: accept and save, never loop
        proc = self.run_hook(self.stop_payload("still no status", active=True))
        self.assertEqual(proc.stdout.strip(), "")
        self.assertTrue((self.memos / "abc123.md").is_file())

    def test_memo_capture_ignores_other_agents(self) -> None:
        proc = self.run_hook(self.stop_payload("Status: DONE", agent_type="Explore"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertFalse(self.memos.exists())

    def test_memo_capture_handback_post_tool_use(self) -> None:
        payload = {
            "hook_event_name": "PostToolUse", "cwd": str(self.repo), "agent_id": "h1",
            "agent_type": "pl:team-pl-qa-engineer", "tool_name": "SubagentHandback",
            "tool_input": {"message": "Status: DONE\nTest plan: y"}, "tool_response": {},
        }
        proc = self.run_hook(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Test plan: y", (self.memos / "h1.md").read_text(encoding="utf-8"))

    def test_memo_capture_fails_open_outside_history(self) -> None:
        plain = self.base / "plain"
        plain.mkdir()
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT))
        proc = subprocess.run(
            [sys.executable, str(MEMO_CAPTURE)], input=json.dumps(self.stop_payload("Status: DONE")),
            cwd=plain, capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
