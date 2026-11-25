# Project Rules — DK Bond Tracker

This file is the project rules loader. It supplements (does not replace) the global rules.

## Mobile Layout Standard (developer ruling 2026-11-25)

EVERY page ships as a proper mobile design at the 412dp reference viewport with the SAME layout language — no page may look like a different kind of UI. The standard = `frontend/confirmed/app_frame/` chrome (56px bar: brand left, sync/bell/avatar right; sticky section tabs; content one-column; FAB 56px right:16/bottom:104; 5-item bottom nav; 16px padding; Midnight Ledger tokens). One row, one column per screen — consistent mobile density, cards/lists only (no desktop tables or wide grids on mobile). This is the acceptance bar for every design review. STITCH SCOPE (developer 2026-11-25): the Stitch project holds FRONTEND DESIGN ONLY — no documents, specs, notes, or other agents' material (shared account; other agents may work there). Locked screens are listed in `frontend/confirmed/STITCH_LOCK_REGISTRY.json` — work ONLY with those as references; redesign only pending/approved screens. EMPTY-STATE-FIRST (developer 2026-11-25, EVERY TIME): every page design STARTS from the EMPTY page — first-open state (zeroed stats, empty lists, form hidden until +, no mock content) — and content is added on top of that foundation. Never design the populated state first. REVIEW PRESENTATION FORMAT (developer 2026-11-25, ALWAYS): every design deliverable IS the ALL-SECTIONS LAYOUT — one row, multiple columns (one 412dp phone frame per section, side by side, 48px gaps) showing the full flow at a glance. This is the standing focus for every page: design it, present it, and review it in all-sections multi-column form — never a single-column mockup and never a partial single-section view.

## Design Lock Import Checklist (developer rule 2026-11-25, 12 items — never miss an item)

When the developer locks a design, the PM imports ALL of these from the Stitch MCP into `frontend/confirmed/<page>/` in ONE pass — nothing ships locked without every row:

1. Section HTML files (one per section/view, mobile) — exported by screen id, old file removed first (same filename rule).
2. All-sections review board HTML (the approved one-column-per-section board).
3. `*_manifest.csv` — component/rule inventory rows for the page.
4. `*_navigation_flow.md` — section switch, sticky tabs, back behavior.
5. `*_design_notes.md` — feedback-fix log (every developer ruling applied).
6. `*_research_references.md` — UI research + backend code sources.
7. Stitch source JSON per screen (`stitch download --format json` by id).
8. INDEX.json entry update — files list, status confirmed, completeness_check PASS (R5).
9. Verify byte-identical md5 vs the worktree source; commit on `front-design-upgrade`.
10. States coverage — empty / loading / error / long-content variants documented per section (community handoff research 2026-11-25; engineers must never invent them).
11. Accessibility notes in the manifest — focus order, accessible names, contrast ≥4.5:1, touch ≥48px.
12. Non-negotiables vs preferences — the WHY layer: locked constraints (chrome, ordering, tokens) vs adjustable, with rejected directions recorded in design_notes.

Only locked inputs live in `frontend/confirmed/` — superseded/previous-work designs are removed from the active evidence folders (clean-input rule).

## Lane Permission (developer ruling 2026-11-25 — CORE)

Never touch another agent's lane without EXPLICIT developer permission: no commits, no merges, no file edits, no WIP commits on `backend-design-upgrade`, `db-store`, or any other active lane. Each branch is owned by whoever works it; the PM acts only on its own frontend lane and on `dev` after developer approval. (Violation 2026-11-25: PM committed + merged the backend lane unbidden — fully reverted to the backend agent's exact state.) Also: re-read AGENTS.md from disk before git-structural actions — session-start copies go stale.

## Platform Scope (developer rulings 2026-11-24/25)

ANDROID / MOBILE ONLY. The web application is dropped — no web designs, no web builds, no web docs. The frontend is being rebuilt in Flutter for Android from the confirmed designs in `frontend/confirmed/` (app_frame static layout + locked pages). ALL design work happens in the Stitch MCP only (D17, zero direct file edits); HTML-only exports; same-filename in-place updates; imports to the base branch remove the old file first. The backend engine (Python/Flask JSON API) is unchanged and serves the Android app.

## Workflow Rules (Q1–Q5, user-defined 2026-11-06)

Q1. Create a new worktree for each issue and name it after the problem being addressed.

Q2. Fix only one issue at a time. Test the changes, push the branch, open a pull request, complete the review process, and then merge it.

Q3. Work on only one issue at a time. Do not make changes outside the scope of the issue. Always report the files that were modified.

