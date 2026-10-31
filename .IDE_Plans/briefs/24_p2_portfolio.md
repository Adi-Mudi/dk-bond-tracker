# Brief 24 — P2 Portfolio lane (plan v1.1 tasks T2.1-T2.3)

Worker: wl-build2. Cwd = `phase-portfolio` worktree (branch from execute-v5 @ P1). NO git writes (PM commits). NO pytest (remote-only testing; py_compile/greps/smoke-import checks allowed). Reply only the REPORT section.

## Inputs (read first)

1. Plan contract: `../.IDE_Plans/dk_bond_tracker_watchlist_stage11_execute_plan_20261031_v1.1.json` — phase P2 tasks T2.1/T2.2/T2.3 (FROM/TO binding; owner Q1-Q4 header).
2. Design truth (locked): `.IDE_Plans/design_drafts/ui_frontend_design_v5.html` — the Portfolio view markup (tabs, table columns, chips, Add Position form, legend, sort caption) is your visual contract; copy structure/classes, keep v5's CSS tokens from the existing `src/static/theme.css` (P1 landed it).
3. Docs: `docs/PRD_DK_Bond_Tracker_addendum_v4.json` (FR-53..57), `docs/SRS_DK_Bond_Tracker_addendum_v4.json`, `docs/Atomic_Functions_addendum_v4.json`, `docs/Pseudocode_addendum_v4.json` (the AF/pseudo entries for add-position, derive-health, sort-payouts, lock).
4. Existing code (P1 state): `src/app.py` (route `/portfolio` with a stub page), `src/templates/base.html` (v5 shell), `src/db.py` (schema: bonds has the 8 arch columns incl start_date/end_date/credit_day/watch_state/status; payment_ledger exists), `src/validators.py` (has find_duplicate_isins etc.), `src/static/`.

## Deliverables

- **T2.1 `src/templates/portfolio.html`** (replace the P1 stub): tabs My Holdings | Payouts (client-side tab switch like v5); My Holdings table columns EXACT FR-53 (Company/ISIN, Rating, Coupon, Yield, Frequency, Invested ₹, Received ₹, Next Payout, Status) fed from `bonds WHERE watch_state='holding'` (empty-state row when none); status chips On-going/Danger/Matured; `+ Add Position` form: start date, end date, auto-calculated tenure in months (whole months), credit day 1..31 + caption "Credit day drives day-wise alerts."; status legend card (Watching/On-going/Danger/Matured meanings per v5); Payouts tab: months = current and past months ONLY (never future), cells from payment_ledger (amount or status chip), rows sorted Danger first, On-going next, Matured last, caption "Danger rows sort to top, On-going next, Matured moves down automatically."
- **T2.2 `src/engine.py`** (new): functions per pseudo v4 — `derive_health(position, ledger_entries, today)`: any unpaid credit-day passed -> Danger; all due paid -> On-going; months_paid >= tenure -> Matured (read-time derivation, no stored health drift); `display_label()` mapping ONLY renders Received/Matured (engine values untouched); `sort_payout_rows()` implementing the Danger->On-going->Matured order; `list_months_through_current()` returning current+past months only.
- **T2.3 `src/lock.py`** (new): `check_add_allowed(company_normalized, isin, conn)` — HARD BLOCK (named AppError, no override) when a bond with same normalized company OR same ISIN exists with derived health On-going or Danger; ALLOWED after Matured (re-buy restarts lifecycle: new row starts On-going); used by BOTH the Add Position POST in app.py and (later) Move to Portfolio — export one function, app.py imports it. Wire the Add Position POST route to: validate dates (reuse validators.date_range_tenure), credit day 1..31, run lock check, insert bond (watch_state='holding') + empty payment_ledger rows for the schedule start.
- Route/page reads: `/portfolio` renders server-side from DB (empty default install shows empty states — no sample rows ever).

## Boundaries

Do NOT touch: base.html, theme.css, app.js, watch/dashboard/goals/notifications/settings templates, tests/, scripts/, db.py schema shape (reuse as-is). app.py edits = ONLY the /portfolio route + Add Position POST + engine/lock imports (keep other routes untouched — other lane owns watch/dashboard).

## Self-check (run, paste)

```
python3 -m py_compile src/engine.py src/lock.py src/app.py && echo PY-COMPILE: ok
grep -nE "https?://" src/templates/portfolio.html || echo EXTERNAL-REFS: clean
grep -c "My Holdings\|Payouts\|Danger\|Matured\|Add Position\|legend" src/templates/portfolio.html
grep -rn "watch_state" src/engine.py src/lock.py src/app.py | head -5
python3 - <<'EOF'
import importlib
for m in ("src.engine","src.lock"): importlib.import_module(m)
print("IMPORTS: ok")
EOF
```

## REPORT

Files +bytes, how rows empty-state renders, tenure/credit-day validation behavior, self-check outputs, one-line summary. BLOCK with reason on any FROM mismatch or ambiguous contract — same standard as wl-build1.
