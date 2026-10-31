# Brief 11 — wl-scrubB — Scrub design/architecture docs (legacy set) to sample data

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
EDIT IN PLACE these 6 files ONLY (zero comments, no git, keep ids/envelopes/structure):
1 design/architecture_dk_bond_tracker_v1.json  2 design/Final_Design_DK_Bond_Tracker_v1.json  3 docs/Schema_Delta_addendum_v1.json  4 docs/Atomic_Functions_DK_Bond_Tracker_v1.json  5 docs/Pseudocode_DK_Bond_Tracker_v2.json  6 docs/Development_Order_DK_Bond_Tracker_v1.json

WHY: D37 + user Q3 — no previous-user data anywhere.

CANONICAL MAP (same as brief 10 — read .IDE_Plans/briefs/10_scrubA.md and apply ITS exact Name/ISIN/Figure maps; do not invent new values).

FILE-SPECIFIC:
- architecture v1: L1 figure pairs in risks/AF-08 notes -> canonical or generic ("computed vs declared baseline"); real bond names anywhere -> sample.
- Final_Design v1: acceptance_matrix L1/NFR-10 rows + holds figures -> canonical/generic (keep pending statuses); any real ISIN/name -> map.
- Schema_Delta v1: watch-sheet census figures/ISIN lists -> sample or generic ("15 sample rows"); keep column/DDL truth (schema structure is product code, not user data).
- Atomic_Functions v1: edge_cases with real names/figures (e.g. Muthoottu examples, 39588/10063) -> map (39588->25000, 10063->10000).
- Pseudocode v2: L1 figure mentions (56227.88 etc.) -> canonical; lock-message examples if any -> Beta Finance Ltd.
- Development_Order v1: L1 hold line figures -> canonical/generic (concept stays).
KEEP: D5 quote, ids (AF/FR/TC), schema DDL, decision ids, excel header names, 'Bond - Watch list '.

SELF-CHECK: parse all 6; grep EVERY real token (names+ISINs+figures from brief 10) -> ZERO hits; print "SCRUB-B OK" + per-file counts. REPORT replacements + output.
