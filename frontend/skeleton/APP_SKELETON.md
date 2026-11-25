# DK Bond Tracker — App Skeleton (web + Android)

- Issue: #338 (spec), Discussion #335 comment 19842481 (dashboard lock context), umbrella #336, Flutter target #337
- Branch: `design-skeleton` (cut from `design-track-a` @ `c781bf98` — the locked dashboard family rides along as fixed input)
- Method: D17 Stitch-only, zero exceptions — every artifact produced by `stitch generate screen` on project `17110477162175329772`, exported via authenticated `stitch download` (HTML + PNG). Zero direct HTML authored. Watchdog-verifiable.
- Theme: D13 Midnight Ledger dark (`#0D1520` family, zero white). Bar: D14 clean-minimal. Implementation target: D18 Flutter — every model below maps to Flutter widgets.
- Status: 2 of 5 boards exported; 3 boards PENDING-STITCH-QUOTA (daily generation + edit limits hit 2026-11-24 ~03:40 IST; regeneration prompts preserved verbatim in Appendix A so any session can finish without re-design).

## 1. Navigation model — ONE primary pattern per platform, zero duplicates

### Web
Frame = sidebar + top bar + inline page tabs.

- Sidebar (fixed, 240px): brand "DK Bond Tracker / Corporate Desk"; five primary destinations with Material Symbols icons — Dashboard (`/`), Portfolio (`/portfolio`), Watchlist (`/watch`), Goals (`/goals`), More; SYSTEM group — Alerts, Settings, About, Feedback; bottom user account card (DK Yield Account).
- Top bar (64px, sticky): DYNAMIC zone = verified tag (lock + VERIFIED BOND YIELDS), page title, inline segmented page tabs (Dashboard | Returns History); STATIC zone = Add Bond icon button FIRST (WhatsApp-style `+`, item 20), then search, notifications bell, help, avatar.
- Page tabs are CONTENT tabs inside a page's tab views — never app-level navigation.

Flutter mapping: `NavigationRail`/persistent sidebar + `AppBar` + `TabBar`/`SegmentedButton` for page tabs.

### Android
Frame = top app bar + content + bottom navigation + FAB.

- Top app bar (56px): app name (brand) LEFT; static icons RIGHT in fixed order — sync, notifications bell, avatar. NO page title, NO search icon, NO verified badge in the bar (search lives in page content). [SUPERSEDED-PART: original spec said "notifications right" only — final ruling 2026-11-24 adds sync + avatar; canonical contract = design/confirmed/app_frame/ (LOCKED).]
- Bottom navigation (one bar): five destinations — Dashboard, Portfolio, Watchlist, Goals, More.
- FAB: 56px circular `#2456E6`, white add icon, bottom-right above the nav (right 16px, bottom 104px — values inherited from the locked mobile dashboard family).
- Explicitly excluded: navigation drawer, duplicate tab bars, second FAB style.

Flutter mapping: `Scaffold` + `NavigationBar` + `FloatingActionButton` (location `endFloat`, docked above the bar).

