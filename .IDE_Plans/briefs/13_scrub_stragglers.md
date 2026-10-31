# Brief 13 — wl-scrubc (round 2) — Straggler files missed by briefs 10/11

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
EDIT IN PLACE these 9 files ONLY (zero comments, no git, structure/ids/envelopes untouched — substitutions only):
1 docs/PRD_DK_Bond_Tracker_addendum_v1.json  (contains Muthoottu)
2 docs/PRD_DK_Bond_Tracker_addendum_v2.json  (39588, 10063)
3 docs/SRS_DK_Bond_Tracker_addendum_v1.json  (Muthoottu)
4 docs/SRS_DK_Bond_Tracker_addendum_v2.json  (Muthoottu, 39588, 10063)
5 docs/Atomic_Functions_addendum_v2.json  (39588, 10063)
6 docs/Pseudocode_DK_Bond_Tracker_v1.json  (1037142.01, 111638.57, 56227.88, -1165738.34, 39588, 10063)
7 docs/Pseudocode_addendum_v2.json  (39588, 10063)
8 docs/Development_Order_addendum_v2.json  (39588, 10063)
9 docs/Test_Plan_addendum_v1.json + docs/Test_Plan_addendum_v2.json ONLY IF still DIRTY when you scan them (wl-scruba may be fixing them in parallel — re-check first; if it is mid-edit, SKIP those two and note it in your report to avoid two writers)

CANONICAL MAP: read .IDE_Plans/briefs/10_scrubA.md — apply ITS Name/ISIN/Figure maps exactly (39588->25000, 10063->10000, 1037142.01->550000.00, 111638.57->28500.00, -1165738.34->-521500.00, Muthoottu->Beta Finance Ltd etc).
KEEP: D5 quote, ids (AF/FR/TC/D#), decision ids, excel header names, L1/L2 concept wording (figures become canonical/generic).

SELF-CHECK: parse every edited file; grep the full real-token list across ALL NINE (or eight if the two skipped) -> ZERO hits; print "SCRUB-STRAGGLER OK" + per-file counts.
REPORT: files edited/skipped, replacement counts, self-check output.
