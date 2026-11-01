# Brief 35 — Design review batch 23 (GATE: final design v6 lock)

You are the REVIEWER. REPORT ONLY — no edits. Reply only the FINDINGS section.

## Frozen baseline (REVIEW-LOCK: ON while you read)

- Artifact: `.IDE_Plans/design_drafts/ui_frontend_design_v6.html` (owner said "design looks good" and ordered review-then-lock; commit 460854f).
- Decisions: `../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` → **D42** (v6 scope: Q2 move panel, Q3 editable newest-first payouts, Q4 attribute parity, Q5 dashboard status sort/filter, Q7 email presets, Q9 returns history + Goals KPI) and **D43** (LOCKED app-wide sort Danger→On-going→Matured + status taxonomy + automatic Danger rule).
- Parent design: `ui_frontend_design_v5.html` (approved) — v6 must be v5 + D42/D43 only (no drift in untouched screens).
- Brief that built it: `.IDE_Plans/briefs/34_design_v6.md`.

## Checks (cite line numbers)

1. **Completeness vs D42/D43**: inline move-expansion panel (labeled fields, no cramped Action cell); payouts newest-left + clickable cells + editor affordance + future months hidden; attribute parity (Add Candidate fields = Details facts grid = My Holdings strip: agency/issuer/secured/face/cycle/invested/broker); dashboard status chips + priority order + filter chips; Holdings rows priority-ordered + caption; email presets Gmail/Outlook/Custom autofill + setup guide + test-email + troubleshooting; Returns history as Dashboard TAB (Overview|Returns history) with paid·pending columns + field-definitions caption; Goals KPI strip linking to returns; Dashboard tab switcher does not break Portfolio tab switching (data-dtab scoping).
2. **D43 correctness everywhere in the artifact**: no list surface shows an order violating Danger→On-going→Matured (check dashboard chart, holdings, payouts, print legend text); status taxonomy purposes present where statuses are introduced (legend).
3. **v5 preservation**: sidebar 6 labels, theme switcher, Hide amounts, Appearance, canonical sample set only, zero banned tokens (Paisalo/Muthoottu/INE101Q/xlsm), zero external refs, HTML parses.
4. **Implementability (deep)**: every new element is buildable within the existing Flask+vanilla+SQLite architecture — name for the implementer: which elements need new routes/fields (payout cell editor posts where? details toggle = pure JS? email test button = new route; attribute fields = existing bond-master columns? check `docs/Watchlist_Architecture_Addendum_v2.json` + `docs/Atomic_Functions_addendum_v4/v5.json` field lists) — flag any design element with NO data-model home (that would block docs/impl).

## Out of scope
Pixel styling taste, v4/v5 history, docs content.

## FINDINGS (max 5)
`F-23x: [CRITICAL|MAJOR|MINOR] <title> — <evidence line> — verdict FIX/PASS`. End with exactly one line: `VERDICT: AGREED` or `VERDICT: BLOCKED: <n> CRITICAL/MAJOR`.
