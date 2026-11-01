# Brief 32 — Review batch 22 (D41 patch wave gate)

You are the REVIEWER. REPORT ONLY — no edits. Reply only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Code: `../patch-d41` branch, HEAD 54bbafb, remote CI **SUCCESS** run 41249462103 (cite it). Diff vs dev: `git -C ../patch-d41 diff dev...HEAD --stat` then read changed files.
- Contracts: brainstorm `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` **D41** (full text + WHY = owner's Q1/Q2/Q3/Q5 + smoke/MCP evidence); `docs/PRD_DK_Bond_Tracker_addendum_v5.json` (FR-62..66), `docs/SRS_DK_Bond_Tracker_addendum_v5.json`, `docs/Atomic_Functions_addendum_v5.json` (AF-70..74), `docs/Test_Plan_addendum_v5.json` (TC-114..128). Plan briefs: `../patch-d41/.IDE_Plans/briefs/30_d41_patch.md`.
- PM evidence (verify, don't re-run): smoke on patch worktree = 4 tenure-0 surfaces 200, move same-month 400 (row untouched), Q1 0.00→302 on valid ISIN, negative/empty still 400.

## Checks (deep; cite file:line)

1. **FR-62 (00.00)**: shared validator accepts 0.00/0/0.0, rejects empty/non-numeric/negative with named errors; both watch + Add Position percent fields use it.
2. **FR-63 (labels)**: exact three strings on BOTH forms; no other label drift.
3. **FR-64 (guard)**: move AND add both validate tenure>=1 + credit bounds BEFORE any insert (trace the code path; zero-write on rejection); error message shape named.
4. **FR-65 (recovery)**: per-row catch ONLY at display boundaries — engine derive_health/grid_model raise paths NOT weakened (no swallowed exceptions in src/engine.py); surfaces 200 with Invalid chip; Remove route revalidates server-side (valid row → 400, invalid → delete); tc25/tc86 retargets preserve the test intent (named error surfacing still covered where in scope).
5. **FR-66 (broker)**: PRAGMA-guarded column add (idempotent migration), persists across insert/move/keep-on-empty-move, watchlist column before Source note, holdings stays 9 columns, drawer shows it; empty-string handling sane.
6. **Hygiene**: no new deps, no comments, no banned tokens (Paisalo|Muthoottu|INE101Q|xlsm), no db-store/database git touches, Test_Plan v5 bindings cover FR-62..66 (coverage gate green evidence: store-gates SATISFIED).

## Out of scope
Old v4 docs, design v5 visuals, style nitpicks, performance.

## FINDINGS (max 5)
`F-22x: [CRITICAL|MAJOR|MINOR] <title> — <file:line> — verdict FIX/PASS`. End with exactly: `VERDICT: AGREED` or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`.
