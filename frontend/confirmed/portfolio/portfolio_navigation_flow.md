# Portfolio — Navigation & Flow (LOCKED 2026-11-24, Android/mobile)

## Section switch
- Two sections on one page: **HOLDINGS** (default) | **PAYOUT DETAILS**.
- Switch = segmented section-tab bar directly under the app bar; bar is **static/sticky** — cards and matrix scroll beneath it.
- Payout is a SEPARATE view (cashflow matrix), never embedded inside holdings. The old embedded "PAYOUT DETAILS VIEW" block was rejected and removed.

## Holdings view
1. App bar (static): brand `DK Bond Tracker` left; sync, bell, avatar right. No page title in body — bottom nav is the only page name.
2. Sticky section tabs.
3. Dim compact control row: horizontally scrollable status chips (All / Active Accruing / Maturing-Redeemed) + trailing filter/search/sort icons + `Showing n of N`.
4. Card list, ordered **Danger → On-going → Matured** (backend `compute_row_status_daywise`); Danger = red left border + red tint; Matured = dim/low-emphasis.
5. Card NEXT PAYOUT area: **status pill FIRST, then date**.
6. FAB (56px, `#2456E6`, right 16 / bottom 104) = Add Bond; bottom nav 5 items with Portfolio active.

## Payout Details view (cashflow matrix)
1. Header strip: `Cashflow Matrix` + instruments chip + Active Reference note.
2. **MONTHLY TOTAL INFLOW row sits directly under column headers** (top — bottom unreachable with many bonds).
3. Month columns LTR: **current month first/left (highlighted) → future ascending → older to the right**.
4. Sticky issuer column; horizontally scrollable month columns (no scroll-hint caption).
5. Cells: amount ONLY in paid cells (green); due = red pill with date, NO amount; sched = blue pill with date, NO amount (backend `queries/grid.py`: amount present iff state=paid).
6. Per-issuer status pills: Danger (top) / On-going (middle) / Matured (dim, last).

## Back behavior
- System back from Payout Details returns to Holdings (same page, tab state).
- Bottom nav route unchanged (Portfolio).
