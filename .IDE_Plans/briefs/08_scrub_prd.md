# Brief 08 — wl-scrub-prd — Anonymize PRD + SRS addenda v3 (sample data only)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverables: EDIT IN PLACE docs/PRD_DK_Bond_Tracker_addendum_v3.json + docs/SRS_DK_Bond_Tracker_addendum_v3.json (only these two). Zero comments. No git.

WHY (user Q3): product docs must be user-agnostic — every user imports their OWN data; no owner-specific values anywhere. Documents must read "start from scratch".

CANONICAL SAMPLE SET (same as design scrub): companies Alpha Securities Ltd/INE9000A01001, Beta Finance Ltd/INE9000A01002, Gamma NBFC Ltd/INE9000A01003, Delta Capital Ltd/INE9000A01004 (+ Epsilon/Zeta/Eta/Theta ...INE9000A01005-008); sample money ₹1,00,000.00, ₹1,50,000.00, ₹7,500.00, ₹28,500.00.

REPLACE in BOTH files (sections + ALL acceptance_criteria examples + statements):
- every real company name (Paisalo, Muthoottu, Navi, INDEL, KRAZYBEE, AKARA, ARMAN, UNIFINZ, BEST CAPITAL, KEERTANA, SPANDANA, KANAKADURGA, IFL, DAR CREDIT, Monedo, REC, PFC, IRFC, NHPC) -> sample companies
- every real ISIN (INE420C07130, INE101Q07BS1, INE342T07569, INE0BUS07CE3, INE07HK07866, INE04Q907199, INE572J07810, INE04UP07162, or any other non-sample INE) -> sample ISINs
- every exact figure 1037142.01 / 10,37,142.01, 111638.57 / 1,11,638.57, -925503.44 / -9,25,503.44, 56227.88 / 56,227.88, -1165738.34 / -11,65,738.34, 1221966.22, 39588, 10063, 48500, 4200, 3100 -> sample values or generic phrasing
- MVP/reconciliation wording: keep the CONCEPT (import must reconcile computed vs declared baseline; mismatch never force-matched) but REMOVE owner-specific numbers; use "totals computed from the imported file (sample: 15 sample positions, e.g. Total Invested ₹5,50,000.00)" style. L1 references become "baseline supplied with the import (owner-specific)".
- AC scenarios (e.g. 'Muthoottu has an active position' or ' MUTHOOTTU ' variant tests in FR-26 ACs from addendum v1/v2 are NOT in your files — but if v3 ACs cite real names like Beta/Muthoottu, swap to sample set: for name-key ACs use ' ALPHA SECURITIES ' casing variant of Alpha Securities Ltd — wait, normalization test needs exact-variant semantics: use sample pair: active 'Alpha Securities Ltd' + candidate '  ALPHA SECURITIES LTD  ' (case variant) blocked; keep logic intact).
ENVELOPE/IDS UNCHANGED: FR-38..49, kind, version, extends, decision_ids, JSON validity. ONLY sample-data substitutions + wording genericization.

SELF-CHECK: json parses both; ids still exactly FR-38..49; grep BOTH files for the full real-token list -> ZERO hits; sample tokens present (>=5 each file); print 'SCRUB-PRD OK'.
REPORT: per-file replacement counts, self-check output.
