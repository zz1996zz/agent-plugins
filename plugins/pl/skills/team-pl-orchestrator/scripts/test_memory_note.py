#!/usr/bin/env python3
"""Regression tests for memory_note.py using disposable vaults."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SCRIPT = Path(__file__).with_name("memory_note.py")
sys.path.insert(0, str(SCRIPT.parent))
from memory_note import slugify  # noqa: E402


class MemoryNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="pl-memory-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve() / "memory"

    def run_helper(self, *args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if expect_ok and result.returncode != 0:
            self.fail(f"helper failed for {args}:\nstdout={result.stdout}\nstderr={result.stderr}")
        if not expect_ok and result.returncode == 0:
            self.fail(f"helper unexpectedly passed for {args}")
        return result

    def test_concurrent_creation_indexes_and_backlinks(self) -> None:
        work = "regression"
        self.run_helper("init-work", work, "--repo", "/tmp/example-repo")

        same_args = ("feature", work, "Concurrent feature", "--date", "2026-07-13")
        with ThreadPoolExecutor(max_workers=8) as pool:
            same_results = list(pool.map(lambda _: self.run_helper(*same_args), range(8)))
        self.assertEqual(1, len({result.stdout.strip() for result in same_results}))

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(
                pool.map(
                    lambda index: self.run_helper(
                        "feature", work, f"Parallel feature {index}", "--date", "2026-07-13"
                    ),
                    range(6),
                )
            )

        feature_result = self.run_helper(
            "feature", work, "API review (compact)", "--date", "2026-07-13"
        )
        feature = Path(feature_result.stdout.strip())
        decision_args = (
            "decision",
            work,
            "Parenthesized link decision",
            "--feature",
            f"features/{feature.name}",
            "--date",
            "2026-07-13",
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            decision_results = list(pool.map(lambda _: self.run_helper(*decision_args), range(8)))
        self.assertEqual(1, len({result.stdout.strip() for result in decision_results}))

        result = self.run_helper("check")
        self.assertIn("0 broken local links", result.stdout)

        work_dir = self.root / "work" / work
        index = (work_dir / "INDEX.md").read_text(encoding="utf-8")
        notes = list((work_dir / "features").glob("*.md")) + list(
            (work_dir / "decisions").glob("*.md")
        )
        for note in notes:
            target = f"({note.parent.name}/{note.name})"
            self.assertEqual(1, index.count(target), target)

        decision = Path(decision_results[0].stdout.strip())
        feature_text = feature.read_text(encoding="utf-8")
        self.assertTrue(feature_text.startswith("---\n"))
        self.assertIn("type: Feature", feature_text)
        self.assertIn('title: "API review (compact)"', feature_text)
        self.assertIn("status: in-progress", feature_text)
        self.assertEqual(1, feature_text.count(decision.name))
        self.assertIn("- Force-stopped:", feature_text)
        self.assertIn("- Unconfirmed stop:", feature_text)
        self.assertIn("- Runtime cleanup: host-owned", feature_text)
        self.assertNotIn("<host-owned | not applicable>", feature_text)
        decision_text = decision.read_text(encoding="utf-8")
        self.assertTrue(decision_text.startswith("---\n"))
        self.assertIn("type: Decision", decision_text)
        self.assertEqual(1, decision_text.count(feature.name))
        self.assertFalse(list(self.root.rglob("*.tmp")))

    def test_rejects_escape_and_detects_broken_link(self) -> None:
        work = "validation"
        self.run_helper("init-work", work)
        escaped = self.run_helper(
            "decision",
            work,
            "Escape attempt",
            "--feature",
            "../outside.md",
            expect_ok=False,
        )
        self.assertIn("escapes work namespace", escaped.stderr)
        self.assertNotIn("Traceback", escaped.stderr)

        broken = self.root / "work" / work / "features" / "broken.md"
        broken.write_text(
            "# Broken\n\n[missing \\[label\\]](missing.md)\n",
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("missing local link:", result.stdout)
        broken.unlink()
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_rejects_invalid_dates_before_creating_a_workspace(self) -> None:
        for value in ("../../escape", "2026-02-30", "20260713"):
            result = self.run_helper(
                "feature",
                "invalid-date",
                "Must not be created",
                "--date",
                value,
                expect_ok=False,
            )
            self.assertIn("date must be a valid YYYY-MM-DD value", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

        self.assertFalse((self.root / "work").exists())
        self.assertFalse(list(Path(self.temp_dir.name).rglob("*must-not-be-created.md")))

    def test_rejects_metadata_injection_and_symlinked_workspaces(self) -> None:
        invalid_commands = (
            ("feature", "bad-title", "Bad\n## Injected", "--date", "2026-07-13"),
            (
                "feature",
                "bad-status",
                "Status injection",
                "--status",
                "done\nOwner: attacker",
                "--date",
                "2026-07-13",
            ),
            (
                "feature",
                "bad-repo",
                "Repo injection",
                "--repo",
                "/tmp/repo\nStatus: done",
                "--date",
                "2026-07-13",
            ),
        )
        for command in invalid_commands:
            result = self.run_helper(*command, expect_ok=False)
            self.assertIn("must be a single-line value", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "work").exists())

        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        work_root = self.root / "work"
        work_root.mkdir(parents=True)
        linked = work_root / "linked"
        linked.symlink_to(outside, target_is_directory=True)
        result = self.run_helper(
            "feature",
            "linked",
            "Must stay inside",
            "--date",
            "2026-07-13",
            expect_ok=False,
        )
        self.assertIn("work namespace must not be a symlink", result.stderr)
        self.assertFalse(list(outside.iterdir()))
        check = self.run_helper("check", expect_ok=False)
        self.assertIn("symlinked work namespace is not allowed", check.stdout)
        linked.unlink()

        feature = Path(
            self.run_helper(
                "feature", "labels", "Review [API]", "--date", "2026-07-13"
            ).stdout.strip()
        )
        index = feature.parent.parent.joinpath("INDEX.md").read_text(encoding="utf-8")
        self.assertIn(r"[Review \[API\]]", index)

        self.run_helper("feature", "collision", "A/B", "--date", "2026-07-13")
        collision = self.run_helper(
            "feature",
            "collision",
            "A:B",
            "--date",
            "2026-07-13",
            expect_ok=False,
        )
        self.assertIn("feature slug collision", collision.stderr)
        self.assertNotIn("Traceback", collision.stderr)
        self.assertEqual(
            1,
            len(list((self.root / "work" / "collision" / "features").glob("*.md"))),
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)


    def test_check_rejects_status_mismatch_between_frontmatter_and_completion(self) -> None:
        self.run_helper("feature", "acme", "Status sync test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        original = feature.read_text(encoding="utf-8")

        # A fresh note agrees with itself.
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        feature.write_text(
            original.replace("- Status: in-progress", "- Status: done-with-risks", 1),
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("feature status mismatch", result.stdout)

        feature.write_text(
            original.replace("status: in-progress", "status: done-with-risks", 1)
            .replace("- Status: in-progress", "- Status: done-with-risks", 1)
            .replace(
                "- Role sandbox: <inherited from lead session | read-only enforced>",
                "- Role sandbox: inherited from lead session",
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_check_rejects_unresolved_choice_placeholder(self) -> None:
        self.run_helper("feature", "acme", "Placeholder test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        original = feature.read_text(encoding="utf-8")

        # A fresh in-progress note ships one deliberate placeholder (Role
        # sandbox); placeholders are enforced only once the note is finished.
        self.assertIn("- Role sandbox: <inherited from lead session | read-only enforced>", original)
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # Injecting a second placeholder into a still in-progress note is
        # still fine — the note has not yet claimed to be finished.
        with_extra_placeholder = original.replace(
            "- Runtime cleanup: host-owned",
            "- Runtime cleanup: <host-owned | not applicable>",
            1,
        )
        feature.write_text(with_extra_placeholder, encoding="utf-8")
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # Once the note claims to be done, every placeholder must be resolved.
        done_with_placeholders = with_extra_placeholder.replace(
            "status: in-progress", "status: done", 1
        ).replace("- Status: in-progress", "- Status: done", 1)
        feature.write_text(done_with_placeholders, encoding="utf-8")
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("unresolved placeholder", result.stdout)

        # Resolving both placeholders lets the finished note pass again.
        resolved = done_with_placeholders.replace(
            "- Runtime cleanup: <host-owned | not applicable>",
            "- Runtime cleanup: host-owned",
            1,
        ).replace(
            "- Role sandbox: <inherited from lead session | read-only enforced>",
            "- Role sandbox: inherited from lead session",
            1,
        )
        feature.write_text(resolved, encoding="utf-8")
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_check_accepts_status_reason_after_the_status_token(self) -> None:
        self.run_helper("feature", "acme", "Status reason test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        original = feature.read_text(encoding="utf-8")

        feature.write_text(
            original.replace("status: in-progress", "status: done-with-risks", 1)
            .replace(
                "- Status: in-progress",
                "- Status: done-with-risks (verification could not run)",
                1,
            )
            .replace(
                "- Role sandbox: <inherited from lead session | read-only enforced>",
                "- Role sandbox: inherited from lead session",
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_check_rejects_done_status_with_force_closed_lifecycle(self) -> None:
        self.run_helper("feature", "acme", "Done gate test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        original = feature.read_text(encoding="utf-8")

        def finish(text: str, status: str) -> str:
            return (
                text.replace("status: in-progress", f"status: {status}", 1)
                .replace("- Status: in-progress", f"- Status: {status}", 1)
                .replace(
                    "- Role sandbox: <inherited from lead session | read-only enforced>",
                    "- Role sandbox: inherited from lead session",
                    1,
                )
            )

        # A code reviewer force-closed without delivering its memo: `done`
        # must be mechanically rejected even though nothing else is wrong.
        force_closed_note = finish(original, "done").replace(
            "- Force-stopped:",
            "- Force-stopped: code-reviewer was force-closed without delivering a memo",
            1,
        )
        feature.write_text(force_closed_note, encoding="utf-8")
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("done status contradicts Team Lifecycle", result.stdout)
        self.assertIn("force-closed", result.stdout)

        # The identical Team Lifecycle content is fine once the status is
        # honest about the unresolved review gate instead of claiming `done`.
        feature.write_text(
            finish(original, "done-with-risks").replace(
                "- Force-stopped:",
                "- Force-stopped: code-reviewer was force-closed without delivering a memo",
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # A `done` note whose Team Lifecycle carries none of the forbidden
        # phrases still passes normally.
        feature.write_text(finish(original, "done"), encoding="utf-8")
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_check_ignores_placeholders_inside_code(self) -> None:
        self.run_helper("feature", "acme", "Code span test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        # Placeholders are enforced only once a note is no longer in-progress;
        # finish it and resolve its one shipped placeholder (Role sandbox) so
        # this test isolates the code-quoting behavior it targets.
        original = (
            feature.read_text(encoding="utf-8")
            .replace("status: in-progress", "status: done", 1)
            .replace("- Status: in-progress", "- Status: done", 1)
            .replace(
                "- Role sandbox: <inherited from lead session | read-only enforced>",
                "- Role sandbox: inherited from lead session",
                1,
            )
        )
        feature.write_text(original, encoding="utf-8")

        quoted_code = original.replace(
            "## Open Questions",
            "## Notes\n\n"
            "- The helper returns `Promise<string | null>` on miss.\n\n"
            "```\n"
            "- Runtime cleanup: <a | b>\n"
            "```\n\n"
            "## Open Questions",
            1,
        )
        feature.write_text(quoted_code, encoding="utf-8")
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # The same text outside code is still an unfinished note.
        feature.write_text(
            quoted_code.replace(
                "- Runtime cleanup: host-owned",
                "- Runtime cleanup: <host-owned | not applicable>",
                1,
            ),
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("unresolved placeholder", result.stdout)

    def test_check_rejects_nonstandard_feature_status(self) -> None:
        self.run_helper("feature", "acme", "Status vocab test", "--repo", "/tmp/acme")
        feature = next((self.root / "work" / "acme" / "features").glob("*.md"))
        original = feature.read_text(encoding="utf-8")
        self.assertIn("status: in-progress", original)

        feature.write_text(
            original.replace("status: in-progress", "status: implemented", 1),
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("nonstandard feature status", result.stdout)

        # Completion must move with the frontmatter, or `check` flags the mismatch.
        feature.write_text(
            original.replace("status: in-progress", "status: done-with-risks", 1)
            .replace("- Status: in-progress", "- Status: done-with-risks", 1)
            .replace(
                "- Role sandbox: <inherited from lead session | read-only enforced>",
                "- Role sandbox: inherited from lead session",
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # The creator must reject vocabulary its own check would flag.
        result = self.run_helper(
            "feature", "acme", "Draft attempt", "--status", "draft", expect_ok=False
        )
        self.assertIn("feature status must be one of", result.stderr + result.stdout)

        # A feature note without any status field is itself a defect.
        feature.write_text(
            "\n".join(
                line
                for line in feature.read_text(encoding="utf-8").splitlines()
                if not line.startswith(("status:", "Status:"))
            )
            + "\n",
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("missing feature status", result.stdout)

    def test_note_title_prefers_frontmatter_and_reads_crlf(self) -> None:
        work_dir = self.root / "work" / "titles"
        features = work_dir / "features"
        features.mkdir(parents=True)
        (work_dir / "INDEX.md").write_text(
            "# Work: titles\n\n## Features\n\n- (none)\n\n## Decisions\n\n- (none)\n",
            encoding="utf-8",
        )
        # Frontmatter title wins over a diverging H1; CRLF frontmatter still parses.
        (features / "titled.md").write_text(
            '---\r\ntype: Feature\r\ntitle: "Frontmatter title"\r\nstatus: done\r\n---\r\n\r\n'
            "# Feature: Body title\r\n",
            encoding="utf-8",
        )
        self.run_helper("check")
        index = (work_dir / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("[Frontmatter title](features/titled.md)", index)
        self.assertNotIn("Body title", index)

    def test_legacy_plain_status_and_frontmatter_precedence(self) -> None:
        work_dir = self.root / "work" / "legacy-status"
        features = work_dir / "features"
        features.mkdir(parents=True)

        # Unmigrated plain-header note: legacy `Status:` line still passes.
        (features / "plain.md").write_text(
            "# Feature: Plain legacy\n\nStatus: done\n", encoding="utf-8"
        )
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # Frontmatter status wins over a stale body line.
        (features / "plain.md").write_text(
            "---\ntype: Feature\ntitle: \"Plain legacy\"\nstatus: bogus\n---\n\n"
            "# Feature: Plain legacy\n\nStatus: done\n",
            encoding="utf-8",
        )
        result = self.run_helper("check", expect_ok=False)
        self.assertIn("nonstandard feature status", result.stdout)
        self.assertIn("'bogus'", result.stdout)

    def test_backslash_content_survives_index_rewrites(self) -> None:
        # Replacement strings must be treated literally: a Windows-style repo
        # path used to crash re.sub with "bad escape" once the section existed.
        self.run_helper("init-work", "first", "--repo", "/tmp/normal-repo")
        self.run_helper("init-work", "second", "--repo", r"C:\Users\name")
        root_index = (self.root / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("work/second/", root_index)

        # Legacy hand-edited backslash values must not crash `check` either.
        solo_index = self.root / "work" / "second" / "INDEX.md"
        self.assertIn(r"C:\Users\name", solo_index.read_text(encoding="utf-8"))
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

        # markdown_label escaping must survive the index rewrite untouched.
        feature = Path(
            self.run_helper(
                "feature", "adv", r"Back\slash\title", "--date", "2026-07-13"
            ).stdout.strip()
        )
        self.run_helper("check")
        index = feature.parent.parent.joinpath("INDEX.md").read_text(encoding="utf-8")
        self.assertIn(r"[Back\\slash\\title]", index)

    def test_long_title_stays_within_filename_limits(self) -> None:
        long_title = "x" * 300
        feature = Path(
            self.run_helper(
                "feature", "longtest", long_title, "--date", "2026-07-13"
            ).stdout.strip()
        )
        self.assertTrue(feature.exists())
        self.assertLessEqual(len(feature.name.encode("utf-8")), 255)

        # Distinct long titles sharing a 120-byte prefix must not collide.
        other = Path(
            self.run_helper(
                "feature", "longtest", "x" * 299 + "y", "--date", "2026-07-13"
            ).stdout.strip()
        )
        self.assertNotEqual(feature, other)
        self.assertIn("0 broken local links", self.run_helper("check").stdout)

    def test_slugify_folds_ascii_punctuation_but_keeps_korean(self) -> None:
        # Commas, parentheses and slashes must fold to hyphens like every other
        # ASCII punctuation mark, while Korean letters pass through untouched.
        title = "결제 취소, 부분(partial) 지원 / v2"
        slug = slugify(title)
        self.assertEqual("결제-취소-부분-partial-지원-v2", slug)
        for char in (",", "(", ")", "/"):
            self.assertNotIn(char, slug)
        self.assertIn("결제", slug)
        self.assertIn("취소", slug)
        self.assertIn("부분", slug)
        self.assertIn("지원", slug)

    def test_normalizes_mixed_legacy_index(self) -> None:
        work_dir = self.root / "work" / "legacy"
        features = work_dir / "features"
        decisions = work_dir / "decisions"
        features.mkdir(parents=True)
        decisions.mkdir()
        (features / "legacy-feature.md").write_text(
            "# Feature: Legacy feature\n\nStatus: done\n", encoding="utf-8"
        )
        (decisions / "legacy-decision.md").write_text(
            "# Decision: Legacy decision\n", encoding="utf-8"
        )
        (work_dir / "INDEX.md").write_text(
            "# Work: legacy\n\n"
            "## Features\n\n- [old](features/legacy-feature.md)\n\n"
            "## Decisions\n\n- [old](decisions/legacy-decision.md)\n\n"
            "## Notes\n\n"
            "Features:\n- [duplicate](features/legacy-feature.md)\n\n"
            "Decisions:\n- [duplicate](decisions/legacy-decision.md)\n",
            encoding="utf-8",
        )

        self.run_helper("check")
        index = (work_dir / "INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(1, index.count("(features/legacy-feature.md)"))
        self.assertEqual(1, index.count("(decisions/legacy-decision.md)"))
        self.assertIn("## Features", index)
        self.assertIn("## Decisions", index)
        self.assertNotIn("\nFeatures:\n", index)
        self.assertNotIn("\nDecisions:\n", index)

    def test_root_flag_is_required(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT), "check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--root", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
