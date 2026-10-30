# Brief 09 — wl-scrub-funcs — Anonymize architecture + AF + pseudocode addenda (sample data only)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverables: EDIT IN PLACE docs/Watchlist_Architecture_Addendum_v1.json, docs/Atomic_Functions_addendum_v3.json, docs/Pseudocode_addendum_v3.json (only these three). Zero comments. No git.

WHY (user Q3): user-agnostic product docs — every user imports their OWN data; no owner-specific values anywhere.

CANONICAL SAMPLE SET: Alpha Securities Ltd/INE9000A01001, Beta Finance Ltd/INE9000A01002, Gamma NBFC Ltd/INE9000A01003, Delta Capital Ltd/INE9000A01004, Epsilon Housing/INE9000A01005, Zeta Infra/INE9000A01006, Eta Retail/INE9000A01007, Theta Motors/INE9000A01008; sample money ₹1,00,000.00 / ₹7,500.00 / ₹28,500.00.

REPLACE in all three files wherever they appear (grep first):
- real names: Paisalo, Muthoottu, Navi, INDEL, KRAZYBEE, AKARA, ARMAN, UNIFINZ, BEST CAPITAL, KEERTANA, SPANDANA, KANAKADURGA, IFL, DAR CREDIT, Monedo, REC, PFC, IRFC, NHPC -> sample set
- real ISINs (any INE not starting INE9000A/INE9000B): INE420C07130, INE101Q07BS1, INE342T07569, INE0BUS07CE3, INE07HK07866, INE04Q907199, INE572J07810, INE04UP07162, INE08XP07431, INE109C07139, INE926R07019, INE104W07245, INE01XO07066, INE0I5X07042, ... -> sample ISINs
- exact figures: 1037142.01, 111638.57, -925503.44, 56227.88, -1165738.34, 1221966.22, 39588, 10063, 48500, 4200, 3100 (and Indian-grouped forms 10,37,142.01 etc.) -> sample amounts or generic phrasing ("computed from imported data")
- schema/import mapping notes may cite real sheet header names (Company Name, ISN, Yeild) — those are EXCEL HEADERS, keep them (they describe the import source, not user data)
ENVELOPE/IDS UNCHANGED: arch kind/sections, AF-52..60 ids + coverage_map FR-38..49, pseudo entry ids + d5_rule exact quote — ONLY sample-data substitutions.

SELF-CHECK: all three json-parse; AF ids still AF-52..60; coverage keys still FR-38..49; d5_rule string unchanged; grep real-token list across the three files -> ZERO hits; sample tokens present; print 'SCRUB-FUNCS OK'.
REPORT: per-file replacement counts, self-check output.
