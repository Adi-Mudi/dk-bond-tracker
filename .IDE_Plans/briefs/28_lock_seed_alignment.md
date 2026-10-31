# Brief 28 — Lock unification test alignment (F-191 fix round)

Worker: wl-lock. Cwd = `execute-v5`. NO git writes (PM commits+pushes). NO pytest (remote-only; py_compile + venv test-client smoke allowed like brief 26). Reply only the REPORT section.

## What PM already changed (do NOT touch src/ except conftest note below)

- `validators.active_position_lock(conn, company, isin)` is now a thin delegator to `lock.check_add_allowed(company, isin, conn)` — ONE shared implementation for both entries (F-191). check_add_allowed: holdings-partition + DERIVED health via engine.derive_health (Matured when end<=today or all window paid; Danger when any due month unpaid and credit day passed; else On-going), raises AppError "Cannot add position: {company} has an active position ({health})".
- `app.py` move-handler arg order fixed.

## Your job: make the lock TESTS green against the shared derived-health routine

1. **tests/conftest.py** — append three helpers (no comments, match existing helper style; `add_bond` already takes credit_day/status params; `add_payment` exists; month iteration can import month_key/add_months from src.status / src.validators as other tests do):
   - `add_danger_seed(conn, company, isin)`: start = today minus 40 days, tenure 60, credit_day=1, NO payments, status="Danger". Returns bond id. (Derived: prior-month due passed unpaid -> Danger, any run date.)
   - `add_ongoing_seed(conn, company, isin)`: start = today minus 10 days, tenure 60, credit_day=28, status="On-going"; then add_payment for EVERY month_key from start through the CURRENT month inclusive (1-3 payments, amount 1000.0). Returns bond id. (Derived: end future, all due paid -> On-going, any run date.)
   - `add_matured_seed(conn, company, isin)`: start = "2025-01-01", tenure 12, status="Completed", no payments. Returns bond id. (Derived: end <= today -> Matured.)
2. **Convert seeds** in these six files ONLY (keep every assertion exactly as written — messages/status strings already match derived outputs; only the SEED setup changes):
   - tests/test_tc60_lock_name.py, test_tc61_lock_isin.py, test_tc62_lock_both_keys.py, test_tc65_lock_message.py: any `add_bond(..., status="On-going")` used to trigger a BLOCK -> `add_ongoing_seed(...)`; `status="Danger"` blocker -> `add_danger_seed(...)`; `status="Completed"` (expects allowed/None) -> `add_matured_seed(...)`. Preserve companies/ISINs/whitespace-case variants exactly (they test normalization).
   - tests/test_tc66_no_override.py + test_tc67_blocked_add.py: `seed_active_beta_finance(db_path)` helpers — they open their own conn; convert their internal add_bond blocker to `add_ongoing_seed` (import from conftest). tc67's BLOCKED_FORM POSTs to /add -> needs the seeded row to derive-block -> ongoing seed.
   - If a seed's company/ISIN/case-variant pattern appears in BOTH seed and assertions, change ONLY the seed call.
3. Sanity (paste): py_compile all touched files; then a venv test-client smoke (no pytest): build a temp DB, add_danger_seed -> POST /add same company -> expect 409 + message containing "(Danger)"; add_ongoing_seed -> POST -> 409 "(On-going)"; add_matured_seed -> POST -> allowed (not 409); direct active_position_lock returns None for allowed case. Also `grep -rn "status=\"Completed\"" tests/test_tc6*.py` list what remains (expected: only intentional matured seeds).

## Boundaries

Do NOT touch: src/* (except nothing), any test outside the six named, engine/lock/validators semantics, messages/assertions. No new dependencies, no comments.

## REPORT

Files+bytes, per-file seed conversion count, smoke outputs, remaining status= list, one-line summary. BLOCK with reason if any assertion's intent cannot hold under derived health.
