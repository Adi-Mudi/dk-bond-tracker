# Brief 15 — wl-review — REVIEW BATCH 16 (read-only; REVIEW-LOCK is ON)

You are the READ-ONLY reviewer. You NEVER edit files. Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
The lock record is in the base checkout: ../.IDE_Plans/dk_bond_tracker_review_log.jsonl (batch 16 entry). Findings must cite evidence (file+field/section).

SCOPE (check pairs only; out-of-scope = anything not named):
A. DECISION FIDELITY — decisions D33-D37 in ../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json vs the document set:
   docs/PRD_DK_Bond_Tracker_addendum_v3.json, docs/SRS_DK_Bond_Tracker_addendum_v3.json, docs/Watchlist_Architecture_Addendum_v1.json, docs/Atomic_Functions_addendum_v3.json, docs/Pseudocode_addendum_v3.json, docs/Test_Plan_addendum_v3.json, docs/Development_Order_addendum_v3.json, .IDE_Plans/design_drafts/watchlist_standalone_mockup_v2.html.
   Verify: D33 two-view+fields+alerts present; D34 Settings sections (SMTP masked/env-override/typed RESET) present; D37 = NO import/xlsm anywhere in these 9 (grep import excel|xlsm|--import), start-from-scratch wording, L1-retired vs L2-still-open consistency with docs/Format_Retirement_Addendum_v1.json.
B. RETIREMENT REGISTER — docs/Format_Retirement_Addendum_v1.json: every retired id (FR-08/10, AF-02..09, import TCs, L1, W1 portion) has a valid replacement listed; no contradiction with active docs (FR-38..49 untouched by retirements).
C. ZERO-USER-DATA PROOF — run your own scan (grep) over ALL of: docs/*.json, design/*.json, design/*.html, .IDE_Plans/design_drafts/* for tokens: Paisalo Muthoottu Navi INDEL KRAZYBEE AKARA ARMAN UNIFINZ KEERTANA SPANDANA KANAKADURGA Monedo DAR CREDIT INE420C07130 INE101Q07BS1 1037142.01 111638.57 56227.88 39588 10063 (EXCLUDE: docs/PRD_DK_Bond_Tracker.json + docs/brainstorm-currently-*.json = known redacted-stub/branch-lag pair). Expected: ZERO hits (scan was clean pre-lock; confirm independently).
D. CODE-GAP LIST vs src/ (expected absences = implementation pending your approval): /settings route, watch_state/rating/coupon columns, move_to_holdings, maturity-scan, filters engine, import_xlsm module (retirement says remove at implementation). List each with file evidence; flag any UNEXPECTED gap/conflict (something docs claim that CONTRADICTS existing code behavior — e.g. a route/column that exists but differs).
E. FINAL-DESIGN READINESS — mockup v2: sections (8 screens + Settings), no real data, v1 also clean; declare whether the package is ready for owner approval.

REPORT FORMAT (strict): numbered findings F65+ [CRITICAL|MAJOR|MINOR] <evidence file:field> <PASS|FIX> — re-reports of already-logged F-ids must reference them instead of reopening. End with exactly one line: VERDICT: AGREED (only if zero CRITICAL/MAJOR) or VERDICT: BLOCKED.
