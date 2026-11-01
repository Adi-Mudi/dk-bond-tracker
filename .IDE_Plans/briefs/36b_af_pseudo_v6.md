# Brief 36b — Atomic Functions + Pseudocode addendum v6

Worker: wl-doc-b. Cwd = fix-watchlist. NO git. One deliverable pair + REPORT.

## Truth
1. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — D41/D42/D43 (D43 sort standard LOCKED).
2. LOCKED design `.IDE_Plans/design_drafts/ui_frontend_design_v6.html` @ 7b67f54.
3. Templates: `docs/Atomic_Functions_addendum_v5.json` (continue AF ids after **AF-74**), `docs/Pseudocode_addendum_v5.json`? — if Pseudocode v5 does not exist, extend `docs/Pseudocode_addendum_v4.json` and say so in the change record (check the directory first).
4. Reference code (pattern truth, read-only): `src/engine.py` (derive_health, sort_payout_rows HEALTH_ORDER), `src/app.py` (payment POST, move route), `src/db.py` (schema/CHECK).

## Deliverables
1. `docs/Atomic_Functions_addendum_v6.json` (extends v5) — AF-75+ covering: payout_cell_edit (save+rederive), month_columns_elapsed_current (newest-first), attribute_collect_candidate + attribute_display_parity (three surfaces), dashboard_priority_sort + status_filter, sort_key_appwide (D43 — single shared ordering function fed by HEALTH_ORDER incl Invalid last), email_preset_apply (Gmail/Outlook/Custom autofill), email_send_test (route + banner), returns_history_aggregate (monthly interest + paid/pending of active + cumulative), goals_kpi_link (view+tab navigation), credit_day_check_migration (1..31 ALTER/rebuild). coverage_map keys = the new FR ids from PRD v6 (FR-67..FR-74 — read `docs/PRD_DK_Bond_Tracker_addendum_v6.json` when wl-doc-a has written it; if absent, map provisionally and note it).
2. `docs/Pseudocode_addendum_v6.json` (extends the latest pseudocode addendum you find) — blocks for each new AF: sort key reuse (single HEALTH_ORDER incl Invalid last — no per-screen reimplementation), payout edit flow, preset autofill, returns aggregation SQL sketch (payment_ledger GROUP BY month DESC), credit-day CHECK migration snippet (table rebuild preserving rows).

## Self-check (paste)
JSON parse both; AF declaration-dup grep empty; banned grep empty; D43 >=3 cites across the two files.

## REPORT: files+bytes, id ranges, coverage keys used, self-check outputs, one-line summary. BLOCK on ambiguity.
