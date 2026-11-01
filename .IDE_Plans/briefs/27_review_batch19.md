# Brief 27 — Review batch 19 (GATE 3: stage-11 IMPLEMENTATION)

You are the REVIEWER for gate 3. REPORT ONLY — never edit any file. Reply with only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Baseline: `execute-v5` branch HEAD (remote CI run 41232462554 = SUCCESS, full suite) vs base `dev` (b9a11ac area) — read the diff with `git -C ../../execute-v5 diff dev...execute-v5 --stat` and read the changed files directly. Pin: HEAD = 97279f0.
- Contracts: plan `../.IDE_Plans/dk_bond_tracker_watchlist_stage11_execute_plan_20261031_v1.1.json` (P0-P4 tasks + REVIEWER-CHECK lines — your primary baseline); truth docs `docs/PRD_DK_Bond_Tracker_addendum_v4.json` (FR-50..61), `docs/Watchlist_Architecture_Addendum_v2.json`, `docs/SRS_DK_Bond_Tracker_addendum_v4.json`; locked design `.IDE_Plans/design_drafts/ui_frontend_design_v5.html` (cwd-relative: in fix-watchlist, use `.IDE_Plans/design_drafts/ui_frontend_design_v5.html`).
- Owner constraints (Q1-Q4) as stated in plan v1.1 header.

## Checks (deep CODE review; every finding cites file:line)

1. **Plan P1-P3 tasks delivered**: schema = ZERO new tables (bonds watch_state partition); arch-v2 routes; v5 shell/tokens; engine read-time health + day-wise Danger; lock = single shared hard-block used by BOTH entries (trace both call sites); Portfolio tabs + payouts window (current+past only, sort Danger→On-going→Matured); Watchlist column whitelist (FR-56) + candidates-only; Dashboard/Goals/Alerts/Settings match v5 + FR-60; FR-55 drawer.
2. **Owner rules**: Q2 zero workbook/import/banned-token refs ANYWHERE in src/+tests/ (grep Muthoottu|Paisalo|xlsm|import_xlsm|workbook — expect ZERO); Q3 tests only touched with v5-aligned intent (deleted 7 dead-feature tests + 2 replaced — verify each deletion maps to a feature actually removed by D37/D38/design v5); Q4 no new dependencies (requirements.txt untouched), SQL centralization (tc45 guards honest: aggregation/join SQL only in queries.py/phase4).
3. **Lock correctness (deep)**: normalize/trim/case handling; Active = On-going OR Danger; Matured re-buy allowed and restarts lifecycle; no override path anywhere; both /add and move handlers route through the same routine.
4. **Security/robustness basics**: no secrets, no user-data leakage, error pages expose only named codes+messages (no tracebacks/paths), SQL parameterized (check the 22 conn.execute call sites for f-string interpolation).
5. **Banned legacy labels**: no rendered `Returned`/`Completed`/`Month Grid` outside rename history; status enum consistency.

## Out of scope

Style nitpicks, docs v1-v4 content, design v5 visuals (approved), test frameworks choice, performance beyond tc48's budget.

## FINDINGS format (strict, max 5)

`F-19x: [CRITICAL|MAJOR|MINOR] <title> — <file:line evidence> — verdict FIX/PASS`. End with exactly one line: `VERDICT: AGREED` (zero CRITICAL/MAJOR in scope) or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`.
