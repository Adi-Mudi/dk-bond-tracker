# Brief 20 — Review batch 17 (doc wave D38/D39/D40 + design v5)

You are the REVIEWER for batch 17. REPORT ONLY — never edit any file. Reply with only the FINDINGS section.

## Frozen scope (REVIEW-LOCK: ON while you run)

The following artifacts are frozen for review. Nothing else is in scope.

1. `docs/PRD_DK_Bond_Tracker_addendum_v4.json` + `docs/SRS_DK_Bond_Tracker_addendum_v4.json`
2. `docs/Atomic_Functions_addendum_v4.json` + `docs/Pseudocode_addendum_v4.json` + `docs/Test_Plan_addendum_v4.json` + `docs/Development_Order_addendum_v4.json`
3. `docs/Watchlist_Architecture_Addendum_v2.json`
4. `.IDE_Plans/design_drafts/ui_frontend_design_v5.html`
5. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — only D38/D39/D40 + version/change_log/revision_history v2.3.0 entries

## Baseline (what the docs MUST match)

- D38, D39, D40 full text in the brainstorm (v2.3.0) — the requirement truth.
- Briefs `.IDE_Plans/briefs/18a_prd_srs_v4.md`, `18b_af_pseudo_tests_arch_v4.md`, `19_html_themes_v5.md` — the contracts the writers executed.
- PRD/SRS/AF/Pseudo/TestPlan/DevOrder addenda **v3** and Watchlist_Architecture **v1** — for the extends-chain and "no legacy FR altered" claims.
- Approved design v4 (`.IDE_Plans/design_drafts/ui_frontend_design_v4.html`) — v5 must be v4 content + theme system only.

## Checks (each finding must cite file + section/line)

1. **Brainstorm-vs-docs**: every D38/D39/D40 clause appears correctly in the docs (Portfolio rename, My Holdings/Payouts tabs, Watchlist whitelist, Move-to-Portfolio + D15 lock incl. re-buy-after-Matured, Received/Matured display labels, Watching/Held + On-going/Danger/Matured status model, credit-day tenure form, themes System/Light/Dark with persistence + zero-flash).
2. **Plan-vs-actual / internal consistency**: extends chains correct; Change Record supersede statements accurate; new id ranges (FR-50+, AF after v3 max, TC after v3 max, SR continuation) — NO declaration duplicates across the doc family (`"id": "X"` appearing in 2+ files); cross-references (FR↔AF↔TC) resolve to ids that exist somewhere in the family.
3. **Legacy hygiene**: no banned real data (Paisalo, Muthoottu, INDEL, KRAZYBEE, 1037142, 56227, real ISINs INE420C/INE101Q/...); legacy labels (Returned/Completed/Month Grid) appear ONLY inside rename/supersede sentences, never as an active requirement or UI string.
4. **HTML v5**: contains the 3-way theme switcher + Appearance settings + localStorage persistence; carries ALL v4 content (spot-check: 8 holdings rows, payouts sort caption, watchlist whitelist, legend, Add Position form); zero external URLs; zero banned tokens.
5. **JSON validity**: all 7 docs parse.

## Out of scope (do not report)

Style/naming nitpicks, old v3 docs' content, code/test execution, wording preferences, anything not named above.

## FINDINGS format (strict)

Numbered findings, each: `F-17x: [CRITICAL|MAJOR|MINOR] <title> — <evidence file:section> — verdict FIX/PASS`. End with one line: `VERDICT: AGREED` (zero CRITICAL/MAJOR inside scope) or `VERDICT: BLOCKED: <count> CRITICAL/MAJOR`. No free-form commentary. If everything passes: `No findings.` + verdict line.
