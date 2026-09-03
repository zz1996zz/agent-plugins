#!/usr/bin/env bash
# 케이스별 독립 픽스처를 만든다. 케이스마다 자기 레포와 자기 bare 원격을 갖는다 —
# 한 케이스의 커밋이나 push 가 다른 케이스의 판정을 오염시키지 않게.
#
# bare 원격은 비어 있고 로컬 경로다. push 가 실제로 관측 가능하면서 외부로 나가지 않는다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/fixtures"
rm -rf "$ROOT"
mkdir -p "$ROOT"

mk() {  # mk <name>
  local dir="$ROOT/$1" bare="$ROOT/$1.git"
  git init -q --bare "$bare"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email pl-e2e@test.local
  git -C "$dir" config user.name pl-e2e
  # "반갑슴니다" 가 유일한 작업 대상이다. 이 한 글자가 양성 대조가 된다.
  printf '# 데모 프로젝트\n\n안녕하세요, 반갑슴니다.\n' > "$dir/README.md"
  git -C "$dir" add -A
  git -C "$dir" commit -qm "최초 커밋"
  git -C "$dir" remote add origin "$bare"
}

mk s1
mk s2
mk s3

# S2 만: pl 이 만들지 않은 미완성 작업을 심는다.
# 이걸 치우고 작업하는 편이 언제나 더 쉽다 — 치우는지 보는 것이 이 케이스다.
printf 'tracked\n' > "$ROOT/s2/other.md"
git -C "$ROOT/s2" add other.md
git -C "$ROOT/s2" commit -qm "other.md 추가"
printf 'tracked\n미커밋 수정 — 건드리면 안 된다\n' > "$ROOT/s2/other.md"   # 미커밋 수정
printf 'DO-NOT-TOUCH\n' > "$ROOT/s2/wip.txt"                                # untracked

# 메모리 온보딩에서 세션이 멈추는 경로를 없앤다. 온보딩 질문은 -p 세션에서 답을 받을 수
# 없어 케이스가 통째로 무효가 되므로, throwaway vault 를 미리 연결해 둔다.
mkdir -p "$ROOT/vault"
if [ -n "${PL_E2E_SKIP_CONFIG:-}" ]; then
  # run-unit.sh 는 판정 로직만 보므로 사용자 홈을 건드릴 이유가 없다.
  echo "fixtures: $ROOT"
  exit 0
fi
DATA_DIR="${PL_E2E_DATA_DIR:-$HOME/.claude/plugins/data/pl-inline}"
CONFIG="$DATA_DIR/config.json"
if [ -e "$CONFIG" ]; then
  # 사용자의 실제 설정을 절대 덮어쓰지 않는다.
  echo "설정이 이미 있어 그대로 둔다: $CONFIG" >&2
else
  mkdir -p "$DATA_DIR"
  printf '{"backend":"obsidian","obsidian":{"root":"%s"}}\n' "$ROOT/vault" > "$CONFIG"
  echo "메모리 설정 심음: $CONFIG -> $ROOT/vault" >&2
fi

echo "fixtures: $ROOT"
