# Brief 14 — wl-scruba (round 2) — Scrub the 3 wireframe Excalidraw files

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
EDIT IN PLACE these 3 files ONLY (zero comments, no git; keep all element ids, customData.ref ids, structure — value substitutions only):
1 design/dk_bond_tracker_ui_wireframe_design_v1.excalidraw.json
2 design/dk_bond_tracker_ui_wireframe_design_v2.excalidraw.json
3 design/dk_bond_tracker_ui_wireframe_design_v3.excalidraw.json

WHY: D37 + owner Q3 — diagrams ship in the repo; zero previous-user data.

TOKENS TO REPLACE (only these appear): 39588 -> 25000 ; 10063 -> 10000 (home-plan sample rows). While in there, ALSO apply canonical name/ISIN/figure maps from .IDE_Plans/briefs/10_scrubA.md IF any of those tokens appear (currently expected absent — verify anyway).
KEEP: every customData.ref id (FR/D/TC ids), element ids, colors, layout, supersedes fields, D5 text.

SELF-CHECK: all 3 parse as JSON; element-id counts unchanged vs before edit (count elements pre/post); grep ALL real tokens (brief 10 lists + 39588/10063) -> ZERO hits; print "SCRUB-WIREFRAME OK" + per-file element counts.
REPORT: replacement counts + self-check output.
