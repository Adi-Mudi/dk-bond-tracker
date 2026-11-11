# Project Rules — DK Bond Tracker

This file is the project rules loader. It supplements (does not replace) the global rules.

## Workflow Rules (Q1–Q5, user-defined 2026-11-06)

Q1. Create a new worktree for each issue and name it after the problem being addressed.

Q2. Fix only one issue at a time. Test the changes, push the branch, open a pull request, complete the review process, and then merge it.

Q3. Work on only one issue at a time. Do not make changes outside the scope of the issue. Always report the files that were modified.

Q4. Update the documentation database whenever code changes are made. The documentation database must remain the single source of truth.

Q5. Use only fleet slots C1 (captain), W1 and W2 (workers), and R1 (reviewer) — see `.fleet/config.json` (W3 removed; C1 owns W1+W2 per global rules).

Q6. Close a terminal as soon as its task completes — workers and captains: kill + rm when their issue task settles (each spawner closes its own). EXCEPTION: the reviewer (R1) is never closed — it stays alive across review gates; the PM starts it and reuses it for subsequent reviews.

Q7. Topology per global rules: PM starts exactly ONE captain; the captain starts its workers; the PM starts the reviewer. First check and follow the global rules (herdr/hc spawn recipe, labels, ready-checks) before acting.

Q8. Android testing rule (user 2026-11-12, refined same day after community research): install the build ONCE per delivery; reset app STATE between test runs instead of uninstalling and reinstalling the package. Community/Android guidance says a fresh-install state is achieved by clearing app data (`pm clear <package>` — the Android Test Orchestrator's clearPackageData behaviour, developer.android.com), not by repeated uninstall/install; `adb install -r` is a store-style update that keeps data; `am force-stop` gives a cold start without wiping; full uninstall is for package changes (signature/manifest) or a broken package only. Reset before a smoke run with `sudo waydroid shell -- pm clear com.dkbondtracker.app` (waydroid app remove is broken here: pm code -3). Reinstall only when the build must truly change.
