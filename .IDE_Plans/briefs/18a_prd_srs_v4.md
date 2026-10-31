# Brief 18a — PRD + SRS addendum v4 (D38/D39/D40)

Worker role: document writer. Create EXACTLY TWO new files in `docs/`. NO git. No other files. Reply only the REPORT section.

## Inputs (read first, in this order)

1. `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` — decisions D38, D39, D40 (brainstorm v2.3.0). D38 and D39 and D40 are all CONFIRMED. Read their full text — it is the requirement truth.
2. `docs/PRD_DK_Bond_Tracker_addendum_v3.json` — format template + FR id history (FR-38..FR-49 live here; FR-01..FR-24 in PRD_v2, FR-25/26 in addendum_v1, FR-27..37 in addendum_v2).
3. `docs/SRS_DK_Bond_Tracker_addendum_v3.json` — format template for SRS (SR id history: continue after the last SR id used across v1..v3).
4. `.IDE_Plans/design_drafts/ui_frontend_design_v4.html` — approved UI truth (2026-10-31). Theme extension lands as `ui_frontend_design_v5.html` (being written in parallel by another worker — reference the path, do not read it).

## Deliverable 1: `docs/PRD_DK_Bond_Tracker_addendum_v4.json`

- id `PRD_DK_Bond_Tracker_addendum_v4`, extends `PRD_DK_Bond_Tracker_addendum_v3`, same top-level shape as v3 (kind/title/version/status/project/extends/sections).
- Change Record section: addendum v4 extends v3; scope = owner decisions D38 (screen restructure), D39 (labels + Add-Position location, approved on ui_frontend_design_v4.html), D40 (multiple themes System/Light/Dark). State explicitly what it supersedes from v3: (a) sidebar nav — Month Grid renamed to Portfolio; (b) the "Two-View Watchlist" section — My Holdings moves OUT of Watchlist into Portfolio tabs, Watchlist becomes candidates-only; (c) "Move to Holdings" action renamed "Move to Portfolio". No legacy FR is altered or deleted — v4 only adds FR-50 onward.
- Design Source section: UI truth = ui_frontend_design_v4.html (approved); theme truth = ui_frontend_design_v5.html (D40); structural wireframe = dk_bond_tracker_ui_wireframe_design_v4.excalidraw.json.
- New FRs (FR-50+, one requirement each, crisp testable sentences) covering at minimum:
  - FR-51 Sidebar navigation exactly: Dashboard | Portfolio | Watchlist | Financial Goals | Alerts | Settings (Portfolio replaces Month Grid).
  - FR-52 Portfolio screen has two tabs: My Holdings and Payouts.
  - FR-53 My Holdings = position registry with columns Company/ISIN, Rating, Coupon, Yield, Frequency, Invested, Received, Next Payout, Status; row opens detail drawer (drawer from D33 remains).
  - FR-54 Add Position action inside Portfolio > My Holdings; form captures start date, end date, auto-calculated tenure (months), credit day (1..31); both Add Position and watchlist Move-to-Portfolio funnel through the same D15 duplicate/lock check.
  - FR-55 Payouts tab = month grid pattern (companies x current/past months only, never future months); cells show amount or status; rows auto-sort Danger top, On-going next, Matured bottom.
  - FR-56 Watchlist is candidates-only: allowed columns Company/ISIN, Rating, Coupon, Est. Yield, Source note, Action; status Watching; NO Invested/Received/Next Payout/health columns anywhere in Watchlist.
  - FR-57 Move to Portfolio converts candidate into position under the D15 lock: a company already On-going or Danger cannot be added again; after Matured a new purchase is allowed (which restarts lifecycle to On-going/Danger).
  - FR-58 Display labels (engine values unchanged): `Returned` renders as `Received`, `Completed` renders as `Matured`.
  - FR-59 Status model — purchase state: Watching | Held; payment health: On-going | Danger | Matured, derived from the Payouts grid; legend shown on Portfolio.
  - FR-60 Multiple themes: System (follow OS), Light (default), Dark — switcher in header + Settings > Appearance; choice persists across restarts; applies with no flash of wrong theme.
- Every FR references its decision (D38/D39/D40) inline.

## Deliverable 2: `docs/SRS_DK_Bond_Tracker_addendum_v4.json`

- id `SRS_DK_Bond_Tracker_addendum_v4`, extends `SRS_DK_Bond_Tracker_addendum_v3`, same shape as SRS v3. Continue SR numbering after the last SR id in v1..v3.
- Cover, as SRS-grade requirements (precise, verifiable):
  - Navigation/structure SRs (D38): exact sidebar labels; Portfolio tabs; Watchlist column whitelist.
  - Label SRs (D39): exact rendered strings `Received` / `Matured`; forbidden rendered strings `Returned` / `Completed` in the UI.
  - Status SRs: enums (Watching|Held) and (On-going|Danger|Matured); derivation source = Payouts grid; legend rendering; Danger row sort position.
  - Add-Position form SRs: date inputs, tenure auto-calculation rule (whole months between start and end), credit day bounds 1-31, credit day drives day-wise danger.
  - Theme SRs (D40): three modes; token-based color system (all colors via CSS custom properties); System mode follows `prefers-color-scheme` live; explicit Light/Dark override OS; persistence in localStorage; zero-flash (stored theme applied before first paint); dark palette constraints (no pure black/white surfaces, WCAG AA contrast, desaturated accents); theme affects every screen identically.
  - Default-data SR: new installation starts empty; the sample rows in the approved design are illustrative only.
- Self-check (run, paste into REPORT):
  - `python3 -c "import json;json.load(open('docs/PRD_DK_Bond_Tracker_addendum_v4.json'));json.load(open('docs/SRS_DK_Bond_Tracker_addendum_v4.json'));print('JSON: ok')"`
  - FR id grep: no duplicate FR ids across `docs/PRD*.json` (`grep -ho 'FR-[0-9]*' docs/PRD*.json | sort | uniq -d` must be empty)
  - SR id grep: no duplicate SR ids across `docs/SRS*.json`
  - banned real tokens clean: `grep -nE "Paisalo|Muthoottu|INDEL|KRAZYBEE|1037142|56227|INE420C|INE101Q" <both files>` empty
  - decision refs present: each of D38/D39/D40 appears ≥3 times in PRD v4

## REPORT

File list + byte sizes, FR/SR id ranges created, self-check outputs, one-line summary.

BLOCK instead of improvising if the id sequences or formats are ambiguous after reading the inputs.
