#!/usr/bin/env bash
set -euo pipefail

ANDROID_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPIKE_DIR="$ANDROID_DIR/spike"

export JAVA_HOME="$SPIKE_DIR/tools/jdk17"
export ANDROID_HOME="$SPIKE_DIR/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$SPIKE_DIR/.gradle-home"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$SPIKE_DIR/tools/gradle-8.9/bin:$PATH"

BUILD_PYTHON="${DKBT_BUILD_PYTHON:-/home/user/.local/share/uv/python/cpython-3.13-linux-x86_64-gnu/bin/python3.13}"

cd "$ANDROID_DIR"
echo "sdk.dir=$ANDROID_HOME" > local.properties

echo "JAVA_HOME=$JAVA_HOME"
java -version 2>&1 | head -1
echo "BUILD_PYTHON=$BUILD_PYTHON"
"$BUILD_PYTHON" --version
echo "ANDROID_HOME=$ANDROID_HOME"

"$SPIKE_DIR/tools/gradle-8.9/bin/gradle" --no-daemon -Pdkbt.buildPython="$BUILD_PYTHON" :app:assembleDebug "$@"

ls -la "$ANDROID_DIR/app/build/outputs/apk/debug/"
