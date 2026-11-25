# D13 Self-Review — Multi-theme round (theme-research + primary re-render)

Date: 2026-11-23 · Track: design-track-a · Scope: the D13 theme directive (brief v4 `theme_directive` v2) — theme-direction research, a three-theme switchable token system, a research-chosen non-white PRIMARY, and a full re-render of all 32 screens in the primary theme.

## Method

1. Research-first (per directive): four fresh fetches on 2026-11-23 — Apple HIG Dark Mode, NN/g Dark Mode vs. Light Mode, GitHub Primer Color, Android/Material 3 design systems (paired schemes). Cited with URLs in `research/notes.md` §F.
2. Theme system authored as a role contract in `DESIGN.md` v2.0 (§1 model, §2 three complete token tables, §6 switcher placement) — same role names across themes, value-swap switching per the Primer pattern, M3 paired-scheme accent behavior (accent lifts lighter on dark for text/link roles).
3. Primary re-render: all 32 screens batch-edited (`stitch edit screen`, 4 chunks × 8, config-only color prompt with explicit per-token values + hard-coded light-hex replacement rules + example.com email rule + font-config protection).
4. Verification sweep of every exported screen HTML (scripted): canvas/ink/surface config values, valid font config, light-theme remnant signatures, h1 presence; plus full-res visual spot checks.

## Theme decision (research-chosen)

- PRIMARY: **Midnight Ledger** — deep blue-black canvas `#0D1520` with base/elevated surface ladder (`#16212E` cards, `#1E2C3B` popovers) and blue accent (`#2456E6` fills, `#8FB4FF` links/active on dark). Not white or white-like; rich, dark, tinted toward blue (bond/finance association).
- Research basis: Apple HIG legitimizes dark-first for focus apps and cites its own finance app (Stocks) shipping dark-only; NN/g evidence (low-vision benefit, user preference) supports offering dark without making light performance claims disappear — hence complete light alternates; Primer/M3 provide the switching mechanics (role tokens, paired schemes).
- Alternates: **Paper Ledger** (tuned light, mist darkened to clear 4.5:1) and **Sepia Ledger** (warm tinted light, bronze accent) — both fully tokened in DESIGN.md §2 so implementation can switch; static mockups render the primary only.

## Findings and actions

| # | Finding | Evidence | Action | Status |
| --- | --- | --- | --- | --- |
| D13-1 | Single-theme directive superseded: DESIGN.md v1.0 carried "exactly one theme… no dark variant… no theme switcher" (§1, §6, §8). | DESIGN.md v1.0 wording | DESIGN.md rewritten to v2.0: three complete token sets (§2), switcher in topbar overflow + Settings > Appearance (§6), print sheet stays ink-on-white in every theme (§4/§7). | FIXED |
| D13-2 | Research requirement >=3 cited theme sources unmet in v1 notes. | research/notes.md (v1) | §F added with 4 fetch-verified sources (Apple HIG, NN/g, Primer, M3) + §F5 decision rationale. | FIXED |
| D13-3 | All 32 screens rendered the light palette; developer rejects white. | v1 exports | Batch re-render to Midnight Ledger across all 32 screens; per-screen sweep confirms dark canvas/ink/surface tokens and zero light remnants (results below). | FIXED |
| D13-4 | Light-theme Mist failed 4.5:1 on white (D12-7). | D12 note | Carried into the new contract: Paper Ledger mist darkened to `#6B7684` (4.6:1); Midnight mist `#7A8A99` clears ~4.8:1 on its surfaces; all status pairs tuned per theme to >=4.5:1. | FIXED |
| D13-5 | Email-guard risk on regeneration: edits can re-embed demo addresses. | D12 commit block | Every theme-edit prompt mandates example.com placeholders; post-edit sweep greps for real-looking addresses before commit. | MITIGATED |
| D13-6 | Static mockups cannot switch themes; drawing a switcher into 32 mockups invites layout drift. | — | Switcher specified in DESIGN.md §6 for implementation; mockups render primary only — recorded as an explicit as-built decision (DESIGN.md §9). | DOCUMENTED |
| D13-7 | A1 audit F-TRKA-01 (MINOR): auxiliary mobile touch targets under 48px (filter chips, secondary buttons) vs RD-09. | A1 Track-A baseline report via C4 | Dedicated touch-target pass after the theme re-render: every interactive element raised to >=48x48px (>=8px gaps) by padding/min-height, not font size; verified per screen in the sweep (h-12 / min-h-[48px] counts) and visually on chip-heavy screens (watchlist_mobile, grid_mobile, search_web). | FIXED |
| D13-8 | Brief v5: HTML evidence was a loose file set with no review entry point. | brief v5 deliverable | Built `evidence/gallery/index.html` — one offline entry page (relative links only), grouped by area with web/mobile badges, one click to every screen; every screen HTML carries a persistent review-nav bar (Gallery / Prev / Next, 48px targets, injected idempotently). | FIXED |
| D13-9 | Brief v6: images are NOT deliverables — review surface is HTML only; bulk PNG export dropped. | brief v6 deliverable | Pipeline changed: no PNG re-export after edits; manifest regenerated as HTML-mandatory (image entries optional, marked pre-D13/superseded); gallery works from HTML alone (CSS preview cards). Existing committed PNGs stay in git (not deleted) as pre-D13 references. | FIXED |
| D13-10 | D14 developer ruling: clean-minimal is the design bar (Zerodha-style sparse; Upstox/Angel-One-style corporate clutter rejected). Multi-theme + dark primary unchanged. | D14 ruling via C4 | Clean-minimal sanity pass added before DONE: scripted clutter scan (chip-stack density, decorative uppercase eyebrows, border-rule density) + targeted strip edits on the worst offenders (row badge stacks reduced to one status chip, decorative eyebrows removed); the ledger's information density itself stays (it is data, not chrome). Results below. | FIXED |

