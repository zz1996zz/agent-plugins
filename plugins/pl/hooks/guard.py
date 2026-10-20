#!/usr/bin/env python3
"""pl PreToolUse guard: mechanically deny the destructive git shortcuts that pl's
Safety Boundaries forbid in prose.

Denied: force-push (flags, +refspec, :ref, --delete/-d, --mirror), reset --hard,
clean -f, the restore/checkout/switch forms that discard uncommitted changes,
--no-verify / commit -n and the config-level hook bypasses (core.hooksPath via -c,
--config-env, GIT_CONFIG_PARAMETERS, `git config`), -c alias.*, stash drop/clear,
branch -D, update-ref -d, reflog expire, gc --prune, worktree remove --force,
`git rm -rf .`, --pathspec-from-file, and `rm -rf .git`.

Commits and pushes themselves are not blocked: the hook cannot know whether the
user asked for them. Blocked are the shortcuts an agent must never pick on its
own. When the user really wants one, they run it themselves with `! <command>`.

Modes:
  guard.py               always judge (skill-frontmatter hook on the lead; Codex plugin hook)
  guard.py --scope role  judge only when the payload's agent_type matches ^pl:team-pl-
                         (Claude Code plugin hook: protects role subagents, ignores other sessions)

Tokenization is shell-aware (quotes, heredocs, backslash-newline, redirections),
so a commit message containing "git push --force" is not a command, and a
heredoc body is not a command. Long options match by unique prefix the way git
accepts them (`--har` → `--hard`). Internal errors fail open (exit 0, no output).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

ROLE_AGENT_PATTERN = re.compile(r"^pl:team-pl-")
WRAPPERS = {"env", "command", "exec", "time", "nohup", "sudo", "nice", "builtin"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "|&", ";;"}
SHORT_FLAG = re.compile(r"^-[A-Za-z]+$")


def deny_message(reason: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"pl 안전 경계: {reason} — 에이전트는 이 명령을 실행하지 않습니다. "
                    "정말 필요하면 프롬프트에 `! <명령>` 으로 직접 실행하세요."
                ),
            }
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------- input


def extract_command(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("command")
    if raw is None:
        raw = tool_input.get("cmd")
    if raw is None:
        return None
    if isinstance(raw, list):
        parts = [str(p) for p in raw]
        # `bash -lc "<script>"` as an argv: the script is the command.
        if len(parts) >= 3 and os.path.basename(parts[0]) in SHELLS and parts[1].startswith("-") and "c" in parts[1]:
            return parts[2]
        return shlex.join(parts)
    return str(raw)


# ---------------------------------------------------------------- tokenization


def strip_heredocs(script: str) -> str:
    """Drop heredoc bodies (`<<EOF ... EOF`) so lines inside them are not commands."""
    out: list[str] = []
    lines = script.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        if match:
            terminator = match.group(2)
            i += 1
            while i < len(lines) and lines[i].strip() != terminator:
                i += 1
        i += 1
    return "\n".join(out)


def is_redirection(token: str) -> bool:
    return bool(re.fullmatch(r"\d*[<>]{1,2}&?\d*|&>|&>>|[<>]\(|>\|", token))


def tokenize(script: str) -> list[str]:
    script = script.replace("\\\n", " ")
    script = strip_heredocs(script)
    lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens: list[str] = []
    for token in lexer:
        tokens.append(token)
    return tokens


def split_commands(script: str) -> list[list[str]]:
    """Split a shell script into simple commands (argv lists), recursing into
    `sh -c`, `eval`, `xargs`, `$( )` and backtick bodies."""
    try:
        tokens = tokenize(script)
    except ValueError:
        # Unbalanced quotes: fall back to a crude split so a broken script still gets judged.
        tokens = script.replace("\\\n", " ").split()
    commands: list[list[str]] = []
    current: list[str] = []
    skip_target = False
    for token in tokens:
        if skip_target:
            # the word after a redirection operator is its target (file or &fd), not an argument
            skip_target = False
            if token not in SEPARATORS and token not in {"(", ")", "{", "}"}:
                continue
        if token in SEPARATORS or token in {"(", ")", "{", "}"} or token == "\n":
            if current:
                commands.append(current)
                current = []
            continue
        if is_redirection(token):
            # `2>&1` tokenizes as "2", ">&", "1": the digit before the operator is an fd, not an argument
            if current and current[-1].isdigit():
                current.pop()
            skip_target = not token.endswith(")")
            continue
        current.append(token)
    if current:
        commands.append(current)
    expanded: list[list[str]] = []
    for argv in commands:
        expanded.extend(expand_nested(argv))
    return expanded


def expand_nested(argv: list[str]) -> list[list[str]]:
    """Yield argv plus any embedded command strings worth judging."""
    result = [argv]
    for i, token in enumerate(argv):
        for inner in re.findall(r"\$\(([^()]*)\)", token) + re.findall(r"`([^`]*)`", token):
            result.extend(split_commands(inner))
    head = [t for t in argv if "=" not in t.split(" ", 1)[0] or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t)]
    base = os.path.basename(head[0]) if head else ""
    if base in SHELLS:
        for j, token in enumerate(head[1:], 1):
            if token.startswith("-") and "c" in token and j + 1 < len(head):
                result.extend(split_commands(head[j + 1]))
                break
    elif base == "eval":
        result.extend(split_commands(" ".join(head[1:])))
    elif base == "xargs":
        # the first non-option word is the command xargs runs; everything after it belongs to that command
        for j, token in enumerate(head[1:], 1):
            if not token.startswith("-"):
                result.append(head[j:])
                break
    return result


# ---------------------------------------------------------------- wrappers


def strip_wrappers(argv: list[str]) -> tuple[list[str], str | None]:
    """Remove leading VAR=val assignments and wrapper commands. Returns (argv, deny reason)."""
    i = 0
    while i < len(argv):
        token = argv[i]
        assignment = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", token)
        if assignment:
            name, value = assignment.groups()
            if name in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT") or name.startswith("GIT_CONFIG_KEY_"):
                if "hookspath" in value.lower() or name == "GIT_CONFIG_COUNT" or name.startswith("GIT_CONFIG_KEY_"):
                    return argv[i:], "훅 우회(GIT_CONFIG_* 환경변수)"
            i += 1
            continue
        base = os.path.basename(token.lstrip("\\"))
        if base in WRAPPERS:
            i += 1
            # skip wrapper options such as `env -i`, `nice -n 5`, `sudo -u x`
            while i < len(argv) and argv[i].startswith("-"):
                if argv[i] in ("-n", "-u", "-g") and i + 1 < len(argv):
                    i += 1
                i += 1
            continue
        break
    rest = list(argv[i:])
    if rest:
        rest[0] = os.path.basename(rest[0].lstrip("\\"))
    return rest, None


# ---------------------------------------------------------------- judging


def opt(token: str, name: str, min_len: int = 5) -> bool:
    """True when token is `name` or an unambiguous prefix of it (git accepts prefixes)."""
    if token == name:
        return True
    if "=" in token and "=" in name:
        return token.split("=", 1)[0] == name.split("=", 1)[0]
    return name.startswith(token) and len(token) >= min_len and token.startswith("--")


def has_short(token: str, letter: str) -> bool:
    return bool(SHORT_FLAG.match(token)) and letter in token[1:]


def judge(argv: list[str]) -> str | None:
    argv, reason = strip_wrappers(argv)
    if reason:
        return reason
    if not argv:
        return None
    head = argv[0]
    if head == "rm":
        for token in argv[1:]:
            if token.rstrip("/") == ".git" or token.endswith("/.git"):
                return ".git 삭제"
        return None
    if head != "git":
        return None

    # global options
    i = 1
    sub = None
    while i < len(argv):
        token = argv[i]
        if token == "-c":
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            if nxt.lower().startswith("core.hookspath="):
                return "훅 우회(-c core.hooksPath)"
            if nxt.lower().startswith("alias."):
                return "별칭 우회(-c alias.*)"
            i += 2
            continue
        if token.startswith("-c") and "=" in token:
            if token[2:].lower().startswith("core.hookspath="):
                return "훅 우회(-c core.hooksPath)"
            if token[2:].lower().startswith("alias."):
                return "별칭 우회(-c alias.*)"
            i += 1
            continue
        if token.startswith("--config-env"):
            if "hookspath" in token.lower():
                return "훅 우회(--config-env core.hooksPath)"
            i += 2 if "=" not in token else 1
            continue
        if token in ("-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        sub = token
        break
    if sub is None:
        return None
    rest = argv[i + 1 :]

    for token in rest:
        if opt(token, "--no-verify", 6):
            return "검사 우회(--no-verify)"

    if sub == "push":
        for token in rest:
            if opt(token, "--force", 5) or opt(token, "--force-with-lease", 9) or opt(token, "--force-if-includes", 9):
                return "force-push"
            if opt(token, "--mirror", 5):
                return "force-push(--mirror)"
            if opt(token, "--delete", 5) or token == "-d":
                return "원격 브랜치 삭제(push --delete)"
            if has_short(token, "f"):
                return "force-push(-f)"
            if has_short(token, "d"):
                return "원격 브랜치 삭제(push -d)"
            if not token.startswith("-") and (token.startswith("+") or (token.startswith(":") and len(token) > 1)):
                return "force-push(refspec)"
    elif sub == "reset":
        for token in rest:
            if opt(token, "--hard"):
                return "hard reset"
    elif sub == "clean":
        for token in rest:
            if opt(token, "--force") or has_short(token, "f"):
                return "clean -f(추적되지 않은 파일 삭제)"
    elif sub == "restore":
        staged = worktree = src = pathish = False
        for token in rest:
            if opt(token, "--staged"):
                staged = True
            elif opt(token, "--worktree"):
                worktree = True
            elif opt(token, "--source", 5) or opt(token, "--source=", 5):
                src = True
            elif opt(token, "--pathspec-from-file", 6) or opt(token, "--pathspec-from-file=", 6):
                pathish = True
            elif token == "--":
                pathish = True
            elif token.startswith("--"):
                pass
            elif token.startswith("-s"):
                src = True
            elif SHORT_FLAG.match(token):
                staged = staged or "S" in token
                worktree = worktree or "W" in token
                src = src or "s" in token
            else:
                pathish = True
        if not (staged and not worktree and not src) and (pathish or src or worktree):
            return "미커밋 변경 폐기(restore)"
    elif sub == "checkout":
        dashdash = newbranch = False
        args: list[str] = []
        for token in rest:
            if token == "--":
                dashdash = True
            elif token in ("-b", "-B") or opt(token, "--orphan", 5):
                newbranch = True
            elif opt(token, "--force"):
                return "미커밋 변경 폐기(checkout -f)"
            elif opt(token, "--pathspec-from-file", 6) or opt(token, "--pathspec-from-file=", 6):
                return "미커밋 변경 폐기(checkout --pathspec-from-file)"
            elif token.startswith("--") or token == "-":
                pass
            elif SHORT_FLAG.match(token):
                if "f" in token:
                    return "미커밋 변경 폐기(checkout -f)"
                if "b" in token or "B" in token:
                    newbranch = True
            else:
                args.append(token)
        if not newbranch:
            if dashdash:
                return "미커밋 변경 폐기(checkout -- <path>)"
            if len(args) >= 2:
                return "미커밋 변경 폐기(checkout <tree-ish> <path>)"
        if len(args) == 1:
            first = args[0]
            if first == "." or first.startswith("./") or first.startswith("../") or first.endswith("/"):
                return "미커밋 변경 폐기(checkout <pathspec>)"
    elif sub == "switch":
        for token in rest:
            if opt(token, "--force") or opt(token, "--discard-changes", 5):
                return "미커밋 변경 폐기(switch --discard-changes)"
            if has_short(token, "f"):
                return "미커밋 변경 폐기(switch -f)"
    elif sub == "stash":
        for token in rest:
            if token.startswith("-"):
                continue
            if token in ("drop", "clear"):
                return f"stash {token}(보관된 작업 삭제)"
            break
    elif sub == "branch":
        delete = force = False
        for token in rest:
            if token == "-D":
                return "branch -D(병합되지 않은 브랜치 강제 삭제)"
            if token == "-d" or opt(token, "--delete", 5):
                delete = True
            elif token == "-f" or opt(token, "--force"):
                force = True
            elif SHORT_FLAG.match(token):
                delete = delete or "d" in token
                force = force or "f" in token
                if "D" in token:
                    return "branch -D(병합되지 않은 브랜치 강제 삭제)"
        if delete and force:
            return "branch --delete --force"
    elif sub == "commit":
        for token in rest:
            if token == "-n" or has_short(token, "n"):
                return "검사 우회(commit -n)"
    elif sub == "update-ref":
        for token in rest:
            if token == "-d" or opt(token, "--delete", 5):
                return "ref 삭제(update-ref -d)"
    elif sub == "reflog":
        if rest and rest[0] in ("expire", "delete"):
            return f"reflog {rest[0]}(복구 이력 삭제)"
    elif sub == "gc":
        for token in rest:
            if opt(token, "--prune", 5) or opt(token, "--prune=", 5):
                return "gc --prune(복구 불가 객체 정리)"
    elif sub == "worktree":
        if rest and rest[0] == "remove":
            for token in rest[1:]:
                if opt(token, "--force") or has_short(token, "f"):
                    return "worktree remove --force"
    elif sub == "rm":
        recursive = force = False
        targets: list[str] = []
        for token in rest:
            if token == "-r" or opt(token, "--recursive", 5) or (SHORT_FLAG.match(token) and "r" in token):
                recursive = True
            if token == "-f" or opt(token, "--force") or (SHORT_FLAG.match(token) and "f" in token):
                force = True
            if not token.startswith("-"):
                targets.append(token)
        if recursive and force and any(t in (".", "./", "*") for t in targets):
            return "git rm -rf .(작업트리 전체 삭제)"
    elif sub == "config":
        joined = " ".join(rest).lower()
        if "core.hookspath" in joined and not any(t in ("--get", "--get-all", "-l", "--list") for t in rest):
            return "훅 우회(config core.hooksPath)"
    return None


# ---------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    scope_role = "--scope" in argv and "role" in argv
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        if scope_role and not ROLE_AGENT_PATTERN.match(str(payload.get("agent_type") or "")):
            return 0
        command = extract_command(payload)
        if not command or "git" not in command and ".git" not in command:
            return 0
        trace = os.environ.get("PL_GUARD_TRACE")
        if trace:
            with open(trace, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        for cmd in split_commands(command):
            reason = judge(cmd)
            if reason:
                print(deny_message(reason))
                return 0
    except Exception:  # noqa: BLE001 — fail open: a broken guard must not block every Bash call
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
