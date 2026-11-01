# Brief 21 — Review batch 18 (GATE 2: stage-11 execution plan)

You are the REVIEWER for gate 2. REPORT ONLY — never edit any file. Reply with only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Plan under review: `../.IDE_Plans/dk_bond_tracker_watchlist_stage11_execute_plan_20261031_v1.0.json` (v1.0) — this is the plan baseline; its FROM/TO items and REVIEWER-CHECK lines are your primary targets.
- `../.IDE_Plans/dk_bond_tracker_watchlist_master_20261030_2355_v1.1.json` — stage 11 entry, owner constraints, scope.
- `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — D38/D39/D40 only (v2.3.1).
- Read-only design/pdoc truth (spot references): `docs/PRD_DK_Bond_Tracker_addendum_v4.json` (FR-50..61), `docs/Watchlist_Architecture_Addendum_v2.json`, `.IDE_Plans/design_drafts/ui_frontend_design_v5.html`.
- Existing code context: `src/app.py`, `src/` layout, `tests/` inventory (read-only).

## Checks (every finding cites file+section or line)

1. **Owner-constraint fidelity (Q1-Q4):** plan executes ONLY locked design v5 content — no invented features beyond PRD FR-50..61; ALL test blocks are REMOTE (no LOCAL test tiers); architecture = existing Flask+vanilla+SQLite pattern with "no new deps" respected; 1 captain + 3 workers exactly.
2. **Seam checks (skill §9):** master stage 11 ↔ plan link matches the actual filename; plan scope == stage scope (nothing extra/missing); brainstorm D38/D39/D40 clauses covered by tasks (restructure, labels, lock, themes, watchlist whitelist, day-wise alerts, empty default).
3. **Plan-structure (Rule 5):** phases have modes SERIES/PARALLEL; every task has action/FROM/TO/Reason/Status; every phase has a test block + REVIEWER-CHECK line; worktree block names one base branch, folder==branch, containment rules, db-store untouched.
4. **P0 dead-tests task:** exactly the 5 workbook-orphaned files named; no other test deletions allowed.
5. **Internal contradictions:** e.g. parallel lanes sharing files, merge order vs branches, remote gate vs any implied local run.

## Out of scope

Code style, the v3/v4 docs' own content, design v5's visual choices (approved), naming taste, anything not named above.

## FINDINGS format (strict)

`F-18x: [CRITICAL|MAJOR|MINOR] <title> — <evidence file:section> — verdict FIX/PASS`. End with exactly one line: `VERDICT: AGREED` (zero CRITICAL/MAJOR in scope) or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`. Max 5 findings. No free-form commentary.
