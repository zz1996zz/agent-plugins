#!/usr/bin/env bash
# install-codex.sh 단위 테스트. 임시 CODEX_HOME 에 설치해 복사·충돌·--force·--dry-run 을 단정한다.
# 모델·네트워크 불필요.
#
#   bash tests/pl-codex/run-install-unit.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN="$HERE/../../plugins/pl"
INSTALL="$PLUGIN/install-codex.sh"
[ -f "$INSTALL" ] || { echo "install-codex.sh 없음: $INSTALL"; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/pl-codex-install.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
fails=0
check() {  # check <name> <condition-exit-code>
  if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fails=$((fails+1)); fi
}

# 1. 빈 홈에 설치 → 9개 복사
export CODEX_HOME="$TMP/home1"
bash "$INSTALL" </dev/null >/dev/null 2>&1; rc=$?
check "fresh install exits 0" $rc
n="$(ls "$CODEX_HOME/agents"/team-pl-*.toml 2>/dev/null | wc -l | tr -d ' ')"
[ "$n" = "9" ]; check "fresh install copies 9 agents (got $n)" $?
cmp -s "$PLUGIN/agents/codex/team-pl-architect.toml" "$CODEX_HOME/agents/team-pl-architect.toml"
check "copied file is byte-identical" $?

# 2. 같은 내용 재설치 → 0, 변경 없음
bash "$INSTALL" </dev/null >/dev/null 2>&1; check "idempotent reinstall exits 0" $?

# 3. 다른 내용의 파일이 있고 비대화형·--force 없음 → 1, 덮어쓰지 않음
echo "# user edit" > "$CODEX_HOME/agents/team-pl-architect.toml"
bash "$INSTALL" </dev/null >/dev/null 2>&1; rc=$?
[ "$rc" -eq 1 ]; check "conflict without --force exits 1 (got $rc)" $?
grep -q "user edit" "$CODEX_HOME/agents/team-pl-architect.toml"; check "conflict leaves user file untouched" $?

# 4. --force → 덮어씀
bash "$INSTALL" --force </dev/null >/dev/null 2>&1; check "--force exits 0" $?
cmp -s "$PLUGIN/agents/codex/team-pl-architect.toml" "$CODEX_HOME/agents/team-pl-architect.toml"
check "--force overwrites" $?

# 5. --dry-run → 파일 안 만듦
export CODEX_HOME="$TMP/home2"
out="$(bash "$INSTALL" --dry-run </dev/null 2>&1)"; rc=$?
check "--dry-run exits 0" $rc
[ ! -e "$CODEX_HOME/agents" ]; check "--dry-run writes nothing" $?
printf '%s' "$out" | grep -q "team-pl-architect.toml"; check "--dry-run lists targets" $?

# 6. --help → 종료 코드 문서화 포함
out="$(bash "$INSTALL" --help 2>&1)"; rc=$?
check "--help exits 0" $rc
printf '%s' "$out" | grep -q "종료 코드"; check "--help includes exit-code documentation" $?

echo "FAIL=$fails"
[ "$fails" -eq 0 ]
