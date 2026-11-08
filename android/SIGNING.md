# Android signing scaffold

How the DK Bond Tracker Android app is signed: debug builds use the default
debug key; release builds are wired through a gitignored `keystore.properties`
and CI secrets. No key material is ever committed.

## Debug builds (default, no setup)

`assembleDebug` is signed automatically with the Android debug keystore
(`~/.android/debug.keystore`, generated on first use). Nothing to configure.
The CI workflow `.github/workflows/android-build.yml` builds debug APKs this way.

## Create a release keystore (once, never committed)

    keytool -genkeypair \
      -keystore release.jks \
      -alias dkbt \
      -keyalg RSA -keysize 2048 -validity 10000 \
      -storetype PKCS12 \
      -dname "CN=DK Bond Tracker, OU=<unit>, O=<org>, L=<city>, S=<state>, C=<cc>"

`keytool` prompts for the store password and the key password. Keep both in a
password manager, never in the repository.

## Wire it through a gitignored keystore.properties

Create `android/keystore.properties` (covered by `android/.gitignore`):

    storeFile=/absolute/path/to/release.jks
    storePassword=<STORE_PASSWORD>
    keyAlias=dkbt
    keyPassword=<KEY_PASSWORD>

## Gradle wiring (apply when release signing is needed)

The current `android/app/build.gradle` intentionally has no release
`signingConfig`, so the debug build is unaffected. When release signing is
wanted, add:

    def keystoreProperties = new Properties()
    def keystorePropertiesFile = rootProject.file("keystore.properties")
    if (keystorePropertiesFile.exists()) {
        keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
    }

    android {
        signingConfigs {
            release {
                storeFile file(keystoreProperties['storeFile'])
                storePassword keystoreProperties['storePassword']
                keyAlias keystoreProperties['keyAlias']
                keyPassword keystoreProperties['keyPassword']
            }
        }
        buildTypes {
            release {
                signingConfig signingConfigs.release
            }
        }
    }

## CI usage without a committed keystore

Store the keystore as a base64 GitHub secret and decode it at build time:

    base64 -w0 release.jks

    - name: Decode release keystore
      env:
        RELEASE_KEYSTORE_BASE64: ${{ secrets.RELEASE_KEYSTORE_BASE64 }}
      run: echo "$RELEASE_KEYSTORE_BASE64" | base64 -d > android/release.jks

    - name: Build release APK
      working-directory: android
      env:
        STORE_PASSWORD: ${{ secrets.RELEASE_STORE_PASSWORD }}
        KEY_PASSWORD: ${{ secrets.RELEASE_KEY_PASSWORD }}
      run: ./gradlew --no-daemon -Pdkbt.buildPython="$(which python3)" :app:assembleRelease

Read the passwords from environment variables; never echo them or write them to
a tracked file.

## Rules

- `*.jks`, `*.keystore` and `keystore.properties` are gitignored in
  `android/.gitignore`; keep them out of every commit.
- No keystore, password, alias secret or `keystore.properties` content is ever
  committed to the repository.
- If a keystore or its password is exposed, rotate the key and re-issue the app.
