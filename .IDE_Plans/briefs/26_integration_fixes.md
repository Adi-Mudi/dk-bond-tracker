# Brief 26 — Integration fix lane: remote-CI alignment (34 failures) + FR-55 drawer

Worker: wl-fix. Cwd = `execute-v5` (merged tree: spine + both lanes). NO git writes (PM commits+pushes; remote CI = the only test tier, owner Q3). NO local pytest. Reply only the REPORT section.

## Context

The v5 redesign replaced legacy surfaces; 34 remote tests fail. Owner Q1/Q4: approved docs+design win; architecture centralization guards stay. Your job = align CODE and TESTS to the approved contract — never re-add a removed feature.

## Exact failure list (CI run 41221814154) and REQUIRED dispositions

**Family 1 — credit-day bounds (UPDATE asserts to 1..31):**
- tc20::test_credit_day_check_rejects_zero_and_29 -> accept 1..31 (reject 0 and 32)
- any tc83 credit-day bounds tests failing similarly -> same update

**Family 2 — Q4 centralization guards (FIX THE CODE, never the tests):**
- tc45×3 (test_app_py_has_no_aggregation_or_join_sql / test_sum_aggregation_only_in_allowed_modules / test_app_py_executes_are_point_lookups_from_query_modules): the lanes' new SQL in src/app.py must move into src/queries.py (allowed module per SUM_ALLOWED) — move aggregation/join/point-lookup queries behind query functions; app.py calls them. Preserve behavior exactly (re-run the routes' logic mentally; py_compile both files).

**Family 3 — privacy-mask contract (FIX TEMPLATES):**
- tc74×3: every rendered money value must carry class="money" (mask hook) per app.js; add classes/spans in dashboard.html/portfolio.html/watch.html wherever amounts render (follow the pattern already used in base/P1 pages — grep app.js for the exact selector and match it, including data-amount attribute if that's what tc74 names).

**Family 4 — feature-dead tests (DELETE the listed tests; their features are removed by approved design):**
- tc40_pnl::test_tc40_dashboard_card_shows_proposed_value_and_l2_badge + test_tc40_dashboard_never_claims_pnl_approved (L2/ledger reconciliation retired by D37)
- tc51×2 (watch "freed" badges — two-view watchlist removed by D38)
- tc76×2 (three inline SVG charts — v5 uses one pure-CSS chart; the negative-segment test may partially survive if v5 has any red/negative styling — if its subject exists in v5 keep it updated, else delete)
- tc77 (donut chart — not in v5)
- If a file becomes empty after deletions, delete the file (and its now-unused helpers).

**Family 5 — UPDATE to v5 truth (read each test AND the new template, update asserts/selectors; do NOT change product behavior):**
- tc25_route_error×2 (error-page surfacing still exists in v5 shell — update expected markers)
- tc27_dashboard×3 (v5 markers: Total Invested / Received / Next Payout / Outstanding)
- tc39_error_surfacing×3 (empty/no-bond month messages — use the exact v5 strings from the templates)
- tc42 (dashboard amounts vs queries — update selectors, keep the amount-vs-DB equality core)
- tc48 (dashboard renders seeded scale — update selectors; keep scale intent)
- tc54×2 (payment updates dashboard — update selectors)
- tc67 (all-surfaces no-trace-of-blocked-duplicate — update the surface list to v5 routes: /, /portfolio, /watch, /goals, /notifications, /settings)
- tc68::test_tc68_post_to_watch_route_creates_nothing — REPLACE: POST /watch still must NOT create a holding; new assert = it creates a candidate only (watch_state='watching'), never 'holding' (FR-54/57: both entries funnel the lock for holdings)
- tc80×2 (investigate: alert-history timestamps persist (keep, fix storage if broken) + "no network or push channels in source" (keep as guard; if a source file still references push/websocket remove that dead code))

**Family 6 — FR-55/FR-53 drawer (BUILD):**
- Holdings rows in portfolio.html open a detail drawer on click (FR-53: "row opens detail drawer"): drawer shows Company/ISIN, rating, coupon, yield, frequency, invested, received, next payout, status + the position's payment history rows (from payment_ledger). Vanilla JS + a small GET route (e.g. /portfolio/<id>/detail returning JSON or a partial) using queries.py functions (centralization!). Style consistent with v5 (simple right-side panel, no animation). Respect empty states.

## Rules

- Boundaries: you own tests/*, src/queries.py, src/app.py (SQL relocation + detail route), the four templates (money classes + drawer), portfolio.html. Do NOT touch engine.py/lock.py logic, db.py, scripts/, base.html/theme.css/app.js (mask contract already exists).
- Zero workbook/import references stay zero. Zero comments in code. No new dependencies.
- Self-check (paste): py_compile all touched .py; `grep -rn "1-28\|1..28" src/ tests/ || echo BOUNDS-31:clean`; tc45 greps from the failing tests now pass structurally (paste the tc45 test bodies' grep equivalents); money-class grep counts; per-test DISPOSITION TABLE (test -> UPDATED/DELETED/REPLACED/PASS-untouched, one line each, all 34).

## REPORT

Disposition table (34 rows), files+bytes changed, drawer route+markup summary, self-check outputs, one-line summary. BLOCK with reason on any test whose approved-doc intent you cannot preserve.
