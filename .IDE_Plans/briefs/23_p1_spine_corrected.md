# Brief 23 — P1 spine CORRECTED (plan v1.1, supersedes brief 22)

Worker: wl-build1. Your BLOCKED report was accepted in full (F-185 REAL, FIXED). The plan was revised to **v1.1**. Execute THIS brief — it mirrors plan v1.1 P1. Work ONLY in your cwd (`execute-v5`). NO git writes. No pytest (remote-only testing). Reply only the REPORT section.

## Contract (plan v1.1, exact)

**T1.1 — ZERO new tables.** Existing schema is the truth (verified by you): `bonds` = every company row, partitioned by `watch_state` ('holding' = Portfolio My Holdings, 'watching' = Watchlist candidates); payments = `payment_ledger`; settings = `alert_prefs` (theme EXCLUDED — theme lives in browser localStorage only, D40/FR-60). Your job: ensure the bonds columns required by FR-53/54 exist (rating, coupon, yield, frequency, invested, start_date, end_date, credit_day, watch_state, status...) — ADD missing columns to the existing CREATE TABLE or migration path only if truly absent; verify first and list what you added vs found. Fresh install still yields ZERO rows. NO CREATE TABLE positions/candidates/payouts/settings/alerts_log anywhere.

**T1.2 — routes per arch v2 (binding):** Dashboard -> `/` (exists), Watchlist -> `/watch` (exists), Alerts -> `/notifications` (exists), Goals -> `/goals` (exists, CRUD at :395 — DO NOT touch its methods), Settings -> `/settings` (create if missing), Portfolio -> `/portfolio` (NEW stub route serving the page; tab logic comes in P2). Sidebar links in base.html use exactly these paths (labels per FR-51: Dashboard, Portfolio, Watchlist, Financial Goals, Alerts, Settings). ALSO remove D37 import remnants: `src/app.py:26` (`from src.import_xlsm import import_workbook`), `src/app.py:658` (`--import` arg), and `src/import_xlsm.py` itself — check nothing else imports it first (`grep -rn import_xlsm src/ tests/` — tests were cleaned; if something still imports, report BLOCKED instead of breaking it).

**T1.3 — REPLACEMENT of existing base.html (acknowledged):** current `src/templates/base.html` (9,223 B) is extended by 10 templates (dashboard, grid, watch, goals, notifications, share, payment_edit, error, payout, add_position). Replace its chrome with the v5 shell from `.IDE_Plans/design_drafts/ui_frontend_design_v5.html`: fixed sidebar (6 exact labels), header (System|Light|Dark segmented control + Hide amounts), `{% block content %}`. **Port the legacy classes those 10 templates use** (banner/chip/table/status styles — grep the templates for class names to get the full list) into `src/static/theme.css` so every page still renders correctly. Add `src/static/app.js`: theme switcher (segments + Settings radios sync), localStorage `dk-theme`, pre-paint pattern from v5, Hide-amounts money mask (v5 behavior). Copy v5 `:root` / `[data-theme=light|dark|system]` token blocks verbatim. Keep `{% block title %}` and any existing macros the templates rely on — inspect before replacing; report anything you cannot preserve.

## Self-check (run, paste)

```
python3 -m py_compile src/app.py && echo PY-COMPILE: ok
grep -rn "CREATE TABLE" src/ | grep -iE "positions|candidates|payouts|settings|alerts_log" || echo "NO-FORBIDDEN-TABLES: clean"
grep -rn "import_xlsm\|--import" src/ || echo "NO-IMPORT: clean"
grep -c "data-theme" src/static/theme.css src/static/app.js src/templates/base.html
grep -oE 'href="/[a-z.]*"' src/templates/base.html | sort -u
grep -nE "https?://|cdn\." src/templates/base.html src/static/theme.css src/static/app.js || echo "EXTERNAL-REFS: clean"
for t in dashboard grid watch goals notifications share payment_edit error payout add_position; do grep -l "block content\|extends" src/templates/$t.html >/dev/null 2>&1 && echo "$t: extends-ok" || echo "$t: CHECK"; done
```

## REPORT

Files changed (+bytes), what columns were found vs added in T1.1, ported legacy classes list, self-check outputs, one-line summary. BLOCK with reason on any ambiguity — your last BLOCK was exactly right; same standard applies.
