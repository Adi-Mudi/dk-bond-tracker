# Design System: DK Bond Tracker (Frontend Redesign, Track A)

> **Implementation target: Flutter** (developer decision D18, 2026-11-24) — this design system (tokens, components, navigation) is built as Flutter widgets (single Dart codebase → web + Android). The backend engine is preserved behind a JSON API adapter; the old Flask/Jinja and native-Java frontends are removed and rebuilt from scratch. Source of truth for colors/typography/spacing below maps directly to Flutter `ThemeData` + widget tokens.
>
> **Platform scope update (developer decision, 2026-11-24): ANDROID-ONLY going forward.** After the current redesign phase completes, the WEB application is dropped — all subsequent design and implementation work targets the Android application only. Web artifacts already produced remain as reference history; every new design ships as a MOBILE/ANDROID pair. The static chrome, tokens, and component contracts below remain authoritative for the Android build.

Status: redesign specification v2.0 (2026-11-23, D13 multi-theme edition — supersedes the v1.0 single-theme directive). Extracted from the current UI (`src/static/theme.css`, `base.html`, evidence/current captures) and re-authored as one coherent, MULTI-THEME system for web + Android. This document governs all redesigned screen generation. Functionality is unchanged; only the design system, components, and navigation are redesigned.

## 1. Visual Theme Model (three switchable themes, one primary)

DKBT ships a multi-theme token system: THREE complete, switchable themes sharing one role contract, with exactly ONE designated primary.

- **PRIMARY — Midnight Ledger (dark)**: deep blue-black canvas, elevated surface ladder, brightened foregrounds, blue accent lifted for dark surfaces. Research-chosen per `research/notes.md` §F (Apple HIG dark-first finance precedent, NN/g low-vision + preference evidence, M3 paired-scheme pattern). Every screen ships rendered in this theme.
- **Alternate — Paper Ledger (light)**: the tuned positive-polarity light scheme (NN/g: best reading performance; kept for users who prefer light).
- **Alternate — Sepia Ledger (light, warm tinted)**: parchment canvas — for users who dislike both white and dark.

Switching is a token-value swap under one role contract (Primer pattern): no component references a raw hex. The switcher lives in the topbar overflow sheet and in Settings > Appearance (Midnight Ledger / Paper Ledger / Sepia Ledger / System default), on every screen. Atmosphere keywords: calm ledger, deep navy canvas, hairline borders, one confident accent per theme, tabular numerals, 8px grid, layered surfaces instead of shadows. Status is never color-only — always icon + text label.

## 2. Color Role Contract & Theme Token Sets

Roles are named once; each theme supplies full values. Canvas is the app background (never content). Surfaces build a base/elevated ladder (Apple HIG dark pattern): canvas < surface < surface-high. Semantic status pairs are per-theme tuned fg/bg, never inverted blindly.

| Role | Midnight Ledger (PRIMARY) | Paper Ledger | Sepia Ledger |
| --- | --- | --- | --- |
| canvas | `#0D1520` | `#F6F7F9` | `#EFE8DC` |
| surface (cards, nav, sheets) | `#16212E` | `#FFFFFF` | `#F9F4EA` |
| surface-high (popovers, dialogs, insets) | `#1E2C3B` | `#FFFFFF` | `#FFFDF8` |
| surface-alt (hover tints, table header band, secondary buttons) | `#1A2735` | `#EEF1F5` | `#E6DCCB` |
| hairline (1px borders) | `#2A3A4C` | `#E3E8EE` | `#D6C9B4` |
| ink (primary text) | `#E8EEF5` | `#16212E` | `#26211A` |
| slate (secondary text) | `#A8B6C4` | `#55606E` | `#5C5546` |
| mist (captions, hints) | `#7A8A99` | `#6B7684` | `#6E6553` |
| accent (primary buttons, active nav, selected filters) | `#2456E6` | `#2456E6` | `#9A5B14` |
| accent-hover | `#1C46C2` | `#1C46C2` | `#7A470F` |
| accent-text (links, active nav labels on canvas/surface) | `#8FB4FF` | `#1D4ED8` | `#9A5B14` |
| on-accent (labels on accent fill) | `#FFFFFF` | `#FFFFFF` | `#FFFDF8` |
| focus ring (2px, 2px offset) | `#8FB4FF` | `#2456E6` | `#9A5B14` |
| paid-fg / paid-bg | `#6FD898` / `#12301E` | `#166534` / `#E8F6EE` | `#1F6B3C` / `#DFEED9` |
| due-fg / due-bg | `#FF8A80` / `#3A1310` | `#B42318` / `#FDECEB` | `#A63222` / `#F7DCD3` |
| upcoming-fg / upcoming-bg | `#FFC46B` / `#3A2A0E` | `#92400E` / `#FDF3E0` | `#8A5A14` / `#F3E3C2` |
| info-fg / info-bg | `#8FB4FF` / `#14263D` | `#1D4ED8` / `#E8EFFC` | `#2B5CAD` / `#DCE6F5` |
| matured-fg / matured-bg | `#A8B6C4` / `#1E2C3B` | `#55606E` / `#EEF1F5` | `#5C5546` / `#E6DCCB` |
| scrim (dialogs, sheets) | `rgba(4,8,14,0.60)` | `rgba(10,15,22,0.45)` | `rgba(38,33,26,0.45)` |

