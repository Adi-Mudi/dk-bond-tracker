# Brief 41 — Review batch 25 (GATE 3: stage-12 IMPLEMENTATION)

You are the REVIEWER (flat). REPORT ONLY — no edits, NO local pytest (cite remote CI runs). Reply only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Code: `execute-v6` branch, HEAD after the two lane merges (remote CI **success** run 41296709273; lane runs: phase-payouts 41296258485 success, phase-dash 41296479444 success, spine 41291148132 success). Diff base: `git -C execute-v6 diff dev...HEAD --stat` then read changed files.
- Contracts: plan `../.IDE_Plans/dk_bond_tracker_watchlist_stage12_impl_plan_20261031_v1.1.json` (P1-P3 tasks + REVIEWER-CHECK lines = primary baseline); PRD/SRS v6 (FR-67..74), Arch v3, AF/Pseudo v6, Test_Plan v6 (TC-129..139); locked design `fix-watchlist/.IDE_Plans/design_drafts/ui_frontend_design_v6.html` @7b67f54; D43 in `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json`.
- Prior findings (do not reopen): batch 17-24 + F-185/191/192/221..227/241..244 in the review log.

## Checks (deep CODE review; cite file:line)

1. **P1 (T1.1-T1.3)**: no status list ordered by company except watchlist; ONE shared sort key (HEALTH_ORDER in engine only — no duplicate constants); credit_day CHECK 1..31 + idempotent migration preserved (spot the migration copy-proof requirement is honored in code).
2. **P2 (T2.1-T2.3)**: payout editor posts ONLY to the existing payment route (no new tables — grep CREATE TABLE = zero beyond base); save triggers read-time re-derive (no stored health writes); months elapsed+current only newest-left; FR-69 parity byte-equal across candidate Details → move → holdings strip; TC-129/130/133/137 exist and are coherent.
3. **P3 (T3.1-T3.4)**: tabs scoped JS (no cross-view desync); filter preserves shared order; returns aggregation = per-row guarded (corrupt row → 200, proven by tc25/tc86 green); cumulative latest == Received card math; goals #returns switches view+tab; email presets exact values (PRD FR-72); test route NEVER 500; tc45 centralization (no aggregate SQL outside queries.py); TC-131/132/134-136 exist.
4. **Owner rules**: Q3 remote-only (no local pytest evidence anywhere: greps/pane claims), Q4 zero new deps (requirements.txt untouched), D43 taxonomy/captions, banned tokens zero across all changed files, no db-store/data/bonds.db writes (git status clean of them).
5. **Merge integrity**: theme.css union resolution kept BOTH lanes' CSS (lane A .rupee + lane B filters/setup-guide/banners); no lost lane features.

## Out of scope
Pre-existing out-of-scope notes already reported (status.py TEXT-amount crash), docs content, style.

## FINDINGS (max 5)
`F-25x: [CRITICAL|MAJOR|MINOR] <title> — <file:line> — verdict FIX/PASS`. End exactly: `VERDICT: AGREED` or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`.
