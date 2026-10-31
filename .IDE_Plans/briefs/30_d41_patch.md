# Brief 30 — D41 patch wave (code): Q1 allowance, Q2 labels, Q3 guard+recovery, Q5 broker

Worker: wl-patch. Cwd = `patch-d41` worktree (branch from dev fa1d95e). NO git writes. NO pytest (remote-only; py_compile + venv test-client smoke allowed). Reply only REPORT. Truth: `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` D41 (read it), plan docs not needed.

## Evidence base (PM smoke — reproduce/verify as you go)

- Q3 ROOT CAUSE: POST /watch/<id>/move with start 2026-11-14 end 2026-11-30 → **302 inserted tenure_months=0** (move path skips the tenure>=1 validation that /add has) → then GET /, /portfolio, /portfolio?tab=payouts, /print all **500** (ERR-health-compute / ERR-query-counts / ERR-print-statement: "tenure_months must be a positive integer: 0"). A live row like this exists in the owner's data/bonds.db (id=2).
- Q1: POST /watch with coupon_pct="0.00" or expected_yield_pct="0.00" → **400** (rejected by watch_percent at src/app.py:576-577 region).
- Q2: Move-to-Portfolio date inputs unlabeled (owner screenshot).
- Q5: no broker field anywhere.

## Tasks

1. **Q1 — allow 00.00**: find the percent validator used for coupon_pct/expected_yield_pct (app.py watch POST + wherever shared). Contract: "0", "0.0", "0.00" ACCEPTED (parsed as 0.0); empty string, non-numeric, negative still rejected with named errors. Apply to Add Candidate AND any Add Position percent fields with the same validator.
2. **Q2 — labels**: in watch.html Move-to-Portfolio mini-form: label the inputs "Purchase date (start date)", "End date", "Credit day — when the amount is credited each month" (visible <label>s, not just placeholders; keep compact). Apply the SAME three wordings to portfolio.html Add Position form fields for consistency.
3. **Q3a — guard**: move handler must validate like /add: run date_range_tenure + tenure>=1 + credit-day bounds BEFORE any insert → same-month range → 400 with named error (mirror /add's message shape).
4. **Q3b — render hardening**: wherever per-row health/status is computed for display (dashboard_model, portfolio holdings+payouts, print status groups, exports if they compute health): catch per-row AppError → that row renders status = `Invalid` (new chip class `.chip-invalid`, style: reuse muted-danger pattern) + caption in row "dates need review"; the PAGE must return 200. Do NOT change derive_health itself (engine stays strict).
5. **Q3c — recovery**: rows that FAIL validity (tenure<1 or unparseable dates) additionally show a small `Remove` button → POST route (e.g. /portfolio/invalid/<id>/remove) that DELETEs only when the row still fails validity (recheck server-side; named error otherwise). Success redirects back.
6. **Q5 — broker**: (a) idempotent migration in db.py/init_db: `ALTER TABLE bonds ADD COLUMN broker TEXT` (guard: PRAGMA table_info). (b) Fields named `broker` in: watch.html Add Candidate, watch.html Move-to-Portfolio form, portfolio.html Add Position form. (c) Persist on insert/move (empty string ok). (d) Watchlist table: new "Broker" column before "Source note". (e) My Holdings: show broker in the FR-55 detail drawer (facts table row "Broker"); table stays 9 columns. (f) empty state captions unchanged.
7. **Tests** (add, remote-run by PM): coupon/yield 0.00 accepted on /watch; move same-month → 400 (no row inserted); tenure-0 row injected directly → all 4 surfaces still 200 + Invalid chip visible + Remove deletes it; broker roundtrip: add candidate with broker → move → holdings row/drawer carries it.

## Rules
No comments in code; no new deps; keep render-200 above all; q4 order = PM runs smoke/CI. Self-check block: py_compile all touched, rerun of PM's smoke pieces (paste results incl the 4 surfaces with a tenure-0 row = 200), grep broker field presence, `grep -rn "watch_percent" src/` showing 0.00 handling.

## REPORT
Files+bytes per task, smoke before/after for Q1/Q3, self-check outputs, one-line summary. BLOCK on ambiguity.
