"""Codex E2E 판정의 양성 대조와 거짓 성공 방지 테스트."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


class SmokeVerdictTests(unittest.TestCase):
    def setUp(self):
        script = Path(__file__).with_name("run_smoke.py")
        self.assertTrue(script.is_file(), "Codex 역할 E2E runner가 없다")
        spec = importlib.util.spec_from_file_location("run_smoke", script)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "keep.txt").write_text("사용자 작업\n")
        self.root = self.work / "docs" / "pl"
        (self.root / "features").mkdir(parents=True)
        (self.root / "features" / "smoke.md").write_text("---\nstatus: done\n---\n")
        self.runtime = self.root / ".runtime" / "smoke"
        (self.runtime / "memos").mkdir(parents=True)
        self.message = "Status: DONE\nGate 1: PASS\nGate 2: PASS\n"
        self.memo = self.runtime / "memos" / (hashlib.sha256(b"child-1").hexdigest() + "-"
                                            + hashlib.sha256(self.message.encode()).hexdigest() + ".md")
        self.memo.write_text(self.message)
        (self.runtime / "evidence.jsonl").write_text('{"command":"python3 -m unittest","exit":0}\n')
        (self.runtime / "ledger.md").write_text("## Team Lifecycle\n- Spawned: pl-review (child-1)\n")
        self.events = [
            {"type": "item.completed", "item": {"type": "collab_tool_call", "tool": "spawn_agent",
             "status": "completed", "receiver_thread_ids": ["child-1"],
             "prompt": "You are a role session. Your lane: review", "agents_states": {}}},
            {"type": "item.completed", "item": {"type": "collab_tool_call", "tool": "wait_agent",
             "status": "completed", "agents_states": {"child-1": {"status": "completed", "message": self.message}}}},
            {"type": "turn.completed"},
        ]

    def assess(self):
        return self.runner.assess(self.work, self.events)

    def test_accepts_real_spawn_completed_memo_and_closed_history(self):
        self.assertEqual([], self.assess())

    def test_rejects_prose_claim_without_spawn(self):
        self.events = [{"type": "item.completed", "item": {"type": "agent_message", "text": "spawn_agent 성공"}},
                       {"type": "turn.completed"}]
        self.assertIn("spawn", " ".join(self.assess()))

    def test_rejects_failed_or_empty_spawn(self):
        for change in ({"status": "failed"}, {"receiver_thread_ids": []}):
            with self.subTest(change=change):
                original = dict(self.events[0]["item"])
                self.events[0]["item"].update(change)
                self.assertIn("spawn", " ".join(self.assess()))
                self.events[0]["item"] = original

    def test_rejects_missing_response_or_mismatched_saved_memo(self):
        self.memo.write_text("Status: DONE\n리드가 대신 작성한 문장\n")
        self.assertIn("memo", " ".join(self.assess()))
        self.memo.write_text(self.message)
        self.events[1]["item"]["agents_states"] = {}
        self.assertIn("memo", " ".join(self.assess()))

    def test_rejects_generic_brief_without_role_definition(self):
        self.events[0]["item"]["prompt"] = "review this"
        self.assertIn("정의", " ".join(self.assess()))

    def test_v2_with_unobservable_response_is_invalid(self):
        self.events[0]["item"]["prompt"] = None
        self.events[1]["item"]["agents_states"] = {}
        problems = self.assess()
        self.assertTrue(problems)
        self.assertEqual(2, self.runner.verdict(problems))

    def test_artifact_pass_without_host_trace_is_invalid(self):
        self.events = [{"type": "turn.completed"}]
        self.assertEqual(2, self.runner.verdict(self.assess()))

    def test_artifact_violation_without_host_trace_is_fail(self):
        self.events = [{"type": "turn.completed"}]
        self.memo.unlink()
        self.assertEqual(1, self.runner.verdict(self.assess()))

    def test_fully_observed_evidence_is_pass(self):
        self.assertEqual(0, self.runner.verdict(self.assess()))

    def test_unrelated_completed_agent_cannot_satisfy_spawn(self):
        self.events[1]["item"]["agents_states"] = {
            "unrelated": {"status": "completed", "message": self.message}}
        self.memo.unlink()
        name = (hashlib.sha256(b"unrelated").hexdigest() + "-"
                + hashlib.sha256(self.message.encode()).hexdigest() + ".md")
        (self.runtime / "memos" / name).write_text(self.message)
        self.assertEqual(1, self.runner.verdict(self.assess()))

    def test_unrelated_ledger_and_malformed_evidence_are_failures(self):
        (self.runtime / "ledger.md").write_text("- Spawned: fabricated-id\n")
        self.assertEqual(1, self.runner.verdict(self.assess()))
        (self.runtime / "ledger.md").write_text("- Spawned: pl-review (child-1)\n")
        (self.runtime / "evidence.jsonl").write_text("not a receipt\n")
        self.assertEqual(1, self.runner.verdict(self.assess()))

    def test_resolved_historical_memo_does_not_fail_completed_review(self):
        old = "Status: BLOCKED\n이전 응답\n"
        name = (hashlib.sha256(b"child-1").hexdigest() + "-"
                + hashlib.sha256(old.encode()).hexdigest() + ".md")
        (self.runtime / "memos" / name).write_text(old)
        self.assertEqual([], self.assess())

    def test_latest_blocked_response_cannot_use_previous_done_memo(self):
        latest = "Status: BLOCKED\n현재 응답\n"
        self.events[1]["item"]["agents_states"]["child-1"]["message"] = latest
        name = (hashlib.sha256(b"child-1").hexdigest() + "-"
                + hashlib.sha256(latest.encode()).hexdigest() + ".md")
        (self.runtime / "memos" / name).write_text(latest)
        self.assertEqual(1, self.runner.verdict(self.assess()))

    def test_rejects_risk_close_or_missing_evidence(self):
        (self.root / "features" / "smoke.md").write_text("---\nstatus: done-with-risks\n---\n")
        self.assertIn("done", " ".join(self.assess()))
        (self.runtime / "evidence.jsonl").unlink()
        self.assertIn("evidence", " ".join(self.assess()))

    def test_rejects_modified_user_work_or_missing_turn_completion(self):
        (self.work / "keep.txt").write_text("수정됨")
        self.assertIn("사용자", " ".join(self.assess()))
        self.events.pop()
        self.assertIn("turn", " ".join(self.assess()))


if __name__ == "__main__":
    unittest.main()
