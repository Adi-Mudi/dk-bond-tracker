# Goals — Design Notes (LOCKED base2026-11-28 — supersedes2026-11-25 notes)

## Flow (navigation_flow)
Empty first open (GOALS 0) -> FAB + (full-screen page) or FORM tab opens the clean4-input form -> save -> list with progress cards -> Details: Saved so far, month-wise derivation table (auto invested/returns + accent totals row), linked bonds with total interest + chevron to bond detail, overflow Edit/Archive menu (no Remove). Back from form returns to list; Goal linking also available from Move to Portfolio (watchlist flow).

## Rulings applied (developer2026-11-28 — locked base)
1. Create form: EXACTLY4 inputs (name · start · end · amount ₹ monthly) — total months + target auto-computed.
2. Tracking is FULLY AUTOMATIC from portfolio activity (purchase dates → invested; bond interest → returns). Manual Record Check-in + Save draft REMOVED. Old failure counter / pace-adjustment banner / Upcoming Pipeline grid DROPPED (locked base is the single truth).
3. Derivation table ends with one static accent totals row; linked-bond rows show total interest received (not monthly) and open bond detail.
4. Empty-state-first; months signal = one signal (negative sticky); no target amounts on cards/detail.

## Research references
- Backend: src/goals.py (add_goal/list_goals), src/queries/summary.py goal_derived, src/views/goals.py routes.
- Locked base: frontend/confirmed/goals/goals_single_page_base.html (screen6e072293…).
