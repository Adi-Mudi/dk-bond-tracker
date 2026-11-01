# Brief 38 — P1 spine: credit-day CHECK migration + shared D43 sort key

Worker: wl-b1. Cwd = `phase-core` worktree (branch from execute-v6 @62de573). NO git writes (PM commits). NO pytest — local = py_compile + smoke only (remote CI is the gate). Reply only REPORT.

## Contract
Plan `../.IDE_Plans/dk_bond_tracker_watchlist_stage12_impl_plan_20261031_v1.1.json` phase **P1 tasks T1.1, T1.2, T1.3** (FROM/TO binding; owner constraints Q3/Q4 + D43 LOCKED in header). Locked design `../fix-watchlist/.IDE_Plans/design_drafts/ui_frontend_design_v6.html` (reference only). DevOrder v5 steps 1-3 (`../fix-watchlist/docs/Development_Order_addendum_v5.json`).

## Tasks (exact)

1. **T1.1 — credit_day CHECK 1..31 + migration** (`src/db.py`): current CHECK allows 1..28 (line ~18) — a credit_day=31 insert IntegrityErrors today. Change to BETWEEN 1 AND 31; add an idempotent PRAGMA-guarded table-rebuild migration so EXISTING databases upgrade in place preserving every row (fresh installs get the new CHECK directly). **Mandatory proof (in-task):** copy a populated DB (use `data/bonds.db` READ-ONLY as source — never modify it), run the migration on the copy, assert row counts identical pre/post, then insert a credit_day=31 row on the copy successfully; paste outputs. NEVER touch the real data/bonds.db or anything under store/ / db-store.
2. **T1.2 — one shared sort key** (`src/engine.py`): export a single ordering function (key = Danger=0, On-going=1, Matured=2, Invalid=3, then company-lower, then id) usable by lists of row-dicts; HEALTH_ORDER stays the single source (no duplicate constants anywhere).
3. **T1.3 — adopt it everywhere** (call-site sweep): every currently company-ordered list consumer switches to the shared key: dashboard bars (src/app.py ~:215 region), My Holdings registry (~:1037), export rows (src/queries.py ~:622 portfolio_snapshot), alerts/notification list ordering if applicable. Payouts/print groups likely already priority — VERIFY they use engine ordering (if they hardcode, refactor them to the shared key too). watchlist (candidates) keeps company order — it has no payment status (allowed exception, note it in REPORT).

## Rules
No comments in code; no new deps; do NOT change derive_health raise paths; do NOT touch tests/ (lanes add TCs later); py_compile all touched files; run a venv test-client smoke: fresh temp DB -> add 2 rows (one seeded Danger, one On-going) -> GET / and /portfolio render 200 with Danger row first; credit-day=31 insert works.

## REPORT
Per task: files+bytes + proof outputs (migration row-count copy test, sort-key source proof via grep, call-site inventory before/after); smoke results; one-line summary. BLOCK with reason on ambiguity.
