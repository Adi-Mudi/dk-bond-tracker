# Brief 02 — wl-prd — PRD + SRS addenda v3 (watchlist redesign)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverables (EXACTLY TWO files): docs/PRD_DK_Bond_Tracker_addendum_v3.json and docs/SRS_DK_Bond_Tracker_addendum_v3.json
Zero comments. No git. Nothing else written.

READ FIRST: .IDE_Plans/dk_bond_tracker_brainstorm_20261030.json decisions D33 (redesign spec), D34 (Settings spec); docs/PRD_DK_Bond_Tracker_addendum_v2.json + docs/SRS_DK_Bond_Tracker_addendum_v2.json (exact envelope/style to clone); design_drafts/watchlist_standalone_mockup_v1.html (skim sections for UI truth — v2 Settings lands in parallel; base Settings content on D34 text).

FILE 1 — PRD addendum v3 envelope: {"id": "PRD_DK_Bond_Tracker_addendum_v3", "kind": "prd", "title", "version": "v1.0", "status": "draft", "project": "01_excel_dashboard", "extends": "PRD_DK_Bond_Tracker_addendum_v2", "sections": [...], "prd_items": [...]}
prd_items EXACTLY FR-38..FR-49 (12 items), shape {id, area, statement, priority:"must", status:"proposed", decision_id}:
FR-38 standalone app shell (window chrome, sidebar nav, status bar) [D33]
FR-39 two-view watchlist: My Holdings + Watching tabs, Move-to-Holdings flow [D33]
FR-40 bond master field set upgrade: credit rating+agency, coupon %, expected yield (manual/offline), payout cycle, issuer type, secured, face value — stored per position [D33]
FR-41 watchlist table: filters (rating/payout/issuer/status), search, sort, density; right-aligned INR, status left-borders [D33]
FR-42 detail drawer per position (facts, payment schedule, actions Edit/Record Payment/Mark-watching) [D33]
FR-43 watchlist alerts panel (overdue payout, due-soon, maturity-soon) fed by credit-day engine + notifications [D33]
FR-44 Settings > Email Alerts: SMTP config UI (host/port SSL-or-STARTTLS/user/App Password masked/recipient/from), Test Email, configured/not status; stored locally (alert_prefs), env vars override [D34]
FR-45 Settings > Alert Preferences: reminder days, overdue, maturity 30/7/1, sweep time toggles [D34]
FR-46 Settings > General: default credit day, privacy-on-startup, INR format, density, theme (dark) [D34]
FR-47 Settings > Data: import Excel, export DB backup, default CSV scope, reset DB (confirm) [D34]
FR-48 Settings > About + offline statement + version [D34]
FR-49 shell integration: status bar row counts + email-status indicator; privacy toggle masks money on watchlist+settings [D33+D34]
decision_id: D33 for FR-38..43+49; D34 for FR-44..48 (scoped form dk_bond_tracker_brainstorm_20261030:D33/D34).
sections: Change Record (watchlist upgrade, D33/D34), Design source (mockup v1 confirmed + v2 Settings), per-area detail sections, Out of Scope (no live market data/prices — offline manual entry per D33; no cloud).

FILE 2 — SRS addendum v3 envelope: {"id": "SRS_DK_Bond_Tracker_addendum_v3", "kind": "srs", ..., "extends": "SRS_DK_Bond_Tracker_addendum_v2", "sections", "requirements"}
requirements: EXACTLY the same 12 ids FR-38..FR-49 (hard FK), each {id, text (SHALL), category:"functional", check_method, status:"draft", "acceptance_criteria":[2-3 Given/When/Then]}.
AC must-haves: FR-39 (tab switch preserves filters; Watching item moves to Holdings = appears in grid/dashboard, count updates); FR-40 (rating/coupon/yield/persisted; yield labeled manual); FR-41 (filter Rating AA returns only AA rows; sort maturity ascending; density persists); FR-43 (credit day missed -> alert card same day + bell badge increments; dismiss removes card but notification history keeps row); FR-44 (App Password masked after save and never re-displayed; Test Email with unconfigured SMTP -> named error banner, no crash; env SMTP_USER overrides stored value); FR-47 (reset DB requires typed confirm 'RESET'; backup produces downloadable .db); FR-49 (privacy ON masks every money cell on watchlist+settings; status bar counts = table row count).
sections: Purpose, D33/D34 traceability table (FR->decision), Settings security notes (local storage, masking, env override), Data model deltas (bonds: +rating TEXT, +rating_agency TEXT, +coupon_pct REAL, +expected_yield_pct REAL, +payout_cycle TEXT, +issuer_type TEXT, +secured INT, +watch_state TEXT CHECK IN ('holding','watching'); alert_prefs: SMTP + preference keys list; NO new tables), Offline constraints.

SELF-CHECK (run, report): PRD: ids == FR-38..49 exactly, decision_ids in {scoped D33, scoped D34}; SRS: same 12 ids, >=2 ACs each, functional, check_method set; both JSON parse.
REPORT: paths, FR list one-liners, self-check output.
