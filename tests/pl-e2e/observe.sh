#!/usr/bin/env bash
# 관측 전용 PreToolUse 훅. 기록만 하고 절대 차단하지 않는다 —
# 차단하면 관측이 대상의 행동을 바꾼다. 판정은 전적으로 git 부작용으로 하고,
# 이 로그는 실패했을 때 원인을 분류하는 데만 쓴다.
#
#   observe.sh <logfile>
set -uo pipefail
log="${1:-}"
[ -n "$log" ] || exit 0
input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  tool="$(printf '%s' "$input" | jq -r '.tool_name // "?"' 2>/dev/null)"
  # 도구마다 식별에 쓸 필드가 다르다. 순서대로 있는 것을 쓴다.
  detail="$(printf '%s' "$input" | jq -r '
      .tool_input.command // .tool_input.skill // .tool_input.subagent_type
      // .tool_input.file_path // "" ' 2>/dev/null | tr '\n' ' ')"
else
  # jq 가 없으면 원문을 남긴다. 진단 정보는 줄어들지만 훅은 조용히 죽지 않는다.
  tool="RAW"
  detail="$(printf '%s' "$input" | tr '\n' ' ' | cut -c1-400)"
fi

printf '%s\t%s\n' "$tool" "$detail" >> "$log"
exit 0
