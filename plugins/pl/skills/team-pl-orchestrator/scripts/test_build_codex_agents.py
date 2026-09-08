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

# 검문소 역할(effort: xhigh 유지)과 프로덕션 역할(effort 없음, 리드 상속)의 예시 프론트매터.
# 모델은 두 역할군 모두 `inherit` — TOML 에는 어느 쪽도 `model` 키를 남기지 않는다.
CHECK_ROLE_SAMPLE = """---
name: team-pl-sample-check
description: Sample check role. Role session; spawned by the PL lead only.
tools: Read, Grep, Glob
model: inherit
effort: xhigh
---

You are the sample check role.

Second paragraph with a '''triple quote''' inside.
"""

PRODUCTION_ROLE_SAMPLE = """---
name: team-pl-sample-production
description: Sample production role. Role session; spawned by the PL lead only.
tools: Read, Write, Edit, Bash, Grep, Glob
model: inherit
---

You are the sample production role.
"""


class BuildCodexAgentsTests(unittest.TestCase):
    def test_parse_agent_splits_frontmatter_and_body(self) -> None:
        fm, body = bca.parse_agent(CHECK_ROLE_SAMPLE)
        self.assertEqual("team-pl-sample-check", fm["name"])
        self.assertEqual("inherit", fm["model"])
        self.assertEqual("xhigh", fm["effort"])
        self.assertTrue(body.startswith("You are the sample check role."))
        self.assertNotIn("---", body.splitlines()[0])

    def test_render_check_role_has_effort_and_no_model_key(self) -> None:
        fm, body = bca.parse_agent(CHECK_ROLE_SAMPLE)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("team-pl-sample-check", data["name"])
        self.assertEqual("xhigh", data["model_reasoning_effort"])
        self.assertEqual("read-only", data["sandbox_mode"])
        self.assertNotIn("model", data)
        self.assertIn("Second paragraph with a '''triple quote''' inside.", data["developer_instructions"])
        self.assertTrue(toml_text.startswith("# Generated from"))

    def test_render_production_role_has_neither_key(self) -> None:
        fm, body = bca.parse_agent(PRODUCTION_ROLE_SAMPLE)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("team-pl-sample-production", data["name"])
        self.assertEqual("workspace-write", data["sandbox_mode"])
        self.assertNotIn("model", data)
        self.assertNotIn("model_reasoning_effort", data)

    def test_render_edit_tools_give_workspace_write(self) -> None:
        fm, body = bca.parse_agent(
            CHECK_ROLE_SAMPLE.replace("tools: Read, Grep, Glob", "tools: Read, Write, Edit, Bash").replace(
                "effort: xhigh\n", ""
            )
        )
        data = tomllib.loads(bca.render_toml(fm, body))
        self.assertEqual("workspace-write", data["sandbox_mode"])
        self.assertNotIn("model", data)
        self.assertNotIn("model_reasoning_effort", data)

    def test_toml_multiline_escapes_runs_of_more_than_three_quotes(self) -> None:
        # Include a lone ''' so the value takes the '"""'-wrapped fallback branch,
        # where a run of 4+ double quotes must still come out escaped correctly.
        body = "a ''' b \"\"\"\" c"
        result = bca._toml_multiline(body)
        data = tomllib.loads("x = " + result)
        self.assertEqual(body, data["x"])

    def test_render_handles_body_with_triple_and_quad_quotes(self) -> None:
        sample_with_quad_quotes = CHECK_ROLE_SAMPLE.replace(
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

    def test_committed_agents_have_no_model_key_and_effort_matches_role_tier(self) -> None:
        # 다섯 검문소 역할만 model_reasoning_effort = "xhigh" 를 갖고, 아홉 역할 모두
        # model 키가 없다 (두 호스트 모두 리드 모델을 상속한다).
        check_roles = {
            "team-pl-architect",
            "team-pl-qa-engineer",
            "team-pl-integration-reviewer",
            "team-pl-code-reviewer",
            "team-pl-security-reviewer",
        }
        production_roles = {
            "team-pl-product-analyst",
            "team-pl-backend-engineer",
            "team-pl-frontend-engineer",
            "team-pl-data-engineer",
        }
        toml_paths = sorted(CODEX_DIR.glob("team-pl-*.toml"))
        self.assertEqual(check_roles | production_roles, {p.stem for p in toml_paths})
        for path in toml_paths:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("model", data, path.name)
            if path.stem in check_roles:
                self.assertEqual("xhigh", data.get("model_reasoning_effort"), path.name)
            else:
                self.assertNotIn("model_reasoning_effort", data, path.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
