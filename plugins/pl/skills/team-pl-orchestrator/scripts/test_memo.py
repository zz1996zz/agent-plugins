#!/usr/bin/env python3
"""hook 없이 lead가 전달받은 memo를 기록하는 경로의 행동 테스트."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pl_history as ph


class MemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "history"
        ph.ensure_layout(self.root)
        self.note = ph.create_feature(self.root, "memo", request="r", repo_name="test", date="2026-11-01")

    def run_memo(self, *args, message="Status: DONE\nGate 1: PASS\nGate 2: PASS\n"):
        return subprocess.run(
            [sys.executable, str(Path(ph.__file__)), "--root", str(self.root), "memo",
             "--feature", self.note.stem, *args],
            input=message, capture_output=True, text=True,
        )

    def test_cli_saves_exact_delivered_memo_without_hooks(self):
        result = self.run_memo("--agent-id", "agent-42")
        self.assertEqual(0, result.returncode, result.stderr)
        path = Path(result.stdout.strip())
        self.assertEqual(self.root / ".runtime" / self.note.stem / "memos", path.parent)
        self.assertEqual("Status: DONE\nGate 1: PASS\nGate 2: PASS\n", path.read_text())
        self.assertEqual(path, Path(result.stdout.strip()))

    def test_cli_rejects_invalid_or_missing_status(self):
        for message in ("", "Done", "quoted\nStatus: DONE\n", "Status: PARTIAL\n"):
            with self.subTest(message=message):
                result = self.run_memo("--agent-id", "agent-42", message=message)
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn("Status:", result.stderr)
        self.assertFalse((self.root / ".runtime" / self.note.stem / "memos").exists())

    def test_cli_maps_opaque_ids_to_distinct_safe_filenames(self):
        paths = set()
        for agent in ("../escape", "/root/pl-review", ".", "..", "a/b", "a\\b"):
            with self.subTest(agent=agent):
                result = self.run_memo("--agent-id", agent)
                self.assertEqual(0, result.returncode, result.stderr)
                path = Path(result.stdout.strip())
                self.assertEqual(self.root / ".runtime" / self.note.stem / "memos", path.parent)
                self.assertNotIn(path, paths)
                self.assertTrue(path.is_file())
                paths.add(path)

    def test_cli_rejects_symlink_escape(self):
        runtime = self.root / ".runtime" / self.note.stem
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (runtime / "memos").symlink_to(outside, target_is_directory=True)
        result = self.run_memo("--agent-id", "agent-42")
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual([], list(outside.iterdir()))

    def test_cli_requires_explicit_feature_even_when_current_exists(self):
        result = subprocess.run(
            [sys.executable, str(Path(ph.__file__)), "--root", str(self.root), "memo", "--agent-id", "a"],
            input="Status: DONE\n", capture_output=True, text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--feature", result.stderr)

    def test_resume_preserves_previous_memo_and_repeat_save_is_idempotent(self):
        first = self.run_memo("--agent-id", "/root/pl_review", message="Status: DONE\nround 1\n")
        second = self.run_memo("--agent-id", "/root/pl_review", message="Status: DONE\nround 2\n")
        repeat = self.run_memo("--agent-id", "/root/pl_review", message="Status: DONE\nround 2\n")
        for result in (first, second, repeat):
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotEqual(first.stdout, second.stdout)
        self.assertEqual(second.stdout, repeat.stdout)
        self.assertEqual("Status: DONE\nround 1\n", Path(first.stdout.strip()).read_text())
        self.assertEqual("Status: DONE\nround 2\n", Path(second.stdout.strip()).read_text())


if __name__ == "__main__":
    unittest.main()