Contrast floor: every fg/bg pair and text role clears 4.5:1 in ALL themes (verified per pair; body text targets 7:1 per Apple HIG). Mid-gray captions that failed 4.5:1 on white in v1.0 were darkened (Paper mist `#6B7684`, was `#8592A1`).

**Emphasis rule (developer feedback, 2026-11-23)**: bright semantic colors are reserved for ACTIVE states (On-going, Danger, Upcoming Due); terminal states (Matured, settled, fully received) render LOW emphasis — muted gray progress bars, slate amounts, muted chips. Emphasis = needs attention.

**Status priority order (developer feedback item 4)**: status-bearing attention lists sort visually by urgency — Danger/overdue rows FIRST, On-going/active rows in the MIDDLE, Matured/completed rows LAST (combined with the dim treatment). Applies to holdings lists, payout queues, and alert feeds; the returns ledger stays chronological (its sort key is the accounting month) with status chips + dimmed settled rows carrying the same emphasis semantics.

## 3. Typography Rules

- **Inter** (system-ui fallback stack): every text, every theme. Tabular numerals (`font-variant-numeric: tabular-nums`) on all money and ISIN strings.
- Scale:
  - **Display 28/36 semibold**: dashboard headline figures (total invested).
  - **H1 22/30 semibold**: page titles.
  - **H2 16/24 semibold**: section/card titles.
  - **Body 15/22 regular**: primary content, table cells.
  - **Small 13/18 regular**: captions, helper text.
  - **Label 12/16 medium, +0.03em, uppercase**: card labels, table column headers, chips.
- Weights: 400 / 500 / 600 only. Line height >=1.45 for body.

## 4. Component Stylings (role-based, theme-agnostic)

- **Buttons** (one family only): min-height 48px, radius 10px, padding 12px 20px, label 15 medium.
  - Primary: accent fill, on-accent label; hover accent-hover; pressed 5% ink tint + `scale(0.99)`. Secondary: surface-alt fill, ink label. Outline: 1px hairline + ink label. Destructive: due-fg outline; filled variant for confirm steps. Text: accent-text label, no border. Disabled: 40% opacity accent/surface-alt.
- **Cards**: surface fill, 1px hairline, radius 12px, padding 20px, shadow `0 1px 2px rgba(0,0,0,0.20)` on dark / `rgba(22,33,46,0.06)` on light themes (dark themes earn depth from the surface ladder, not shadow).
- **Stat cards**: Label 12 uppercase mist, value 28/36 semibold tabular, sub-line 13 slate.
- **Data table**: sticky header row on surface-alt, 48px rows, hairline row separators, first column = human-readable company name + ISIN subline, numeric columns right-aligned tabular, row actions as 48px icon buttons right-aligned, hover tint = surface-alt. Below 640px the table becomes a stacked card list — no horizontal scrolling at any breakpoint.
- **Status chips**: pill radius 999, fg/bg pairs from section 2, icon + text label, interactive chips and buttons render at least 48px tall (48px wide for icon-only) with >=8px gaps (RD-09; audit F-TRKA-01 fix).
- **Inputs & selects**: 52px height, 1px hairline border, radius 10px, 16px text (no mobile zoom), label above field, error text 13 due-fg below field with icon; focus switches border to accent + focus ring.
- **Dialogs & sheets**: centered card radius 16px on surface-high over scrim, 24px padding, primary action right. Bottom sheet variant on mobile. Destructive dialogs restate the consequence in plain language.
- **Empty states**: centered icon, one-line plain-language message, one primary action.
- **Tooltips/guide**: 13/18 on ink-inverse surface (dark themes: near-white surface with ink text; light themes: ink surface with white text), radius 8px.
- **Tab sections (dashboard, developer feedback 2026-11-23)**: the dashboard page is a two-tab page under the page header — segmented tab control ("Dashboard" | "Returns History", 48px tabs in a surface-alt container, active = surface fill + ink, inactive = mist; default tab on load = Dashboard). Tab 1 keeps the dashboard content (filter chips, KPI cards, Invested vs Received, Cashflow Rhythm, Action Required); Tab 2 carries the whole Returns History & Coupon Ledger alone (title, Filter By Year, Tax CSV, full table, one aligned footer row: period count left, pagination right, no dead space). No empty placeholder regions anywhere.
- **Print statement**: stays ink-on-white in every theme (print target); reuses the same semantic status hues darkened for paper, no shadows.

## 5. Layout Principles

> **Static layout LOCKED (2026-11-24): `design/confirmed/app_frame/` is the single chrome source of truth** — top bar 56px (brand left; sync → bell → avatar right), search in content only, 5-item bottom nav (Dashboard/Portfolio/Watchlist/Goals/More), FAB 56px `#2456E6` right:16/bottom:104, no page titles in the bar, Android-only. Every page inherits this frame unchanged (contract: `app_frame_manifest.csv`); page designs fill ONLY the dynamic zone. Per-page chrome aligns to the frame one page at a time.

