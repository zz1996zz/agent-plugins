#!/usr/bin/env bash
# pl PreToolUse guard. SKILL.md 의 Safety Boundaries 가 산문으로 금지한 파괴적 지름길을
# 기계적으로 막는다: force-push, reset --hard, clean -f, --no-verify(와 core.hooksPath 우회),
# stash drop/clear, branch -D, 그리고 미커밋 변경을 폐기하는 restore·checkout·switch 형태.
#
# 커밋·push 자체는 막지 않는다 — 훅은 사용자가 그걸 요청했는지 알 수 없다. 여기서 막는 것은
# 어떤 요청에서도 에이전트가 스스로 택하면 안 되는 지름길이다. 사용자가 진짜 원하면 프롬프트에서
# `! <명령>` 으로 직접 실행한다. 되돌릴 수 없는 행동은 사람 손에 남긴다.
#
# 판정은 셸 세그먼트(&& || ; | 개행) 단위, 인용문을 벗긴 토큰 기준이다. 커밋 메시지 속
# "--force" 는 플래그가 아니고, `echo "git reset --hard"` 는 git 명령이 아니다.
set -uo pipefail
# jq 가 없으면 페이로드를 읽을 수 없다. 모든 Bash 를 막는 것보다 조용히 비활성이 낫지만,
# 그래서 README 전제조건에 jq 를 적어 두었다 — 여기서 빠지면 훅이 있는 줄 알고 없는 셈이 된다.
command -v jq >/dev/null 2>&1 || exit 0

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
[ -n "$cmd" ] || exit 0
# 싼 사전 필터: git 이 없으면 막을 것도 없다.
printf '%s' "$cmd" | grep -q 'git' || exit 0

