#!/usr/bin/env bash
# 안전 훅(plugins/pl/hooks/guard.py) 단위 매트릭스. PreToolUse 페이로드를 직접 주입해
# deny/allow 를 단정한다. bash 와 python3 만 있으면 되고 모델·네트워크가 필요 없다.
# 훅의 판정 로직을 손대면 커밋 전에 돌린다.
#
#   bash tests/pl-guard/run-unit.sh [hook-path]
#
# 케이스 형식: name @@@ command @@@ expected [@@@ shape]
#   shape: claude(기본) | codex | array | cmdkey | role:none | role:<agent_type> | role:codex
#   role:* 는 훅을 `--scope role` 로 호출한다(플러그인 훅 모드). 나머지는 인자 없이(스킬 훅·Codex 모드).
#   command 안의 리터럴 `\n` 은 개행으로 바뀐다.
#
# 판정: stdout 이 비어 있으면 ALLOW, 유효한 JSON 이고 "deny" 를 담으면 DENY. 그 외(깨진 JSON,
# exit code != 0)는 FAIL — 훅이 조용히 죽는 것과 허용을 구별해야 하기 때문이다.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="${1:-$HERE/../../plugins/pl/hooks/guard.py}"
[ -f "$HOOK" ] || { echo "훅을 찾을 수 없다: $HOOK"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 가 필요하다"; exit 2; }

# name @@@ command @@@ expected [@@@ shape]
CASES='
d01-push-force          @@@ git push --force origin main                              @@@ DENY
d02-push-f              @@@ git push -f origin main                                   @@@ DENY
d03-push-fu-bundled     @@@ git push -fu origin feature                               @@@ DENY
d04-push-force-lease    @@@ git push --force-with-lease origin main                   @@@ DENY
d05-push-C-dir          @@@ git -C /tmp/x push --force                                @@@ DENY
d06-reset-hard          @@@ git reset --hard HEAD~1                                   @@@ DENY
d07-reset-hard-later    @@@ cd /tmp/x && git reset --hard origin/main                 @@@ DENY
d08-clean-fd            @@@ git clean -fd                                             @@@ DENY
d09-clean-f             @@@ git clean -f                                              @@@ DENY
d10-commit-no-verify    @@@ git commit --no-verify -m msg                             @@@ DENY
d11-commit-n            @@@ git commit -n -m msg                                      @@@ DENY
d12-push-no-verify      @@@ git push --no-verify origin feature                       @@@ DENY
d13-hookspath-bypass    @@@ git -c core.hooksPath=/dev/null commit -m msg             @@@ DENY
d14-stash-clear         @@@ git stash clear                                           @@@ DENY
d15-stash-drop          @@@ git stash drop stash@{0}                                  @@@ DENY
d16-branch-D            @@@ git branch -D feature                                     @@@ DENY
d17-branch-delete-force @@@ git branch --delete --force feature                       @@@ DENY
d18-env-prefix          @@@ GIT_TRACE=1 git push --force                              @@@ DENY
d19-after-pipe          @@@ echo ok | git reset --hard                                @@@ DENY
d20-restore-dashdash    @@@ git restore -- README.md                                  @@@ DENY
d21-restore-source      @@@ git restore --source=HEAD -- README.md                    @@@ DENY
d22-restore-dot         @@@ git restore .                                             @@@ DENY
d23-checkout-dashdash   @@@ git checkout -- README.md                                 @@@ DENY
d24-checkout-head-path  @@@ git checkout HEAD -- README.md                            @@@ DENY
d25-checkout-dot        @@@ git checkout .                                            @@@ DENY
d26-restore-quoted      @@@ git restore "README.md"                                    @@@ DENY
d27-restore-quoted-sq   @@@ git restore '\''src/a.py'\''                                @@@ DENY
d28-restore-short-src   @@@ git restore -S -s HEAD a.py                                @@@ DENY
d29-checkout-tree-path  @@@ git checkout HEAD README.md                                @@@ DENY
d30-checkout-force      @@@ git checkout -f main                                       @@@ DENY
d31-checkout-dot-slash  @@@ git checkout ./src                                         @@@ DENY
d32-checkout-trailing   @@@ git checkout src/                                          @@@ DENY
d33-switch-force        @@@ git switch -f main                                         @@@ DENY
d34-switch-discard      @@@ git switch --discard-changes main                           @@@ DENY
a01-push-plain          @@@ git push origin feature                                   @@@ ALLOW
a02-push-upstream       @@@ git push -u origin feature                                @@@ ALLOW
a03-commit-msg-force    @@@ git commit -m "force push 금지 문서화"                      @@@ ALLOW
a04-commit-msg-reset    @@@ git commit -m '\''reset --hard 관련 정리'\''                @@@ ALLOW
a05-echo-not-git        @@@ echo "git push --force"                                   @@@ ALLOW
a06-reset-soft          @@@ git reset --soft HEAD~1                                   @@@ ALLOW
a07-reset-path          @@@ git reset HEAD README.md                                  @@@ ALLOW
a08-clean-dry-run       @@@ git clean -n                                              @@@ ALLOW
a09-stash-push          @@@ git stash push -u -m wip                                  @@@ ALLOW
a10-stash-list          @@@ git stash list                                            @@@ ALLOW
a11-branch-d-merged     @@@ git branch -d merged-feature                              @@@ ALLOW
a12-commit-am           @@@ git commit -am msg                                        @@@ ALLOW
a13-commit-amend        @@@ git commit --amend --no-edit                              @@@ ALLOW
a14-status              @@@ git status --porcelain                                    @@@ ALLOW
a15-grep-force          @@@ grep -rn -- --force docs/                                 @@@ ALLOW
a16-no-git              @@@ ls -la                                                    @@@ ALLOW
a17-compound-safe       @@@ git add -A && git commit -m msg && git push -u origin x    @@@ ALLOW
a18-restore-staged      @@@ git restore --staged README.md                            @@@ ALLOW
a19-checkout-branch     @@@ git checkout main                                         @@@ ALLOW
a20-checkout-new-branch @@@ git checkout -b feature                                   @@@ ALLOW
a21-checkout-previous   @@@ git checkout -                                            @@@ ALLOW
a22-checkout-b-dashdash @@@ git checkout -b feat --                                    @@@ ALLOW
a23-checkout-b-from     @@@ git checkout -b new main                                   @@@ ALLOW
a24-switch-branch       @@@ git switch main                                            @@@ ALLOW
a25-switch-create       @@@ git switch -c new                                          @@@ ALLOW
a26-checkout-quiet      @@@ git checkout -q main                                       @@@ ALLOW
a27-checkout-slash-name @@@ git checkout feature/x                                     @@@ ALLOW
a28-checkout-quoted-dot @@@ git checkout "."                                           @@@ DENY
a29-push-delete-msg     @@@ git commit -m "remove --delete flag docs"                   @@@ ALLOW
a30-log-grep            @@@ git log --grep "reset --hard" --oneline                    @@@ ALLOW
a31-diff-redirect       @@@ git diff HEAD > /tmp/d.patch                               @@@ ALLOW
a32-worktree-add        @@@ git worktree add ../wt feature                             @@@ ALLOW
a33-gc-plain            @@@ git gc                                                     @@@ ALLOW
a34-rm-cached           @@@ git rm --cached a.txt                                      @@@ ALLOW
a35-python-c-git-str    @@@ python3 -c "print('"'"'git reset --hard'"'"')"               @@@ ALLOW
c01-codex-push-force    @@@ git push --force origin main                              @@@ DENY  @@@ codex
c02-codex-reset-hard    @@@ git reset --hard HEAD~1                                   @@@ DENY  @@@ codex
c03-codex-no-verify     @@@ git commit --no-verify -m msg                             @@@ DENY  @@@ codex
c04-codex-push-plain    @@@ git push origin feature                                   @@@ ALLOW @@@ codex
c05-codex-msg-force     @@@ git commit -m "force push 금지 문서화"                      @@@ ALLOW @@@ codex
b01-abbrev-hard         @@@ git reset --har HEAD                                       @@@ DENY
b02-abbrev-forc         @@@ git clean --forc                                           @@@ DENY
b03-abbrev-no-veri      @@@ git commit --no-veri -m msg                                @@@ DENY
b04-env-git             @@@ env git push --force origin main                           @@@ DENY
b05-command-git         @@@ command git reset --hard                                   @@@ DENY
b06-abs-git             @@@ /usr/bin/git push --force                                  @@@ DENY
b07-xargs               @@@ echo x | xargs git push --force                            @@@ DENY
b08-sh-c                @@@ sh -c "git reset --hard"                                   @@@ DENY
b09-eval                @@@ eval "git clean -fd"                                       @@@ DENY
b10-subshell            @@@ (git reset --hard)                                         @@@ DENY
b11-single-amp          @@@ true & git reset --hard                                    @@@ DENY
b12-redirect-after      @@@ git reset --hard>/dev/null                                 @@@ DENY
b13-backslash-newline   @@@ git reset \\n--hard                                        @@@ DENY
b14-push-plus           @@@ git push origin +main                                      @@@ DENY
b15-push-colon          @@@ git push origin :old-branch                                @@@ DENY
b16-push-delete         @@@ git push --delete origin old                               @@@ DENY
b17-push-mirror         @@@ git push --mirror backup                                   @@@ DENY
b18-update-ref-d        @@@ git update-ref -d refs/heads/x                             @@@ DENY
b19-reflog-expire       @@@ git reflog expire --expire=now --all                       @@@ DENY
b20-gc-prune            @@@ git gc --prune=now                                         @@@ DENY
b21-worktree-rm-force   @@@ git worktree remove --force ../wt                          @@@ DENY
b22-rm-rf-dotgit        @@@ rm -rf .git                                                @@@ DENY
b23-git-rm-rf-dot       @@@ git rm -rf .                                               @@@ DENY
b24-pathspec-from-file  @@@ git checkout --pathspec-from-file=list.txt                 @@@ DENY
b25-stash-q-drop        @@@ git stash -q drop                                          @@@ DENY
b26-alias-c             @@@ git -c alias.x="reset --hard" x                            @@@ DENY
b27-config-hookspath    @@@ git config core.hooksPath /dev/null                        @@@ DENY
b28-config-env          @@@ git --config-env=core.hooksPath=X commit -m m              @@@ DENY
b29-git-config-params   @@@ GIT_CONFIG_PARAMETERS="'"'"'core.hooksPath=/x'"'"'" git commit -m m @@@ DENY
b30-bash-lc             @@@ bash -lc "cd /x && git push -f"                            @@@ DENY
b31-dollar-paren        @@@ echo $(git reset --hard)                                   @@@ DENY
b32-time-prefix         @@@ time git clean -fd                                         @@@ DENY
b33-push-d              @@@ git push -d origin old                                     @@@ DENY
b34-rm-r-dotgit-slash   @@@ rm -r .git/                                                @@@ DENY
f01-msg-semicolon       @@@ git commit -m "docs; git push --force is banned"           @@@ ALLOW
f02-checkout-redirect   @@@ git checkout main 2>&1                                     @@@ ALLOW
f03-heredoc-body        @@@ cat > n.md <<'\''EOF'\''\ngit reset --hard x\nEOF          @@@ ALLOW
f04-tag-msg             @@@ git tag -a v1 -m "release; git branch -D old"              @@@ ALLOW
f05-commit-multiline    @@@ git commit -m "line1\ngit reset --hard in body"             @@@ ALLOW
p01-array-command       @@@ git push --force                                           @@@ DENY  @@@ array
p02-cmd-key             @@@ git push --force                                           @@@ DENY  @@@ cmdkey
p03-array-safe          @@@ git status                                                 @@@ ALLOW @@@ array
r01-scope-role-no-agent @@@ git push --force                                           @@@ ALLOW @@@ role:none
r02-scope-role-explore  @@@ git push --force                                           @@@ ALLOW @@@ role:Explore
r03-scope-role-pl       @@@ git push --force                                           @@@ DENY  @@@ role:pl:team-pl-backend-engineer
r04-scope-role-codex    @@@ git push --force                                           @@@ ALLOW @@@ role:codex
r05-scope-role-pl-safe  @@@ git status                                                 @@@ ALLOW @@@ role:pl:team-pl-qa-engineer
'

OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
printf '%-24s %-8s %-8s %s\n' CASE EXPECT ACTUAL RESULT
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "$CASES" | while IFS= read -r line; do
  name="$(printf '%s' "$line" | awk -F'@@@' '{print $1}' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -n "$name" ] || continue
  cmd="$( printf '%s' "$line" | awk -F'@@@' '{print $2}' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  exp="$( printf '%s' "$line" | awk -F'@@@' '{print $3}' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  shape="$(printf '%s' "$line" | awk -F'@@@' '{print $4}' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  shape="${shape:-claude}"
  args=""
  case "$shape" in role:*) args="--scope role" ;; esac
  payload="$(PL_CMD="$cmd" PL_SHAPE="$shape" python3 - <<'PY'
import json, os
cmd = os.environ["PL_CMD"].replace("\\n", "\n")
shape = os.environ["PL_SHAPE"]
base = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}}
if shape == "codex" or shape == "role:codex":
    # Codex CLI PreToolUse 페이로드 (developers.openai.com/codex/hooks). tool_input.command 는 Claude 와 같은 키.
    base = {"session_id": "s1", "transcript_path": None, "cwd": "/tmp/x", "hook_event_name": "PreToolUse",
            "permission_mode": "default", "turn_id": "t1", "tool_name": "Bash", "tool_use_id": "u1",
            "tool_input": {"command": cmd}, "model": "gpt-5"}
elif shape == "array":
    base["tool_input"] = {"command": ["bash", "-lc", cmd]}
elif shape == "cmdkey":
    base["tool_input"] = {"cmd": cmd}
elif shape.startswith("role:") and shape not in ("role:none", "role:codex"):
    base["agent_id"] = "a1"
    base["agent_type"] = shape[len("role:"):]
print(json.dumps(base, ensure_ascii=False))
PY
)"
  # shellcheck disable=SC2086
  out="$(printf '%s' "$payload" | python3 "$HOOK" $args 2>/dev/null)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    act="EXIT$rc"
  elif [ -z "$out" ]; then
    act=ALLOW
  elif printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("hookSpecificOutput",{}).get("permissionDecision")=="deny" else 3)' 2>/dev/null; then
    act=DENY
  else
    act=BADJSON
  fi
  [ "$act" = "$exp" ] && res=PASS || res=FAIL
  printf '%-24s %-8s %-8s %s\n' "$name" "$exp" "$act" "$res"
done | tee "$OUT"
printf '%s\n' "------------------------------------------------------"
p="$(grep -c ' PASS$' "$OUT")"; f="$(grep -c ' FAIL$' "$OUT")"
echo "PASS=$p FAIL=$f"
[ "$f" -eq 0 ]
