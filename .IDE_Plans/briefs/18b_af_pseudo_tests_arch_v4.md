# Brief 18b — AF / Pseudocode / Test Plan / Dev Order / Architecture addenda (D38/D39/D40)

Worker role: document writer. Create EXACTLY FIVE new files in `docs/`. NO git. No other files. Reply only the REPORT section.

## Inputs (read first, in this order)

1. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — D38, D39, D40 all CONFIRMED (brainstorm v2.3.0). Full text is the requirement truth.
2. Format/id templates (continue each id sequence after the last used, never renumber):
   - `docs/Atomic_Functions_addendum_v3.json`
   - `docs/Pseudocode_addendum_v3.json`
   - `docs/Test_Plan_addendum_v3.json`
   - `docs/Development_Order_addendum_v3.json`
   - `docs/Watchlist_Architecture_Addendum_v1.json`
3. `docs/PRD_DK_Bond_Tracker_addendum_v4.json` — another worker is writing it in parallel; it carries FR-50+ for the same scope. Reference FR-50..FR-60 range as written in brief 18a (FR-51 nav, FR-52 tabs, FR-53 registry, FR-54 Add Position+D15 lock, FR-55 payouts grid+auto-sort, FR-56 watchlist whitelist, FR-57 move-to-portfolio lock incl. re-buy after Matured, FR-58 labels, FR-59 status model, FR-60 themes). If the file already exists, cross-check ids; if not yet written, trust this list.
4. `.IDE_Plans/design_drafts/ui_frontend_design_v4.html` — approved UI truth.

## Deliverable 1: `docs/Atomic_Functions_addendum_v4.json`

extends v3. New AFs (continue AF numbering) covering:
- apply-theme(mode): set `data-theme` on html root per System/Light/Dark; resolve System via `prefers-color-scheme` and follow OS changes live.
- persist-theme(mode) / restore-theme-at-boot(): localStorage read before first paint (zero-flash).
- portfolio-tab-switch(tab): My Holdings ⇄ Payouts.
- add-position flow: capture start/end date → compute tenure months → capture credit day → run D15 duplicate/lock check → create position (Held).
- move-to-portfolio(candidate): same D15 lock check → convert Watching→Held.
- derive-payment-health(position): from Payouts grid entry for the credit day — paid on time → On-going; not entered on credit day → Danger same day; tenure end reached → Matured.
- sort-payouts-rows(): Danger top, On-going next, Matured bottom.
- render-label(mapping): display-time mapping Returned→Received, Completed→Matured (engine values untouched).

## Deliverable 2: `docs/Pseudocode_addendum_v4.json`

extends v3. Pseudocode blocks (match v3's block format exactly) for each new AF above, plus the pre-paint theme bootstrap snippet and the tenure calculation (whole months between start and end dates).

## Deliverable 3: `docs/Test_Plan_addendum_v4.json`

extends v3. New TCs (continue TC numbering; brief 17's worker saw TC-91 exists, so start after the true max) at minimum:
- TC: sidebar renders exactly the six D38 labels; "Month Grid" absent from nav.
- TC: Portfolio tabs switch; Holdings columns == FR-53 list; Watchlist columns == FR-56 whitelist (Invested/Received/Next Payout absent in Watchlist).
- TC: Add Position tenure auto-calc (e.g. 2025-05-15→2026-11-15 = 18 months) and credit-day bounds (reject 0/32).
- TC: duplicate lock — adding company X while On-going/Danger rejected; allowed again after Matured; after re-buy status restarts On-going/Danger.
- TC: display labels — DOM shows Received/Matured; Returned/Completed never rendered (engine values unchanged: a stored 'Completed' still displays 'Matured').
- TC: payout auto-sort — given mixed statuses the row order is Danger, On-going..., Matured...; future months not rendered.
- TC: theme — System/Light/Dark switch changes tokens on every screen; Dark never shows pure #000/#fff surfaces; explicit choice survives reload (localStorage); default install = Light; zero-flash (no unpainted wrong-theme frame on reload with saved dark); OS switch while mode=System updates live.
- TC: new install starts empty (no sample rows).

## Deliverable 4: `docs/Development_Order_addendum_v4.json`

extends v3. Ordered implementation entries for the new AFs (theme token layer first, then nav/tabs restructure, then watchlist whitelist + move-to-portfolio lock, then payouts auto-sort + derive-health, then label mapping, then themes UI polish), each citing its AF/FR refs, LOCAL test tag per entry.

## Deliverable 5: `docs/Watchlist_Architecture_Addendum_v2.json`

extends v1. Sections covering:
- View-layer restructure (D38): component map Dashboard / Portfolio(My Holdings, Payouts) / Watchlist(candidates) / Goals / Alerts / Settings; note the D33 drawer and alerts panel survive, attached to Portfolio rows.
- Data ownership: positions table owns Invested/Received/Next Payout; candidate store owns watchlist rows; status derived at read time from payouts entries; label mapping exists ONLY at render layer.
- Locking: single shared D15 lock routine used by both Add Position and Move to Portfolio (module-monolith: Flask + server-rendered/vanilla-JS front end, SQLite store).
- Theme subsystem (D40): CSS custom-property token sets (light/dark), `data-theme` attribute on html, System = prefers-color-scheme, localStorage persistence, pre-paint bootstrap script; no framework, no external assets.

## Self-check (run, paste into REPORT)

```
python3 -c "import json,glob;[json.load(open(f)) for f in ['docs/Atomic_Functions_addendum_v4.json','docs/Pseudocode_addendum_v4.json','docs/Test_Plan_addendum_v4.json','docs/Development_Order_addendum_v4.json','docs/Watchlist_Architecture_Addendum_v2.json']];print('JSON: ok')"
grep -ho 'AF-[0-9]*' docs/Atomic_Functions*.json | sort | uniq -d
grep -ho 'TC-[0-9]*' docs/Test_Plan*.json | sort | uniq -d
grep -nE "Paisalo|Muthoottu|INDEL|KRAZYBEE|1037142|56227|INE420C|INE101Q" docs/*_addendum_v4.json docs/Watchlist_Architecture_Addendum_v2.json
```

JSON ok; both dup-grep outputs empty; banned-token grep empty.

## REPORT

File list + byte sizes, id ranges created per file, self-check outputs, one-line summary.

BLOCK instead of improvising if formats/id sequences are ambiguous after reading the inputs.
