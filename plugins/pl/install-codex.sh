#!/usr/bin/env bash
# pl 의 Codex 역할 에이전트를 $CODEX_HOME/agents/ 에 설치한다.
#
# 왜 필요한가: Codex 플러그인은 skills/·hooks/ 는 번들하지만 custom agents 는 번들하지 못한다
# (openai/codex#18988, open). 그래서 `codex plugin add pl@zz1996zz` 뒤에 이 스크립트를 한 번
# 돌려야 `$pl` 이 역할 세션을 스폰할 수 있다. 이슈가 닫혀 plugin.json 에 agents 필드가 생기면
# 이 스크립트와 README 의 3단계 설치 안내를 제거한다.
#
# 종료 코드: 0 = 전부 설치됨 · 1 = 일부 미설치(비대화형 충돌, 또는 대화형에서 사용자가 덮어쓰기를 거부)
#            · 2 = 소스 없음 / 알 수 없는 옵션
#
#   bash install-codex.sh            # 충돌 시 파일마다 확인(비대화형이면 중단)
#   bash install-codex.sh --force    # 확인 없이 덮어쓴다
#   bash install-codex.sh --dry-run  # 무엇을 복사할지만 출력
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/agents/codex"
DEST="${CODEX_HOME:-$HOME/.codex}/agents"
FORCE=0; DRY=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $arg" >&2; exit 2 ;;
  esac
done

shopt -s nullglob
files=("$SRC"/team-pl-*.toml)
[ "${#files[@]}" -gt 0 ] || { echo "소스가 없다: $SRC (build_codex_agents.py 를 먼저 돌렸는가?)" >&2; exit 2; }

if [ "$DRY" -eq 1 ]; then
  echo "대상: $DEST"
  for f in "${files[@]}"; do echo "  $(basename "$f")"; done
  exit 0
fi

mkdir -p "$DEST"
copied=0; skipped=0
for f in "${files[@]}"; do
  name="$(basename "$f")"
  target="$DEST/$name"
  if [ -f "$target" ] && ! cmp -s "$f" "$target"; then
    if [ "$FORCE" -eq 0 ]; then
      if [ -t 0 ]; then
        printf '%s 이(가) 이미 있고 내용이 다르다. 덮어쓸까? [y/N] ' "$target"
        read -r answer
        case "$answer" in y|Y) ;; *) echo "건너뜀: $name"; skipped=$((skipped+1)); continue ;; esac
      else
        echo "충돌: $target 의 내용이 다르다. --force 로 덮어쓰거나 파일을 직접 정리하라." >&2
        exit 1
      fi
    fi
  fi
  cp "$f" "$target"
  copied=$((copied+1))
done
echo "설치 완료: $copied 개 복사, $skipped 개 건너뜀 → $DEST"
[ "$skipped" -eq 0 ]
