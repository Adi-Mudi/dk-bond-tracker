# Brief 22 — P1 spine: schema, routes, shell+themes (stage 11, tasks T1.1-T1.3)

Worker: wl-build1. Work ONLY in your cwd (`execute-v5` worktree). Execute the plan's P1 exactly. **NO git** (no add/commit/push — PM commits). No pytest (owner rule: all testing is remote). Reply only the REPORT section.

## Inputs (read first)

1. Plan: `../.IDE_Plans/dk_bond_tracker_watchlist_stage11_execute_plan_20261031_v1.0.json` — tasks **T1.1, T1.2, T1.3** are your contract (their FROM/TO is binding; owner constraints Q1-Q4 in the header are law).
2. Design truth (locked): `.IDE_Plans/design_drafts/ui_frontend_design_v5.html` — copy the exact `:root`, `html[data-theme="light"]`, `html[data-theme="dark"]`, `[data-theme="system"]` token blocks, sidebar markup structure, header actions (System|Light|Dark segmented control + Hide amounts), and the pre-paint localStorage `dk-theme` bootstrap script VERBATIM into your shell/theme files. This is the ONLY visual source.
3. Docs: `docs/Watchlist_Architecture_Addendum_v2.json` (data ownership + theme subsystem), `docs/PRD_DK_Bond_Tracker_addendum_v4.json` (FR-51/52 routes; FR-60 themes), `docs/SRS_DK_Bond_Tracker_addendum_v4.json`.
4. Existing pattern: read `src/app.py` and the current `src/` layout FIRST and extend that exact style (Flask render_template, existing config/db helpers) — Q4: same architecture, no new dependencies, requirements.txt untouched.

## Deliverables (in `execute-v5`)

- **T1.1 schema**: bootstrap creating EMPTY tables — positions, candidates, payouts, settings, alerts_log per arch v2 fields (positions: company, isin, rating, coupon, yield, frequency, invested, start_date, end_date, credit_day, status; candidates: company, isin, rating, coupon, est_yield, source_note, state default 'watching'; payouts: position_id, month, amount, received_flag, status; settings: theme default 'system', hide_amounts default 0, smtp fields, share flags). Fresh install = zero rows, no import code path anywhere (D37).
- **T1.2 routes**: `src/app.py` gains the 6 routes (`/dashboard`, `/portfolio`, `/watchlist`, `/goals`, `/alerts`, `/settings`) rendering empty-state templates (they will fill with real markup in later phases — provide minimal valid pages now that pull base.html). Keep every existing route working exactly as before.
- **T1.3 shell**: `src/templates/base.html` (sidebar with the exact 6 labels, header actions, `{% block %}` content), `src/static/theme.css` (v5 token blocks only — no other redesign), `src/static/app.js` (theme switcher sync across segments/radios + localStorage + pre-paint pattern, Hide-amounts mask toggling all `.money` elements like v5). Settings screen gets the Appearance section (System/Light/Dark radios) wired to the same logic (T3.3 owns the rest of Settings — you only add the Appearance card stub inside settings.html if you must; prefer wiring via base so lane B just adds cards).

## Boundaries (non-goals)

Do NOT build: portfolio/watchlist/dashboard content tables (P2/P3), engine/lock modules (P2), alerts/goals/settings full content (P3), any test files, any git command.

## Self-check (run, paste into REPORT)

```
python3 -m py_compile src/app.py && echo "PY-COMPILE: ok"
grep -c "Dashboard\|Portfolio\|Watchlist\|Financial Goals\|Alerts\|Settings" src/templates/base.html
grep -c "data-theme" src/static/theme.css src/templates/base.html src/static/app.js
grep -nE "https?://|cdn\.|googleapis|unpkg|jsdelivr" src/templates/base.html src/static/theme.css src/static/app.js || echo "EXTERNAL-REFS: clean"
grep -nE "import_xlsm|--import|v5.5_40L" src/ -r || echo "NO-IMPORT: clean"
git status --short 2>/dev/null | head -5 || true   (read-only glance; do NOT stage/commit anything)
```

## REPORT

Files created/changed (paths + bytes), self-check outputs pasted, one-line summary. BLOCK with reason if a FROM state doesn't match reality (the plan's FROM was written by the PM — if the actual code differs, report it instead of improvising).
