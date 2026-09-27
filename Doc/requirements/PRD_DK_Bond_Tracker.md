---
artifact: PRD
project: DK_Bond_Tracker
version: 1.0.0
status: draft
stage: drafting-prd
run: 2026-09-27T13-04--currently-the-data-is-stored-in
created: 2026-09-27T14:57:14.607Z
updated: 2026-09-27T14:57:14.607Z
documentType: product-software-requirements
profile: basic
profileVersion: 1.0.0
mission: "Currently, the data is stored in an XLSM workbook. I am considering migrating it to a SQLite database with a lightweight front end. My main goal is to have a solution that is easy to maintain, scalable as the data grows, and simple to work with in the future. What would be your recommendation? Which approach would be the most practical and user-friendly?"
projectName: DK_Bond_Tracker
---

# Product and Software Requirements Specification — DK_Bond_Tracker

## 1. Objective

Replace the macro-enabled Excel bond tracker (`v5.5_40L_Project_Tracker.xlsm`) with a full rebuild: a local SQLite database plus a lightweight Flask web UI that reproduces all current behavior (payment ledger, live dashboard, status engine, CSV export) while fixing the Excel/VBA quirks, runs fully offline on any desktop OS, and stays easy to maintain as the data grows.

## 2. Problem

The current bond tracker is a mini-application trapped inside an XLSM file: VBA rebuilds the dashboard on every open/save (blocking MsgBox), month headers are hardcoded Sep-2025..Feb-2027, the month scan stops at Jan-2031, "Danger" checks only the previous month, errors are silently swallowed by `On Error Resume Next`, and the dashboard is a stale static snapshot between saves. Sharing means sending the whole workbook, and any export to CSV/xlsx loses all behavior. The owner wants an offline, lightweight, shareable, maintainable solution that scales as the portfolio grows.

## 3. System Actors

1. **Primary — Owner (Adi-Mudi):** tracks 15 bonds, records monthly payments, reads the dashboard, exports CSV.
2. **Secondary — Friends (peer users):** receive a copy of the app and run it on their own machines with their own local database; no cloud or accounts.
3. **Tertiary — Spreadsheet/CSV consumers:** people who receive exported CSV files for sharing/printing (read-only, outside the system).

## 4. User Stories

| ID | Actor | Story | Source | Status |
|---|---|---|---|---|
| US-01 | Owner | As a user, I keep all data offline on my own system with no cloud/accounts, so I stay in full control. | FR-01 | proposed |
| US-02 | Friend | As a friend receiving the app, I run it with Flask and a browser on any OS with no build step. | FR-02 | proposed |
| US-03 | Owner | As the owner, I see which completed bonds freed their principal so I can reinvest it. | FR-17 | proposed |
| US-04 | Owner | As the owner, I export data to CSV for sharing/printing since Excel is no longer the front end. | FR-07 | proposed |
| US-05 | Owner | As the owner, I view a live dashboard (totals, status counts, this-month returns, 83-month history) without opening Excel. | FR-05 | proposed |

## 5. Scope

**In-scope:** local SQLite schema (bond master, payment ledger, home plan); Flask local web UI with Excel-like month grid; one-time XLSM import; live dashboard queries; fixed status engine; CSV export; quirk fixes from the Excel analysis; owner wish-list features staged in later phases.

**Out-of-scope:** cloud sync, accounts/authentication, mobile apps, network multi-user mode, real-time market data, replacing Excel files retroactively beyond the one-time import (Excel stays read-only backup).

## 6. MVP

### MVP Goal

A friend can copy one folder to their machine, run a single launch command, import the existing XLSM (or start empty), record payments in a month grid, and see a live dashboard with correct statuses and CSV export — with Excel no longer required for any daily operation.

### MVP Users

The owner first; then friends running the same folder on their own machines with their own local DB file.

### MVP Requirements

- FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, FR-10, FR-17, FR-18, FR-19, FR-20, FR-21, FR-24

### Explicitly Not in MVP

