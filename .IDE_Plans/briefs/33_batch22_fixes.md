# Brief 33 — Batch 22 fixes (F-221..F-225)

Worker: wl-fix2. Cwd = `patch-d41` (HEAD 54bbafb, CI green). NO git. NO pytest (venv smoke ok). Reply only REPORT. Reviewer evidence is exact — implement, don't re-litigate.

## Fixes (all findings REAL, adjudicated by PM)

1. **F-221 (MAJOR) — non-numeric amount must never 500**: `src/app.py:227` (dashboard_model `invested = float(row["amount"] or 0.0)` outside try) and `src/app.py:942` (_portfolio_holdings same) — wrap per-row: unparseable amount -> that row treated as invalid (same Invalid-chip contract: status Invalid, invested shown as — or 0 with caption, HTTP 200 on / and /portfolio). Do NOT weaken any engine raise. Check sibling float() calls at display boundaries (grid/print/exports already covered by reviewer) — only fix ones OUTSIDE existing per-row catches that can 500.
2. **F-222 (MAJOR) — Add Position percent fields must reject empty**: `src/app.py:1113-1116` passes required=False into percent_value -> '' accepted as None -> 302+NULL. Contract (PRD v5 FR-62 + SRS AC): coupon_pct and expected_yield_pct on ALL THREE forms reject empty with named 400. Make the portfolio-add path require them (keep 0.00 valid). Watch path already correct — don't break it.
3. **F-223 (MINOR) — Remove row-type check**: `/portfolio/invalid/<id>/remove` revalidation (~app.py:1229-1240) must also require `watch_state='holding'`; candidate (watching) -> named 400, zero writes.
4. **F-224 (MINOR) — payouts Remove + doc amendment**:
   a. `src/templates/portfolio.html` payouts tab rows: show Remove button for rows whose health is Invalid (reuse the same POST route; small button consistent with holdings row).
   b. Amend DRAFT docs in `../fix-watchlist/docs/` (they are unapproved drafts — edit in place): `PRD_DK_Bond_Tracker_addendum_v5.json` FR-65 statement + `SRS_DK_Bond_Tracker_addendum_v5.json` FR-65 AC1 so the clause reads: every surface that renders rows shows the Invalid chip (holdings, payouts, print marker); the Remove action appears on Holdings rows and Payouts rows (single server route revalidating a holding); dashboard exposes the bad-row count/flag as an aggregate note (no row list there). Keep all other FR-65 text (200 guarantee, severity) unchanged.
5. **F-225 (MINOR) — broker NULL**: both insert paths (watch add ~app.py:591/619-621, portfolio add ~1118-1146): blank/whitespace broker -> store NULL (not ''). Preserve existing non-empty values; move-with-blank-keeps-candidate logic unchanged (COALESCE semantics preserved: only coerce the INPUT, don't null out candidate data).

## Tests (append to tests/test_tc87_d41_patch.py)

- inject amount='abc' holding -> GET / and /portfolio = 200 + Invalid shown (F-221).
- POST /portfolio add with coupon_pct='' and separately expected_yield_pct='' -> 400 named, zero rows (F-222); 0.00 still 302.
- POST invalid-remove on a watching candidate -> 400 named, candidate intact (F-223).
- payouts row for invalid holding shows Remove; POST works (F-224a).
- blank broker inserts -> IS NULL on both paths (F-225).

## Self-check (paste)
py_compile all touched; smoke: the 5 scenarios above via venv test-client (no pytest); `grep -n "float(row\[\"amount\"\]" src/app.py` showing remaining calls are inside per-row catches (or none); PRD/SRS JSON parse after edits.

## REPORT
Per-finding: file+line changes + smoke before/after; doc amendment diff summary; self-check outputs; one-line summary. BLOCK if any finding's contract is ambiguous.
