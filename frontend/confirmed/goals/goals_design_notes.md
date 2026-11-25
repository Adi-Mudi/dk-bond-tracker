# Goals — Design Notes (LOCKED 2026-11-25)

## Flow (navigation_flow)
Empty first open (GOALS 0) -> FAB + or Create button opens the FORM (same-file, hidden until then) -> save -> list with progress cards -> Details: check-ins strip (auto + manual fallback), linked bonds (goal_derived), overflow guarded delete. Back from form returns to list; Goal linking also available from Move to Portfolio (watchlist flow).

## Rulings applied (developer 2026-11-25)
1. Monthly plan: invest target auto-computed (monthly x months) — no manual target math.
2. Tracking is FULLY AUTOMATIC from portfolio activity; months with no investment show RED MISSED errors + failure counter (example: 2 months missed).
3. Order: current month first then next; goals by soonest end-date, completed dim last.
4. Empty-state-first; all-sections board format; 4-tier/status colors per DESIGN.md.

## Research references
- Backend: src/goals.py (add_goal/list_goals/set_checkin, months_until/between), src/queries/summary.py goal_derived, src/views/goals.py routes.
- M3 progress/empty-state patterns; handoff research (storyflow/desisle) for states layer.
