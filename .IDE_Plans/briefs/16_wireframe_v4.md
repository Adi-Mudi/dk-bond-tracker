# Brief 16 — wl-scruba — Wireframe v4 (Excalidraw): Portfolio restructure per D38/D39

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverable (EXACTLY ONE new file): .IDE_Plans/design_drafts/dk_bond_tracker_ui_wireframe_design_v4.excalidraw.json
Method: deep-copy .IDE_Plans/design_drafts/dk_bond_tracker_ui_wireframe_design_v3.excalidraw.json, keep ALL v3 elements byte-identical, ADD new elements (new ids prefixed v4_), envelope adds "supersedes": "dk_bond_tracker_ui_wireframe_design_v3". Zero comments, no git, do not modify v3.

READ FIRST: brainstorm D38/D39 (../.IDE_Plans is base — actually read /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json, keys D38/D39) — they define the restructure.

WHAT TO DRAW (restructure visible at a glance):
1. Sidebar nav update: v4 new sidebar text element: "Dashboard | Portfolio | Watchlist | Financial Goals | Alerts | Reports | Settings" with note "(Month Grid renamed -> Portfolio)".
2. PORTFOLIO screen (new big container, replace hero role): segmented tabs [My Holdings] [Payouts]:
   a. My Holdings table mock: columns Company/ISIN | Rating | Coupon | Yield | Payout | Invested | Received ₹ (label change note) | Next Payout | Status chips On-going/Danger/Matured (label note: was Completed) ; Add Position button box with ref note "(proposal A — both entry paths run D15 lock)"; drawer hint box.
   b. Payouts tab mock: the month-grid pattern box: bonds x months, cells paid/due, auto-sort badge "Danger top -> Matured bottom (derived from this grid)".
3. WATCHLIST screen (candidates only): table columns Company | ISIN | Rating | Coupon | Yield | Intent | Notes | status chip "Watching"; action box "Move to Portfolio -> (D15 lock check)"; note box "NO invested/received/next-payout/health columns here (D38)".
4. Status model legend box: "Purchase state: Watching -> Held | Payment health (Portfolio only, derived from Payouts grid): On-going / Danger / Matured (was Completed)".
5. Keep v3 elements (old Month Grid + old watchlist tabs) but ADD strike-through style labels? Simpler: add small "SUPERSEDED by v4" tags on the old Month Grid/old two-view elements (new text elements near them).
REFS (D121, valid ids only): FR-01..49, NFR-1..13, DATA-01..05, D1..D39, TC-01..104, documents (SRS_DK_Bond_Tracker_v1 etc.). Suggestions: Portfolio container -> FR-31/FR-04 satisfy + D38 trace; My Holdings -> FR-41/FR-42 + D38; Payouts -> FR-03/FR-31 satisfy; Add Position (proposal A) -> FR-39 + D39 trace; Watchlist candidates -> D38 trace + FR-48? (use FR-39 or FR-43 if apt; avoid unknown ids); status legend -> D5-equivalent refs: FR-06 trace (D5 engine).

SELF-CHECK (run, include output):
python3 - <<'EOF'
import json
w=json.load(open('.IDE_Plans/design_drafts/dk_bond_tracker_ui_wireframe_design_v4.excalidraw.json'))
v3=json.load(open('.IDE_Plans/design_drafts/dk_bond_tracker_ui_wireframe_design_v3.excalidraw.json'))
assert w['type']=='excalidraw' and w.get('supersedes','').endswith('v3')
ids=[e['id'] for e in w['elements']]; assert len(ids)==len(set(ids))
v3ids={e['id'] for e in v3['elements']}; assert v3ids<=set(ids), 'v3 elements preserved'
valid={f'FR-{n}' for n in range(1,50)} if False else ({f'FR-{n:02d}' for n in range(1,50)}|{f'NFR-{n}' for n in range(1,14)}|{f'DATA-{n:02d}' for n in range(1,6)}|{f'D{n}' for n in range(1,40)}|{f'TC-{n}' for n in range(1,105)}|{'SRS_DK_Bond_Tracker_v1','PRD_DK_Bond_Tracker_v2','Test_Plan_DK_Bond_Tracker_v1','architecture_dk_bond_tracker_v1'})
refs=[]
for e in w['elements']:
    r=(e.get('customData') or {}).get('ref')
    if r: refs+=[it['id'] if isinstance(it,dict) else it for it in (r if isinstance(r,list) else [r])]
bad=[x for x in refs if x not in valid]
assert not bad, bad
blob=json.dumps(w)
for k in ['Portfolio','Payouts','My Holdings','Watching','Matured','Received','Move to Portfolio','D15 lock']:
    assert k in blob, k
print('OK v4:', len(ids),'elements (+%d new), refs %d all valid'%(len(ids)-len(v3ids), len(refs)))
EOF
REPORT: path, element/ref counts, new elements list (ids), self-check output.
