#!/usr/bin/env bash
# Import-boundary check (Essential 0.6 / 0.17): features must not import other features' internals.
set -euo pipefail
cd "$(dirname "$0")/../frontend/app"

FAIL=0
for f in $(find lib/features -name '*.dart' -type f 2>/dev/null); do
  owner=$(echo "$f" | sed -E 's|lib/features/([^/]+)/.*|\1|')
  while IFS= read -r imp; do
    target=$(echo "$imp" | sed -E "s|.*package:app/features/([^/'\"]+).*|\1|")
    if [ "$target" != "$imp" ] && [ "$target" != "$owner" ]; then
      echo "BOUNDARY VIOLATION: $f imports feature '$target' (own feature: $owner)"
      FAIL=1
    fi
  done < <(grep -E "import 'package:app/features/" "$f" 2>/dev/null || true)
done

if [ "$FAIL" -ne 0 ]; then
  echo "Feature-isolation rule (0.6): cross-feature sharing must go through lib/shared/ only."
  exit 1
fi
echo "flutter import boundaries OK"
