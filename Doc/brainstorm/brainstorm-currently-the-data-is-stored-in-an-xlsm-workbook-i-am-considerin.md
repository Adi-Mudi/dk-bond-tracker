---
artifact: brainstorm
project: currently-the-data-is-stored-in-an-xlsm-workbook-i-am-considerin
version: 1.0.0
status: published
stage: brainstorming
run: 2026-09-27T13-04--currently-the-data-is-stored-in
created: 2026-09-27T14:22:31.123Z
updated: 2026-09-27T14:22:31.123Z
---

# Brainstorm Notes — XLSM → SQLite + lightweight front end migration

## Mission

Currently, the data is stored in an XLSM workbook. I am considering migrating it to a SQLite database with a lightweight front end. My main goal is to have a solution that is easy to maintain, scalable as the data grows, and simple to work with in the future.

What would be your recommendation? Which approach would be the most practical and user-friendly?

## Interview Answers

1. Q: What kind of lightweight front end do you want? A: User was worried an "app" means separate Android/Linux/desktop builds; wants it very lightweight; asked to first study what the Excel data contains, then recommend. Resolved into Q1.
2. Q: Who will use it, and where? A: Offline only. Shareable with friends; each user keeps data on their own local system — no cloud, no accounts.
3. Q: How much of the current XLSM behavior should migrate? A: Full rebuild — data + Dashboard + status logic all leave Excel; XLSM can be retired as the working tool.
4. Q: (scope correction) Study source of truth? A: docs/RTM.md was written after the fact; the actual logic lives in the Excel only — study `v5.5_40L_Project_Tracker.xlsm` itself, not the document.

## Scout Proposals

### NEW EXTRACTOR
- (none — code/doc/community scouts were not dispatched; community scan selected but web search disabled by run flag)

### PRD CHECKER
- (not run at brainstorm stage)

### RTM CHECKER
- (not run at brainstorm stage)

### WEB SEARCH AGENT (community scan selected, web disabled by flag)
- community: (skipped — web search NOT ALLOWED for this run)
- official: (skipped)
- similar: (skipped)

### DOC-CODE-ANALYST FINDINGS (persistent session, verified against the .xlsm itself)
- Source verified: fresh olevba 0.60.2 + raw sheet XML + styles.xml extraction; SHA-256 matches live workbook byte-for-byte.
- Workbook is a mini-app: 15 bonds, 5 sheets (Note, Bond - Watch list, Monthly Returns, Dashboard, Home Plan); payment grid Sep-2025 → Jul-2032 (96 month columns).
- Core formulas: K = SUM(months received), L = K − J (Maturity Amount); Dashboard summary = COUNTA/COUNTIF/SUM over Monthly Returns; E6 = SUM(current month column).
- Status engine (col A): Danger = previous calendar month cell empty (single-month check only — older misses invisible); Completed = months paid ≥ tenure (overrides Danger); else On-going. Colors: green paid / light red due; status colors via CF (red/orange/green).
- Triggers: Workbook_Open/BeforeSave rebuild Dashboard (static snapshot) + regenerate headers + inject K/L + blocking MsgBox; Worksheet_Change on tenure/start-month/month cells re-runs row status.
- Quirks to fix in migration: headers hardcoded Sep-2025..Feb-2027; month scan stops Jan-2031; Danger checks only previous month; dashboard stale between saves; col widths +2 per open; On Error Resume Next silences failures; dead code (second Workbook_Open, AddWorksheetChangeEvent); duplicate-ISIN CF covers only D7 + D14:D16; header-text coupling.
- Data quality: verbatim typos (Staus, Yeild, ISN, "Till Rerun Amount ", Quartely, Totall, Payment type Type); same 15 bonds in Watch list and Monthly Returns, numbers reconcile; Home Plan logs real irregular savings (39588, 10063, 0).
- Owner wish list (Note sheet): discount amounts, TDS deduction, quarterly/yearly payment options, Dashboard P&L + ongoing bond TL value, and "most important": completed bonds must free up for reinvestment (duplicate-deduction only for Ongoing/Danger).
- Migration must reproduce: bond master, payment ledger, derived totals as queries, status rules (fix single-month Danger quirk), dashboard views, watch-list analytics, Home Plan schedule.

## Decision Summary
- new-fr: [SQLite local DB schema (bonds, payments ledger, home_plan), Flask local web UI (browser-based, cross-platform, offline per-user data), dashboard as live queries (summary counts/amounts, this-month returns, 83-month history, status overview), CSV export, one-time XLSM import script, payment month-grid UI rendering, owner wish-list features (discount, TDS, quarterly/yearly payouts, P&L, reinvestment/free-up flag)]
- update-fr: [status rules migrate from VBA with fixes — Danger = any unpaid past month (not just previous month), Completed overrides, zero-value = unpaid preserved]
- helper-update: []
- new-helper: []

## Agreed

- Q1: Which front-end framework for the local web app? — Flask + simple HTML pages (tiny, no build step, runs on any OS, easy for friends to run)
- Q2: How should existing XLSM data migrate into SQLite? — One-time Python script imports the .xlsm into SQLite; Excel kept as read-only backup
- Q3: Should monthly payments be stored as rows instead of Excel's month columns? — Row-per-payment ledger in SQLite (bond, month, amount, paid) + Excel-like month-grid rendered by the UI; totals/status become live queries; fixes hardcoded headers, Jan-2031 scan limit, and stale dashboard
- Q4: Is CSV/Excel export needed once Excel is no longer the front end? — Yes, CSV export for sharing/printing

## Not wanted

- (none)

## Open

- (none)