deny() {
  jq -n --arg reason "pl 안전 경계: $1 — 에이전트는 이 명령을 실행하지 않습니다. 정말 필요하면 프롬프트에 \`! <명령>\` 으로 직접 실행하세요." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# 세그먼트로 쪼갠 뒤 인용문을 자리표시 토큰 `Q` 로 바꾼다. 지워 버리면 `git restore "README.md"`
# 처럼 인용된 경로가 위치 인자 없이 남아 판정을 빠져나간다. `Q` 는 플래그가 아니므로 커밋 메시지
# 속 `--force` 는 여전히 플래그로 세지 않는다.
segments="$(printf '%s' "$cmd" | awk '{ gsub(/&&/,"\n"); gsub(/\|\|/,"\n"); gsub(/;/,"\n"); gsub(/\|/,"\n"); print }')"

while IFS= read -r raw; do
  seg="$(printf '%s' "$raw" | sed -E "s/\"[^\"]*\"/Q/g; s/'[^']*'/Q/g" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -n "$seg" ] || continue
  # 앞의 환경변수 대입(FOO=bar git …)은 건너뛴다.
  seg="$(printf '%s' "$seg" | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*//')"
  printf '%s' "$seg" | grep -Eq '^git([[:space:]]|$)' || continue

  # 토큰화. git 전역 옵션 중 인자를 받는 것(-C dir, -c k=v, --git-dir x)은 인자를 함께 건너뛴다.
  read -r -a toks <<<"$seg"
  sub=""; i=1
  while [ "$i" -lt "${#toks[@]}" ]; do
    t="${toks[$i]}"
    case "$t" in
      -c)
        # `-c core.hooksPath=…` 는 --no-verify 와 같은 우회다.
        nxt="${toks[$((i+1))]:-}"
        case "$nxt" in core.hooksPath=*) deny "훅 우회(-c core.hooksPath)" ;; esac
        i=$((i+2)); continue ;;
      -C|--git-dir|--work-tree|--namespace) i=$((i+2)); continue ;;
      -c*=*)
        case "$t" in -ccore.hooksPath=*) deny "훅 우회(-c core.hooksPath)" ;; esac
        i=$((i+1)); continue ;;
      -*) i=$((i+1)); continue ;;
      *) sub="$t"; break ;;
    esac
  done
  [ -n "$sub" ] || continue
  rest=("${toks[@]:$((i+1))}")

  # 모든 서브커맨드 공통: --no-verify 는 검사 우회다.
  for t in ${rest[@]+"${rest[@]}"}; do
    [ "$t" = "--no-verify" ] && deny "검사 우회(--no-verify)"
  done

  case "$sub" in
    push)
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          --force|--force-with-lease|--force-with-lease=*|--force-if-includes) deny "force-push" ;;
          -[a-zA-Z]*)  # 묶인 짧은 옵션(-fu) 안의 f
            case "$t" in *f*) deny "force-push(-f)" ;; esac ;;
        esac
      done ;;
    reset)
      for t in ${rest[@]+"${rest[@]}"}; do [ "$t" = "--hard" ] && deny "hard reset"; done ;;
    clean)
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          --force) deny "clean -f(추적되지 않은 파일 삭제)" ;;
          -[a-zA-Z]*) case "$t" in *f*) deny "clean -f(추적되지 않은 파일 삭제)" ;; esac ;;
        esac
      done ;;
    restore)
      # `git restore <path>` 는 reset --hard 와 같은 급의 소실이다 — 워킹트리의 미커밋 변경이
      # 사라진다. 인덱스만 되돌리는 `--staged` 단독은 워킹트리를 건드리지 않으므로 통과시킨다.
      # 인용된 경로는 위에서 `Q` 로 남고, 여기서는 그것도 위치 인자(경로)로 센다.
      staged=0; worktree=0; src_given=0; pathish=0
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          --staged) staged=1 ;;
          --worktree) worktree=1 ;;
          --source|--source=*) src_given=1 ;;
          --) pathish=1 ;;
          --*) ;;
          -s*) src_given=1 ;;   # 짧은 형태 `-s <tree>` 도 --source 와 같다
          -[a-zA-Z]*)
            case "$t" in *S*) staged=1 ;; esac
            case "$t" in *W*) worktree=1 ;; esac
            case "$t" in *s*) src_given=1 ;; esac ;;
          *) pathish=1 ;;
        esac
      done
      if [ "$staged" = 1 ] && [ "$worktree" = 0 ] && [ "$src_given" = 0 ]; then
        :
      elif [ "$pathish" = 1 ] || [ "$src_given" = 1 ] || [ "$worktree" = 1 ]; then
        deny "미커밋 변경 폐기(restore)"
      fi ;;
    checkout)
      # 브랜치 전환(`git checkout <branch>`, `-b`, `-`, `-q main`)은 통과. 워킹트리를 덮어쓰는
      # 형태는 폐기다: pathspec(`-- <path>`, `<tree-ish> <path>`, `.`, `./src`, `src/`)과 `-f`.
      # `-b`/`-B`/`--orphan` 이 있으면 브랜치 생성이므로 `--`·인자 2개 규칙을 적용하지 않는다
      # (`git checkout -b feat --` 오탐 방지).
      # 한계: 인용된 경로는 `Q` 한 토큰으로 남아 브랜치명과 구별할 수 없어 `git checkout "."` 은
      # 통과한다. `restore` 는 위치 인자 자체를 경로로 보므로 그쪽에는 이 구멍이 없다.
      dashdash=0; nargs=0; first=""; newbranch=0
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          --) dashdash=1 ;;
          -b|-B|--orphan) newbranch=1 ;;
          --force) deny "미커밋 변경 폐기(checkout -f)" ;;
          --*) ;;
          -) ;;
          -[a-zA-Z]*)
            case "$t" in *f*) deny "미커밋 변경 폐기(checkout -f)" ;; esac
            case "$t" in *b*|*B*) newbranch=1 ;; esac ;;
          *) nargs=$((nargs+1)); [ "$nargs" = 1 ] && first="$t" ;;
        esac
      done
      if [ "$newbranch" = 0 ]; then
        [ "$dashdash" = 1 ] && deny "미커밋 변경 폐기(checkout -- <path>)"
        [ "$nargs" -ge 2 ] && deny "미커밋 변경 폐기(checkout <tree-ish> <path>)"
      fi
      if [ "$nargs" = 1 ]; then
        case "$first" in
          .|./*|../*|*/) deny "미커밋 변경 폐기(checkout <pathspec>)" ;;
        esac
      fi ;;
    switch)
      # checkout 에서 분리된 브랜치 전환 명령. 전환 자체는 통과하되, 미커밋 변경을 버리는
      # `-f`/`--force`/`--discard-changes` 는 막는다. `-C`/`--force-create` 는 브랜치 강제
      # 생성이라 워킹트리를 버리지 않으므로 통과한다.
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          --force|--discard-changes) deny "미커밋 변경 폐기(switch --discard-changes)" ;;
          --*) ;;
          -) ;;
          -[a-zA-Z]*) case "$t" in *f*) deny "미커밋 변경 폐기(switch -f)" ;; esac ;;
        esac
      done ;;
    stash)
      case "${rest[0]:-}" in drop|clear) deny "stash ${rest[0]}(보관된 작업 삭제)" ;; esac ;;
    branch)
      del=0; force=0
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          -D) deny "branch -D(병합되지 않은 브랜치 강제 삭제)" ;;
          -d|--delete) del=1 ;;
          -f|--force) force=1 ;;
          -[a-zA-Z]*) case "$t" in *d*) del=1 ;; esac; case "$t" in *f*) force=1 ;; esac ;;
        esac
      done
      [ "$del" = 1 ] && [ "$force" = 1 ] && deny "branch --delete --force" ;;
    commit)
      for t in ${rest[@]+"${rest[@]}"}; do
        case "$t" in
          -n) deny "검사 우회(commit -n)" ;;
          -[a-zA-Z]*) case "$t" in *n*) deny "검사 우회(commit -n)" ;; esac ;;
        esac
      done ;;
  esac
done <<EOF
$segments
EOF

exit 0
