#!/usr/bin/env bash
# 안전 훅(plugins/pl/hooks/guard.sh) 단위 매트릭스. PreToolUse 페이로드를 직접 주입해
# deny/allow 를 단정한다. bash 와 jq 만 있으면 되고 모델·네트워크가 필요 없다.
# 훅의 판정 로직을 손대면 커밋 전에 돌린다.
#
#   bash tests/pl-guard/run-unit.sh [hook-path]
#
# 페이로드 형식: name @@@ command @@@ expected [@@@ shape: claude(기본)|codex]
#
# a28 은 알려진 한계다: 인용문은 자리표시 토큰 `Q` 로 바뀌므로 `git checkout "."` 는 브랜치명과
# 구별되지 않는다. `restore` 는 위치 인자 자체를 경로로 보므로 d26·d27 처럼 막힌다.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="${1:-$HERE/../../plugins/pl/hooks/guard.sh}"
[ -f "$HOOK" ] || { echo "훅을 찾을 수 없다: $HOOK"; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다 (macOS: brew install jq)"; exit 2; }

# name @@@ command @@@ expected
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
d27-restore-quoted-sq   @@@ git restore 'src/a.py'                                     @@@ DENY
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
a28-checkout-quoted-dot @@@ git checkout "."                                           @@@ ALLOW
c01-codex-push-force    @@@ git push --force origin main                              @@@ DENY  @@@ codex
c02-codex-reset-hard    @@@ git reset --hard HEAD~1                                   @@@ DENY  @@@ codex
c03-codex-no-verify     @@@ git commit --no-verify -m msg                             @@@ DENY  @@@ codex
c04-codex-push-plain    @@@ git push origin feature                                   @@@ ALLOW @@@ codex
c05-codex-msg-force     @@@ git commit -m "force push 금지 문서화"                      @@@ ALLOW @@@ codex
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
  if [ "$shape" = "codex" ]; then
    # Codex CLI PreToolUse 페이로드 (learn.chatgpt.com/docs/hooks, 2026-09). tool_input.command 는
    # Claude 와 같은 키다 — 추가 필드가 판정을 흔들지 않는지 고정한다.
    payload="$(jq -n --arg c "$cmd" '{session_id:"s1",transcript_path:null,cwd:"/tmp/x",hook_event_name:"PreToolUse",permission_mode:"default",turn_id:"t1",tool_name:"Bash",tool_use_id:"u1",tool_input:{command:$c},model:"gpt-5"}')"
  else
    payload="$(jq -n --arg c "$cmd" '{hook_event_name:"PreToolUse",tool_name:"Bash",tool_input:{command:$c}}')"
  fi
  out="$(printf '%s' "$payload" | bash "$HOOK" 2>&1)"
  case "$out" in *'"deny"'*) act=DENY ;; *) act=ALLOW ;; esac
  [ "$act" = "$exp" ] && res=PASS || res=FAIL
  printf '%-24s %-8s %-8s %s\n' "$name" "$exp" "$act" "$res"
done | tee "$OUT"
printf '%s\n' "------------------------------------------------------"
p="$(grep -c ' PASS$' "$OUT")"; f="$(grep -c ' FAIL$' "$OUT")"
echo "PASS=$p FAIL=$f"
[ "$f" -eq 0 ]
