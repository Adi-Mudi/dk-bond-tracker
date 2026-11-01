# Brief 36a — PRD + SRS addendum v6 (D42/D43 implementation round)

Worker: wl-doc-a. Cwd = fix-watchlist. NO git. No local pytest. One deliverable pair + REPORT.

## Truth (read fully)
1. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — **D41, D42, D43** (D43 = LOCKED sort standard + status taxonomy + automatic Danger rule; D42 = v6 feature scope; D41 = prior patch wave).
2. LOCKED design: `.IDE_Plans/design_drafts/ui_frontend_design_v6.html` @ 7b67f54 — the ONLY visual truth (payouts Nov/Oct newest-first, inline move panel, attribute parity, dashboard tabs+filters, email presets, returns history definitions).
3. Templates: `docs/PRD_DK_Bond_Tracker_addendum_v5.json`, `docs/SRS_DK_Bond_Tracker_addendum_v5.json` (continue FR ids after **FR-66**; same shapes).

## Deliverables
1. `docs/PRD_DK_Bond_Tracker_addendum_v6.json` (extends v5) — FR-67+ (one per cluster, cite D-numbers):
   - FR-67: Payouts cells editable inline (click cell -> amount + received flag + Save via existing payment route); statuses re-derive immediately (D42).
   - FR-68: Payout months = elapsed + current ONLY, newest left (D42; F-231 lesson); future never rendered.
   - FR-69: Attribute parity — Add Candidate collects rating agency/issuer type/secured/face value/payout cycle/invested/broker; identical attributes visible in Watchlist Details grid AND My Holdings attribute strip (D42).
   - FR-70: Dashboard status chips + filter + Danger-first order (D42) — subset of D43.
   - FR-71: **D43 app-wide sort standard**: Danger -> On-going -> Completed/Matured on EVERY list (dashboard, holdings, payouts, exports, print, alerts) + status taxonomy purposes + automatic Danger rule (due date passed with no entry -> same-day Danger).
   - FR-72: Email presets Gmail/Outlook/Custom autofill + setup guide + Send test email + troubleshooting (D42; values: smtp.gmail.com 587 TLS/465 SSL app-password-only, smtp.office365.com 587 STARTTLS).
   - FR-73: Returns history as Dashboard TAB: Month / Interest received / Positions paid·pending (of active) / Cumulative running total; newest first; Goals KPI strip links to it (D42 + owner Q1.1 definitions verbatim-ish).
   - FR-74: Move-to-Portfolio inline expansion panel with labeled fields (D42).
2. `docs/SRS_DK_Bond_Tracker_addendum_v6.json` (extends v5) — verifiable ACs per FR above. MUST include F-233 implementation cautions as requirements: (a) credit_day storage CHECK must migrate 1..28 -> 1..31 (D41 owner rule) or inserts of 31 fail; (b) Goals #returns link switches view AND activates the Returns tab; (c) watchlist candidate whitelist/entry form extends to the D42 attribute set (supersedes arch-v2 whitelist text).

## Self-check (paste)
JSON parse both; declaration-level FR dup-grep empty across PRD family + SRS family; banned grep (Paisalo|Muthoottu|INE101Q|xlsm) empty; D41/D42/D43 counts >=3 each per file.

## REPORT: files+bytes, FR range, self-check outputs, one-line summary. BLOCK on ambiguity.