- Home Plan schedule reproduction (FR-12, Phase 3)
- Watch-list analytics formulas (FR-11, Phase 3)
- Discount / TDS / quarterly-yearly payouts / P&L dashboard (FR-13..FR-16, Phase 4)
- Duplicate-ISN validation hardening and schema decoupling polish (FR-22, FR-23, Phase 2)

### MVP Exit Criteria

Import reconciles exactly (15 bonds, Total Investment 1037142.01, Total Till Return 111638.57, Total Balance -925503.44), dashboard reflects edits without any open/save event, every FR-01..FR-24 Phase-1 acceptance test passes, and a clean machine reaches a working dashboard within 1 minute using one documented command.

## 7. Success Metrics

| ID | Metric | Target | Measurement | Status |
|---|---|---|---|---|
| SM-01 | Import reconciliation | 15 bonds; totals 1037142.01 / 111638.57 / -925503.44 exact | Compare import result vs Excel-derived figures | proposed |
| SM-02 | Dashboard freshness | 0 open/save events needed to reflect latest entry | Manual test: edit payment, reload view | proposed |
| SM-03 | Status correctness | All unpaid past months flagged Danger; Completed overrides; zero = unpaid | Fixture portfolio with seeded gaps | proposed |
| SM-04 | No window limits | Bond starting Feb-2031+ gets correct status and grid rendering | Seed bond with start month ≥ Feb-2031 | proposed |

## 8. Phases

### Phase 0 — Foundation

#### Goal
Project skeleton, Python/Flask/SQLite dependencies, test harness, XLSM parser spike (HF-05).

#### Requirements
None (prerequisite only; no FR ids).

#### Acceptance Criteria
App skeleton boots; parser spike reads the real XLSM sheets.

#### Dependencies
Python 3.14 venv; oletools/openpyxl available for parsing.

#### Risks
Formula-vs-static-value mix in sheets (Home Plan) complicates parsing.

#### Out of Scope
Any requirement rows.

### Phase 1 — MVP

#### Goal
Complete Excel replacement: schema, ledger, import, grid UI, fixed status engine, live dashboard, CSV export, quirk fixes, error surfacing, reinvestment free-up.

#### Requirements
FR-01, FR-02, FR-03, FR-04 (incl. color rules), FR-05, FR-06, FR-07, FR-08, FR-09, FR-10, FR-17, FR-18, FR-19, FR-20, FR-21, FR-24.

#### Acceptance Criteria
MVP Exit Criteria (§6) all met.

#### Dependencies
Phase 0; original XLSM available as import source.

#### Risks
Import parity with VBA-derived values; status-rule differences vs old behavior must be clearly communicated.

#### Out of Scope
Home Plan, watch-list analytics, discount/TDS/payout-cycle/P&L features.

### Phase 2 — Essential improvements

#### Goal
Robustness: error surfacing polish, duplicate-ISIN validation, schema decoupling.

#### Requirements
FR-22, FR-23; ERR-03, ERR-04.

#### Acceptance Criteria
Duplicate ISN flagged across full bond set; no header-text/position coupling remains; unresolvable current month yields explicit message.

#### Dependencies
Phase 1 schema.

#### Risks
None significant.

#### Out of Scope
New analytics features.

### Phase 3 — Advanced features

#### Goal
Home Plan savings schedule and watch-list analytics reproduction.

#### Requirements
FR-11, FR-12; DATA-03, DATA-04 consumption; ERR-06.

#### Acceptance Criteria
Home Plan reproduces incl. irregular savings (39588, 10063, 0); watch-list formulas (discount, TDS, per-month, qty TL) match Excel outputs.

#### Dependencies
Phase 1 import (fields already landed in DATA-03/04).

#### Risks
Formula/static mix in Home Plan — stored values must be preserved.

#### Out of Scope
Owner wish-list items not yet delivered.

### Phase 4 — Scale and optimization

#### Goal
Remaining owner wish-list plus scale validation.

