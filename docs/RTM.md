# Requirements Traceability Matrix (RTM)

**Project:** v5.5 40L Bond Project Tracker
**Source File:** `v5.5_40L_Project_Tracker.xlsm`
**Version:** v5.5
**RTM Version:** 1.0
**Date:** 2026-09-06

---

## 1. Purpose

This document maps each functional requirement of the bond project tracker to the VBA macro that implements it, plus a manual test case that verifies the requirement is met. The requirements below are **derived from observed VBA behavior** in `vbaProject.bin`, since no formal requirements document was supplied with the file.

---

## 2. Workbook Structure

| # | Sheet Name        | Purpose                                          |
|---|-------------------|--------------------------------------------------|
| 1 | Note              | Notes / instructions                            |
| 2 | Bond - Watch list | Bonds being monitored                          |
| 3 | Monthly Returns   | Main data sheet (source for all calculations)   |
| 4 | Dashboard         | Auto-generated summary view                    |
| 5 | Home Plan         | User-defined planning sheet                     |

---

## 3. VBA Modules

| Module             | Location       | Purpose                                        |
|--------------------|----------------|------------------------------------------------|
| ThisWorkbook.cls   | class module   | Auto-triggers on file open and before save     |
| Sheet1.cls         | class module   | Empty (placeholder)                            |
| Sheet2.cls         | class module   | Worksheet_Change event handler                 |
| Module1.bas        | standard module| Dashboard build and update logic               |
| Module2.bas        | standard module| Monthly Returns formatting and status logic    |

---

## 4. RTM Table