### Anti-duplicate rule
App-level navigation is exactly one pattern per platform (web sidebar / Android bottom nav). Page-level tabs (dashboard family's Dashboard | Returns History | Cashflow) render inside page content on both platforms and are the ONLY tabs.

## 2. Screen inventory (17 families × web + Android)

Locked dashboard family is a FIXED INPUT — never redesigned; every later page must consume it via the layout system (§4) and component set (§5).

| # | Family | Web | Android | Status |
|---|--------|-----|---------|--------|
| 1 | Dashboard (Dashboard tab) | `dashboard_web.html` | `dashboard_mobile.html` | LOCKED (`c781bf98`) |
| 2 | Returns History + Coupon Ledger (Cashflow tab views) | `dashboard_returns_web.html` | `dashboard_returns_mobile.html` | LOCKED (`c781bf98`) |
| 3 | Portfolio | `portfolio_web.html` | `portfolio_mobile.html` | open (#339) |
| 4 | Bond detail | `bond_detail_web.html` | `bond_detail_mobile.html` | open (#339) |
| 5 | Watchlist | `watchlist_web.html` | `watchlist_mobile.html` | open (#339) |
| 6 | Goals | `goals_web.html` | `goals_mobile.html` | open (#339) |
| 7 | Alerts | `alerts_web.html` | `alerts_mobile.html` | open (#339) |
| 8 | Payouts | `payout_web.html` | `payout_mobile.html` | open (#339) |
| 9 | Payment edit | `payment_edit_web.html` | `payment_edit_mobile.html` | open (#339) |
| 10 | Settings | `settings_web.html` | `settings_mobile.html` | open (#339) |
| 11 | About | `about_web.html` | `about_mobile.html` | open (#339) |
| 12 | Feedback | `feedback_web.html` | `feedback_mobile.html` | open (#339) |
| 13 | Search | `search_web.html` | `search_mobile.html` | open (#339) |
| 14 | Grid | `grid_web.html` | `grid_mobile.html` | open (#339) |
| 15 | Print | `print_web.html` | `print_mobile.html` | open (#339) |
| 16 | Share | `share_web.html` | `share_mobile.html` | open (#339) |
| 17 | Error | `error_web.html` | `error_mobile.html` | open (#339) |

Reference inputs for the open families: existing redesigned exports in `evidence/redesigned_html/` (track A, release `design-galleries-v1`); they hang off this skeleton in #339 and consume §5 components 1:1 — no duplicate primitives per family.

## 3. Screen-flow map (matches existing backend capabilities; zero functionality changes)

- **Add-bond journey**: Dashboard / Watchlist → Add Bond (FAB or top-bar `+`) → Add Bond form (ISIN fetch states: idle → checking → found/not-found → offline) → Candidate preview → Move to Portfolio confirmation → Portfolio.
- **Cashflow journey**: Dashboard (Cashflow Rhythm card) → Returns History / Coupon Ledger tab → Payout schedule → Payment edit (TDS reason).
- **Alerts journey**: Top-bar / bottom-nav notifications entry → Alerts list → Bond detail (rating watch context).
- **Settings journey**: Settings → Appearance (theme switcher) → Backup (Drive) → Privacy (hide amounts) → About / Feedback.

All four journeys stay inside existing engine capabilities (fetch, store, alerts, backup, print/share) — the skeleton wires screens, it adds no features.

## 4. Layout system

### Web page frame
- Sidebar 240px fixed; top bar 64px sticky; content column `max-width: 1400px`, horizontal padding 32px, vertical rhythm `space-y-6` (24px).
- Grid: KPI row `repeat(3, 1fr)` from `md`; content sections `grid-cols-1` → `lg:grid-cols-12` (8/4 splits for master-detail; full-width sections span 12). Verified at 1280 and 1920 — zero dead zones.

### Android frame
- Reference viewport 412dp (locked mobile export `width=412`); top app bar 56px; bottom navigation standard height + safe-area inset; FAB 56px, `right: 16px`, `bottom: 104px` (above the nav).
- Content is a single fluid stack; cards carry 16px padding, 8px+ gaps.

### Tokens (D13 Midnight Ledger — single source, no raw colors outside this table)
| Token | Value | Token | Value |
|---|---|---|---|
| canvas | `#0D1520` | accent (bond-blue) | `#2456E6` |
| card | `#16212E` | accent hover | `#1C46C2` |
| elevated | `#1E2C3B` | info / info-bg | `#8FB4FF` / `#14263D` |
| hairline | `#2A3A4C` | danger / danger-bg | `#FF8A80` / `rgba(255,138,128,.12)` |
| ink | `#E8EEF5` | success / success-bg | `#6FD898` / `rgba(111,216,152,.12)` |
| secondary | `#A8B6C4` | warning / warning-bg | `#FFC46B` / `rgba(255,196,107,.12)` |
| muted | `#7A8A99` | radius | 8 / 12 / chip-full |

Type: Inter. Display 28/36 semibold; H1 22/30; H2 16/24; body 15/22; small 13/18; label 12/16 (medium, +0.03em tracking on uppercase labels). Spacing: 8px grid — 4/8/12/16/24/32; tabular numerals for every money figure.

## 5. Component inventory — one canonical style each

| Component | Canonical style (single) | Canonical source | Flutter widget |
|---|---|---|---|
| Card | `#16212E` surface, `#2A3A4C` hairline, radius 12, soft shadow | dashboard family | `Card` |
| KPI stat card | label row → large tabular value → hairline footnote row, 16px padding | dashboard KPI row | `Card` + column |
| Filter chips | full-radius; active `#2456E6`/white, inactive elevated + hairline | dashboard chips | `FilterChip` |
| Buttons | primary filled `#2456E6`; secondary elevated + hairline; danger `#FF8A80` | dashboard (alert/returns) | `FilledButton` / `OutlinedButton` |
| Segmented tabs | 48px targets, active = filled surface + ink, two selection indicators | dashboard header tabs (item 12) | `SegmentedButton`/`TabBar` |
| Data table | uppercase muted header, hairline dividers, tabular numerals, sticky header on web | Returns History table | `DataTable`/`Table` |
| FAB | 56px circle, `#2456E6`, white add icon, right 16 / bottom 104 | locked mobile dashboard | `FloatingActionButton` |
| Alert card | danger border + top glow bar, red title, action pair | dashboard Action Required (item 22) | custom `Card` variant |
| Progress bar | 8px rounded track, single-color fill | holdings rows | `LinearProgressIndicator` |
| Status badges | pill chips: Danger, On-going, Upcoming, Matured (icon + text, never color-only) | holdings + returns rows | `Chip` |

Zero duplicate variants: a family needing a new look extends an existing primitive in #339 rather than introducing a second style.

## 6. Stitch artifacts (screen ids + evidence)

| Board | Screen id | Device | Evidence | Status |
|---|---|---|---|---|
| skeleton_overview_web | `9c25a361d4834ae5a2096ca74be3506d` | DESKTOP | `skeleton_overview_web.html` + `.png` | READY |
| skeleton_overview_android | `8b9c7671342d41d2baba4ca11addef8b` | MOBILE | `skeleton_overview_android.html` + `.png` | READY |
| skeleton_nav_model | `3f2dab5be45743db8c78277b5ff9efa2` | DESKTOP | `skeleton_nav_model.html` + `.png` | READY |
| skeleton_screen_flow | `b77b12a2d0dd4562b5713f2b4d98cb4f` | DESKTOP | `skeleton_screen_flow.html` + `.png` | READY |
| skeleton_components | `a667f8a8960e4f90aa6390a89b2c73bc` | DESKTOP | `skeleton_components.html` + `.png` | READY |

## Appendix A — regeneration prompts for the 3 pending boards (verbatim; run `stitch generate screen --project 17110477162175329772 --device DESKTOP --title <board> --json`, then authenticated `stitch download` HTML+PNG into this directory)

### skeleton_nav_model
Design a dark documentation board titled 'Navigation Model - DK Bond Tracker' for a bond portfolio tracker. Midnight Ledger dark theme: background #0D1520, panels #16212E, hairline borders #2A3A4C, accent #2456E6, text #E8EEF5, muted #7A8A99, Inter font, clean minimal. Two equal panels side by side. Left panel header 'WEB - ONE PATTERN' with a blue badge, showing a tree diagram: root node 'Web App Frame', branch 'Sidebar (240px)' with five child nodes Dashboard, Portfolio, Watchlist, Goals, More, branch 'System group' with Alerts, Settings, About, Feedback, branch 'Top bar' with search, notifications, help, avatar, and branch 'Page tabs' with Dashboard and Returns History. Right panel header 'ANDROID - ONE PATTERN' with a blue badge, showing a tree: root node 'Android App Frame', branch 'Top app bar' with app name and notifications, branch 'Bottom navigation' with Dashboard, Portfolio, Watchlist, Goals, More, and branch 'FAB' with 'Add Bond (56px circular)'. Tree nodes are small dark cards with icons, connector lines in #2A3A4C with #2456E6 highlight on primary paths. Footer strip across both panels: 'ZERO DUPLICATE PATTERNS - one primary navigation per platform'.

### skeleton_screen_flow
Design a dark documentation board titled 'Screen Flow Map - DK Bond Tracker' for a bond portfolio tracker. Midnight Ledger dark theme: background #0D1520, node cards #16212E, hairline borders #2A3A4C, accent arrows #2456E6, text #E8EEF5, muted #7A8A99, Inter font, clean minimal. Four horizontal journey swimlanes stacked vertically, each with a small lane label on the left and a chain of labeled node cards connected by arrows. Lane 1 'ADD BOND': Dashboard to Watchlist to Add Bond form to Candidate preview to Confirmation to Portfolio. Lane 2 'CASHFLOW': Dashboard to Cashflow Rhythm to Payout schedule to Payment edit. Lane 3 'ALERTS': Notifications bell to Alerts list to Bond detail. Lane 4 'SETTINGS': Settings to Appearance to Backup to Privacy to About. Each node card is a compact dark rounded rectangle with a small Material Symbols icon and label. Arrows between nodes are #2456E6 with arrowheads. Footer strip: 'Flows match existing backend capabilities - no functionality changes'.

### skeleton_components
Design a dark style-guide board titled 'Component Inventory - DK Bond Tracker' for a bond portfolio tracker. Midnight Ledger dark theme: background #0D1520, specimen cards #16212E, hairline borders #2A3A4C, accent #2456E6, text #E8EEF5, muted #7A8A99, Inter font, clean minimal, generous spacing. A labeled grid of canonical UI primitives, exactly one specimen per component, each with a small uppercase caption underneath: 1 'CARD' a plain surface card with hairline border and 12px radius. 2 'KPI STAT CARD' with label, large value and footnote row. 3 'FILTER CHIPS' row with active chip in #2456E6 with white text and inactive chips in elevated surface. 4 'BUTTONS' row: primary filled #2456E6, secondary elevated with hairline border, danger #FF8A80. 5 'SEGMENTED TABS' a 48px two-tab pair with active tab filled. 6 'DATA TABLE' a compact table with uppercase sticky-style header row, hairline row dividers, tabular numbers. 7 'FAB' a 56px circular #2456E6 button with white add icon. 8 'ALERT CARD' danger card with red top glow bar, red title, action buttons. 9 'PROGRESS BAR' thin rounded track with filled portion. 10 'STATUS BADGES' row: Danger, On-going, Upcoming, Matured chips. Footer caption: 'ONE CANONICAL STYLE PER COMPONENT - NO DUPLICATE VARIANTS'.

## Changelog
- 2026-11-24 v0.1: initial skeleton — 2/5 boards exported (daily Stitch generation quota exhausted mid-run); nav model, inventory, flows, layout system, component set documented; 3 boards pending with verbatim regeneration prompts (Appendix A).
