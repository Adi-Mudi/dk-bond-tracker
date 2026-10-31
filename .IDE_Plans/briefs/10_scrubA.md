# Brief 10 — wl-scrubA — Scrub requirement/test docs (legacy set) to sample data

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
EDIT IN PLACE these 8 files ONLY (zero comments, no git, keep all ids/envelopes/structure; ONLY value substitutions):
1 docs/PRD_DK_Bond_Tracker_v2.json  2 docs/SRS_DK_Bond_Tracker_v1.json  3 docs/Feasibility_XLSM_Parser_v1.json  4 docs/Test_Plan_DK_Bond_Tracker_v1.json  5 docs/Test_Plan_addendum_v1.json  6 docs/Test_Plan_addendum_v2.json  7 docs/Atomic_Functions_addendum_v1.json  8 docs/Pseudocode_addendum_v1.json

WHY: D37 + user Q3 — no previous-user data anywhere in product docs; every user starts from scratch.

CANONICAL REPLACEMENT MAP (apply mechanically, including Indian-grouped forms):
Names: Paisalo->Alpha Securities Ltd; Muthoottu Mini Financiers|Muthoottu|MUTHOOTTU->Beta Finance Ltd|Beta Finance|BETA FINANCE; Navi Finserv|Navi->Gamma NBFC Ltd; INDEL MONEY|INDEL->Delta Capital Ltd; KRAZYBEE->Epsilon Housing Ltd; AKARA->Zeta Infra Ltd; ARMAN->Eta Retail Ltd; UNIFINZ->Theta Motors Ltd; BEST CAPITAL->Kappa Power Ltd; KEERTANA->Lambda Infra Ltd; SPANDANA->Mu Finance Ltd; KANAKADURGA->Nu Gold Ltd; IFL->Alpha Securities Ltd; DAR CREDIT->Beta Finance Ltd; Monedo->Gamma NBFC Ltd; REC->Kappa Power Ltd; PFC->Lambda Infra Ltd; IRFC->Mu Finance Ltd; NHPC->Nu Gold Ltd.
ISINs: INE420C07130->INE9000A01001; INE101Q07BS1->INE9000A01002; INE342T07569->INE9000A01003; INE0BUS07CE3->INE9000A01004; INE07HK07866->INE9000A01005; INE08XP07431->INE9000A01006; INE109C07139->INE9000A01007; INE926R07019->INE9000A01008; INE04UP07162->INE9000C03001; INE0NES07329->INE9000C03002; INE572J07810->INE9000C03003; INE104W07245->INE9000C03004; INE01XO07066->INE9000C03005; INE04Q907199->INE9000C03006; INE0I5X07042->INE9000C03007; any other non-sample INE -> next free INE9000C030xx.
Figures (both plain and Indian-grouped forms): 1037142.01|10,37,142.01->550000.00|5,50,000.00; 111638.57|1,11,638.57->28500.00|28,500.00; -925503.44|-9,25,503.44|-521503.44? use ->-521500.00|-5,21,500.00; 56227.88|56,227.88->28500.00|28,500.00; -1165738.34|-11,65,738.34->-521500.00|-5,21,500.00; 1221966.22|12,21,966.22->570000.00|5,70,000.00; 39588->25000; 10063->10000; 48500->22000; 4200->4500; 3100->3200; 55410.69->7500.00; 240234.90->100000.00. L1/L2: keep the CONCEPT wording (pending baseline / pending confirmation) but any figure must become canonical sample or generic ("computed vs declared baseline").
KEEP (do not touch): excel header names (Company Name, ISN, Yeild, Staus, No Of Month), sheet name 'Bond - Watch list ', decision ids, TC/FR/AF ids, D5 quote, sample names if already present.

SELF-CHECK: parse all 8 JSONs; grep all 8 for EVERY real token (names+ISINs+figures lists above) -> ZERO hits; print "SCRUB-A OK" + per-file hit counts (=0 each). REPORT per-file replacements + output.
