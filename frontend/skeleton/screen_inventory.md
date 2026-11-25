# DK Bond Tracker — Screen Inventory (existing UI audit)

Track: design-track-a · Date: 2026-11-23 · Source: `src/templates/`, `src/views/`, `src/static/theme.css`, `src/templates/base.html`, `android/app/src/main/java/com/dkbondtracker/app/MainActivity.java`.

Platform fact: the Android app is a WebView shell (`MainActivity.java` loads `http://127.0.0.1:<port>/` served by an embedded Flask via Chaquopy). One UI serves web and Android; the redesign must be responsive, not two separate designs.

## 1. Global shell (all screens) — `base.html` + `theme.css`
| Region | Current state |
| --- | --- |
| Sidebar (>=768px) | 8 links: Dashboard, Portfolio, Watchlist, Financial Goals, Alerts, Settings, About, Feedback. Unicode-glyph "icons" via CSS `::before`. Collapse button. |
| Bottom tabs (<768px) | 5 tabs: Dashboard, Portfolio, Watchlist, Goals, More ("More" opens drawer). Inline SVG icons. |
| Topbar | Hamburger drawer button (dead — hidden at every width, see F-06), page title, alerts bell + dropdown, search overlay (plus dedicated /search page), help (guide popover), overflow menu (theme switch + privacy toggle). |
| Global dialogs | Update-available popup, auto-fetch consent popup, page-guide popover, "Why bonds?" popover, confirm dialog, tooltips. |
| Themes | Light / dark / system, hand-tuned token sets in `theme.css`. |

## 2. Page screens (web routes -> templates -> Android counterpart)
| # | Route | Template | Screen | Key components / notes |
| --- | --- | --- | --- | --- |
| 1 | `/` | dashboard.html | Dashboard | "Zone 1 — key figures" stat cards, "Zone 2 — detail": Invested vs Received bar chart, Returns history table. |
| 2 | `/portfolio` | portfolio.html | Portfolio (holdings) | Holdings table, filters, per-row actions, position detail side drawer (`Position detail` h2). Largest template (672 lines). |
| 3 | `/portfolio/<id>`, `/portfolio/<id>/detail` | portfolio_detail.html | Bond detail | Facts grid, attribute facts partial, per-bond actions. No h1. |
| 4 | `/watch` | watch.html (1438 lines) | Watchlist | Add-bond form (multi-field), fetched-details popup, held-positions table, remove-bond confirm, ISIN lookup actions. Largest screen. |
| 5 | `/goals` | goals.html | Financial Goals | New-goal form, goal cards with progress, monthly check-in ("Intent log"), linked bonds list, empty state. |
| 6 | `/search` | search.html | Search results | Grouped results list (holdings + watchlist), reachable via topbar overlay too. |
| 7 | `/notifications` | notifications.html | Alerts feed | Grouped feed cards with severity color-coding, clear/read-all actions. |
| 8 | `/settings` | settings.html | Settings | 8 sections: General, Privacy, Theme, Email, Notifications, Day-wise rules, Share/Export, Data. |
| 9 | `/grid` | grid.html | Payment grid (matrix) | Month x bond payment matrix; no h1. |
| 10 | `/payout` | payout.html | Payout schedule (per company) | Inline h1 with font-size override (18px). |
| 11 | `/payment/<bond>/<month>` | payment_edit.html | Payment edit | Single-card form; inline-styled h1. |
| 12 | `/print` | monthly_print.html | Monthly print statement | A4 print-only statement with its own token set (`print-statement`). |
| 13 | `/share` | share.html | Share snapshot | Export/share options with checkbox + format radios. |
| 14 | `/feedback` | feedback.html | Feedback | Form + 3 confirmation states (opened issue / saved locally / thanks). |
| 15 | `/about` | about.html | About | 8 zone sections: app+data, developer, source, data sources, updates, debug-signed updates, license, disclaimer. |
| 16 | (any error) | error.html | Error page | Error message + recovery link. |

Overlay-only components reused across screens: guide popover, tooltips (4 color-coded kinds), confirm dialog, notifications dropdown, search overlay, update popup, consent popup.

