# Brief 37 — Review batch 24 (GATE 2: stage-12 implementation plan)

You are the REVIEWER (flat topology). REPORT ONLY — no edits, no local pytest. Reply only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Plan: `../.IDE_Plans/dk_bond_tracker_watchlist_stage12_impl_plan_20261031_v1.0.json` (v1.0) — primary baseline; its phases/tasks/REVIEWER-CHECK lines are your contract.
- Master: `dk_bond_tracker_watchlist_master_20261030_2355_v1.0.json` (v1.2, stage 12 row) in this same directory's fix-watchlist checkout: `fix-watchlist/.IDE_Plans/...`.
- Brainstorm: `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — D41/D42/D43 (D43 LOCKED sort standard).
- Locked design: `fix-watchlist/.IDE_Plans/design_drafts/ui_frontend_design_v6.html` @7b67f54 (read-only reference for scope claims).
- Docs contracts: `fix-watchlist/docs/PRD_DK_Bond_Tracker_addendum_v6.json` (FR-67..74), `SRS_..._v6`, `Watchlist_Architecture_Addendum_v3`, `Development_Order_addendum_v5` (8 REMOTE steps), `Test_Plan_addendum_v6` (TC-129..137).

## Checks (cite file:section)

1. **Seam checks (skill §9):** every stage-12 phase cites D41/D42/D43 or FR-67..74; plan link matches master v1.2 stage-12 row; scope == stage scope (nothing extra/missing vs Development Order v5's 8 steps).
2. **Owner constraints honored in the plan text:** fleet cap 1+3 D113 spawn; REMOTE-only test blocks (no LOCAL tiers); architecture = Flask+vanilla+SQLite no-new-deps (requirements.txt untouched listed); D43 single shared sort key mandated (T1.2/T1.3) with no per-template sorting.
3. **Rule 5 structure:** every phase has mode SERIES/PARALLEL + test block + REVIEWER-CHECK; every task has action/FROM/TO/Reason/Status; WORKTREE block single base branch, folder==branch HARD-FAIL, containment, db-store + live-checkout untouched; risks present.
4. **Migration safety:** T1.1 credit-day CHECK rebuild requires copy-smoke + row-count assert (verify the task text demands it); fresh-install path untouched.
5. **Merge/approval gates:** sequence gate (phases -> execute-v5 -> dev only after batch 25 + CI green), D52 one-question close, station-close order workers -> captain -> PM.

## Out of scope
Code (none written yet), docs content beyond contract matching, style taste, prior batches.

## FINDINGS (max 5)
`F-24x: [CRITICAL|MAJOR|MINOR] <title> — <evidence> — verdict FIX/PASS`. End with exactly: `VERDICT: AGREED` or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`.