| Req ID | Requirement                                                                                              | Module           | Sub / Function                  | Trigger             | Test Case                                                                                                                        |
|--------|----------------------------------------------------------------------------------------------------------|------------------|--------------------------------|---------------------|----------------------------------------------------------------------------------------------------------------------------------|
| R1     | Dashboard sheet is auto-created if missing                                                               | Module1          | `FixBondDashboard`             | Workbook_Open       | Open the file with the Dashboard sheet deleted. Verify Dashboard sheet is recreated with headers.                                |
| R2     | Dashboard is rebuilt automatically every time the workbook is opened                                      | ThisWorkbook     | `Workbook_Open`                | Auto (file open)    | Close the file, reopen it. Verify Dashboard cells show latest Monthly Returns data.                                              |
| R3     | Dashboard is rebuilt automatically every time the workbook is saved                                      | ThisWorkbook     | `Workbook_BeforeSave`          | Auto (file save)    | Edit a cell in Monthly Returns, save the file. Verify Dashboard updates before save completes.                                   |
| R4     | Dashboard shows Portfolio Summary counts (Total, Danger, On-going, Completed)                            | Module1          | `UpdateDashboardSummary`       | Inside FixBondDashboard | Open file. Verify B3:B6 show correct COUNTA / COUNTIF values matching Monthly Returns column A.                              |
| R5     | Dashboard shows Portfolio Summary amounts (Total Investment, Till Return, Balance)                       | Module1          | `UpdateDashboardSummary`       | Inside FixBondDashboard | Verify E3:E5 show SUM of Monthly Returns columns G, K, L respectively.                                                        |
| R6     | Dashboard shows This Month Returns based on current calendar month (dynamic)                              | Module1          | `UpdateDashboardSummary`       | Inside FixBondDashboard | Set system date or headers such that current month changes. Verify E6 reflects current month's column sum.                   |
| R7     | Dashboard shows a Full Monthly Returns History table in columns L and M                                  | Module1          | `CreateMonthlyHistoryTable`    | Inside FixBondDashboard | Verify L3:M{n} lists every month header from Monthly Returns (col N onward) with its SUM.                                       |
| R8     | Current calendar month row in the History table is highlighted yellow                                    | Module1          | `CreateMonthlyHistoryTable`    | Inside FixBondDashboard | Verify the row whose month matches Format(Date, "mmm-yy") has a yellow interior color.                                          |
| R9     | Bonds Status Overview shows all bonds, sorted by status (Danger first, then On-going, then Completed)   | Module1          | `UpdateBondsStatusOverview`    | Inside FixBondDashboard | Add rows of each status. Verify Dashboard A10 onward shows Danger first, On-going next, Completed last.                          |
| R10    | Each row in Bonds Status Overview is color-coded by status (red/orange/green)                            | Module1          | `UpdateBondsStatusOverview`    | Inside FixBondDashboard | Verify row's column A fill color matches its status (Danger = red, On-going = orange, Completed = green).                       |
| R11    | Dashboard formatting (merged title row, blue header bar, borders, autofit) is applied                    | Module1          | `ApplyDashboardFormatting`     | Inside FixBondDashboard | Verify A1:F1 merged with blue fill, A8:J8 merged with blue fill, borders on A9:J{last}, autofit applied.                       |
| R12    | Monthly Returns headers (Row 1, columns N to AF) are regenerated as Sep-2025 to Feb-2027                 | Module2          | `RegenerateMonthlyHeaders`     | Inside InitializeMonthlyReturnsFormatting | Trigger `InitializeMonthlyReturnsFormatting`. Verify N1:AF1 show mmm-yy dates from Sep-25 to Feb-27 in sequence.       |
| R13    | Monthly Returns row is color-coded for payment status: green if paid, light red if due                  | Module2          | `FormatRowPaymentTracking`     | Inside InitializeMonthlyReturnsFormatting and Worksheet_Change | Set a cell in N:Z to a non-zero value (green), leave another empty (light red). Verify fill colors.                  |
| R14    | Auto status: column A is set to "Danger" if previous calendar month payment is missing                   | Module2          | `FormatRowPaymentTracking`     | Inside InitializeMonthlyReturnsFormatting and Worksheet_Change | Leave the cell for the previous month empty. Verify column A updates to "Danger".                                      |
| R15    | Auto status: column A is set to "Completed" if all tenure payments are made                              | Module2          | `FormatRowPaymentTracking`     | Inside InitializeMonthlyReturnsFormatting and Worksheet_Change | Fill all cells in the tenure range with non-zero values. Verify column A becomes "Completed".                            |
| R16    | Formulas injected into K (Till Return = SUM N:XFD) and L (Balance = K-J) for each row                    | Module2          | `InjectFormulas`               | Inside InitializeMonthlyReturnsFormatting | Verify K2:K{last} contain `=SUM(N2:XFD2)` and L2:L{last} contain `=K2-J2`.                                              |
| R17    | Date columns (B, M, Maturity Date) are formatted as dd-mmm-yyyy                                          | Module2          | `FormatDateColumns`            | Inside InitializeMonthlyReturnsFormatting | Verify cells in B, M, and Maturity Date column display as dd-mmm-yyyy.                                                    |
| R18    | Currency formatting in INR (₹) applied to all money columns (K, L, E, H, I, J on Dashboard)             | Module1, Module2 | `UpdateDashboardSummary`, `UpdateBondsStatusOverview`, `InjectFormulas` | Inside respective builds | Verify number format string contains `[$\u20B9]` (INR symbol).                                                              |
| R19    | Worksheet_Change event is auto-attached and triggers row reformat on edits to Tenure (H) or Months (M, N+) | Sheet2, Module1 | `Worksheet_Change`, `AddWorksheetChangeEvent` | Auto (cell edit)   | Edit cell H2 or M2 in Monthly Returns. Verify the corresponding row's color coding updates.                                    |
| R20    | Helper function `FindStartingMonthColumn` locates the column index for a given starting month            | Module2          | `FindStartingMonthColumn`     | Called by FormatRowPaymentTracking | Pass a valid starting month. Verify the returned column matches the header date.                                            |

---

## 5. Test Approach

Since this project has **no automated test framework** (no pytest, no unittest, no VBA test runner), all tests are executed manually inside Excel. Recommended approach for each test:

1. Open `v5.5_40L_Project_Tracker.xlsm` in Microsoft Excel.
2. Enable macros when prompted.
3. Perform the action described in the Test Case column.
4. Compare actual result against the requirement description.

**Pre-conditions for all tests:**
- Monthly Returns sheet must contain at least 2 rows of bond data (column A populated, column E populated).
- Headers in Row 1 of Monthly Returns must include: `Status`, `ISIN`, `Company Name`, `Rating`, `Principle TL Amount`, `Tenure (Months)`, `Maturity Date`, `Maturity Amount`, `Till Return`, `Balance`, `Starting Month`.

---

## 6. Out of Scope

The following are observed in the workbook but **not covered as requirements** in this RTM because they are data artifacts, not behavior:

- Named ranges like `microsoft.com:RD`, `microsoft.com:FV`, `microsoft.com:LET_WF`
- Sheet `Note` content
- Sheet `Home Plan` content
- Existing comments and threaded comments

These may be added as requirements after a future review.

---

## 7. Change Log

| Date       | Version | Author | Notes                                                  |
|------------|---------|--------|--------------------------------------------------------|
| 2026-09-06 | 1.0     | Kimi   | Initial RTM, derived from VBA source in vbaProject.bin |