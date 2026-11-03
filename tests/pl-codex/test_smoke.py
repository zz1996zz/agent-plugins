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

    def use_v2_trace(self):
        self.trace = self.work / "sessions"
        self.trace.mkdir()
        self.events = [{"type": "thread.started", "thread_id": "parent-1"},
                       {"type": "turn.completed"}]
        self.agent_path = "/root/pl_review"
        self.root_records = [
            {"type": "session_meta", "payload": {"id": "parent-1", "source": "exec"}},
            {"type": "response_item", "payload": {
                "type": "function_call", "namespace": "collaboration", "name": "spawn_agent",
                "call_id": "spawn-1", "arguments": json.dumps({
                    "task_name": "pl_review", "message": "You are a role session. Your lane: review"})}},
            {"type": "response_item", "payload": {
                "type": "function_call_output", "call_id": "spawn-1",
                "output": json.dumps({"task_name": self.agent_path})}},
            {"type": "response_item", "payload": {
                "type": "agent_message", "author": self.agent_path, "recipient": "/root",
                "content": [{"type": "input_text", "text": "Message Type: FINAL_ANSWER\n"
                             "Task name: /root\nSender: /root/pl_review\nPayload:\n" + self.message}]}},
        ]
        self.child_records = [
            {"type": "session_meta", "payload": {
                "id": "child-uuid", "parent_thread_id": "parent-1", "agent_path": self.agent_path}},
            {"type": "event_msg", "payload": {"type": "task_started"}},
            {"type": "event_msg", "payload": {
                "type": "task_complete", "last_agent_message": self.message}},
        ]
        self.memo.unlink()
        self.memo = self.runtime / "memos" / (
            hashlib.sha256(self.agent_path.encode()).hexdigest() + "-"
            + hashlib.sha256(self.message.encode()).hexdigest() + ".md")
        self.memo.write_text(self.message)
        (self.runtime / "ledger.md").write_text("- Spawned: pl-review (/root/pl_review)\n")

    def assess_trace(self):
        for name, records in (("parent", self.root_records), ("child", self.child_records)):
            (self.trace / (name + ".jsonl")).write_text(
                "".join(json.dumps(row) + "\n" for row in records))
        try:
            return self.runner.assess(self.work, self.events, trace_dir=self.trace)
        except TypeError as exc:
            self.fail(f"V2 원본 세션 증거를 검증할 수 없음: {exc}")

    def test_accepts_v2_spawn_child_and_parent_received_memo(self):
        self.use_v2_trace()
        self.assertEqual([], self.assess_trace())

    def test_v2_unrelated_parent_or_path_cannot_prove_spawn(self):
        self.use_v2_trace()
        for field, wrong in (("parent_thread_id", "other-parent"), ("agent_path", "/root/other")):
            with self.subTest(field=field):
                original = self.child_records[0]["payload"][field]
                self.child_records[0]["payload"][field] = wrong
                self.assertEqual(2, self.runner.verdict(self.assess_trace()))
                self.child_records[0]["payload"][field] = original

    def test_v2_requires_actual_parent_delivery_and_child_completion(self):
        self.use_v2_trace()
        delivery = self.root_records.pop()
        self.assertEqual(2, self.runner.verdict(self.assess_trace()))
        self.root_records.append(delivery)
        self.child_records.append({"type": "event_msg", "payload": {"type": "task_started"}})
        self.assertEqual(2, self.runner.verdict(self.assess_trace()))

    def test_v2_every_successful_spawn_needs_its_own_child_evidence(self):
        self.use_v2_trace()
        self.root_records.extend([
            {"type": "response_item", "payload": {
                "type": "function_call", "namespace": "collaboration", "name": "spawn_agent",
                "call_id": "spawn-2", "arguments": json.dumps({
                    "task_name": "second", "message": "You are a role session. Your lane: review"})}},
            {"type": "response_item", "payload": {
                "type": "function_call_output", "call_id": "spawn-2",
                "output": json.dumps({"task_name": "/root/second"})}},
        ])
        self.assertEqual(2, self.runner.verdict(self.assess_trace()))

    def test_v2_forged_saved_memo_is_failure(self):
        self.use_v2_trace()
        self.memo.write_text("Status: DONE\n리드가 대신 작성한 검토\n")
        self.assertEqual(1, self.runner.verdict(self.assess_trace()))

    def test_v2_encrypted_brief_is_unobservable_rather_than_a_missing_role(self):
        self.use_v2_trace()
        args = json.loads(self.root_records[1]["payload"]["arguments"])
        args["message"] = "gAAAAA" + "a" * 160
        self.root_records[1]["payload"]["arguments"] = json.dumps(args)
        problems = self.assess_trace()
        self.assertEqual(2, self.runner.verdict(problems))
        self.assertIn("brief", " ".join(problems))

    def test_v2_latest_blocked_response_cannot_use_old_done(self):
        self.use_v2_trace()
        self.child_records.extend([
            {"type": "event_msg", "payload": {"type": "task_started"}},
            {"type": "event_msg", "payload": {
                "type": "task_complete", "last_agent_message": "Status: BLOCKED\n미완료"}},
        ])
        self.root_records[-1]["payload"]["content"][0]["text"] = (
            "Message Type: FINAL_ANSWER\nPayload:\nStatus: BLOCKED\n미완료")
        self.assertEqual(1, self.runner.verdict(self.assess_trace()))

    def test_accepts_one_terminal_file_newline_without_changing_memo_content(self):
        self.message = self.message.rstrip("\n")
        self.events[1]["item"]["agents_states"]["child-1"]["message"] = self.message
        self.memo.unlink()
        saved = self.message + "\n"
        self.memo = self.runtime / "memos" / (hashlib.sha256(b"child-1").hexdigest() + "-"
                                            + hashlib.sha256(saved.encode()).hexdigest() + ".md")
        self.memo.write_text(saved)
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
