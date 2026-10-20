#!/usr/bin/env bash
# install-codex.sh 단위 테스트. 임시 CODEX_HOME 에 설치해 복사·충돌·--force·--dry-run·--prune 을 단정한다.
# 모델·네트워크 불필요.
#
#   bash tests/pl-codex/run-install-unit.sh
#
# 종료 코드 계약(install-codex.sh 헤더와 같다): 0 전부 설치 · 3 충돌/건너뜀 있음(나머지는 설치됨)
# · 1 복사 실패 · 2 소스 없음/옵션 오류.
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
count_agents() { find "$1" -maxdepth 1 -name 'team-pl-*.toml' 2>/dev/null | wc -l | tr -d ' '; }
expect() {  # expect <name> <test-command...>   e.g. expect "x" [ "$n" = 9 ]
  local name="$1"; shift
  if "$@"; then check "$name" 0; else check "$name" 1; fi
}

# 1. 빈 홈에 설치 → 9개 복사
export CODEX_HOME="$TMP/home1"
bash "$INSTALL" </dev/null >/dev/null 2>&1; rc=$?
check "fresh install exits 0" $rc
n="$(count_agents "$CODEX_HOME/agents")"
expect "fresh install copies 9 agents (got $n)" [ "$n" = "9" ]
cmp -s "$PLUGIN/agents/codex/team-pl-architect.toml" "$CODEX_HOME/agents/team-pl-architect.toml"; ok=$?
check "copied file is byte-identical" $ok

# 2. 같은 내용 재설치 → 0, 변경 없음
bash "$INSTALL" </dev/null >/dev/null 2>&1; ok=$?; check "idempotent reinstall exits 0" $ok

# 3. 다른 내용의 파일이 둘 있고 비대화형·--force 없음 → 3, 둘 다 덮어쓰지 않고 나머지는 설치됨
echo "# user edit" > "$CODEX_HOME/agents/team-pl-architect.toml"
echo "# user edit" > "$CODEX_HOME/agents/team-pl-qa-engineer.toml"
rm -f "$CODEX_HOME/agents/team-pl-security-reviewer.toml"
out="$(bash "$INSTALL" </dev/null 2>&1)"; rc=$?
expect "conflict without --force exits 3 (got $rc)" [ "$rc" -eq 3 ]
grep -q "user edit" "$CODEX_HOME/agents/team-pl-architect.toml"; ok=$?; check "conflict leaves first user file untouched" $ok
grep -q "user edit" "$CODEX_HOME/agents/team-pl-qa-engineer.toml"; ok=$?; check "conflict leaves second user file untouched" $ok
cmp -s "$PLUGIN/agents/codex/team-pl-security-reviewer.toml" "$CODEX_HOME/agents/team-pl-security-reviewer.toml"; ok=$?
check "files after a conflict are still installed" $ok
printf '%s' "$out" | grep -q "2 개 충돌"; ok=$?; check "summary counts both conflicts" $ok

# 4. --force → 덮어씀
bash "$INSTALL" --force </dev/null >/dev/null 2>&1; ok=$?; check "--force exits 0" $ok
cmp -s "$PLUGIN/agents/codex/team-pl-architect.toml" "$CODEX_HOME/agents/team-pl-architect.toml"; ok=$?
check "--force overwrites" $ok

# 5. --dry-run → 파일 안 만듦
export CODEX_HOME="$TMP/home2"
out="$(bash "$INSTALL" --dry-run </dev/null 2>&1)"; rc=$?
check "--dry-run exits 0" $rc
expect "--dry-run writes nothing" [ ! -e "$CODEX_HOME/agents" ]
printf '%s' "$out" | grep -q "team-pl-architect.toml"; ok=$?; check "--dry-run lists targets" $ok

# 6. --help → 종료 코드 문서화 포함
out="$(bash "$INSTALL" --help 2>&1)"; rc=$?
check "--help exits 0" $rc
printf '%s' "$out" | grep -q "종료 코드"; ok=$?; check "--help includes exit-code documentation" $ok

# 7. 대상 디렉터리가 읽기 전용 → cp 실패가 실패로 보고됨 (exit 1, "실패" 포함). root 는 권한을 무시하므로 건너뛴다.
if [ "$(id -u)" -ne 0 ]; then
  export CODEX_HOME="$TMP/home3"
  mkdir -p "$CODEX_HOME/agents"
  chmod 555 "$CODEX_HOME/agents"
  out="$(bash "$INSTALL" </dev/null 2>&1)"; rc=$?
  chmod 755 "$CODEX_HOME/agents"
  expect "read-only dest exits 1 (got $rc)" [ "$rc" -eq 1 ]
  printf '%s' "$out" | grep -q "실패"; ok=$?; check "read-only dest reports 실패" $ok
else
  echo "SKIP  read-only dest (running as root)"
fi

# 8. --prune → 소스에 없는 team-pl-*.toml 만 삭제, 다른 파일은 보존
export CODEX_HOME="$TMP/home4"
bash "$INSTALL" </dev/null >/dev/null 2>&1
echo 'name = "stale"' > "$CODEX_HOME/agents/team-pl-old-role.toml"
echo 'name = "mine"' > "$CODEX_HOME/agents/my-agent.toml"
bash "$INSTALL" --prune </dev/null >/dev/null 2>&1; ok=$?; check "--prune exits 0" $ok
expect "--prune removes stale team-pl toml" [ ! -e "$CODEX_HOME/agents/team-pl-old-role.toml" ]
expect "--prune keeps unrelated toml" [ -e "$CODEX_HOME/agents/my-agent.toml" ]
n="$(count_agents "$CODEX_HOME/agents")"; expect "--prune leaves 9 agents (got $n)" [ "$n" = "9" ]

# 9. 대상이 심볼릭 링크 → 복사 거부(실패로 집계), 링크 대상은 그대로
export CODEX_HOME="$TMP/home5"
mkdir -p "$CODEX_HOME/agents" "$TMP/elsewhere"
echo "# dotfile" > "$TMP/elsewhere/real.toml"
ln -s "$TMP/elsewhere/real.toml" "$CODEX_HOME/agents/team-pl-architect.toml"
out="$(bash "$INSTALL" --force </dev/null 2>&1)"; rc=$?
expect "symlinked target exits 1 (got $rc)" [ "$rc" -eq 1 ]
grep -q "dotfile" "$TMP/elsewhere/real.toml"; ok=$?; check "symlink target not overwritten" $ok
printf '%s' "$out" | grep -q "심볼릭"; ok=$?; check "symlink refusal is reported" $ok

# 10. 알 수 없는 옵션 → 2
bash "$INSTALL" --bogus </dev/null >/dev/null 2>&1; rc=$?
expect "unknown option exits 2 (got $rc)" [ "$rc" -eq 2 ]

echo "FAIL=$fails"
[ "$fails" -eq 0 ]
