# Watchlist — Design Notes & Feedback Fix Log (LOCKED 2026-11-25)

All rulings developer 2026-11-25, applied via Stitch edits only (D17), single-file same-name exports.

| # | Feedback | Fix applied |
|---|----------|-------------|
| 1 | Work only on the all-sections board | Single-page file deleted; board is the only deliverable |
| 2 | Show designs as one row multiple columns | 5-column board (form, ledger, move, remove, first-open) |
| 3 | ISIN duplicated | ISIN only in Quick Lookup; Identity shows read-only locked chip |
| 4 | Expected Yield = user input; rest auto | auto chips on fetch fields; user fields empty ("you enter") |
| 5 | Senior Secured Debenture confusing | relabeled "Secured" + helper (asset-backed senior claim) |
| 6 | Empty user fields, no suggestions; per-unit math | values empty; Value per unit (auto) = invested ÷ qty |
| 7 | Notification section to the top | WATCHING + ALERTS + Rating Watch above the form; AVG EXP YIELD removed |
| 8 | Multi-broker same-ISIN | broker chips per card + compare-brokers card (GoldenPi/Zerodha/Grip) |
| 9 | Move button too bright | secondary styling; accent reserved for values and Save/Confirm |
| 10 | Move form approved | unchanged (Q5 "really good") |
| 11 | Held positions confusing | integrated: company-first cards with nested [HELD]/[WATCH] ISIN rows |
| 12 | Duplicate ISIN must error | red ERR-watch-dup banner + guidance under the lookup |
| 13 | Default History field (background automation) | disabled field + COMING SOON chip; single default ISIN = HIGHER RISK |
| 14 | Broker suggestions | typeahead: GoldenPi, Grip Invest, IndiaBonds, Zerodha + free entry |
| 15 | App shell unclear | every frame: full shell + sticky ADD FORM/LEDGER tabs |
| 16 | Delete must be buried | Details → overflow → Remove → type ISIN + hold 2s (col04) |
| 17 | Goals link during move | LINK TO GOAL select + Update goals → return & continue; background allocation |
| 18 | Form must not show on open; FAB page-specific | form hidden until `+`; legend: Dashboard/Portfolio/Watchlist → Add Bond, Goals → Goal form |

Rejected/removed: AVG EXP YIELD stat, separate Held tab, single-page working file, prefilled field values, duplicate ISIN input, bright Move buttons, front-facing delete.
