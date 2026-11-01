# Batch 26 brief — post-merge review (stage 12 close gate)

You are reviewer `wl-rev26`. Report ONLY — never edit files.

## Scope (exactly these — anything else is out of bounds)

1. **Merge integrity**: root repo `dev` at merge commit of `execute-v6` (verify `git log --oneline -3` in root). Confirm the merge brought: attribute_facts.html, tests tc138/tc139, watch.html move-panel rename, app.js dashboard tabs, theme.css union (lane A `.rupee` + lane B filter-chips/setup-guide/banners — both present in `src/static/theme.css`).
2. **CI evidence**: `gh run list --branch dev --limit 2` — the stage-12 merge push run must be `success`. Cite run id.
3. **Containment**: `git status --porcelain` in root, `fix-watchlist`, `execute-v6` — no `data/bonds.db`, no `db-store/` modifications anywhere.
4. **F-245 fix verification**: `src/templates/watch.html` — row id is `move-panel-<id>` (line ~159), both `data-panel` attrs (toggle ~154, cancel ~184) say `move-panel-`, submit button keeps `id="move-<id>"` (~183, now unique), and `tests/test_tc138_payouts_parity.py` asserts match (regex + `html.index` + data-panel).
5. **Q3/Q4 spot checks** (from plan v1.1 reviewer-check):
   - No stored-health writes added: grep `UPDATE bonds SET status` outside pre-existing dev code.
   - `credit_day` CHECK 1..31 + PRAGMA-guarded rebuild migration still present (`src/db.py`).
   - Banned tokens zero hits on `git diff dev~1..HEAD` (Paisalo|Muthoottu|INDEL|KRAZYBEE|Home Plan|execute-v5).
   - `requirements.txt` untouched vs dev~1.
6. **Local-run sanity**: `python3 -m py_compile src/app.py src/engine.py src/queries.py src/db.py` from root — report pass/fail. NO pytest locally.

## Out of scope
- Style nitpicks, docs wave content (already gated), plan v1.1 wording, any file not named above.
- No re-opening of batch 25 findings (F-245 was fixed; verify only its presence as in item 4).

## Output format
```
F-261: [SEVERITY] … evidence: file:line / run id — verdict: AGREED|BLOCKED
F-262: …
VERDICT: AGREED|BLOCKED: n
```
AGREED requires zero CRITICAL/MAJOR. MINORs are non-blocking but must be listed.
