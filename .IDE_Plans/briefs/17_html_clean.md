# Brief 17 — Clean minimal frontend design HTML (one deliverable)

You are a worker in the fix-watchlist worktree. Read this brief and execute EXACTLY as written. One file only. NO git (no add/commit/push). Reply with only the REPORT section.

## Deliverable

Create EXACTLY one file:

`.IDE_Plans/design_drafts/ui_frontend_design_v4.html`

(relative to worktree root `/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist`)

It is the approved-content, clean/minimal, light-theme frontend design of the DK Bond Tracker standalone app, for the user's final approval. Draft — stays in design_drafts/ until the user approves.

## Design rules (community-researched: clean + minimal + trustworthy fintech)

- SELF-CONTAINED: one HTML file, inline `<style>`, tiny inline vanilla JS allowed ONLY for sidebar-view switching and Portfolio tab switching. NO frameworks, NO CDN, NO external fonts/images/URLs at all.
- LIGHT theme: page background `#f8f9fa`, cards/panels `#ffffff`, text `#111827`, muted `#6b7280`, borders `#e5e7eb`. ONE accent color only (use `#2563eb`). Danger chip `#dc2626` on `#fef2f2`; On-going chip `#16a34a` on `#f0fdf4`; Matured chip `#6b7280` on `#f3f4f6`; Watching chip `#2563eb` on `#eff6ff`.
- 8px spacing system (8/16/24/32/48). Generous white space. 4 typographic levels: page title 22px/650, section title 16px/600, body 14px, caption 12px muted. Font: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- Money in `font-variant-numeric: tabular-nums`. Table rows 48px. Subtle card shadow only (`0 1px 2px rgba(0,0,0,.05)`). NO gradients, NO glass, NO animations, NO emoji. Icons: plain unicode or none.
- Layout: fixed left sidebar 220px white + main content max-width 1100px with 32px padding. Top-right header actions: "Hide amounts" privacy toggle (renders money as `₹••••••` when ON — Zerodha-style) + "Add Position" only on Portfolio.
- Most important number top-left on Dashboard (Total Invested).

## Screens (all in ONE file, sidebar switches views)

Sidebar items (exact): Dashboard | Portfolio | Watchlist | Financial Goals | Alerts | Settings

1. **Dashboard** — cards: Total Invested `₹5,50,000.00` (top-left, largest), Received `₹28,500.00`, Next Payout `₹7,500.00 · 15 Nov 2026`. One simple pure-CSS bar chart: Invested vs Received per company (8 bars, two-tone: accent + muted). Note line: "Monthly history shows completed months + current month only — future months are never shown."
2. **Portfolio** — two tabs: [My Holdings] [Payouts]
   - **My Holdings** (position registry): primary button `+ Add Position`. Table columns: Company / ISIN | Rating | Coupon | Yield | Frequency | Invested ₹ | Received ₹ | Next Payout | Status. 8 canonical rows (below). Status chips: On-going / Danger / Matured. Below the table a compact "Add Position" form mock: Start date (date input), End date (date input), auto-calculated Tenure `18 months`, Credit day (e.g. 15th of month) with caption "Credit day drives day-wise alerts."
   - **Payouts** (month-grid): companies as rows, months Oct/Nov/Dec 2026 as columns, each cell a status chip or amount. Note under grid: "Danger rows sort to top, On-going next, Matured moves down automatically."
   - **Status legend** under both tabs: `Watching` = candidate in Watchlist, not owned · `On-going` = payment healthy · `Danger` = payment missed on credit day · `Matured` = completed, no longer pays.
3. **Watchlist** — candidates ONLY. Button `+ Add Candidate`. Table: Company / ISIN | Rating | Coupon | Est. Yield | Source note | Action (`Move to Portfolio`). One status chip `Watching` per row. NO Invested/Received/Next Payout columns here. Caption: "Watchlist holds candidates only. 'Move to Portfolio' creates the position and locks the company while it is On-going or Danger." Use 4 sample candidates (can reuse canonical names + 2 more below).
4. **Financial Goals** — placeholder: one goal card "Steady Income Plan — 10 years" with target/saved/progress bar (pure CSS). Caption: "Goal naming to be confirmed."
5. **Alerts** — day-wise rules card: "If Received amount is not entered on the credit day → status becomes Danger same day." Channels: In-app notification + Email (personal SMTP, personal→personal). Toggle rows (pure CSS switches or checkboxes).
6. **Settings** — sections: Email (SMTP host/port/from/to, personal account), Privacy ("Hide amounts by default" checkbox), Currency (INR), Share/Export (customize what to include: holdings / payouts / goals — checkboxes), Data ("Start empty — no data imported").

