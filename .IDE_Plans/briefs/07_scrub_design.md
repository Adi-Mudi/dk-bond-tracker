# Brief 07 — wl-scrub-design — Anonymize mockup v2 (sample data only)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverable: EDIT IN PLACE .IDE_Plans/design_drafts/watchlist_standalone_mockup_v2.html (the only file; v1 stays untouched as history). Zero comments. No git.

WHY (user decision Q3): the product ships EMPTY and every user enters their OWN data — designs/docs must show only SAMPLE data, never the owner's real portfolio.

CANONICAL SAMPLE SET (use exactly this across all docs):
- Holdings rows (8): Alpha Securities Ltd/INE9000A01001, Beta Finance Ltd/INE9000A01002, Gamma NBFC Ltd/INE9000A01003, Delta Capital Ltd/INE9000A01004, Epsilon Housing Ltd/INE9000A01005, Zeta Infra Ltd/INE9000A01006, Eta Retail Ltd/INE9000A01007, Theta Motors Ltd/INE9000A01008
- Watching candidates (4): Kappa Power Ltd/INE9000B02001, Lambda Infra Ltd/INE9000B02002, Mu Finance Ltd/INE9000B02003, Nu Gold Ltd/INE9000B02004
- Money: Total Invested ₹5,50,000.00 · Current Returns ₹28,500.00 · Next Payout ₹22,000.00 · row invested ₹1,00,000.00/₹1,50,000.00/₹2,00,000.00 · returned ₹7,500.00/₹12,000.00 · alert amounts ₹4,500.00 and ₹3,200.00 · drawer face value ₹1,00,000
- Statuses: 1 Danger row (Beta, overdue), 1 Completed (Alpha), rest On-going; credit days 5/12/26 generic OK.

REPLACE (grep then fix every occurrence): any real names (Paisalo, Muthoottu, Navi, INDEL, KRAZYBEE, AKARA, ARMAN, UNIFINZ, BEST CAPITAL, KEERTANA, SPANDANA, KANAKADURGA, IFL Finance, DAR CREDIT, Monedo, REC, PFC, IRFC, NHPC), real ISINs (INE420C07130, INE101Q07BS1, INE342T07569, INE0BUS07CE3, INE07HK07866, INE04Q907199, INE572J07810, INE04UP07162, and any other INE not in the sample set), real amounts (10,37,142.01 / 1037142.01, 56,227.88 / 56227.88, -11,65,738.34 / -1165738.34, 1,11,638.57 / 111638.57, -9,25,503.44 / -925503.44, 1,22,196.22, 39588, 10063, 48,500, 4,200, 3,100 — note alert 4,200/3,100 -> 4,500/3,200).
Keep: structure, features, D5 legend, offline notes, Settings content, layout, colors, counts may be adjusted to match sample rows (e.g. "8 positions • 4 watching").

SELF-CHECK: python3 assert sample names/ISINs present; ALL real tokens absent (scan the full replace list); 'screen_settings' still present; no http(s). Print 'SCRUB-DESIGN OK' + counts of replacements made.
REPORT: replacements count, self-check output.
