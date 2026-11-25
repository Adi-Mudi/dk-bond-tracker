# DK Bond Tracker — Frontend Redesign Track A: Research Notes

Date: 2026-11-23 · Track: design-track-a · Method: live fetch of each source on 2026-11-23 (FetchURL/curl).

Purpose: gather cited best practices and benchmark practices from leading web apps and leading Android/finance apps before redesigning all DK Bond Tracker screens. Each entry: source URL + what we take from it.

## A. Best-practice sources

### A1. Touch targets — Nielsen Norman Group
- Source: https://www.nngroup.com/articles/touch-target-size/
- Take: interactive elements need >=1cm x 1cm (0.4in) physical size; small targets slow tapping and cause mis-taps; spacing between stacked targets must prevent accidental activation; primary actions deserve larger targets; users in motion or with reduced dexterity need even bigger targets.
- Applied to DKBT: every row action, chip, and nav item >=48px target with >=8px gap (RD-09); primary buttons (Record Payment, Add Goal) rendered larger than secondary.

### A2. Data tables — Nielsen Norman Group
- Source: https://www.nngroup.com/articles/data-tables/
- Take: tables must support 4 tasks — find records, compare data, view/edit a single row, take action on records. First column should be a human-readable identifier; freeze header row/column; keep comparable columns adjacent; avoid crowding row actions; batch actions via checkbox + toolbar.
- Applied to DKBT: portfolio table uses issuer as readable first column; sticky header; per-row primary action + overflow menu; grid view for scanning.

### A3. Layout / adaptability — Apple Human Interface Guidelines
- Source: https://developer.apple.com/design/human-interface-guidelines/layout
- Take: order content by importance top/leading; align elements and use indentation for hierarchy; group related items with spacing/containers; progressive disclosure keeps screens clean; adapt layout to size classes rather than device type; keep functionality constant across sizes; support text-size changes (stack columns when needed).
- Applied to DKBT: same nav model at all widths (sidebar -> bottom bar), card grids collapse to single column at 360px, no functionality removed at any breakpoint (RD-08).

### A4. Contrast / accessibility — WebAIM (WCAG 2)
- Source: https://webaim.org/articles/contrast/
- Take: body text >=4.5:1 contrast; large text >=3:1; UI component boundaries and focus indicators >=3:1 against adjacent colors; never use color alone to convey status (pair with icon/text); every interactive state must keep contrast.
- Applied to DKBT: status colors (paid/due/overdue) always paired with text label + icon; visible focus ring token; muted text capped at one gray level above the 4.5:1 floor.

### A5. Material 3 theming — Android Developers
- Source: https://developer.android.com/develop/ui/compose/designsystems/material3
- Take: M3 defines color roles (primary/on-primary, primary-container/on-primary-container, surface/surface-variant), a 15-step type scale (display/headline/title/body/label), shape scale, tonal elevation; NavigationBar for <=5 destinations on compact, NavigationRail and NavigationDrawer for medium/large; accessible color pairings enforced via on-color roles.
- Applied to DKBT: tokens named with M3-style roles so web CSS and the Android WebView share one system; bottom navigation bar on compact, rail on >=768px.

## B. Benchmark: leading web apps (3)

### B1. GitHub — Primer design system
- Source: https://primer.style
- Take: GitHub builds all product UI from one token set ("Primitives" for color, spacing, typography) plus shared foundations for accessibility; one component library ships every screen.
- Applied to DKBT: single token file (CSS custom properties) drives all 16 web screens and the Android WebView; no per-screen ad-hoc colors (RD-07).

### B2. Shopify — Polaris
- Source: https://polaris.shopify.com
- Take: Shopify ships one unified UI framework across all admin surfaces so every screen feels like the same product; data display (charts/tables/lists) comes from shared components, not one-offs.
- Applied to DKBT: one shared card, table, and status-badge component set reused on dashboard/portfolio/watch/goals (RD-07).

### B3. Atlassian — Design System
- Source: https://atlassian.design
- Take: "one design language" across all Atlassian apps — unified color, typography, iconography, grid foundations keep multi-screen products cohesive and familiar.
- Applied to DKBT: coherent navigation model + identical page-header pattern on every screen (RD-10).

## C. Benchmark: leading Android/finance apps (3)

### C1. Monzo — payment disputes redesign
- Source: https://monzo.com/blog/more-than-money-back-reimagining-payment-disputes-at-monzo
- Take: give customers context instead of a quiz — context panel on the payment itself; "before you start" screen sets expectations; pre-submission validation prevents doomed forms; plain-English explanations for confusing items; every experiment measured.
- Applied to DKBT: payment edit / goal check-in forms open with context (bond, month, amount) and validate before submit; destructive actions get confirmation with consequences spelled out.

### C2. Monzo — product design practice
- Source: https://monzo.com/blog/my-first-3-months-at-monzo-as-a-product-designer/
- Take: Monzo maintains a well-crafted internal design system all squads use; language is always "simple, clear and jargon-free" ("making your writing clearer isn't dumbing down, it's smartening up"); compliance is built into design steps rather than bolted on.
- Applied to DKBT: jargon-free labels (e.g. "Money coming this month" not "accruals"); microcopy tokens; consent screens written plainly.

### C3. Zerodha Kite — Stock SIP redesign (leading Indian finance web/app)
- Source: https://zerodha.com/z-connect/kite/introducing-updated-stock-sip-experience-on-kite-web
- Take: collapsed a multi-step flow (create basket -> link schedule -> fund) into one create flow with inline choices; quantity vs amount modes presented clearly; pause/skip/delete exposed as simple row actions; funding automation (UPI Autopay) folded into the same screen; constraints (trading holidays, fractional units) stated up front.
- Applied to DKBT: goal check-in and payment recording become single-screen flows; recurring actions (auto-fetch sync) offer pause/resume inline; limitations (offline mode, fetch consent) stated on-screen before the action.

