# DK Bond Tracker — Android app (Stage 2 skeleton)

Gradle + Chaquopy project that packages the REAL desktop core (`src/`) as an
Android debug APK. The desktop Flask app runs on-device through Chaquopy
(embedded CPython) and is rendered in a WebView, so there is exactly one copy of
the product logic: the repository's `src/`.

## Contents

| Path | Purpose |
| --- | --- |
| `settings.gradle`, `build.gradle`, `gradle.properties` | Gradle root: AGP 8.7.2 + Chaquopy 17.2.0 |
| `app/build.gradle` | app module: SDK levels, ABIs, Chaquopy python version + pip |
| `app/src/main/AndroidManifest.xml` | INTERNET only, allowBackup=false, network security config |
| `app/src/main/res/xml/network_security_config.xml` | cleartext permitted for 127.0.0.1/localhost only |
| `app/src/main/java/com/dkbondtracker/app/MainActivity.java` | WebView + Chaquopy bootstrap |
| `app/src/main/python/main.py` | thin launcher: starts the real Flask app on 127.0.0.1 |
| `app/src/main/python/src` | symlink -> `../../../../../src` (the repo's real core) |
| `gradlew`, `gradle/wrapper` | Gradle 8.9 wrapper (CI builds without a preinstalled gradle) |
| `build_debug.sh` | sets the local toolchain env and runs `:app:assembleDebug` |

## Real core, no copies (D2)

`app/src/main/python/` holds ONLY the thin launcher `main.py` plus the symlink
`src -> ../../../../../src`, which points at the repository's `src/` package.
Chaquopy follows the symlink when it collects the python source set, so the APK
carries the repo core unchanged (compiled `.pyc` plus templates and static
assets) and nothing is duplicated or committed under `android/`.

Verification on the built debug APK:

- `git diff dev -- src/` -> EMPTY.
- `assets/chaquopy/app.imy` contains `src/*.pyc` (32), `src/views/*.pyc`,
  `src/queries/*.pyc`, `main.pyc`, `src/templates/*.html` (15) and
  `src/static/*` (`app.js`, `theme.css`, `theme.js`).

## Python version (B3)

Chaquopy `version = "3.13"` (16 KB page-size readiness). The build machine needs
a Python 3.13 for Chaquopy's bytecode compilation and pip step; the default is
`/home/user/.local/share/uv/python/cpython-3.13-linux-x86_64-gnu/bin/python3.13`
(override with `-Pdkbt.buildPython=<path>` or the `DKBT_BUILD_PYTHON` env var).
No fallback was needed: Chaquopy 17.2.0 accepted 3.13 and packaged
`libpython3.13.so`.

## ABI / SDK levels

- `abiFilters "arm64-v8a", "x86_64"` (arm64 device + x86_64 Waydroid smoke).
- minSdk 24, targetSdk 34, compileSdk 34.

## Permissions / security

- INTERNET only.
- `android:allowBackup="false"`.
- `android:networkSecurityConfig` permits cleartext to `127.0.0.1` and
  `localhost` only (AND-03), instead of a global `usesCleartextTraffic`.

## Build

Local tools live under `android/spike/` (gitignored): JDK 17, Gradle 8.9,
Android SDK and a shared Gradle home.

    DKBT_BUILD_PYTHON=/path/to/python3.13 bash android/build_debug.sh

or manually:

    export JAVA_HOME=.../android/spike/tools/jdk17
    export ANDROID_HOME=.../android/spike/android-sdk
    export GRADLE_USER_HOME=.../android/spike/.gradle-home
    echo "sdk.dir=$ANDROID_HOME" > android/local.properties
    .../android/spike/tools/gradle-8.9/bin/gradle \
        -Pdkbt.buildPython=$DKBT_BUILD_PYTHON :app:assembleDebug

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.

## Notes

- `local.properties`, `.gradle/`, `build/` and the pip cache are gitignored;
  the python `src` entry is a symlink, not a copy, so nothing under `src/` is
  modified.
- The bundled `src/design/` assets ride along because they live in the repo
  `src/` tree; they are inert at runtime.
- `gradlew` and `gradle-wrapper.jar` are the standard Gradle-generated wrapper.