Action-only routes (no separate UI, listed for completeness): `/auth/google/callback`, `/gmail/connect`, `/gmail/disconnect`, `/export.csv`, `/share/generate`, `/settings/import`, `/settings/auto-fetch/*`, `/settings/email/test`, `/notifications/clear`, `/notifications/read_all`, `/watch/lookup*`, `/watch/refresh`, `/watch/<id>/delete`, `/watch/<id>/move`, `/watch/months`, `/goals/<id>/checkin|edit|delete`, `/portfolio/<id>/refresh|listing_status`, `/portfolio/invalid/<id>/remove`, `/payment/<id>/<month>` POST, `/update/dismiss`, `/feedback/retry`.

## 3. Duplicate / near-duplicate components (RD-07 evidence)
1. **Two button systems**: `.btn` / `.btn-primary` / `.btn-secondary` / `.btn-sm` AND `.ui-btn` / `.ui-btn-primary` / `-secondary` / `-destructive` / `-text` / `-compact` coexist in theme.css.
2. **Versioned alert components**: bell dropdown uses `bell-badge-v3` / `alert-dropdown-v3` / `alert-item-v3`; the notifications page uses a separate `.alert-feed .alert-card` family with slightly different styling.
3. **Two icon systems**: unicode glyphs in sidebar (`::before` content), inline SVGs in bottom tabs and topbar.
4. **Two table patterns**: `.table-wrap` responsive wrapper vs fixed `min-width: 40rem` tables (`#returns-table`, `#watch-list`, `#holdings-table`, `#payouts-table`).
5. **Radius drift**: 6px buttons, 8px cards/inputs, 10px popups, 4px bars, `--radius` 0.5rem used selectively.
6. **Detail surfaces**: portfolio.html ships an in-page "Position detail" drawer while portfolio_detail.html is a separate page for the same data.

## 4. Overflow / responsiveness spots (RD-08 evidence)
1. Four tables forced to `min-width: 40rem` -> horizontal scrolling below 640px inside `.table-wrap`.
2. Watchlist (1438 lines) and Portfolio (672 lines) pack forms + tables + popups into one column at 360px.
3. Sidebar on <768px becomes a horizontally scrolling link strip *in addition to* the bottom tabs — two mobile nav surfaces.
4. Alert dropdown fixed `min(23.75rem, 80vw)` with 14px/12.5px mixed type; long messages wrap into the timestamp column.
5. `chart-label` truncates at 45% width; bar rows wrap under 34rem container.

## 5. Inconsistencies / quality observations (feeding findings.md)
1. Heading hierarchy irregular: dashboard/grid/portfolio_detail/attribute_facts have no `h1`; payout/payment_edit use inline `style="font-size:18px"` overrides.
2. User-visible developer labels: dashboard zone titles literally read "Zone 1 — key figures" / "Zone 2 — detail"; share.html heading carries spec refs "(D18 / FR-29)".
3. Theme + privacy controls live inside the topbar overflow menu — low discoverability.
4. Status colors exist in two token generations (`--paid`/`--due`/`--completed` cell fills vs `--ok-fg`/`--warn-fg`/`--danger-fg` chip pairs).
5. Touch targets: buttons/inputs honor 48px; static chips (4px 8px padding) and small `.btn-refresh-isin` rely on invisible `::after` hit-area corridors (`inset: -1.125rem`) that overlap neighbouring rows.
6. F-06 (dead control): `.drawer-btn` is `display:none` at max-767px AND min-768px and on /watch — the topbar hamburger can never render; only bottom-tab "More" opens the drawer on mobile.
7. `body.print-statement` re-declares a private token set, bypassing the shared system.
8. Dashboard stat cards duplicate `.card` styling as `.stat-card` with the same declaration block.

## 6. Inventory coverage contract (for the redesign)
Every row in section 2 gets a redesigned counterpart (web desktop + mobile). Global shell (sidebar/bottom-tabs/topbar/dialogs) is redesigned once as the shared navigation model. No screen may be dropped; no functionality may change.
