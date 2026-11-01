#!/usr/bin/env python3
"""격리된 Codex에서 PL light 역할·memo·verify·close를 실제 실행한다.

개인 agent 설치와 hook은 사용하지 않는다. 기존 사용자 config는 수정하지 않고
인증 파일만 임시 CODEX_HOME에 복사한다. 모델은 --model을 명시한 경우에만 선택한다.
실패 시 로그와 작업 경로를 출력하며 임시 실행 자료는 사용자가 확인하도록 남긴다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "plugins/pl/skills/team-pl-orchestrator/scripts/pl_history.py"


def assess(work: Path, events: list[dict]) -> list[str]:
    """산문 주장 대신 host 이벤트와 실제 저장 파일을 판정한다."""
    problems = []
    if not any(e.get("type") == "turn.completed" for e in events):
        problems.append("관측 불가: turn 완료 이벤트 없음")
    calls = [e["item"] for e in events if e.get("type") == "item.completed"
             and e.get("item", {}).get("type") == "collab_tool_call"]
    spawns = [c for c in calls if c.get("tool") == "spawn_agent" and c.get("status") == "completed"
              and c.get("receiver_thread_ids")]
    if not spawns:
        problems.append("관측 불가: 실제 spawn 성공 증거 없음")
    for spawn in spawns:
        prompt = spawn.get("prompt")
        if prompt is not None and ("Your lane:" not in prompt or "role session" not in prompt):
            problems.append("spawn brief에 PL 역할 정의 누락")
    root = work / "docs/pl"
    notes = list((root / "features").glob("*.md"))
    if len(notes) != 1:
        problems.append("단일 feature를 done으로 close하지 않음")
        return problems
    if not re.search(r"(?m)^status: done$", notes[0].read_text()):
        problems.append("feature를 done으로 close하지 않음")
    runtime = root / ".runtime" / notes[0].stem
    memos = {p.name: p.read_text() for p in (runtime / "memos").glob("*.md")}
    if not any(m.startswith("Status: DONE\n") for m in memos.values()):
        problems.append("완료된 역할 memo 없음")
    states = {key: state for call in calls for key, state in call.get("agents_states", {}).items()
              if state.get("status") == "completed" and state.get("message")}
    spawned_ids = {key for spawn in spawns for key in spawn["receiver_thread_ids"]}
    if set(states) - spawned_ids:
        problems.append("spawn과 무관한 역할의 완료 응답")
    if states and spawned_ids - set(states):
        problems.append("관측 불가: 일부 spawn의 완료 응답 없음")
    if any(s.get("prompt") is not None for s in spawns) and not states:
        problems.append("관측 불가: V1에서 완료된 역할 memo 수신 증거 없음")
    elif spawns and not states:
        problems.append("관측 불가: V2의 역할 응답과 반환 ID 대응")
    # V1이 전달한 응답은 원문과 대조한다. V2 JSONL은 응답·task_name 대응을 내보내지 않는다.
    for agent_id, state in states.items():
        if not state["message"].startswith("Status: DONE\n"):
            problems.append("현재 역할 응답이 DONE이 아님")
        name = (hashlib.sha256(agent_id.encode()).hexdigest() + "-"
                + hashlib.sha256(state["message"].encode()).hexdigest() + ".md")
        if memos.get(name) != state["message"]:
            problems.append("수신한 역할 응답과 저장 memo 불일치")
    ledger = runtime / "ledger.md"
    if not ledger.is_file() or not re.search(r"(?m)^- Spawned:\s*\S", ledger.read_text()):
        problems.append("반환된 역할 ID의 ledger 기록 없음")
    elif states:
        lifecycle = re.search(r"(?m)^- Spawned:\s*(.*)$", ledger.read_text()).group(1)
        for agent_id in states:
            if not re.search(rf"(?<![\w/-]){re.escape(agent_id)}(?![\w/-])", lifecycle):
                problems.append("반환된 역할 ID와 ledger 불일치")
    evidence = runtime / "evidence.jsonl"
    try:
        records = [json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
        valid = any(isinstance(r, dict) and r.get("command") and r.get("exit") == 0 for r in records)
    except (OSError, ValueError):
        valid = False
    if not valid:
        problems.append("verify evidence 없음")
    if not (work / "keep.txt").is_file() or (work / "keep.txt").read_text() != "사용자 작업\n":
        problems.append("사용자 작업 변경")
    return problems


def verdict(problems: list[str]) -> int:
    """관측된 위반은 FAIL(1), 위반 없이 증거 부족이면 INVALID(2)다."""
    if any(not p.startswith("관측 불가:") for p in problems):
        return 1
    return 2 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", choices=("pl", "team-pl-orchestrator"), default="pl")
    parser.add_argument("--model", help="테스트에 사용할 lead 모델(생략 시 Codex 기본값)")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not shutil.which("codex"):
        print("INVALID: codex CLI 없음")
        return 2
    run = Path(tempfile.mkdtemp(prefix="pl-codex-smoke-")).resolve()
    work, home = run / "work", run / "codex"
    work.mkdir()
    home.mkdir(mode=0o700)
    print(f"실행 자료: {run}", flush=True)
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if auth.is_file():
        shutil.copyfile(auth, home / "auth.json")
        (home / "auth.json").chmod(0o600)
    elif not os.environ.get("CODEX_API_KEY"):
        print("INVALID: 인증 없음")
        return 2
    env = dict(os.environ, CODEX_HOME=str(home))
    (home / "config.toml").write_text('[features]\nhooks = false\nmulti_agent = true\n')
    (work / "app.py").write_text('def greet():\n    return "Helo"\n')
    (work / "test_app.py").write_text(
        'import unittest\nfrom app import greet\n\nclass GreetingTest(unittest.TestCase):\n'
        '    def test_greeting(self):\n        self.assertEqual("Hello", greet())\n')
    (work / "keep.txt").write_text("사용자 작업\n")
    (work / ".agents").mkdir()
    (work / ".agents/pl.md").write_text('---\nverifyCommands:\n  - python3 -m unittest -v\n---\n')
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    # 로컬 plugin을 임시 홈에 설치하여 packaging과 실제 entrypoint도 함께 검증한다.
    setup = (["codex", "plugin", "marketplace", "add", str(REPO)],
             ["codex", "plugin", "add", "pl@zz1996zz"])
    try:
        for index, command in enumerate(setup):
            result = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=60)
            (run / f"setup-{index}.log").write_text(result.stdout + result.stderr)
            if result.returncode:
                print(f"INVALID: plugin 설치 exit {result.returncode}, setup-{index}.log 확인")
                return 2
        prompt = (f'${args.entry} light app.py의 greet() 반환값 Helo를 Hello로 고치고 기존 unittest로 검증하라. '
                  'keep.txt는 사용자의 미완성 작업이므로 보존하라. commit, push, 외부 서비스 변경, '
                  '개인 agent 설치와 설정 변경은 하지 마라. PL의 역할·리뷰·기록·완료 절차를 수행하라.')
        command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--json",
                   "-s", "workspace-write", "-C", str(work)]
        if args.model:
            command.extend(["--model", args.model])
        with (run / "events.jsonl").open("w") as output, (run / "stderr.log").open("w") as errors:
            result = subprocess.run(command + [prompt], env=env, stdout=output, stderr=errors,
                                    stdin=subprocess.DEVNULL, timeout=args.timeout)
        if result.returncode:
            print(f"INVALID: Codex session exit {result.returncode}")
            return 2
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()
                  if line.startswith("{")]
        problems = assess(work, events)
        for name, command in (
            ("app", ["python3", "-m", "unittest", "-v"]),
            ("freshness", ["python3", str(HELPER), "check", "--evidence-only", "--feature",
                           next((work / "docs/pl/features").glob("*.md"), Path("missing")).stem]),
        ):
            check = subprocess.run(command, cwd=work, capture_output=True, text=True)
            (run / f"{name}.log").write_text(check.stdout + check.stderr)
            if check.returncode:
                problems.append(f"{name} 검증 exit {check.returncode}")
        if subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=work,
                          capture_output=True).returncode == 0:
            problems.append("요청하지 않은 commit 생성")
        code = verdict(problems)
        artifact = [p for p in problems if not p.startswith("관측 불가:")]
        host = [p for p in problems if p.startswith("관측 불가:")]
        print("ARTIFACT " + ("FAIL: " + "; ".join(artifact) if artifact else "PASS"))
        print("HOST " + ("UNOBSERVABLE: " + "; ".join(host) if host else "PASS"))
        print({0: "PASS", 1: "FAIL", 2: "INVALID"}[code])
        print("관측 한계: V2 JSONL은 task_name↔UUID 대응과 model/effort를 공개하지 않는다.")
        return code
    except subprocess.TimeoutExpired as exc:
        (run / "timeout.log").write_bytes((exc.stdout or b"") + (exc.stderr or b""))
        print("INVALID: 실행 시간 초과")
        return 2
    finally:
        # 토큰은 실행 자료에 남기지 않는다. 이 파일은 이 실행에서 생성한 복사본이다.
        (home / "auth.json").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
