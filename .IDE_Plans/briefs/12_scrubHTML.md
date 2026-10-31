# Brief 12 — wl-scrubHTML — Scrub the 4 HTML designs to sample data

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
EDIT IN PLACE these 4 files ONLY (zero external refs stay zero; zero comments; no git):
1 design/ui_frontend_design_v1.html  2 design/ui_frontend_design_v2.html  3 design/ui_frontend_design_v3.html  4 design/monthly_print_design_v1.html

WHY: D37 + user Q3 — designs are shipped in the repo; no previous-user data may appear anywhere.

CANONICAL MAP: read .IDE_Plans/briefs/10_scrubA.md and apply ITS exact Name/ISIN/Figure maps.
FILE NOTES:
- ui v1/v2: sample bond rows, ISINs, amounts, alert names (Muthoottu..), L1 figure mentions, 'Paisalo Completed' etc. — map all; keep layout/tokens/sections/D5/Settings (v2) untouched.
- ui v3: same + charts sample data (bars/donut values may use sample counts — any real totals -> canonical), watching candidates (REC/PFC/IRFC/NHPC -> Kappa/Lambda/Mu/Nu), status-bar/summary amounts -> canonical.
- monthly_print: 15-bond payment table -> replace with the 8 canonical sample holdings (repeat rows to keep table shape if needed); summary figures -> canonical (5,50,000.00 / 28,500.00 / -5,21,500.00); L1 note text keeps concept, figures canonical; owner name placeholder stays [Owner Name].
KEEP: D5 verbatim (HTML-escaped ok), layout, CSS, section ids, 'python src/app.py', Settings content, no http(s)/cdn.

SELF-CHECK: all 4 parse as text; grep EVERY real token -> ZERO hits in all 4; sample tokens present in each; print "SCRUB-HTML OK" + per-file counts. REPORT replacements + output.
