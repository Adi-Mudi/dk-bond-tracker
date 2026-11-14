#!/bin/sh
set -u

VER="${1:-}"
[ -n "$VER" ] || { echo "usage: sh scripts/release-checklist.sh X.Y.Z"; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2
FAILS=0

fail() {
  echo "release-checklist: FAIL $1"
  FAILS=$((FAILS + 1))
}

GRADLE="android/app/build.gradle"

VN="$(sed -n 's/^[[:space:]]*versionName[[:space:]]*"\([^"]*\)".*/\1/p' "$GRADLE" | head -n 1)"
VC="$(sed -n 's/^[[:space:]]*versionCode[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$GRADLE" | head -n 1)"

if [ "$VN" = "$VER" ] && [ -n "$VC" ]; then
  :
else
  fail "version: android/app/build.gradle versionName is '${VN:-missing}' (expected $VER) and versionCode is '${VC:-missing}'"
fi

grep -q "^version = \"$VER\"" pyproject.toml || fail "version: pyproject.toml version is not $VER"
grep -q "APP_VERSION = \"$VER\"" src/version.py || fail "version: src/version.py APP_VERSION is not $VER"
grep -q "$VER" android/README.md || fail "version: android/README.md does not contain $VER"

TPL="docs/release_note_template.json"
if [ ! -f "$TPL" ]; then
  fail "release-note template: $TPL is missing"
elif ! python3 -c "import json,sys; d=json.load(open('$TPL')); ids=[s.get('id') for s in d.get('sections',[])]; sys.exit(0 if 'signing_model' in ids and 'migration_flow' in ids else 1)" 2>/dev/null; then
  fail "release-note template: $TPL does not parse as JSON or lacks signing_model/migration_flow sections"
fi

if git ls-files android | grep -E '\.jks$|\.keystore$|keystore\.properties$' >/dev/null; then
  fail "signing material: tracked *.jks, *.keystore or keystore.properties under android/"
fi

WF=".github/workflows/android-release.yml"
if [ ! -f "$WF" ]; then
  fail "release workflow: $WF is missing"
elif ! grep -q "'v\*'" "$WF" || grep -q "branches:" "$WF"; then
  fail "release workflow: $WF does not trigger only on v* tags"
fi

if grep -qiE "(may|might|could|can) (lose|wipe)|data (may be|will be|is) (lost|wiped)|expect(ed)? (data )?loss|routine data loss|lose your data" "$TPL" android/SIGNING.md 2>/dev/null; then
  fail "data-loss wording: $TPL or android/SIGNING.md normalises update data loss"
fi

if [ "$FAILS" -eq 0 ]; then
  echo "release-checklist: ALL GREEN ($VER)"
  exit 0
fi
exit 1
