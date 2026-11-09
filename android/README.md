# DK Bond Tracker — Android app (Stage 2 skeleton)

Gradle + Chaquopy project that packages the REAL desktop core (`src/`) as an
Android debug APK. The desktop Flask app runs on-device through Chaquopy
(embedded CPython) and is rendered in a WebView, so there is exactly one copy of
the product logic: the repository's `src/`.

## Contents

| Path | Purpose |
| --- | --- |
| `settings.gradle`, `build.gradle`, `gradle.properties` | Gradle root: AGP 8.7.2 + Chaquopy 17.2.0 |
| `app/build.gradle` | app module: SDK levels, ABIs, Chaquopy python version + pip, release signing |
| `app/src/main/AndroidManifest.xml` | INTERNET only, allowBackup=false, network security config |
| `app/src/main/res/xml/network_security_config.xml` | cleartext permitted for 127.0.0.1/localhost only |
| `app/src/main/java/com/dkbondtracker/app/MainActivity.java` | WebView + Chaquopy bootstrap + export/share (AND-04) |
| `app/src/main/java/com/dkbondtracker/app/ExportProvider.java` | read-only ContentProvider that shares files from the app-private `exports` dir |
| `app/src/main/python/main.py` | thin launcher: starts the real Flask app on 127.0.0.1 |
| `app/src/main/python/src` | symlink -> `../../../../../src` (the repo's real core) |
| `gradlew`, `gradle/wrapper` | Gradle 8.9 wrapper (CI builds without a preinstalled gradle) |
| `build_debug.sh` | sets the local toolchain env and runs `:app:assembleDebug` |
| `build_release.sh` | same toolchain env, runs `:app:assembleRelease` (signed release APK) |

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
`/home/divakaran/.local/share/uv/python/cpython-3.13-linux-x86_64-gnu/bin/python3.13`
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
- The export `ExportProvider` is `exported="false"` with `grantUriPermissions="true"`; it serves
  only the app-private `files/exports` directory, read-only, with canonical-path containment, and
  the `content://` URI reaches `ACTION_SEND` with a read-only grant.

## Export / share (AND-04)

The Settings "Share / Export" card links to `/export.csv?scope=full`. On Android the WebView
`DownloadListener` fetches that localhost CSV, saves it under `files/exports`, and opens the system
share sheet through `ExportProvider`; on the web the same link simply downloads the CSV.

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

## Release build (signed)

The release APK is signed with a **local** keystore that is never committed
(`*.jks`, `*.keystore` and `keystore.properties` are gitignored in
`android/.gitignore`).

One-time keystore + local properties (create once, keep out of git):

    cd android
    spike/tools/jdk17/bin/keytool -genkeypair \
      -keystore spike/dkbt-release.jks -alias dkbt \
      -keyalg RSA -keysize 2048 -validity 10000 -storetype PKCS12 \
      -dname "CN=DK Bond Tracker, OU=<unit>, O=<org>, L=<city>, S=<state>, C=<cc>"

    cat > keystore.properties <<'EOF'
    storeFile=spike/dkbt-release.jks
    storePassword=<store password>
    keyAlias=dkbt
    keyPassword=<key password>
    EOF

Build the signed release APK (one command):

    bash android/build_release.sh
    # override the build python if needed:
    DKBT_BUILD_PYTHON=/path/to/python3.13 bash android/build_release.sh

Output: `android/app/build/outputs/apk/release/app-release.apk`, signed with the
keystore above.

Rebuilds are NOT sha256-identical (zip metadata differs per build); to verify a
build is ours, check the signer cert sha256
`9e2d58a2518d70da9b9829659c94e35962bb6792fe590dcc99e6fe7fa418de47` and the
size class (~36 MB) instead of the APK sha256.

`app/build.gradle` reads the signing material from `keystore.properties` only
when that file exists; otherwise it falls back to these CI environment
variables, so no secret is ever written into the tracked tree:

    DKBT_RELEASE_KEYSTORE_FILE, DKBT_RELEASE_STORE_PASSWORD,
    DKBT_RELEASE_KEY_ALIAS, DKBT_RELEASE_KEY_PASSWORD

Verify the signer and run the on-device smoke pass:

    android/spike/tools/jdk17/bin/java -jar \
      android/spike/android-sdk/build-tools/34.0.0/lib/apksigner.jar \
      verify --print-certs android/app/build/outputs/apk/release/app-release.apk

    DKBT_APK=android/app/build/outputs/apk/release/app-release.apk \
      DKBT_CLEAN=1 bash android/device_smoke.sh

(`DKBT_CLEAN=1` removes an existing install first, so the pass starts from a
fresh app.)

## Notes

- `local.properties`, `.gradle/`, `build/` and the pip cache are gitignored;
  the python `src` entry is a symlink, not a copy, so nothing under `src/` is
  modified.
- The bundled `src/design/` assets are excluded from Chaquopy packaging
  (`chaquopy { sourceSets { main { exclude "src/design/**" } } }` in
  `app/build.gradle`); they are inert at runtime and dropping them saves ~96 KB
  of APK size.
- `gradlew` and `gradle-wrapper.jar` are the standard Gradle-generated wrapper.
