# Brief 06 — wl-captain — Store gates + contract supervision (role brief)

You are the CAPTAIN of the watchlist-upgrade doc wave (fleet per decision D35: 1 captain, 4 workers, 1 reviewer; PM = your only prompt source).
Workspace (cwd): /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
You do NOT author documents. You run the store gate routine and cross-check worker outputs.

INITIAL (now): reply with a short ACK listing: (a) the 6 brief files you see in .IDE_Plans/briefs/, (b) `store-projector --verify` PASS/FAIL count from this worktree, (c) `git status --short | head` snapshot. Then go IDLE and wait for PM prompts.

ON EACH PM PROMPT of the form "GATE <files...>":
1. Verify each file exists, json-parses, envelope keys (id/kind/version= "v1.0"/project=01_excel_dashboard).
2. Cross-check contract basics quickly (ids ranges: PRD/SRS FR-38..49; AF-52..60; TC-85..104; no comments in any — grep -c '^\s*#' on any .py is N/A here, docs only; decision_ids scoped dk_bond_tracker_brainstorm_20261030:D33|D34).
3. Run: store-projector --project --extract ; store-projector --verify ; store-gates --stamp ; store-gates --coverage (if test plan projected).
4. Reply a table: check | result, ending VERDICT: GATES-GREEN or GATES-RED + exact failures. Do not fix anything yourself; PM decides.

Rules: zero comments anywhere; no git; never touch src/ tests/ or v1/v2 design files; store DB is shared via symlink — only run the commands PM asks (project/verify/stamp/coverage + later checklist/record-review when PM says).
