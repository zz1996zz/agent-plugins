#!/usr/bin/env python3
"""build_codex_agents.py 의 변환 규칙과 --check 동작을 고정한다."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if sys.version_info < (3, 11):  # tomllib 은 3.11+. 런타임 헬퍼와 달리 생성기는 개발 도구다.
    print("skipped: build_codex_agents tests need Python 3.11+ (tomllib)")
    sys.exit(0)

import tomllib  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import build_codex_agents as bca  # noqa: E402

AGENTS_DIR = SCRIPT_DIR.parents[2] / "agents"
CODEX_DIR = AGENTS_DIR / "codex"

# 검문소 역할(opus/high)과 프로덕션 역할(sonnet/high)의 예시 프론트매터. 모델 alias 는
# Claude Code 전용이므로 TOML 에는 어느 쪽도 `model` 키를 남기지 않고 effort 만 옮긴다.
CHECK_ROLE_SAMPLE = """---
name: team-pl-sample-check
description: Sample check role. Role session; spawned by the PL lead only.
tools: Read, Grep, Glob
model: opus
effort: high
---

You are the sample check role.

Second paragraph with a '''triple quote''' inside.
"""

PRODUCTION_ROLE_SAMPLE = """---
name: team-pl-sample-production
description: Sample production role. Role session; spawned by the PL lead only.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
effort: high
---

You are the sample production role.
"""


class BuildCodexAgentsTests(unittest.TestCase):
    def test_parse_agent_splits_frontmatter_and_body(self) -> None:
        fm, body = bca.parse_agent(CHECK_ROLE_SAMPLE)
        self.assertEqual("team-pl-sample-check", fm["name"])
        self.assertEqual("opus", fm["model"])
        self.assertEqual("high", fm["effort"])
        self.assertTrue(body.startswith("You are the sample check role."))
        self.assertNotIn("---", body.splitlines()[0])

    def test_render_check_role_has_effort_and_no_model_key(self) -> None:
        fm, body = bca.parse_agent(CHECK_ROLE_SAMPLE)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("team-pl-sample-check", data["name"])
        self.assertEqual("high", data["model_reasoning_effort"])
        self.assertEqual("read-only", data["sandbox_mode"])
        self.assertNotIn("model", data)
        self.assertIn("Second paragraph with a '''triple quote''' inside.", data["developer_instructions"])
        self.assertTrue(toml_text.startswith("# Generated from"))

    def test_render_production_role_has_effort_and_no_model_key(self) -> None:
        fm, body = bca.parse_agent(PRODUCTION_ROLE_SAMPLE)
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("team-pl-sample-production", data["name"])
        self.assertEqual("workspace-write", data["sandbox_mode"])
        self.assertNotIn("model", data)
        self.assertEqual("high", data["model_reasoning_effort"])

    def test_render_role_without_effort_omits_the_key(self) -> None:
        fm, body = bca.parse_agent(PRODUCTION_ROLE_SAMPLE.replace("effort: high\n", ""))
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertNotIn("model", data)
        self.assertNotIn("model_reasoning_effort", data)

    def test_render_edit_tools_give_advisory_workspace_write(self) -> None:
        fm, body = bca.parse_agent(
            CHECK_ROLE_SAMPLE.replace("tools: Read, Grep, Glob", "tools: Read, Write, Edit, Bash").replace(
                "effort: high\n", ""
            )
        )
        toml_text = bca.render_toml(fm, body)
        data = tomllib.loads(toml_text)
        self.assertEqual("workspace-write", data["sandbox_mode"])
        self.assertIn("# advisory:", toml_text)
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

    def test_render_prepends_shared_preamble(self) -> None:
        fm, body = bca.parse_agent(CHECK_ROLE_SAMPLE)
        data = tomllib.loads(bca.render_toml(fm, body, preamble="Shared rules here."))
        self.assertTrue(data["developer_instructions"].startswith("Shared rules here.\n"))
        self.assertIn("You are the sample check role.", data["developer_instructions"])

    def test_shared_preamble_is_extracted_from_roles_md(self) -> None:
        preamble = bca.load_preamble()
        self.assertIn("final response", preamble.lower())
        self.assertNotIn("<!-- preamble:start -->", preamble)
        for toml_path in CODEX_DIR.glob("team-pl-*.toml"):
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            self.assertTrue(data["developer_instructions"].startswith(preamble.strip()), toml_path.name)

    def test_committed_agents_frontmatter_is_subagent_contract(self) -> None:
        team_tools = {"SendMessage", "TaskList", "TaskGet", "TaskUpdate", "Agent"}
        for path in sorted(AGENTS_DIR.glob("team-pl-*.md")):
            fm, body = bca.parse_agent(path.read_text(encoding="utf-8"))
            tools = {t.strip() for t in fm["tools"].split(",")}
            self.assertFalse(tools & team_tools, path.name)
            self.assertIn(fm["model"], {"opus", "sonnet"}, path.name)
            self.assertIn(fm["effort"], {"medium", "high"}, path.name)
            self.assertTrue(fm.get("maxTurns", "").isdigit() and int(fm["maxTurns"]) > 0, path.name)
            self.assertIn("Your lane:", body, path.name)
            self.assertIn("Status: DONE | NEEDS_DECISION | BLOCKED", body, path.name)
            self.assertIn("Unverifiable statically:", body, path.name)
            self.assertNotIn("delivery channel", body, path.name)

    def test_committed_agents_have_no_model_key_and_effort_matches_frontmatter(self) -> None:
        # 아홉 역할 모두 model 키가 없고(Codex 는 리드 모델 상속; Claude alias 는 옮길 수 없다),
        # model_reasoning_effort 는 .md 프론트매터의 effort 와 같다.
        md_paths = sorted(AGENTS_DIR.glob("team-pl-*.md"))
        toml_paths = sorted(CODEX_DIR.glob("team-pl-*.toml"))
        self.assertEqual({p.stem for p in md_paths}, {p.stem for p in toml_paths})
        for md_path, toml_path in zip(md_paths, toml_paths):
            fm, _ = bca.parse_agent(md_path.read_text(encoding="utf-8"))
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            self.assertNotIn("model", data, toml_path.name)
            self.assertEqual(fm["effort"], data.get("model_reasoning_effort"), toml_path.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