## D. Sources attempted but unreachable from this network
- https://revolut.design (DNS/connection failure, 2026-11-23)
- https://design.wise.com (connection failure, 2026-11-23)
- m3.material.io and medium.com require JS/return 404 to fetchers; used developer.android.com M3 page instead (A5).

## F. Theme direction (D13 round — multi-theme system, 2026-11-23)

Method: live fetch of each source on 2026-11-23 (FetchURL/curl). Question: how do leading finance/product apps and platform systems choose theme direction (dark/rich/tinted bases, semantic roles, contrast), and how should a multi-theme system ship?

### F1. Apple Human Interface Guidelines — Dark Mode
- Source: https://developer.apple.com/design/human-interface-guidelines/dark-mode
- Take: dark palettes are NOT inversions of light — dimmer backgrounds pair with brighter foregrounds, and semantic colors (label, separator, control) adapt per appearance; iOS dark uses two background sets (base = dimmer, receding; elevated = brighter, advancing) to build depth; aim >=4.5:1, strive 7:1 for small text; Apple's own Stocks app (finance) ships a permanently dark appearance where focus matters — dark-first is a legitimate primary for an immersive, glanceable finance product; people expect apps to respect their appearance choice.
- Applied to DKBT: the primary theme is a dark navy ledger ("Midnight Ledger") with a base/elevated surface ladder (canvas < card < sheet); every semantic role re-tuned for dark rather than inverted; strive 7:1 for body, >=4.5:1 floor everywhere; the system carries switchable light alternates so the user preference is respected.

### F2. Nielsen Norman Group — Dark Mode vs. Light Mode: Which Is Better?
- Source: https://www.nngroup.com/articles/dark-mode/
- Take: academic evidence favors light mode for reading performance in normal-vision users, BUT NN/g strongly recommends designers offer a dark-mode switch: (1) sustained light-mode reading may be associated with myopia; (2) users with cloudy ocular media (cataract) read better in dark mode; (3) some users simply prefer it — "they should be able to [switch]". The switch should be pervasive across all screens, and apps in frequent use (long-form/financial reading) should provide it.
- Applied to DKBT: the system ships THREE complete switchable themes with the switch reachable on every screen (topbar overflow + Settings > Appearance) — dark primary, light alternate, warm-tinted alternate; dark is not a default because "dark = better UX", but because the developer's taste and low-vision/preference evidence support it, with the light alternates preserving NN/g's positive-polarity performance benefits for those who want them.

### F3. GitHub Primer — Color (functional tokens across color modes)
- Source: https://primer.style/foundations/color
- Take: GitHub ships its product UI as semantic FUNCTIONAL tokens (button-primary-fgColor-rest, bgColor-hover, danger-fgColor...) whose VALUES swap per color mode (light/dark/dimmed) while every component references only roles — that is what makes modes switchable without redesigning components; component states (rest/hover/active/disabled/selected) are first-class token entries.
- Applied to DKBT: the three DKBT themes are defined as complete role-token sets (canvas, surface ladder, ink/mist text roles, accent + on-accent, four status fg/bg pairs, component states incl. hover/pressed/focus/disabled) — switching is a value swap under one token contract; no component references a raw hex.

### F4. Android Developers — Material 3 design systems (paired light/dark schemes)
- Source: https://developer.android.com/develop/ui/compose/designsystems/material3
- Take: M3 generates PAIRED schemes — `md_theme_light_primary #476810` vs `md_theme_dark_primary #ACD370`: on dark, the accent becomes a LIGHTER tone of the same hue (not the same hex), and every role has an on-color counterpart (onPrimary flips to a dark ink); Theme.kt holds both schemes so switching is structural, not per-screen styling.
- Applied to DKBT: Bond Blue light (#2456E6 fill) lifts to a brighter blue for dark-theme links/active states (#8FB4FF) while buttons keep a saturated fill with on-color labels; the WebView (Android shell) consumes the same token contract as the web CSS — one system, three value sets.

### F5. Synthesis — theme decision for DKBT
1. PRIMARY (research-chosen, developer mandate: not white/white-like): **Midnight Ledger** — deep blue-black canvas with a base/elevated surface ladder. Research basis: Apple HIG's dark-first finance precedent (Stocks) + focus/glanceability of a money ledger; dark serves low-vision users (NN/g, Legge) and reads as a "trust vault" rather than a document; tinted toward blue (bond/finance association) instead of pure black to avoid OLED smearing and to keep the ledger calm.
2. Alternates: **Paper Ledger** (the tuned light scheme — positive-polarity reading performance per NN/g) and **Sepia Ledger** (warm tinted light — parchment canvas for users who dislike both white and dark).
3. All three carry the SAME role names and the same 4.5:1 floor (7:1 target for body text); status colors stay green/red/amber/blue semantically with per-theme tuned fg/bg pairs, always icon+text (never color-only).

## G. Original synthesis (v1 research, retained) — design principles for the redesign

1. One token system (color roles, 4/8px spacing, type scale, radii) shared by all screens and both platforms.
2. Navigation: 5 fixed destinations (Dashboard, Portfolio, Watch, Goals, Settings) as bottom bar on compact widths, rail/sidebar from 768px up.
3. Tables for comparison (portfolio/grid), cards for scanning (dashboard/watch), progressive disclosure everywhere else.
4. Touch targets >=48px, gaps >=8px, focus ring visible, status never color-only.
5. Every form opens with context, validates before submit, and states limits up front.
6. Plain-language labels and consistent page-header pattern on all screens.