## Canonical sample data (ONLY these — nothing else)

Holdings (8):
1. Alpha Securities Ltd · INE9000A01001 · AA · 8.5% · 9.1% · Monthly · 1,00,000.00 · 7,500.00 · 15 Nov 2026 · On-going
2. Beta Finance Ltd · INE9000A01002 · AA- · 8.2% · 8.9% · Monthly · 75,000.00 · 5,250.00 · 20 Nov 2026 · On-going
3. Gamma NBFC Ltd · INE9000A01003 · A+ · 9.0% · 9.6% · Monthly · 60,000.00 · 4,500.00 · 05 Nov 2026 · Danger
4. Delta Capital Ltd · INE9000A01004 · AA · 8.0% · 8.5% · Monthly · 80,000.00 · 5,250.00 · 10 Dec 2026 · On-going
5. Epsilon Housing Ltd · INE9000A01005 · A · 9.5% · 10.1% · Monthly · 55,000.00 · 3,200.00 · — · Matured
6. Zeta Infra Ltd · INE9000A01006 · AA- · 8.4% · 8.8% · Monthly · 70,000.00 · 1,050.00 · 25 Nov 2026 · On-going
7. Eta Retail Ltd · INE9000A01007 · A+ · 9.2% · 9.8% · Monthly · 65,000.00 · 1,200.00 · 01 Dec 2026 · On-going
8. Theta Motors Ltd · INE9000A01008 · AA · 8.6% · 9.0% · Monthly · 45,000.00 · 550.00 · — · Matured

Totals: Invested `5,50,000.00` · Received `28,500.00` · Outstanding `-5,21,500.00`. Money format Indian grouping, ₹ prefix.

Watchlist candidates (4): Alpha Securities Ltd · INE9000A01001 · AA · 8.5% · 9.1% · "saw in grip invest"; Kappa Power Ltd · INE9000C03001 · AA- · 8.8% · 9.3% · "india bonds screener"; Lambda Infra Ltd · INE9000C03002 · A+ · 9.4% · 10.0% · "golden pie list"; Mu Finance Ltd · INE9000C03003 · A · 9.8% · 10.4% · "peer suggestion".

BANNED anywhere in the file: Paisalo, Muthoottu, Navi, INDEL, KRAZYBEE, AKARA, ARMAN, UNIFINZ, KEERTANA, SPANDANA, KANAKADURGA, IFL, Monedo, NHPC, IRFC, PFC, REC, any real ISIN (anything not starting INE9000A/B/C), and figures 1037142, 10,37,142, 111638, 56227, 925503, 1165738, 1221966.

## Labels (exact — legacy names forbidden)

Use: `Received ₹` (not Returned), `Matured` (not Completed), `My Holdings`, `Payouts`, `Watching`, `Add Position`, `Move to Portfolio`, `Hide amounts`.

## Self-check (run all, paste outputs into REPORT)

```
F=.IDE_Plans/design_drafts/ui_frontend_design_v4.html
wc -c "$F"
for m in "My Holdings" Payouts Watching Matured "Received ₹" "Add Position" "Move to Portfolio" "Hide amounts" Portfolio Watchlist "Financial Goals" Alerts Settings; do printf '%s=%s\n' "$m" "$(grep -c "$m" "$F")"; done
grep -nE "Paisalo|Muthoottu|INDEL|KRAZYBEE|1037142|10,37,142|56227|111638|925503|1165738|1221966|INE420C|INE101Q|INE342T|INE0BUS|INE07HK|INE08XP|INE109C|INE926R|INE04UP|INE0NES|INE572J|INE104W|INE01XO|INE0I5X" "$F" || echo "REAL-TOKENS: clean"
grep -oE "INE[0-9A-Z]{9}" "$F" | sort -u | grep -vE "^INE9000[ABC]" || echo "ISINS: clean"
grep -nE "https?://|cdn\.|googleapis|unpkg|jsdelivr" "$F" || echo "EXTERNAL-REFS: clean"
python3 -c "import html.parser,sys
class P(html.parser.HTMLParser): pass
P().feed(open('$F',encoding='utf-8').read()); print('HTML-PARSE: ok')"
```

All must pass: markers ≥1 each, REAL-TOKENS clean, ISINS clean, EXTERNAL-REFS clean, HTML-PARSE ok.

## REPORT (reply with only this)

- file path + byte size
- marker counts block
- self-check outputs (paste)
- one-line summary of what the mockup shows

Done-condition: file exists, every self-check passes, REPORT sent. If anything in this brief is impossible or ambiguous, reply BLOCKED with the reason instead of improvising.
