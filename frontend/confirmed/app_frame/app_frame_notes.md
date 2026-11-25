# Static Layout — App Frame (LOCKED 2026-11-24)

## Grounding (read before design, per developer)
1. `APP_SKELETON.md` §1 — Android frame: top app bar 56px (app name left, notifications right), one bottom nav (5 destinations), FAB 56px right:16/bottom:104, **excluded**: drawer / duplicate tab bars / second FAB style. Flutter mapping: `Scaffold + NavigationBar + FloatingActionButton(endFloat)`.
2. `DESIGN.md` §5 — grid 4/8, mobile padding 16px, touch ≥48px, contrast ≥4.5:1, status never color-only, mobile = summary-first cards.
3. Old-app captures (`evidence/current/`) — destination set: Dashboard, Portfolio, Watchlist, Goals, More (+ Alerts/Settings secondary).
4. Chrome audit of the two locked pages — found the mismatch this frame resolves (dashboard: title-in-bar, no sync; portfolio: no avatar).

## Contract (canonical — supersedes per-page chrome drift)
- Top bar: brand left; **sync → bell → avatar** right; no titles/search/verified-badge in the bar.
- Search lives in page content.
- Bottom nav: 5 items, active = page indicator.
- FAB: 56px `#2456E6`, right 16 / bottom 104, Add Bond, identical everywhere.
- Dynamic zone: only zone that changes per page.
- Flutter build (F3/F4) reads this contract as the chrome source of truth.

## Alignment sequencing (developer: "go one by one")
Pages align to this frame as they are visited in the page-by-page pass; dashboard bar alignment deferred (its Stitch source is stale vs the amnesty-era lock — see PM report 2026-11-24, options a/b/c; dashboard artwork untouched for now).

## Stitch
- Board screen: `398d626c974b459cbff5523b1534a50d` (project `17110477162175329772`), HTML-only export.