Q4. Update the documentation database whenever code changes are made. The documentation database must remain the single source of truth.

Q5. Use only fleet roles C (captain — watches W and is the sole sender of W's task prompts per the freebuff protocol), W (worker), R (reviewer), and A (auditor, dispatched for audits only). Concrete slot ids, CLIs and models live ONLY in `.fleet/config.json` — the SSOT per global rule D4; AGENTS.md names roles (C/W/R/A), never ids or models, so changes land in one place only. (History: 2026-11-14 rulings — captain dropped then reinstated as the worker's watcher; second worker removed.)

Q6. Close a terminal as soon as its task completes — workers: kill + rm when their issue task settles (each spawner closes its own). EXCEPTION: the reviewer (R) is never closed — it stays alive across review gates; the PM starts it and reuses it for subsequent reviews.

Q7. Topology (2026-11-14 rulings): the PM starts ONE captain (C — concrete slot, CLI/model per `.fleet/config.json`) — C watches W continuously per the freebuff-via-herdr protocol (screen + chat-disk every 1-2s, stuck/blocked detection) and is the sole sender of W's task prompts (state-gated via the freebuff-send.py hook); the PM supervises C, starts reviewer R, and authors briefs. Spawn mechanics follow the global rules (herdr/hc recipe, labels, ready-checks). Reintroduce more workers only with parallel waves. When a captain is used, the PM's brief MUST explicitly tell it to ACTIVATE THE WATCHDOG as its first action after spawning the worker (start freebuff-watch.py on the worker lane + keep it running, fleet-watchdog check before dispatches, re-arm on every exit, report watchdog status with batch reports). WATCHING IS THE CAPTAIN'S WORK ONLY (developer ruling 2026-11-24): the PM does NOT run watchdog ticks, supervise chains, or worker-watch loops of any kind — the PM's own chain is fully retired (was backup-only). PM duties are limited to: authoring briefs, coordinating with C/R/A, receiving reports, and making gate/decision calls; the PM supervises the captain, never the watchers' watch loops.

Q8. Android testing rule (user 2026-11-12, refined same day after community research): install the build ONCE per delivery; reset app STATE between test runs instead of uninstalling and reinstalling the package. Community/Android guidance says a fresh-install state is achieved by clearing app data (`pm clear <package>` — the Android Test Orchestrator's clearPackageData behaviour, developer.android.com), not by repeated uninstall/install; `adb install -r` is a store-style update that keeps data; `am force-stop` gives a cold start without wiping; full uninstall is for package changes (signature/manifest) or a broken package only. Reset before a smoke run with `sudo waydroid shell -- pm clear com.dkbondtracker.app` (waydroid app remove is broken here: pm code -3). Reinstall only when the build must truly change.

Q9. Merge-approval rule (user 2026-11-18, simplified 2026-11-22): ALL feature work happens in per-issue worktrees/branches cut from `dev`, named after the issue. PRs target `dev`; every gate runs (CI green, review verdict); merging into `dev` requires the DEVELOPER's explicit approval — the PM presents the evidence and waits; never merge on agent initiative. Housekeeping files (evidence, specs, rules, gitignore, fixtures, docs-DB snapshots) may be committed directly to dev with `FORCE_DEV_COMMIT=1` (the repo's pre-commit guard requires this flag on dev). FOUNDATION PHASE closed (developer, 2026-11-22): the `foundation` branch was retired after all its content returned to dev via PRs #333/#334; worktrees no longer use it. `main` stays frozen at its last stable point — the DEVELOPER merges `dev`→`main` manually when declaring a stable line; agents never touch `main`. The `db-store` lane (documentation DB, Q4) is kept: db-store is created from `main` only and carries `store/` snapshot commits only — NEVER merge dev (or any branch) into db-store (developer ruling 2026-11-23: the global anchor gate is correct; the earlier dev-merge practice was wrong); that branch is local-only (never pushed). Staging tests run from branch builds; release publishing stays gated by developer approval as in RELEASING.md. (History: 2026-11-18 rulings — foundation-phase isolation and PM autonomous foundation merges — superseded by this simplification.)

Q10. Staging-mode rule (user 2026-11-18): staging/device tests run in HEADED mode (Waydroid window visible) so the developer can see exact issues directly — not headless. Headless remains only for quick endpoint checks the developer does not need to watch. On a staging failure: tester stops (never fixes code), the finding routes through Discussion -> Issue -> full sequence -> fix -> re-stage, and the developer approves the merge before anything lands on dev.