#### Requirements
FR-13, FR-14, FR-15, FR-16; NFR-11 verification.

#### Acceptance Criteria
Discount, TDS, quarterly/yearly cycles, and Dashboard P&L/ongoing TL value delivered; dashboard < 2s with 150 bonds × 96 months.

#### Dependencies
Phase 1 ledger; Phases 2–3 preferred complete.

#### Risks
Payout-cycle changes touch ledger/status logic — regression tests required.

#### Out of Scope
Cloud, mobile, networked multi-user.

## 9. Functional Requirements

| ID | Requirement | Priority | Phase | Acceptance | Verification | Status |
|---|---|---|---|---|---|---|
| FR-01 | The system SHALL store all data in a local SQLite database schema comprising a bond master table, a row-per-payment ledger table, and a home_plan table. | must | 1 | All three tables exist with documented columns | Integration test | proposed |
| FR-02 | When a user starts the application, the system SHALL serve a Flask web UI locally with no build step, requiring only Python and a browser. | must | 1 | One launch command opens a working dashboard in a browser | Manual test on clean machine | proposed |
| FR-03 | When a payment is recorded, the system SHALL store it as one ledger row (bond ref, month, amount, paid flag) instead of a month column. | must | 1 | Payment persisted as a single row | Integration test | proposed |
| FR-04 | When the user opens the month grid, the system SHALL render an Excel-like grid (months across) derived from ledger rows, coloring paid cells green, due cells light red, and status cells red/orange/green for Danger/On-going/Completed. | must | 1 | Grid matches ledger; colors correct per state | Visual + fixture test | proposed |
| FR-05 | When the user views the dashboard, the system SHALL compute all figures (portfolio summary counts/amounts, this-month returns, monthly history, status overview) as live queries/views. | must | 1 | Every figure equals the query result over current data | Integration test | proposed |
| FR-06 | When any past-month payment is missing, the system SHALL set status Danger; when payments made ≥ tenure, the system SHALL set status Completed (overriding Danger); a zero-value payment SHALL count as unpaid. | must | 1 | Seeded-gap portfolio yields expected statuses | Unit test (HF-01) | proposed |
| FR-07 | When the user requests an export, the system SHALL produce a UTF-8 CSV of any displayed dataset. | must | 1 | CSV opens correctly in a spreadsheet app | Manual test | proposed |
| FR-08 | When the import script is run, the system SHALL read the source XLSM once and populate SQLite, keeping the Excel file as a read-only backup. | must | 1 | All sheets imported; source file unmodified | Integration test | proposed |
| FR-09 | When payments exist, the system SHALL compute Till Return as the sum of paid ledger rows and Balance as Till Return minus Maturity Amount, as queries (never stored). | must | 1 | Totals match Excel figures | Unit test (HF-02) | proposed |
| FR-10 | When import completes, the system SHALL hold all 15 bonds' master fields exactly as in the source workbook. | must | 1 | 15 bonds, field-by-field comparison | Integration test | proposed |
| FR-11 | When the watch list is viewed, the system SHALL reproduce the analytics formulas (discount, TDS, per-month, qty TL, 12-month totals). | should | 3 | Computed values match Excel watch-list outputs | Comparison test | proposed |
| FR-12 | When the Home Plan is viewed, the system SHALL reproduce the 84-month savings schedule including irregular savings (39588, 10063, 0). | should | 3 | Schedule and totals match stored Excel values | Comparison test | proposed |
| FR-13 | When a bond has a discount, the system SHALL record and display the discount amount per bond. | should | 4 | Discount visible on bond detail | Manual test | proposed |
| FR-14 | When a payout is due, the system SHALL compute and display TDS deduction on payouts. | should | 4 | TDS shown per payout | Unit test | proposed |
| FR-15 | When a bond's payment type is quarterly or yearly, the system SHALL generate due dates on that cycle instead of monthly. | should | 4 | Quarterly/yearly schedules correct | Unit test | proposed |
| FR-16 | When the dashboard is viewed, the system SHALL show P&L and ongoing bond total (TL) value. | should | 4 | P&L and TL figures displayed and correct | Manual + query test | proposed |
| FR-17 | When a bond reaches Completed, the system SHALL free its principal for reinvestment, and duplicate-deduction rules SHALL apply only to On-going and Danger bonds. | must | 1 | Completed principal available to reinvest; deduction skips completed | Unit test | proposed |
| FR-18 | When the current month is beyond a fixed range, the system SHALL still generate grid columns/borders dynamically with no hardcoded Feb-2027 window. | must | 1 | Any month range renders without schema change | Unit test (HF-07) | proposed |
| FR-19 | When a bond's payment window starts Feb-2031 or later, the system SHALL still compute status and render its rows (no scan-window limit). | must | 1 | Late-start bond gets status and grid | Fixture test | proposed |
| FR-20 | When data changes, the system SHALL refresh the dashboard on the next view without any open/save event trigger. | must | 1 | Edit → reload shows new figures | Manual test | proposed |
| FR-21 | When an operation fails, the system SHALL surface the error to the user visibly; the system SHALL NOT swallow errors silently. | must | 1 | Induced failure produces visible message | Negative test | proposed |
| FR-22 | When a duplicate ISN exists in the bond set, the system SHALL flag it across the entire set (not a partial row range). | should | 2 | Duplicate anywhere is flagged | Unit test | proposed |
| FR-23 | When data is read or written, the system SHALL use stable schema keys and SHALL NOT couple logic to header text or column positions. | should | 2 | Renaming display labels changes no logic | Code review + test | proposed |
| FR-24 | When payment history changes, the system SHALL recompute the bond status immediately without requiring open/save events. | must | 1 | Edit payment → status updates | Integration test | proposed |

