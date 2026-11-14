#!/bin/sh
set -eu

apk="${1:-}"
if [ -z "$apk" ] || [ ! -f "$apk" ]; then
  echo "error: APK not found: ${apk:-<no path given>}" >&2
  exit 2
fi

expected="${DKBT_RELEASE_FINGERPRINT:-}"
if [ -z "$expected" ]; then
  echo "::notice::guard skipped: no pinned fingerprint configured"
  exit 0
fi

if [ -n "${ANDROID_HOME:-}" ] && [ -x "$ANDROID_HOME/build-tools/34.0.0/apksigner" ]; then
  APKSIGNER="$ANDROID_HOME/build-tools/34.0.0/apksigner"
elif command -v apksigner >/dev/null 2>&1; then
  APKSIGNER="apksigner"
else
  echo "error: apksigner not found on PATH and \$ANDROID_HOME/build-tools/34.0.0/apksigner is missing" >&2
  exit 2
fi

actual=$("$APKSIGNER" verify --print-certs "$apk" 2>/dev/null \
  | sed -n 's/^Signer #1 certificate SHA-256 digest: *//p' \
  | tr -d ' :' | tr 'A-F' 'a-f')
expected=$(printf '%s' "$expected" | tr -d ' :' | tr 'A-F' 'a-f')

if [ -z "$actual" ]; then
  echo "error: could not extract the signer SHA-256 fingerprint from apksigner output" >&2
  exit 1
fi

if [ "$actual" != "$expected" ]; then
  echo "signature mismatch: expected SHA-256 $expected, got $actual" >&2
  exit 1
fi

echo "signature matches pinned fingerprint $expected"