- **Grid**: 4px base / 8px rhythm. Page padding 16px (mobile) / 24px (>=768). Card gap 16px. Section spacing 24px.
- **Breakpoints**: fluid 360 / 768 / 1280 / 1920. Content max-width 1200px centered at 1920. Stat grid: 1 column at 360, 2 at 768, 3 at 1280. Detail pages: two-column (facts + actions) at >=1024, stacked below.
- **Touch/accessibility**: all targets >=48x48px, gaps >=8px, visible focus ring on all interactives, status never color-only, body text >=4.5:1 contrast (7:1 target), no horizontal scroll at 360 — in every theme.
- **Density**: ledger-dense tables stay on desktop; mobile gets summary-first cards with progressive disclosure (details on tap).

## 6. Navigation Model (RD-10)

One coherent model on both platforms:
- **Five primary destinations**: Dashboard (`/`), Portfolio (`/portfolio`), Watchlist (`/watch`), Goals (`/goals`), More.
- **Compact (<768px)**: fixed bottom tab bar with the 5 destinations (48px targets, active = accent icon + label). "More" opens a bottom sheet listing secondary destinations: Alerts, Settings, About, Feedback.
- **Regular (>=768px)**: persistent left sidebar rail (240px) with the same 5 primary + a Secondary group (Alerts, Settings, About, Feedback). Collapsible to icons. No horizontally scrolling link strip on mobile — the sidebar drawer is removed from <768 entirely.
- **Topbar**: page title left; right actions: search (opens overlay + full `/search` page), alerts bell with dropdown, help. **Appearance switcher** (Midnight Ledger / Paper Ledger / Sepia Ledger / System) sits in the topbar overflow sheet as a shortcut and in Settings > Appearance — reachable on every screen (NN/g: the switch should be pervasive). Privacy toggle ("Hide amounts") stays beside it in the overflow sheet.
- Global overlays (guide, why-bonds, confirm, update popup, consent popup) keep one shared dialog pattern and follow the active theme's surface/scrim tokens.

## 7. Platform Notes (web + Android)

- The Android app is a WebView shell over this same responsive UI: one design serves both; no separate Android-only components. Theme choice persists in localStorage and is applied before first paint (no flash).
- Respect `env(safe-area-inset-*)` for bottom tabs under gesture bars; keep 48px targets; visible pressed states for touch.
- Android back button closes top overlay first (existing behavior preserved).
- The A4 monthly print statement keeps its dedicated print token set (ink-on-white in every theme) — redesigned to the same status palette but print-optimized.

## 8. Stitch Generation Notes

- **Atmosphere keywords (primary render)**: Midnight Ledger dark — deep blue-black canvas `#0D1520`, elevated card surface `#16212E`, hairline `#2A3A4C`, bright ink `#E8EEF5`, single blue accent (fill `#2456E6`, links/active `#8FB4FF`), tabular numerals, 8px grid, layered surfaces, calm ledger.
- **Component prompts**: 48px accent-filled primary buttons with 10px radius; dark cards radius 12 with 1px hairline and 20px padding; sticky-header tables with 48px rows and right-aligned tabular numerals; pill status chips pairing icon + text (`Paid` green `#6FD898/#12301E`, `Due` red `#FF8A80/#3A1310`, `Watching` blue `#8FB4FF/#14263D`); 52px inputs with labels above; bottom tab bar with 5 labeled destinations on mobile.
- **Per-screen content**: see `evidence/screen_inventory.md` for the screen list; every redesigned screen keeps the same fields and actions as the existing screen (zero functionality change).

## 9. As-Built Notes (D12 self-review + D13 theme round)

Recorded after the compare rounds against the generated screens (see `evidence/self_review_d12.md`, `evidence/self_review_d13.md`):

- **Type**: Inter ships via the screens' embedded Tailwind config. The first generation pass wrapped the stack in extra quotes (`"\"Inter, system-ui, sans-serif\""`) — an invalid single family name that rendered as the browser serif default on 26 of 32 screens. Fixed on every affected screen in the D12 round; all screens now render Inter.
- **D12 as-built primary blue (superseded by D13)**: the v1 screens bound `primary: #003dc1` with `primary-container: #2456e6` as hover — the D13 theme round replaces the baked palette with the Midnight Ledger token set (§2) on every screen, so the D12 shade-pairing note is historical.
- **Radius**: as-built scale is 2/4/8/12px (`rounded`/`lg`/`xl`/`full`) — buttons 8px, cards 12px, dialogs 12–16px. §4's 10px button radius is approximated by the 8px token; visually consistent everywhere.
- **Grid cells**: desktop payment-matrix cells sit below the 48px target (a pointer-first surface); the mobile transformation replaces the matrix with stacked full-width cards carrying 48px actions, per §4.
- **Switcher in mockups**: the static screens render the PRIMARY theme only; the switcher control is specified in §6 and implemented in code, not drawn into every mockup (static HTML cannot switch themes).