## 10. Non-Functional Requirements

| ID | Category | Requirement | Phase | Verification | Status |
|---|---|---|---|---|---|
| NFR-1 | offline | The system SHALL operate entirely offline for all features. | 1 | Disconnect network, run full workflow | proposed |
| NFR-2 | security/privacy | The system SHALL keep data in a local SQLite file with no cloud, accounts, or outbound transmission. | 1 | Inspect traffic; config review | proposed |
| NFR-3 | portability | The system SHALL run on any desktop OS with only Python and a browser, with no build step. | 1 | Run on Windows/Linux/macOS | proposed |
| NFR-4 | usability | When launched on a clean machine, the system SHALL reach a working dashboard within 1 minute via a single documented command. | 1 | Timed clean-machine test | proposed |
| NFR-5 | maintainability | The system SHALL centralize business logic in one module/SQL views and SHALL NOT recreate header-text coupling. | 1 | Code review | proposed |
| NFR-6 | maintainability | The system SHALL surface errors visibly and SHALL NOT swallow failures. | 1 | Negative tests | proposed |
| NFR-7 | reliability | When a view is requested, the system SHALL recompute dashboard/status values and SHALL NOT serve stale snapshots. | 1 | Edit → reload test | proposed |
| NFR-8 | data-integrity | The system SHALL enforce: Danger = any past unpaid month; Completed overrides; zero = unpaid (verification obligation for FR-06). | 1 | Fixture portfolio test | proposed |
| NFR-9 | reliability | The system SHALL NOT use hardcoded date headers or scan-window limits. | 1 | Boundary tests (Feb-2027+, Feb-2031+) | proposed |
| NFR-10 | data-integrity | When import runs, the system SHALL reproduce the full dataset with totals reconciling exactly (15 bonds, 1037142.01, 111638.57, -925503.44). | 1 | Reconciliation test | proposed |
| NFR-11 | scalability | The system SHALL render the dashboard in under 2 seconds with 150 bonds × 96 months without schema change. | 4 | Seeded-data performance test | proposed |
| NFR-12 | usability | The system SHALL provide CSV export of any displayed dataset. | 1 | Export each view | proposed |
| NFR-13 | portability | The system SHALL keep the DB file as the sole persistence artifact, transferable by file copy. | 1 | Copy DB to second machine, open | proposed |

