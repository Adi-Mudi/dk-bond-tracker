# Watchlist — Navigation & Flow (LOCKED 2026-11-25)

## Page structure (single continuous flow, no watch/held split)
1. App shell (static): brand bar → sticky `ADD FORM | LEDGER` tabs → content → bottom nav (Watchlist active) → FAB.
2. **Notifications first**: WATCHING + ALERTS stats → Rating Watch alert card.
3. **Add Bond form is HIDDEN on open** — it appears only after tapping FAB `+` (or the ADD FORM tab). First open = LEDGER tab + zeroed notifications + empty-ledger placeholder.
4. **Integrated ledger**: company-first cards mixing `[HELD]` rows (units/completed/ongoing/settled) and `[WATCH]` rows (broker/yield/Move) with counts; compare-brokers card for same-ISIN multi-broker yields.
5. **Move to Portfolio**: inline confirmation (qty, amount, date, broker ref) + Link-to-Goal (select existing → Update goals → return and continue).

## FAB `+` semantics (page-specific)
- Dashboard / Portfolio / Watchlist → **Add Bond form**
- Goals → **Goal form** (in design)

## Delete (watchlist only, buried)
Card → Details → overflow (⋮) → Remove (red) → type full ISIN + hold 2s → removed. Held positions are never deleted here. No front-facing delete button, ever.

## Back behavior
- System back from the Add Bond sheet → returns to ledger state (form closes, entries preserved).
- Goals detour (Update goals) → returns to Move-to-Portfolio with entries intact.
