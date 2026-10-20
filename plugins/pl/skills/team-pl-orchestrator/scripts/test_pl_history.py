#!/usr/bin/env python3
"""Behavior tests for pl_history.py — the in-repo history helper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import pl_history as ph  # noqa: E402


def git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def make_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "init")
    return repo


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def resolve(self, cwd: Path, **kw):
        return ph.resolve(cwd, config_path=kw.get("config_path"), work=kw.get("work"), root_override=kw.get("root_override"))


class WhereTests(TempDirCase):
    def test_where_defaults_to_docs_pl_in_repo(self) -> None:
        repo = make_repo(self.base)
        resolved = self.resolve(repo)
        self.assertEqual(resolved.mode, "repo")
        self.assertEqual(resolved.root, repo / "docs" / "pl")
        ph.ensure_layout(resolved.root)
        self.assertEqual((resolved.root / ".runtime" / ".gitignore").read_text(encoding="utf-8"), "*\n")
        self.assertTrue((resolved.root / "architecture.md").is_file())
        self.assertTrue((resolved.root / "features").is_dir())
        self.assertTrue((resolved.root / "decisions").is_dir())

    def test_where_reads_team_history_dir(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        (repo / ".agents" / "pl.md").write_text("---\nhistoryDir: notes/pl\n---\n", encoding="utf-8")
        resolved = self.resolve(repo)
        self.assertEqual(resolved.root, repo / "notes" / "pl")
        self.assertEqual(resolved.history_dir, "notes/pl")

    def test_where_rejects_escaping_history_dir(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        for bad in ("../x", "/abs/path", ".git/x", "docs/../../x"):
            (repo / ".agents" / "pl.md").write_text(f"---\nhistoryDir: {bad}\n---\n", encoding="utf-8")
            with self.assertRaises(ph.HistoryError, msg=bad):
                self.resolve(repo)
        self.assertFalse((repo / "docs").exists())

    def test_where_ignores_local_history_dir_with_warning(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        (repo / ".agents" / "pl.local.md").write_text("---\nhistoryDir: elsewhere\nworkNamespace: old\n---\n", encoding="utf-8")
        resolved = self.resolve(repo)
        self.assertEqual(resolved.root, repo / "docs" / "pl")
        self.assertTrue(any("historyDir" in w for w in resolved.warnings))
        self.assertTrue(any("workNamespace" in w for w in resolved.warnings))

    def test_where_merges_verify_commands_team_and_local(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        (repo / ".agents" / "pl.md").write_text(
            "---\nverifyCommands:\n  - a\nprotectedPaths:\n  - infra/\n---\n", encoding="utf-8"
        )
        (repo / ".agents" / "pl.local.md").write_text("---\nverifyCommands:\n  - b\n  - a\n---\n", encoding="utf-8")
        resolved = self.resolve(repo)
        self.assertEqual(resolved.verify_commands, ["a", "b"])
        self.assertEqual(resolved.protected_paths, ["infra/"])

    def test_where_prefers_agents_local_over_claude_local(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        (repo / ".claude").mkdir()
        (repo / ".agents" / "pl.local.md").write_text("---\nverifyCommands:\n  - agents\n---\n", encoding="utf-8")
        (repo / ".claude" / "pl.local.md").write_text("---\nverifyCommands:\n  - claude\n---\n", encoding="utf-8")
        resolved = self.resolve(repo)
        self.assertEqual(resolved.verify_commands, ["agents"])
        self.assertTrue(any("pl.local.md" in w for w in resolved.warnings))

    def test_where_local_mode_uses_xdg_and_work(self) -> None:
        cwd = self.base / "plain"
        cwd.mkdir()
        xdg = self.base / "xdg"
        with unittest.mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(xdg)}):
            resolved = self.resolve(cwd, work="foo")
        self.assertEqual(resolved.mode, "local")
        self.assertEqual(resolved.root, xdg / "pl" / "history" / "foo")
        self.assertIsNone(resolved.repo_top)

    def test_where_local_mode_without_work_uses_inbox(self) -> None:
        cwd = self.base / "plain"
        cwd.mkdir()
        with unittest.mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.base / "xdg")}):
            resolved = self.resolve(cwd)
        self.assertEqual(resolved.root.name, "inbox")
        self.assertTrue(any("inbox" in w for w in resolved.warnings))

    def test_where_local_mode_config_history_root(self) -> None:
        cwd = self.base / "plain"
        cwd.mkdir()
        config = self.base / "config.json"
        config.write_text(json.dumps({"historyRoot": str(self.base / "hist")}), encoding="utf-8")
        resolved = self.resolve(cwd, config_path=config, work="w")
        self.assertEqual(resolved.root, self.base / "hist" / "w")

    def test_where_cli_json_output(self) -> None:
        repo = make_repo(self.base)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "pl_history.py"), "where", "--json"],
            cwd=repo, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["mode"], "repo")
        self.assertTrue(data["created"])
        self.assertTrue((repo / "docs" / "pl" / ".runtime" / ".gitignore").is_file())

    def test_where_cli_rejects_with_exit_2(self) -> None:
        repo = make_repo(self.base)
        (repo / ".agents").mkdir()
        (repo / ".agents" / "pl.md").write_text("---\nhistoryDir: ../x\n---\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "pl_history.py"), "where"], cwd=repo, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("historyDir", proc.stderr)


class NoteTests(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = make_repo(self.base)
        self.resolved = self.resolve(self.repo)
        ph.ensure_layout(self.resolved.root)
        self.root = self.resolved.root

    def test_feature_creates_note_and_runtime_ledger(self) -> None:
        path = ph.create_feature(self.root, "Add partial cancel", request="partial cancel", repo_name="shop", date="2026-10-20")
        self.assertEqual(path, self.root / "features" / "2026-10-20-add-partial-cancel.md")
        text = path.read_text(encoding="utf-8")
        fm = ph.parse_frontmatter(text)
        self.assertEqual(fm["status"], "in-progress")
        self.assertEqual(fm["title"], "Add partial cancel")
        self.assertEqual(fm["repo"], "shop")
        self.assertEqual(fm["decisions"], [])
        headings = [l for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(headings, [
            "## Request", "## Scope", "## Roles and Opinions", "## Synthesis", "## Challenges",
            "## PL Decisions", "## Implementation Summary", "## Changed Files", "## Verification",
            "## Review", "## Completion", "## Open Questions",
        ])
        self.assertIn("partial cancel", text)
        ledger = self.root / ".runtime" / "2026-10-20-add-partial-cancel" / "ledger.md"
        self.assertTrue(ledger.is_file())
        self.assertIn("## Execution Ledger", ledger.read_text(encoding="utf-8"))
        self.assertIn("## Wave Baselines", ledger.read_text(encoding="utf-8"))

    def test_feature_same_title_same_day_is_idempotent(self) -> None:
        first = ph.create_feature(self.root, "Same", request="r1", repo_name="x", date="2026-10-20")
        before = first.read_text(encoding="utf-8")
        second = ph.create_feature(self.root, "Same", request="r2", repo_name="x", date="2026-10-20")
        self.assertEqual(first, second)
        self.assertEqual(first.read_text(encoding="utf-8"), before)

    def test_feature_slug_collision_different_title_fails(self) -> None:
        ph.create_feature(self.root, "Add X!", request="", repo_name="x", date="2026-10-20")
        with self.assertRaises(ph.HistoryError):
            ph.create_feature(self.root, "Add X?", request="", repo_name="x", date="2026-10-20")

    def test_decision_links_both_ways(self) -> None:
        feature = ph.create_feature(self.root, "Feat", request="", repo_name="x", date="2026-10-20")
        decision = ph.create_decision(self.root, "Use queue", feature=feature, supersedes=None, date="2026-10-20")
        self.assertEqual(decision, self.root / "decisions" / "2026-10-20-use-queue.md")
        dfm = ph.parse_frontmatter(decision.read_text(encoding="utf-8"))
        self.assertEqual(dfm["status"], "accepted")
        self.assertEqual(dfm["feature"], "features/2026-10-20-feat.md")
        ffm = ph.parse_frontmatter(feature.read_text(encoding="utf-8"))
        self.assertEqual(ffm["decisions"], ["decisions/2026-10-20-use-queue.md"])

    def test_decision_supersedes_marks_old(self) -> None:
        feature = ph.create_feature(self.root, "Feat", request="", repo_name="x", date="2026-10-20")
        old = ph.create_decision(self.root, "Old", feature=feature, supersedes=None, date="2026-10-19")
        new = ph.create_decision(self.root, "New", feature=feature, supersedes=old, date="2026-10-20")
        ofm = ph.parse_frontmatter(old.read_text(encoding="utf-8"))
        self.assertEqual(ofm["status"], "superseded")
        self.assertEqual(ofm["superseded_by"], "decisions/2026-10-20-new.md")
        nfm = ph.parse_frontmatter(new.read_text(encoding="utf-8"))
        self.assertEqual(nfm["supersedes"], "decisions/2026-10-19-old.md")

    def test_list_reads_frontmatter_only(self) -> None:
        f = ph.create_feature(self.root, "Feat", request="", repo_name="x", date="2026-10-20")
        ph.create_decision(self.root, "Dec", feature=f, supersedes=None, date="2026-10-20")
        rows = ph.list_notes(self.root, kind=None, status=None)
        self.assertEqual([(r["type"], r["title"]) for r in rows], [("Feature", "Feat"), ("Decision", "Dec")])
        self.assertEqual(ph.list_notes(self.root, kind="decision", status="accepted")[0]["title"], "Dec")
        self.assertEqual(ph.list_notes(self.root, kind="feature", status="done"), [])
        self.assertEqual([p.name for p in self.root.rglob("INDEX.md")], [])

    def test_feature_stem_accepts_stem_name_or_path(self) -> None:
        f = ph.create_feature(self.root, "Feat", request="", repo_name="x", date="2026-10-20")
        for ref in ("2026-10-20-feat", "2026-10-20-feat.md", str(f), "features/2026-10-20-feat.md"):
            self.assertEqual(ph.feature_stem(self.root, ref), "2026-10-20-feat", ref)
        with self.assertRaises(ph.HistoryError):
            ph.feature_stem(self.root, "nope")

    def test_feature_cli_prints_path(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "pl_history.py"), "feature", "CLI feat", "--request", "r", "--date", "2026-10-20"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(Path(proc.stdout.strip()), self.root / "features" / "2026-10-20-cli-feat.md")


class VerifyTests(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = make_repo(self.base)
        self.resolved = self.resolve(self.repo)
        ph.ensure_layout(self.resolved.root)
        self.root = self.resolved.root
        self.feature = ph.create_feature(self.root, "Feat", request="", repo_name="x", date="2026-10-20")
        self.stem = self.feature.stem

    def py(self, code: str) -> list[str]:
        return [sys.executable, "-c", code]

    def test_verify_records_evidence_and_section(self) -> None:
        rc = ph.run_verify(self.resolved, self.stem, self.py("print(1)"))
        self.assertEqual(rc, 0)
        records = [json.loads(l) for l in ph.evidence_path(self.root, self.stem).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["exit"], 0)
        self.assertEqual(records[0]["tail"], ["1"])
        self.assertTrue(records[0]["fp_after"])
        text = self.feature.read_text(encoding="utf-8")
        self.assertIn("| 0 |", text)
        self.assertIn("print(1)", text)

    def test_verify_failure_exit_propagates(self) -> None:
        rc = ph.run_verify(self.resolved, self.stem, self.py("import sys; sys.exit(3)"))
        self.assertEqual(rc, 3)
        self.assertIn("| 3 |", self.feature.read_text(encoding="utf-8"))

    def test_fingerprint_ignores_history_root(self) -> None:
        before = ph.fingerprint(self.repo, self.root)
        (self.root / "features" / "scratch.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(before, ph.fingerprint(self.repo, self.root))
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        self.assertNotEqual(before, ph.fingerprint(self.repo, self.root))

    def test_fingerprint_post_run_is_baseline(self) -> None:
        ph.run_verify(self.resolved, self.stem, self.py("open('coverage.out','w').write('c')"))
        record = ph.latest_evidence(self.root, self.stem)[list(ph.latest_evidence(self.root, self.stem))[0]]
        self.assertNotEqual(record["fp_before"], record["fp_after"])
        self.assertEqual(record["fp_after"], ph.fingerprint(self.repo, self.root))
        self.assertIn("command modified the working tree", self.feature.read_text(encoding="utf-8"))

    def test_withdraw_removes_from_required_and_logs(self) -> None:
        argv = self.py("print(2)")
        ph.run_verify(self.resolved, self.stem, argv)
        command = ph.command_string(argv)
        ph.withdraw(self.resolved, self.stem, command, "wrong suite")
        self.assertNotIn(command, ph.required_commands(self.resolved, self.stem))
        text = self.feature.read_text(encoding="utf-8")
        self.assertIn("withdrawn: wrong suite", text)
        last = json.loads(ph.evidence_path(self.root, self.stem).read_text(encoding="utf-8").splitlines()[-1])
        self.assertTrue(last["withdrawn"])

    def test_withdraw_verify_command_refused(self) -> None:
        (self.repo / ".agents").mkdir()
        (self.repo / ".agents" / "pl.md").write_text("---\nverifyCommands:\n  - echo team\n---\n", encoding="utf-8")
        resolved = self.resolve(self.repo)
        with self.assertRaises(ph.HistoryError):
            ph.withdraw(resolved, self.stem, "echo team", "no")
        self.assertIn("echo team", ph.required_commands(resolved, self.stem))

    def test_fingerprint_none_in_local_mode(self) -> None:
        self.assertIsNone(ph.fingerprint(None, self.root))

    def test_verify_cli(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "pl_history.py"), "verify", "--feature", self.stem, "--", sys.executable, "-c", "print('ok')"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok", proc.stdout)


class FrontmatterTests(unittest.TestCase):
    def test_parse_frontmatter_simple_lists_and_scalars(self) -> None:
        text = "---\nhistoryDir: docs/pl\nverifyCommands:\n  - ./gradlew test\n  - npm test\nquoted: \"a: b\"\n---\nbody\n"
        data, warnings = ph.parse_frontmatter_simple(text)
        self.assertEqual(data["historyDir"], "docs/pl")
        self.assertEqual(data["verifyCommands"], ["./gradlew test", "npm test"])
        self.assertEqual(data["quoted"], "a: b")
        self.assertEqual(warnings, [])

    def test_parse_frontmatter_simple_warns_on_nested(self) -> None:
        text = "---\nnested:\n  key: value\n---\n"
        data, warnings = ph.parse_frontmatter_simple(text)
        self.assertNotIn("nested", data)
        self.assertTrue(warnings)

    def test_parse_frontmatter_simple_no_frontmatter(self) -> None:
        self.assertEqual(ph.parse_frontmatter_simple("# just text\n"), ({}, []))


if __name__ == "__main__":
    unittest.main()
