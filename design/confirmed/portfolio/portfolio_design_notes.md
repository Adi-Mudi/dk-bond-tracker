# Portfolio — Design Notes & Feedback Fix Log (LOCKED 2026-11-24)

All decisions below are developer rulings from 2026-11-24, applied via Stitch MCP edits only (D17), same-filename in-place exports (R2).

| # | Feedback | Fix applied |
|---|----------|-------------|
| 1 | Two marked rows too tall | Sub-tabs + rating chips + search/sort controls merged into ONE single control row |
| 2 | Wide dropdowns → icons | Frequency/sort/accrued became compact icon cluster (filter/search/sort 32px, mist) |
| 3 | "Portfolio" in two places confusing | Body title + subtitle removed; app bar shows brand; bottom nav is the only page name |
| 4 | No live feed exists | `FEED: LIVE SYNC` badge removed; sync icon added to app-bar static zone (sync, bell, avatar) |
| 5 | Header eating the screen | 5 stacked rows compressed to 3; M3 small-top-app-bar pattern (researched) |
| 6 | Section tabs must be static | HOLDINGS / PAYOUT DETAILS bar made sticky |
| 7 | Payout content confusing, run-rate/TDS not accepted | Embedded PAYOUT DETAILS VIEW (grouped list + summaries) REJECTED and fully removed |
| 8 | Payout = matrix like reference, fully populated | Cashflow matrix built: issuer rows × month cells, real amounts/pills, footer totals |
| 9 | Due amounts unknown (user enters paid manually) | Amounts only in paid cells — mirrors `src/queries/grid.py` |
| 10 | Status marking | Backend statuses per issuer: Danger top (fully red) → On-going middle → Matured last (dim), from `src/status.py` |
| 11 | Totals unreachable at bottom with many bonds | MONTHLY TOTAL INFLOW row moved to TOP (under headers) |
| 12 | Scroll hint not needed | "Scroll matrix horizontally for timeline" removed |
| 13 | Scheduled dates wanted like Due | Sched pills carry dates (`Sched Nov 18` …) |
| 14 | Card order | NEXT PAYOUT: status pill BEFORE date |
| 15 | Platform | Android-only after this phase; this package is the mobile deliverable |

Rejected/superseded: embedded payout view, FEED badge, body page title, scroll hint, wide dropdown filters, PNG exports (HTML only).
