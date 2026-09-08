#!/usr/bin/env python3
"""build_codex_agents.py 의 변환 규칙과 --check 동작을 고정한다."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import build_codex_agents as bca  # noqa: E402

AGENTS_DIR = SCRIPT_DIR.parents[2] / "agents"
CODEX_DIR = AGENTS_DIR / "codex"

SAMPLE = """---
name: team-pl-sample
description: Sample role. Role session; spawned by the PL lead only.
tools: Read, Grep, Glob
model: opus
effort: xhigh
---

You are the sample role.

Second paragraph with a '''triple quote''' inside.
"""


class BuildCodexAgentsTests(unittest.TestCase):
    def test_parse_agent_splits_frontmatter_and_body(self) -> None:
        fm, body = bca.parse_agent(SAMPLE)
        self.assertEqual("team-pl-sample", fm["name"])
        self.assertEqual("opus", fm["model"])
        self.assertEqual("xhigh", fm["effort"])
        self.assertTrue(body.startswith("You are the sample role."))
        self.assertNotIn("---", body.splitlines()[0])

    def test_render_maps_model_effort_and_sandbox(self) -> None:
        fm, body = bca.parse_agent(SAMPLE)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("team-pl-sample", data["name"])
        self.assertEqual(bca.MODEL_MAP["opus"], data["model"])
        self.assertEqual("xhigh", data["model_reasoning_effort"])
        self.assertEqual("read-only", data["sandbox_mode"])
        self.assertIn("Second paragraph with a '''triple quote''' inside.", data["developer_instructions"])
        self.assertTrue(toml_text.startswith("# Generated from"))

    def test_render_edit_tools_give_workspace_write_and_default_effort(self) -> None:
        fm, body = bca.parse_agent(
            SAMPLE.replace("tools: Read, Grep, Glob", "tools: Read, Write, Edit, Bash")
            .replace("model: opus", "model: sonnet")
            .replace("effort: xhigh\n", "")
        )
        data = tomllib.loads(bca.render_toml(fm, body))
        self.assertEqual("workspace-write", data["sandbox_mode"])
        self.assertEqual(bca.MODEL_MAP["sonnet"], data["model"])
        self.assertEqual("high", data["model_reasoning_effort"])

    def test_unknown_model_is_an_error(self) -> None:
        fm, body = bca.parse_agent(SAMPLE.replace("model: opus", "model: haiku"))
        with self.assertRaises(ValueError):
            bca.render_toml(fm, body)

    def test_toml_multiline_escapes_runs_of_more_than_three_quotes(self) -> None:
        # Include a lone ''' so the value takes the '"""'-wrapped fallback branch,
        # where a run of 4+ double quotes must still come out escaped correctly.
        body = "a ''' b \"\"\"\" c"
        result = bca._toml_multiline(body)
        data = tomllib.loads("x = " + result)
        self.assertEqual(body, data["x"])

    def test_render_handles_body_with_triple_and_quad_quotes(self) -> None:
        sample_with_quad_quotes = SAMPLE.replace(
            "Second paragraph with a '''triple quote''' inside.\n",
            'Second paragraph with a \'\'\'triple quote\'\'\' and """" four quotes inside.\n',
        )
        fm, body = bca.parse_agent(sample_with_quad_quotes)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual(body, data["developer_instructions"])

    def test_build_writes_one_toml_per_role_and_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rc = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--out-dir", str(out)],
                check=False,
            ).returncode
            self.assertEqual(0, rc)
            sources = sorted(p.stem for p in AGENTS_DIR.glob("team-pl-*.md"))
            self.assertEqual(sources, sorted(p.stem for p in out.glob("*.toml")))
            self.assertEqual(9, len(sources))
            for toml_path in out.glob("*.toml"):
                tomllib.loads(toml_path.read_text(encoding="utf-8"))  # 파싱 가능해야 한다

            check_ok = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--out-dir", str(out), "--check"],
                check=False,
            ).returncode
            self.assertEqual(0, check_ok)

            drifted = next(out.glob("*.toml"))
            drifted.write_text(drifted.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            check_drift = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--out-dir", str(out), "--check"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, check_drift.returncode)
            self.assertIn(drifted.name, check_drift.stderr + check_drift.stdout)

    def test_foreign_toml_survives_build_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            foreign = out / "other.toml"
            out.mkdir(parents=True, exist_ok=True)
            foreign.write_text('name = "not-ours"\n', encoding="utf-8")

            rc = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--out-dir", str(out)],
                check=False,
            ).returncode
            self.assertEqual(0, rc)
            self.assertTrue(foreign.is_file(), "non-check build must not delete unrelated *.toml files")

            check_rc = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--out-dir", str(out), "--check"],
                check=False,
            ).returncode
            self.assertEqual(0, check_rc, "--check must not flag an unrelated *.toml file as drift")

    def test_committed_codex_agents_are_up_to_date(self) -> None:
        rc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_codex_agents.py"), "--check"], check=False
        ).returncode
        self.assertEqual(0, rc, "agents/codex/*.toml 가 소스와 다르다 — build_codex_agents.py 를 다시 돌려라")
        self.assertEqual(9, len(list(CODEX_DIR.glob("team-pl-*.toml"))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
