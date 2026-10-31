# Brief 25 — P3 Watchlist/Dashboard/Goals/Alerts/Settings lane (plan v1.1 tasks T3.1-T3.3)

Worker: wl-build3. Cwd = `phase-watchlist` worktree (branch from execute-v5 @ P1). NO git writes (PM commits). NO pytest (remote-only testing; py_compile/greps allowed). Reply only the REPORT section.

## Inputs (read first)

1. Plan contract: `../.IDE_Plans/dk_bond_tracker_watchlist_stage11_execute_plan_20261031_v1.1.json` — phase P3 tasks T3.1/T3.2/T3.3 (FROM/TO binding; owner Q1-Q4 header).
2. Design truth (locked): `.IDE_Plans/design_drafts/ui_frontend_design_v5.html` — Watchlist, Dashboard, Goals, Alerts, Settings views are your visual contract (copy markup structure/classes; tokens already in `src/static/theme.css` from P1).
3. Docs: `docs/PRD_DK_Bond_Tracker_addendum_v4.json` (FR-51, FR-56, FR-60), `docs/SRS_DK_Bond_Tracker_addendum_v4.json`, `docs/Watchlist_Architecture_Addendum_v2.json` (routes /watch, /, /goals, /notifications, /settings).
4. Existing code (P1 state): `src/app.py` (routes exist; /goals CRUD at :395 KEEP), `src/templates/base.html` (v5 shell), `src/templates/watch.html`, `dashboard.html`, `goals.html`, `notifications.html`, `settings.html` (settings is a P1 stub — you fill it), `src/db.py`.

## Deliverables

- **T3.1 `src/templates/watch.html`** (replace): candidates ONLY — rows from `bonds WHERE watch_state='watching'`; columns EXACT FR-56: Company/ISIN, Rating, Coupon, Est. Yield, Source note, Action(`Move to Portfolio` button); `Watching` chip beside each name; FORBIDDEN anywhere on this page: Invested, Received, Next Payout, health chips (On-going/Danger/Matured) — grep-proof required; `+ Add Candidate` form (company, ISIN, rating, coupon, est yield, source note) with entry validation (normalized-company + ISIN uniqueness across the WHOLE bonds table — reject duplicates with named error; no format-invalid rows). Caption: "Watchlist holds candidates only. 'Move to Portfolio' creates the position and locks the company while it is On-going or Danger." Move-to-Portfolio POST: calls `src.lock.check_add_allowed` (import from src.lock — built by the other lane on phase-portfolio; if src/lock.py does not exist YET in your worktree, import it anyway and note in REPORT that cross-lane merge lands it — do NOT duplicate the lock logic) then flips watch_state to 'holding' with form fields start/end/credit day (mini-form or reuse Add Position pattern).
- **T3.2 `src/templates/dashboard.html`** (replace): cards — Total Invested (primary, largest, top-left), Received, Next Payout + Outstanding caption; all from DB aggregates (zero rows -> ₹0.00 states); ONE pure-CSS Invested-vs-Received horizontal bar pair per holding (v5 chart pattern, widths from aggregates); note line: "Monthly history shows completed months + current month only — future months are never shown."
- **T3.3 `src/templates/goals.html`, `notifications.html`, `settings.html`** (replace/fill): goals — keep existing CRUD behavior/data flow, present rows as v5 goal cards (target/saved/progress bar, empty default); notifications (Alerts) — day-wise rule card text ("If Received amount is not entered on the credit day → status becomes Danger same day.") + channel checkboxes (In-app notification, Email (personal SMTP, personal → personal)) persisted to alert_prefs; settings — Email (SMTP host/port/from/to), Privacy (Hide amounts by default), Currency INR, Share/Export checkboxes (Holdings/Payouts/Goals), Data card "Start empty — no data imported.", Appearance card (System/Light/Dark radios wired to the SAME dk-theme logic in app.js — if app.js needs a hook, add a small inline script in settings.html rather than editing app.js, OR extend app.js ONLY by appending radios-sync code; state which in REPORT).

## Boundaries

Do NOT touch: base.html, theme.css, portfolio.html, engine.py, lock.py, scripts/, db.py schema. app.py edits = ONLY the routes for watch POSTs/dashboard data/settings save if needed (keep /goals methods as-is, keep /portfolio untouched — other lane owns it).

## Self-check (run, paste)

```
python3 -m py_compile src/app.py && echo PY-COMPILE: ok
grep -nE "Invested|Received ₹|Next Payout" src/templates/watch.html || echo "WATCH-WHITELIST: clean (no investment columns)"
grep -c "Watching\|Move to Portfolio\|Add Candidate" src/templates/watch.html
grep -c "Total Invested\|Received\|Next Payout\|Outstanding" src/templates/dashboard.html
grep -c "System\|Light\|Dark\|Appearance" src/templates/settings.html
grep -nE "https?://" src/templates/watch.html src/templates/dashboard.html src/templates/settings.html || echo EXTERNAL-REFS: clean
```

## REPORT

Files +bytes, watchlist whitelist proof, settings wiring choice (app.js append vs inline), self-check outputs, one-line summary. BLOCK with reason on FROM mismatches or if src/lock.py cross-lane dependency looks unsafe to reference.