## D14 clean-minimal sanity pass (results)

- Scripted clutter scan across all 32 screens: chip counts, decorative-eyebrow counts, border-rule counts per screen (worst offenders listed in the round log).
- Targeted strip edits: dashboard (web+mobile) row-badge stacks reduced to one status chip per holding; portfolio_web same; search_web decorative eyebrow removed; feedback_web meta badges ("DESK V2.4", "PRODUCT INTELLIGENCE & LEDGER AUDIT") removed.
- Accepted with rationale: uppercase micro-labels that NAME a section (e.g. "PAYMENT STATUS") stay — they are the §3 label token doing hierarchy work, not decoration; the returns/holdings tables stay dense because the data is the content (Zerodha's own tables are equally dense); per-theme status colors stay (semantic, few-hued).
- Re-verified after edits: sweep green on theme tokens; no light remnants; touch targets unchanged (48px pass was separate).

## Verification (primary re-render)

- Scripted sweep (final): 32/32 screens show `ledger-canvas = #0D1520` (single canvas value across the set), dark ink `#E8EEF5` / card surface `#16212E`, valid Inter config, zero light-remnant signatures (`#faf8ff`, `#f6f7f9`, `#eef1f5`, `#e3e8ee`, `#8592a1`, `#55606e`, `bg-white`), h1 on primary pages. Full log: sweep `bad screens: 0/32`.
- Touch targets (F-TRKA-01): 48px-target markers (`h-12` / `min-h-[48px]`) present on every interactive screen (range 3–67 per screen; print pages exempt as print targets).
- Content invariance: theme edits changed only colors; declutter edits changed only badge stacks/eyebrows/meta chips; file sizes within normal bounds of their sources.
- D11→D13 theme model: three complete switchable token sets in DESIGN.md §2 (Midnight Ledger primary, Paper Ledger, Sepia Ledger); switcher specified in §6; screens render the primary.
- Manifest v3.0: HTML entries mandatory (32/32 ok, 32/32 Canvas URLs); PNG entries marked pre-D13/superseded (not regenerated per brief v6).
- Gallery (brief v5/v6): `evidence/gallery/index.html` — offline single entry page, 32 relative screen links grouped by area (web/mobile badges), plus DESIGN.md/notes/manifest links; every screen carries the injected review-nav bar (Gallery / Prev / Next).
- Email-guard: regenerated screens audited for real-looking addresses; all demo addresses use example.com placeholders.

## D14 clean-minimal pass note

The D14 sanity pass edits landed on dashboard (web+mobile), portfolio_web, search_web, feedback_web; the remaining screens passed the clutter scan (chip usage there is functional: filters and status chips, one per row after the pass; section micro-labels that NAME a section are kept as the §3 label token). Zerodha-sparse overall impression preserved: one accent family per theme, airy 8px rhythm, minimal chrome (sidebar/bottom-tabs + topbar only).

## Developer fine-tune round (dashboard, items 1-5)

Applied after D14, folded into the same commit:

1. **Matured dim (item 1)**: Shree Cement NCD (Matured, 100% returned) renders low-emphasis — gray progress bar `#3A4A5C`, muted chip, slate amounts; bright green/red/amber reserved for active states. Rule recorded in DESIGN.md §2.
2. **Two-tab dashboard (item 2)**: segmented tab control "Dashboard" | "Returns History" (48px tabs, active = surface fill + ink; default Dashboard). Tab 1 = dashboard content unchanged; Tab 2 = Returns History & Coupon Ledger alone. Evidence ships one mockup per tab state: `dashboard_web`/`dashboard_mobile` (Tab 1) + new `dashboard_returns_web`/`dashboard_returns_mobile` (Tab 2) — gallery links both.
3. **Empty regions + footer (item 3)**: empty placeholder boxes below the Invested vs Received card removed; Returns History footer is one aligned row (period count left, pagination right).
4. **Status priority order (item 4)**: Invested vs Received rows sorted Danger (Piramal) → On-going → Matured (dimmed); filter chips reordered All, Danger, Upcoming Due, On-going, Matured. Alert feed + payout queue already group by severity (verified during capture review). Returns ledger stays chronological by design (documented in DESIGN.md §2 emphasis/priority note).
5. **Mobile KPI strip + mobile priority (item 5)**: dashboard_mobile KPI cards in one compact horizontal strip (equal widths, no horizontal scroll at 360); item-4 ordering applied to all mobile lists including bottom sections.

Coverage: the redesign now ships 34 screen views (32 screens + 2 dashboard tab states); screen_inventory coverage contract unchanged — every inventory row keeps its redesigned counterpart.

## F-TRKA-02 repair round (A1 critical — content/filename scramble)

- **Confirmed the finding**: D13 batch edits returned screen results in an order different from their input ids; my zip-based folding mislabeled 17 of 32 name→id pairs. Theme sweeps passed (all screens share the dark palette) but never checked content identity — the gap A1 caught.
- **Repair method**: downloaded all 93 canvas candidate ids from every edit log, classified each by content (h1 + section markers + device + theme/target feature flags), and rebuilt the name→id mapping from what each screen IS (`/tmp/catalog.json`, 97 classified rows). 7 names carried explicit overrides (dashboard tab states, 3 regenerations, watchlist/error/payout fixes); the rest were scored picks (class + dark + targets).
- **Edits run in this round**: E2 mobile structure (items 5-6), E3 grid_web theme+targets, E4 error_mobile theme, E5 payout_web desktop conversion, E1b Mahindra row restore (E1 row-move was correctly REFUSED — order already compliant: Piramal Danger → On-going → Shree Matured last). bond_detail_web repointed to a correct dark candidate (9bdd42be); error_mobile + grid_web fixed with deterministic local patches (palette remnant + font-quote) after edit models under-delivered.
- **Verification**: identity audit filename==content on all 34 (33/34 + 1 over-strict predicate reviewed as correct: bond_detail_mobile issuer h1 + facts grid); dashboard feature checks ALL GREEN (web: chips order, dim, danger-first, mahindra; mobile: tabs, chips, action-up, cashflow, KPI strip); theme sweep 0/34 bad; manifest v3.0 regenerated from the content-verified ids (34/34 html_ok, 34/34 Canvas URLs); gallery rebuilt (34 cards); zero non-example.com emails.
- **D15 confirmed delivery**: `evidence/redesigned_html/dashboard_web.html` + `dashboard_mobile.html` copied into `frontend/confirmed/dashboard/` in place (R2), INDEX.json dashboard status flipped rework-pending → confirmed with changelog entry.
- **Item 7 (receipt column removed — no data flow exists)**: PM verified zero receipt references in the application (src/db/queries/templates/android) — the receipt UI was invented. Removed: `RECEIPT` column (header + 5 per-row cells) from the web Returns History table, 5 `View Receipt` buttons from the mobile stacked-month cards, the `Ref: CMS…` receipt/reference button rows (4), and receipt-claiming prose ("bank credit receipts" → "net credits" on both returns views; grid Ledger Tip "credit receipt" → "credit"). Dashboard tab-1 views had no receipt elements; `frontend/confirmed/dashboard/` copies verified receipt-free. Decorative Material icon ligatures (`receipt_long` on Tax Document / voucher / Ledger History glyphs) remain — they are icon font names for existing TDS/voucher/history concepts, not a receipt UI.
- **Item 9 (navigation + screen flow + inner-screen chrome)**: authored `evidence/navigation_flow.md` (3-layer nav, uniform inner-screen chrome, the 7 key flows a-g, state/back/FAB/modal rules); gallery gained a compact flow-map section linking all 7 journeys (11 unique screen targets, 0 broken links). Chrome fixes by deterministic injection: uniform `[← Back]` chip added to the 7 inner screens that lacked any back affordance (search/settings/about/grid × web+mobile); persistent bottom tab bar injected into the 4 mobile inner screens missing it (bond_detail, payment_edit, search, error — donor markup from settings_mobile); payment_edit_mobile's stacked Save/Cancel converted to a fixed sticky footer raised above the tab bar (`bottom:76px`). Desktop breadcrumbs verified present across web inner screens (chevron/Fixed Income Ledger trails); print sheet and error page remain documented exceptions (flow doc §2). Dashboard confirmed copies untouched this item (no dashboard-file changes).

## Round log

- D13 round: research (4 sources) → DESIGN.md v2.0 (3-theme token system, primary designated) → 32-screen re-render (4 batch edits; re-edits where the sweep caught misses) → touch-target pass (F-TRKA-01 fold-in from A1 via C4) → HTML re-export + manifest v3.0 (HTML-mandatory per brief v6) → connected gallery (brief v5) → sweep + verification → commit.
- Add-on rounds folded: brief v6 (HTML-only review surface) and D14 (clean-minimal sanity pass) landed mid-pipeline — both applied before the final sweep; the final sweep is the post-D14 state (0/32 flagged).
