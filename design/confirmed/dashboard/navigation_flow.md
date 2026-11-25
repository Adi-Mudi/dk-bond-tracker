# DK Bond Tracker — Navigation & Screen Flow (Track A)

Date: 2026-11-23 · Track: design-track-a · Implementable spec for the redesigned UI (Midnight Ledger primary). Source of the design artifacts: `evidence/redesigned_html/` + gallery.

## 1. Three-layer navigation

| Layer | Chrome | Contains |
| --- | --- | --- |
| L1 — Global | Desktop: left sidebar (240px, 5 primary + secondary group). Mobile: fixed bottom tab bar (Dashboard, Portfolio, Watchlist, Goals, More). | Primary destinations (pages) + utility pages (Alerts, Settings, About, Feedback, Share, Print). |
| L2 — Page | Page header: title + subtitle/status line + right actions (Export/Add Bond/search overlay triggers). Segmented tabs where the page has tabs (Dashboard \| Returns History). Filter chips, KPI strips, lists. | Page content sections. |
| L3 — Inner screen | **Uniform inner-screen chrome** (§2): back affordance + page title + right actions; desktop breadcrumb; mobile keeps bottom tabs visible; forms carry a sticky Cancel/Save footer. | Detail, forms, utility views (bond detail, payment edit, search results, share, settings, about, grid, error). |

## 2. Uniform inner-screen chrome

Every L3 screen shows, top to bottom:

1. **`[← Back]` affordance + page title** (left) — label may name the destination (`Back to Ledger`, `Back to Payment Matrix`) but the affordance position and hit target (48px) are uniform.
2. **Right actions** — overflow/context actions only (never the global create action; that is the FAB, §3).
3. **Desktop breadcrumb** — parent trail under/next to the header: `Dashboard / Bond / ISIN …` (rendered with chevron icons or the `Fixed Income Ledger › …` trail — both already present across web inner screens).
4. **Mobile: bottom tab bar stays visible** on inner screens (never hidden by a form or detail view).
5. **Forms: sticky footer** with `Cancel` (left/outline) and `Save …` (right/primary), raised above the bottom tab bar.

**Documented exceptions:** the monthly print sheet is A4 ink-on-white (its chrome is `Back to Ledger` + print toolbar; no app tabs on the sheet); the full error page is terminal recovery (`Try again` + `Go to dashboard`, no breadcrumb).

## 3. Create action (FAB)

- **List screens only** (Dashboard, Portfolio, Watchlist): circular 56px accent FAB, bottom-right (`right:16px; bottom:104px` — clears bottom tabs and the Gallery review control), white `+`, `aria-label="Add Bond"`.
- Hidden inside forms and inner screens (including Dashboard's Returns History tab content area — the FAB persists on the dashboard *page* chrome for parity; it never overlaps sticky footers because forms hide it).
- Desktop additionally keeps a compact `+ Add Bond` text button in the page header next to Export Statement.
- The existing app's nav shells the FAB follows: sidebar ≥768px, bottom tabs <768px.

## 4. The seven key flows

| # | Flow | Steps |
| --- | --- | --- |
| (a) | Add Bond | FAB `+` → **Add Bond form** (full page) → inline validation (ISIN lookup, required fields) → success toast/confirm → navigates to **Bond Detail**. Form hides the FAB; sticky Cancel/Save footer. |
| (b) | List → Detail | Portfolio/Watchlist/Goals row tap → **Bond Detail** → row actions open: Payment Edit, Share snapshot, Watch toggle (confirm modal for destructive remove only). |
| (c) | Detail → Payment Edit | Bond Detail action → **Payment Edit** (full-page form, sticky Cancel/Save) → Save → returns to **Bond Detail** with success toast (state preserved). |
| (d) | Search | Header search icon → **search overlay** (quick modal — allowed: quick-search is modal-class) OR full `/search` page → result → **Bond Detail** → Back returns to search with query + scroll context intact. |
| (e) | Alerts | Header bell → **alerts feed** (dropdown for glance, full feed page for triage) → item tap jumps to the relevant screen (settings rule, bond, payout month). |
| (f) | Utilities | Settings / About / Share / Print open as L3 pages from the More sheet or sidebar secondary group; each has back to its launcher (`history.back()` semantics) — Print additionally has its dedicated toolbar. |
| (g) | Errors | **Inline errors** (fields, fetch failures) render in place with retry — never a navigation. **Full error page** only for dead routes (404/unhandled) → `Try again` (retry) + `Go to dashboard` (recovery). |

## 5. State rules

1. **Back preserves parent state**: filters, sort, active tab, and scroll position of the parent list/page are restored when returning (browser back and the `[← Back]` affordance behave identically).
2. **Forms are full pages** — never modals. Modals are reserved for: confirms (destructive), filter sheets, and quick-search overlay.
3. **FAB scope**: list screens only (Dashboard, Portfolio, Watchlist). Hidden inside forms and detail views.
4. **One back chain**: inner screen → its parent (flow table), never a dead end; every inner screen offers at least one forward recovery path.
5. Theme switcher (Midnight/Paper/Sepia/System) lives in the topbar overflow + Settings > Appearance and is reachable from every layer.

## 6. Artifact map

- Screens: `evidence/redesigned_html/` (34 views) — chrome components are visible in the inner-screen set (`bond_detail_*`, `payment_edit_*`, `search_*`, `share_*`, `settings_*`, `about_*`, `grid_*`, `error_*`, `print_*`).
- Gallery entry: `evidence/gallery/index.html` (includes the compact flow map).
- Confirmed dashboard copies: `design/confirmed/dashboard/` (D15 in-place).

## Cashflow tab placement (developer 2026-11-25)
The locked Dashboard third tab **Cashflow** hosts the **Cashflow Calendar** view (calendar board: `design-skeleton/evidence/cashflow_calendar/cashflow_calendar_all_sections.html` — current month first, then next; paid-only amounts; per-bond schedule). No standalone nav destination; also reachable via More if needed later.
