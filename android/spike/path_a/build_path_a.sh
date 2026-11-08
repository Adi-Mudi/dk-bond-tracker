#!/usr/bin/env bash
set -euo pipefail

SPIKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="$SPIKE_DIR/tools/jdk17"
export ANDROID_HOME="$SPIKE_DIR/android-sdk"
export ANDROIDSDK="$ANDROID_HOME"
export ANDROIDNDK="$ANDROID_HOME/ndk/25.2.9519653"
export GRADLE_USER_HOME="$SPIKE_DIR/.gradle-home"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"

source "$SPIKE_DIR/.venv-p4a/bin/activate"

cd "$SPIKE_DIR/path_a"

echo "JAVA_HOME=$JAVA_HOME"
java -version 2>&1 | head -1
echo "ANDROIDSDK=$ANDROIDSDK"
echo "ANDROIDNDK=$ANDROIDNDK"

START=$(date +%s)

p4a apk \
  --private app \
  --package=com.dkbondtracker.spike \
  --name="DK Bond Tracker" \
  --version=0.1 \
  --bootstrap=webview \
  --requirements=python3,flask,sqlite3 \
  --arch=x86_64 \
  --android-api=34 \
  --ndk-api=24 \
  --port=5000 \
  --dist-name=dkbt_path_a \
  --sdk-dir="$ANDROID_HOME" \
  --ndk-dir="$ANDROIDNDK" \
  --storage-dir="$SPIKE_DIR/.p4a-storage" \
  --local-recipes="$SPIKE_DIR/tools/local-recipes" \
  --debug

END=$(date +%s)
echo "PATH_A_BUILD_SECONDS=$((END - START))"
