#!/usr/bin/env bash
set -euo pipefail

SPIKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="$SPIKE_DIR/tools/jdk17"
export ANDROID_HOME="$SPIKE_DIR/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$SPIKE_DIR/.gradle-home"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$SPIKE_DIR/tools/gradle-8.9/bin:$PATH"

BUILD_PYTHON="${DKBT_BUILD_PYTHON:-/home/user/.local/bin/python3.11}"

cd "$SPIKE_DIR/path_b"
echo "sdk.dir=$ANDROID_HOME" > local.properties

echo "JAVA_HOME=$JAVA_HOME"
java -version 2>&1 | head -1
echo "BUILD_PYTHON=$BUILD_PYTHON"
"$BUILD_PYTHON" --version
echo "ANDROID_HOME=$ANDROID_HOME"

START=$(date +%s)
gradle --no-daemon -Pdkbt.buildPython="$BUILD_PYTHON" :app:assembleDebug --stacktrace
END=$(date +%s)
echo "PATH_B_BUILD_SECONDS=$((END - START))"

ls -la app/build/outputs/apk/debug/
