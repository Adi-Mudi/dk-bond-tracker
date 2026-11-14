# Releasing DK Bond Tracker

How to cut a release. The signed APK is built by CI from a tag — you never
build or sign a release APK by hand.

## One-time setup (already done for v1.0.8)

1. Create the keystore once (never committed):

       keytool -genkeypair \
         -keystore release.jks \
         -alias dkbt \
         -keyalg RSA -keysize 2048 -validity 10000 \
         -storetype PKCS12 \
         -dname "CN=DK Bond Tracker, O=DK"

   Press Enter at the key-password prompt: PKCS12 uses the same password for
   the store and the key.

2. Back the keystore up offline (second secure place). Losing the key is as
   fatal as leaking it — see `android/SIGNING.md` for the leak response.

3. Set the GitHub secrets (Settings → Secrets and variables → Actions):

   - `DKBT_RELEASE_KEYSTORE_BASE64` — `base64 -w0 release.jks` output
   - `DKBT_RELEASE_PASSWORD` — the keystore password (used for both the store
     and key password; PKCS12 requires them to be identical)
   - `DKBT_RELEASE_KEY_ALIAS` — `dkbt`
   - `DKBT_RELEASE_FINGERPRINT` — output of
     `keytool -list -v -keystore release.jks -alias dkbt | grep "SHA256:"`

4. Protect the `android-release` environment (Settings → Environments):
   required reviewer, deployment tag policy `v*`.

## Cutting a release (every time)

Run through `scripts/release-checklist.sh <X.Y.Z>` first — it must print
`ALL GREEN` (it checks the four-file version sync, the release-note template,
no tracked signing material, the workflow trigger, and caveat wording).

1. Bump the version in all four places:

   - `android/app/build.gradle` — `versionCode` (increment) + `versionName`
   - `pyproject.toml` — `version`
   - `src/version.py` — `APP_VERSION`
   - `android/README.md`

2. Update the release note (sections: signing model, migration flow when it
   applies to this release's users, New / Changed with issue links, Full
   Changelog link `v<prev>-release...v<X.Y.Z>-release`).

3. Commit, push to `dev`, then tag and push the tag:

       git tag -a vX.Y.Z-release -m "DK Bond Tracker vX.Y.Z"
       git push origin vX.Y.Z-release

4. CI (`android-release.yml`) builds and guards the APK. Approve the run:
   Actions → android-release → Review deployments → tick android-release →
   **Approve and deploy**. The `Check release signature` step fails the job if
   the APK was not signed with the pinned certificate.

5. Download the artifact `dk-bond-tracker-release-apk` (the file is named
   `DK-Bond-Tracker-<X.Y.Z>.apk`), compute its checksum:

       sha256sum DK-Bond-Tracker-<X.Y.Z>.apk > DK-Bond-Tracker-<X.Y.Z>.apk.sha256

6. Test on a device before publishing:

   - fresh install opens and works;
   - if the previous install was a debug-era build: export the backup,
     uninstall, install this APK, restore — ledger intact.

7. Publish:

       gh release create vX.Y.Z-release \
         --title "DK Bond Tracker vX.Y.Z" \
         --notes-file <note.md> --latest \
         DK-Bond-Tracker-<X.Y.Z>.apk DK-Bond-Tracker-<X.Y.Z>.apk.sha256

   Keep the SHA-256 line in the release body too, not only the asset.

## Renaming rule

The APK filename is set in `android/app/build.gradle`
(`outputFileName = "DK-Bond-Tracker-${variant.versionName}.apk"`) — it follows
the version automatically. The release title is always
`DK Bond Tracker vX.Y.Z`; the tag is always `vX.Y.Z-release`.

## If the key or the applicationId ever changes

Users cannot update in place — they must uninstall (losing local data unless
they exported a backup) and install fresh. Treat both as permanent; see
`android/SIGNING.md` for the full key-leak response.