## 11. Data and Interfaces

| ID | Type | Name | Requirement | Source |
|---|---|---|---|---|
| DATA-01 | Entity | Bond master | status, purchase date, broker, ISN, company, rating, principle TL, tenure, maturity date/amount, interest start, payment type | FR-10 |
| DATA-02 | Entity | Payment ledger | bond ref, month, amount, paid flag (Sep-2025..Jul-2032+) | FR-03 |
| DATA-03 | Entity | Home Plan schedule | month index 1..84, saving (incl. 39588/10063/0), rate, per-year interest, countdown, remaining interest; totals | FR-12 |
| DATA-04 | Entity | Watch-list analytics | face value, principle, T.L.P, discount, per-month, 10% TDS, 12-month, qty, TL principle | FR-11 |
| DATA-05 | Derived (query-only) | Totals | Till Rerun, Balance, status — computed, never stored | FR-09 |

## 12. Errors and Edge Cases

| ID | Condition | Expected Behavior |
|---|---|---|
| ERR-01 | Bond beyond old Jan-2031 scan window | Status and rendering still produced; never silently skipped |
| ERR-02 | Zero-value payment in a past month | Treated as unpaid; Danger check applies |
| ERR-03 | Current month cannot be resolved for This Month Returns | Explicit message shown, not a silent 0 |
| ERR-04 | Duplicate ISN in bond set | Flagged across entire bond set |
| ERR-05 | XLSM import failure | Failure reported explicitly, never silently swallowed |
| ERR-06 | Home Plan formula/static mix | Import preserves stored values verbatim |

## 13. Constraints

1. Fully offline; no cloud services or accounts (user requirement).
2. Data lives in a single local SQLite file per user (shareable by file copy).
3. Desktop-only for now; browser is the UI (no separate Android/Linux/desktop builds).
4. Python 3.14 environment already exists (`.venv` with oletools).
5. Original XLSM remains as read-only backup; it must not be modified by the tool.
6. Web search was disabled during brainstorming; all requirements trace only to local artifacts.
7. ISO/IEC 29110 basic profile; IEC 62304 safety class A (non-safety-critical tracking tool).

## 14. Dependencies and Risks

1. Python + Flask + SQLite availability on users' machines (low risk, standard install).
2. XLSM parsing dependency (openpyxl/oletools) for import — formula/static mix may hide values (medium risk; spike in Phase 0).
3. Behavior change vs old Excel (fixed Danger rule, no MsgBox) may surprise users — communicate in changelog.
4. Friends' machines vary by OS — NFR-3 portability test required.
5. No formal upstream requirements existed; RTM was derived after the fact — the workbook itself is source of truth.

## 15. Out of Scope

1. Cloud sync, accounts, authentication.
2. Networked multi-user mode / shared server database.
3. Android/iOS native apps.
4. Live bond-market data feeds.
5. Modifying the source XLSM file.
6. Retroactive rewriting of historical Excel files beyond the one-time import.

## 16. Open Questions

| ID | Question | Impact | Owner | Status |
|---|---|---|---|---|
| Q-01 | Should header typos (Staus, Yeild, ISN, "Till Rerun") be corrected in the new UI labels? | Low — display-only; new schema uses clean field names | Owner | Open |
| Q-02 | Should Home Plan irregular savings be editable in-app or import-only? | Medium — affects Phase 3 UI scope | Owner | Open |
| Q-03 | Quarterly/yearly cycles (FR-15): does the ledger stay monthly with grouping, or store cycle rows? | Medium — Phase 4 data-model detail | Owner | Open |

## 17. Acceptance Criteria

