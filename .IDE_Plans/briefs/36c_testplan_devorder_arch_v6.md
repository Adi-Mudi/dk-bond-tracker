# Brief 36c — TestPlan v6 + Development Order v4 + Architecture Addendum v3

Worker: wl-doc-c. Cwd = fix-watchlist. NO git. No local pytest. Three deliverables + REPORT.

## Truth
1. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — D41/D42/D43 (D43 LOCKED sort standard).
2. LOCKED design `.IDE_Plans/design_drafts/ui_frontend_design_v6.html` @ 7b67f54.
3. Templates: `docs/Test_Plan_addendum_v5.json` (continue TC ids after **TC-128**), `docs/Development_Order_addendum_v3.json` (next = v4), `docs/Watchlist_Architecture_Addendum_v2.json` (next = v3).
4. F-233 implementability seams (from design review, bind them): payment editor maps to existing POST payment route + payment_ledger; email test = NEW route persisting via alert_prefs; attribute fields = FR-40 set + broker ALTER; credit-day CHECK must migrate 1..28 -> 1..31; Goals #returns link needs view+tab JS; arch-v2 candidate whitelist predates D42.

## Deliverables
1. `docs/Test_Plan_addendum_v6.json` (extends v5) — TC-129+ (REMOTE level, strategy: GitHub Actions only), one TC per: payout cell edit saves + status re-derives; payouts month headers never exceed current month and are newest-first; dashboard/holdings/payouts/exports/print all emit Danger->On-going->Matured order (D43 — table of surfaces); status filter chips; attribute parity roundtrip (candidate -> move -> holdings strip values equal); email preset autofill values + test-email banner states; returns tab paid·pending math + cumulative running total + Goals KPI link navigation; credit_day=31 accepted post-CHECK-migration (and rejected before); move inline panel fields labels exact (FR-67..74 bindings — read PRD v6 when available, provisional map OK with a note).
2. `docs/Development_Order_addendum_v4.json` (extends v3) — ordered REMOTE-gated steps: schema CHECK migration -> sort-key unification -> payout editor routes -> attribute ALTER+forms+strips -> dashboard tabs/filters -> email preset+test route -> returns aggregation+Goals link -> full-suite CI green.
3. `docs/Watchlist_Architecture_Addendum_v3.json` (extends v2) — sections: payout-edit route ownership (existing payment POST, payment_ledger truth); NEW email-test route + alert_prefs key/value persistence + mailer.py; D43 sort enforcement points (ONE shared sort key — engine HEALTH_ORDER incl Invalid; applied at query or model layer per surface, never per-template sorting); attribute-column inventory (FR-40 + broker + which need bonds ALTER + credit-day CHECK migration 1..31); supersede note: arch-v2 candidate-whitelist text extended to the D42 attribute set; #returns link navigation contract (view switch + dashboard tab activation).

## Self-check (paste)
JSON parse x3; TC declaration-dup empty; banned grep empty; D42/D43 >=3 cites per file.

## REPORT: files+bytes, id ranges, self-check outputs, one-line summary. BLOCK on ambiguity.
