# Brief 40 — P3 Lane B: dashboard tabs/status/filters, returns history, goals link, email presets

Worker: wl-b3. Cwd = `phase-dash` worktree (branch created FROM execute-v6 after P1 merge — PM creates it). NO git writes. NO pytest — py_compile + venv test-client smoke only. Reply only REPORT.

## Contract
Plan `../.IDE_Plans/dk_bond_tracker_watchlist_stage12_impl_plan_20261031_v1.1.json` phase **P3 tasks T3.1/T3.2/T3.3/T3.4** (FROM/TO binding). Locked design `../fix-watchlist/.IDE_Plans/design_drafts/ui_frontend_design_v6.html` (Dashboard tabs + filter chips + Returns history table + Goals KPI + Settings presets are the visual truth — port structure/classes). Docs: PRD v6 FR-70/72/73, SRS v6 ACs, Arch v3 (email test route + alert_prefs persistence + #returns navigation contract), AF v6 (presets/returns/kpi AFs). Base = execute-v6 AFTER P1 (shared sort key from engine; statuses/chips infra from D41 exists).

## Tasks

1. **T3.1 — dashboard upgrade**: tabs Overview | Returns history (scoped JS switcher like design `data-dtab`); per-company bar rows gain status chips; filter chips All | Danger | On-going | Matured (vanilla JS filter); rows already sorted by shared key after P1 (verify, do not re-sort in JS differently — filter must PRESERVE shared order); 'sorted by priority' caption.
2. **T3.2 — returns history tab**: server aggregation from payment_ledger: per month (elapsed+current only, NEWEST FIRST): Interest received (sum paid amounts), Positions paid · pending (count of holdings credited vs awaiting, of active), Cumulative running total (latest == dashboard Received); current month highlighted; no future months. Query helpers go in src/queries.py (centralization guard: no aggregation SQL in app.py/templates — tc45).
3. **T3.3 — goals KPI + email presets**: Goals view top KPI strip (Earned this month, Total received) + link that navigates to Dashboard AND activates the Returns tab (Arch v3 contract); Settings>EMAIL: provider dropdown Gmail/Outlook/Custom autofill (exact values per PRD FR-72: smtp.gmail.com 587 TLS / 465 SSL alt; smtp.office365.com 587 STARTTLS), collapsible setup guide markup, Send test email button -> NEW route (Arch v3: persists result via alert_prefs, uses mailer if configured, NEVER 500 — failure renders the banner text from design).
4. **T3.4 — tests**: new file `tests/test_tc139_dashboard_returns_email.py` (align ids with Test_Plan v6 TC-131/132/134/135/136): tabs switch, filter preserves order, returns math (interest/paid-pending/cumulative==Received card), preset autofill values, test-email banner both outcomes, credit_day31 insert (pair proof with P1 migration).

## Rules
No comments; no new deps; shared sort only; tc45 centralization respected (SQL in queries.py); no future months anywhere; never touch store/ or real data/bonds.db; banned-token sweep stays clean.

## REPORT
Per task files+bytes + smoke outputs (tabs, filter order, returns math table, preset values, banner, credit31); self-check block; one-line summary. BLOCK on ambiguity.