1. Import of the real XLSM reproduces 15 bonds and exact totals (SM-01).
2. Dashboard figures change immediately after any payment edit, with no open/save event (SM-02).
3. Status engine flags every unpaid past month; Completed overrides Danger; zero counts unpaid (SM-03).
4. A bond starting Feb-2031+ receives correct status and grid rendering (SM-04).
5. CSV export opens correctly in a spreadsheet application.
6. A clean machine reaches a working dashboard within 1 minute using one documented command (NFR-4).
7. All Phase-1 FR rows pass their verification method with status moving proposed → verified.

## 18. Helper Function Candidates

| ID | Name | Purpose | Source Requirements | Inputs | Outputs | Errors | Testable |
|---|---|---|---|---|---|---|---|
| HF-01 | computeBondStatus | Bond status Danger/On-going/Completed with fixed Danger rule | FR-06, FR-24, NFR-8 | bond id, ledger rows, today | status string | ERR-02 | yes |
| HF-02 | computeTillReturnAndBalance | Till Return = SUM paid; Balance = Till Return − Maturity (Excel K/L) | FR-09, FR-05, NFR-10 | ledger rows, maturity amount | till return, balance | — | yes |
| HF-03 | computeThisMonthReturns | Sum of current-month payments without static-0 fallback quirk | FR-05, FR-20, NFR-7 | ledger, today | month total | ERR-03 | yes |
| HF-04 | aggregateMonthlyHistory | Full-range history (Sep-2025..Jul-2032+), future months 0 | FR-05, FR-18, NFR-7, NFR-9 | ledger | month/total rows | — | yes |
| HF-05 | parseXlsmImport | Parse XLSM sheets to normalized records; tolerate header typos; flag dup ISN | FR-08, FR-10, FR-12, FR-22, NFR-10 | .xlsm path | records | ERR-04, ERR-05, ERR-06 | yes |
| HF-06 | exportCsv | UTF-8 CSV export of any dataset | FR-07, NFR-12 | rows, headers | CSV bytes/file | — | yes |
| HF-07 | computeMonthWindow | Derived month window/index — replaces hardcoded headers + Jan-2031 limit | FR-18, FR-19, NFR-9 | start month, range | column window | ERR-01 | yes |
| HF-08 | computeTenureWindow | start..start+tenure−1 due months + maturity month; drives ledger/status/grid | FR-03, FR-06, FR-24, NFR-8 | start month, tenure | due-month list | — | yes |
| HF-09 | mapPaymentStatusStyle | Cell/status display colors (green paid, light red due, red/orange/green status) replacing conditional formatting | FR-04 | paid flag, status | color/style key | — | yes |

## 19. Glossary

| Term | Definition |
|---|---|
| Bond tracker | The system being replaced: XLSM workbook with VBA dashboard/status engine |
| Ledger | One row per payment (bond, month, amount, paid flag) — the core storage model |
| Month grid | Excel-like view with months across columns, rendered from ledger rows |
| Till Return (K) | Total payments received to date for a bond (Excel column K = SUM of month cells) |
| Balance (L) | Till Return − Maturity Amount (Excel column L; negative = still to receive) |
| Danger / On-going / Completed | Status engine states; Danger = any past unpaid month (fixed rule), Completed = tenure fully paid |
| Watch list | Static analysis sheet with discount/TDS/yield formulas per bond |
| Home Plan | 84-month savings simulation schedule with interest calculations |
| Wish list | Owner's Note-sheet TODO: discount, TDS, quarterly/yearly, P&L, reinvestment free-up |
| PSRS | Product and Software Requirements Specification (this document) |
| EARS | Easy Approach to Requirements Syntax (When/While/… sentence shapes) |

## 20. Change Log

- 2026-09-27 — PRD scout team (fr-extractor, nfr-checker, helper-detector, consolidator) + parent merge — initial draft v1.0.0 created from brainstorm notes and doc-code analysis of the actual .xlsm. User decisions applied: FR-04 extended with color rules; NFR-11 numeric target (2s @ 150 bonds × 96 months) confirmed; FR-21 promoted to must/Phase 1; FR-17 + US-03 promoted from wishlist to Phase 1 (owner's "most important feature"); FR-12 + DATA-03 moved to Phase 3.
