# Brief 39 — P2 Lane A: payout editor + attribute parity

Worker: wl-b2. Cwd = `phase-payouts` worktree (branch created FROM execute-v6 after P1 merge — PM creates it). NO git writes. NO pytest — py_compile + venv test-client smoke only (remote CI gates). Reply only REPORT.

## Contract
Plan `../.IDE_Plans/dk_bond_tracker_watchlist_stage12_impl_plan_20261031_v1.1.json` phase **P2 tasks T2.1/T2.2/T2.3** (FROM/TO binding). Locked design `../fix-watchlist/.IDE_Plans/design_drafts/ui_frontend_design_v6.html` (visual truth: payouts cells, move panel, Details grid, attribute strip). Docs: PRD v6 FR-67/68/69, AF v6 (payout_cell_edit, attribute parity AFs), Pseudocode v6 (blocks for both). Base state = execute-v6 AFTER P1 (shared sort key already exported from src/engine.py — USE it, never re-sort per template).

## Tasks

1. **T2.1 — editable payouts, newest-first** (templates + existing route only):
   - Month columns: elapsed + current only, NEWEST LEFT (verify current template order; strip any future column at render time — window ends at current month, F-231 rule).
   - Past/current cells become `<button class="payout-cell">` opening an inline mini-editor (amount + Received? checkbox + Save/Cancel) that POSTs the EXISTING payment route (grep `@app.route` for the payment/save handler — F-233 seam; NO new tables/routes unless the existing route truly cannot serve the tab context — if blocked, BLOCK and report instead of inventing).
   - After save, next render re-derives statuses (engine) — no cached health writes.
   - Rows keep the shared D43 sort (Danger→On-going→Matured, Invalid last).
2. **T2.2 — attribute parity** (FR-69): Add Candidate collects Rating agency, Issuer type, Secured, Face value, Payout cycle, Invested ₹ (fields exist on the watch form already from D41 era? — check; add missing inputs) → persist via existing bonds columns/ALTER path (db already has payout_cycle/issuer_type/secured/face_value/watch_investment columns per db.py CHECKs — verify); Move carries them; Holdings renders the compact attribute strip row (colspan across table) with the SAME values; Watchlist Details grid shows the same (Details toggle may exist only in design — implement as row-expand or drawer consistent with base patterns; keep vanilla JS).
3. **T2.3 — tests**: append to `tests/` a new file `tests/test_tc138_payouts_parity.py` (next free TC id after consulting `../fix-watchlist/docs/Test_Plan_addendum_v6.json` — use TC-129/130/133/137 ids in docstring-less test names): TC-129 payout edit saves + status re-derives; TC-130 no future month headers; TC-133 parity roundtrip (candidate→move→holdings strip equal values); TC-137 move panel renders the FR-67..74 labels. REMOTE marks per Test_Plan v6 (match its `level` convention).

## Rules
No comments; no new deps; derive_health raise paths untouched; engine shared sort only; never touch store/ or data/bonds.db (temp DBs only); smoke via venv test-client.

## REPORT
Per task files+bytes + smoke outputs (edit→rederive proof, future-month proof, parity equality proof); self-check block (py_compile, greps for route reuse, banned-token scan); one-line summary. BLOCK on ambiguity (especially if the existing payment route cannot serve the editor).
