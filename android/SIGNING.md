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

## Gradle wiring (already in the repo)

`android/app/build.gradle` already wires the release `signingConfig`: it reads
the gitignored `android/keystore.properties`, falls back to the
`DKBT_RELEASE_KEYSTORE_FILE`, `DKBT_RELEASE_STORE_PASSWORD`,
`DKBT_RELEASE_KEY_ALIAS` and `DKBT_RELEASE_KEY_PASSWORD` environment variables,
and fails the build with a named `GradleException` ("Release signing is not
configured") when neither source exists. Debug builds are unaffected.

## CI release signing

`.github/workflows/android-release.yml` builds and guards release APKs. It
triggers only on `v*` tag pushes, runs inside the protected `android-release`
environment (required reviewers, deployment tag policy `v*`), and sources every
signing input from GitHub secrets:

- `DKBT_RELEASE_KEYSTORE_BASE64` - decoded to `$RUNNER_TEMP/dkbt-release.jks`
  (never a tracked path)
- `DKBT_RELEASE_STORE_PASSWORD`, `DKBT_RELEASE_KEY_ALIAS`,
  `DKBT_RELEASE_KEY_PASSWORD` - exported as the `DKBT_RELEASE_*` environment
  variables Gradle expects
- `DKBT_RELEASE_FINGERPRINT` - the pinned SHA-256 certificate fingerprint

After `assembleRelease` the workflow runs `scripts/check-release-signature.sh`:
it extracts the signer certificate fingerprint with `apksigner verify
--print-certs`, compares it with the pinned fingerprint, and fails the job on a
mismatch - a debug-signed APK can never reach a release tag again. With no
fingerprint secret configured the guard skips with a visible `::notice::`
annotation instead (development/fork builds).

## Key backup

- Keep an offline copy of the release keystore (`*.jks`) in a second secure place.
- Keep the store and key passwords in a password manager, never in a tracked file.
- Losing the key is as fatal as leaking it: no update can be signed with a new key
  for the same app, so users cannot upgrade in place.

## Key validity

The `-validity 10000` value in the keytool command above is about 27 years. Use a
validity of 25 years or more so the key outlives the app's expected lifetime.

## Key leak response

If the release key is stolen, an attacker can sign a malicious update that
installs over the real app, because Android trusts the signature, not the
source. The key cannot be revoked. The only escape is changing the package name,
which creates a new app identity that existing users do not update from.

## Rules

- `*.jks`, `*.keystore` and `keystore.properties` are gitignored in
  `android/.gitignore`; keep them out of every commit.
- No keystore, password, alias secret or `keystore.properties` content is ever
  committed to the repository.
- If a keystore or its password is exposed, rotate the key and re-issue the app.
