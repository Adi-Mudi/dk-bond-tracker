# Portfolio — Research References (LOCKed package)

## UI pattern research (applied to header/controls)
- Material Design 3 — Chips guidelines: inline single-row chip sets, horizontal scroll on compact, 48dp targets, concise labels. https://m3.material.io/components/chips/guidelines
- Material Design 3 — compact breakpoints (<600dp): content-first; lists over cards; whole-chip tap targets. https://m3.material.io/foundations/layout/applying-layout
- Material Design 3 — small top app bar pattern for content-first screens (used for the compressed 3-row header). https://m3.material.io/components/top-app-bars
- Source captured during design 2026-11-24 (Brave search, M3 results).

## Backend logic researched (design mirrors code)
- `src/status.py` — bond statuses: `Danger` (past unpaid month OR credit-day overdue), `On-going`, `Completed` (matured); `compute_row_status_daywise`.
- `src/queries/grid.py` — cashflow cell states: `paid` / `due` / `future`; **amount carried only when state == paid** (`amount = … if state == "paid" else None`) — the basis for "no due amounts" rule.
- `src/queries/detail.py` — `_month_state`: paid+amount>0 → paid; due passed → unpaid (no amount); else soon.
- `src/engine.py` — `sort_rows` urgency ordering (Danger → On-going → Matured).
- `src/print.py` — status marks Danger/On-going/Completed/Invalid.
- `frontend/confirmed/dashboard/DESIGN.md` — status chip colors: Paid `#6FD898/#12301E`, Due `#FF8A80/#3A1310`, Watching `#8FB4FF/#14263D`; emphasis rule (terminal states dim); status priority order.

## Stitch sources (locked screens)
- Holdings: screen `1e13609e9940410b88951aa03ebc1dbc` (project `17110477162175329772`)
- Payout matrix: screen `53cab5093200438a88e7d55b01d65654`
- Edit chain history recorded in `portfolio_design_notes.md`; exports are HTML-only per developer rule.
