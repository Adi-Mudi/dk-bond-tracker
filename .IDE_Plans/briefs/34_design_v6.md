# Brief 34 — UI design v6 (D42): payouts editing, attribute parity, dashboard statuses, email presets, returns history

Worker: wl-design6. NO git. One deliverable. Reply only REPORT.

## Deliverable
`.IDE_Plans/design_drafts/ui_frontend_design_v6.html` — copy of `ui_frontend_design_v5.html` (same tokens, light+dark, sidebar, privacy mask — byte-preserve what isn't listed below) PLUS these v6 changes:

1. **(Q2) Move-to-Portfolio layout** — Watchlist Action column keeps only a `Move to Portfolio` button; clicking expands an inline row panel BELOW the row (colspan full width) with a clean 3-column labeled grid: Purchase date (start date) | End date | Credit day — when the amount is credited each month | Broker | Move (submit) | Cancel. No more cramped vertical stack inside the Action cell.
2. **(Q3) Editable Payouts + reversed timeline** — Payouts tab: month columns ordered NEWEST-LEFT → older right (Dec, Nov, Oct… caption "latest month first"); every past/current month cell is clickable → shows inline mini-editor (amount + Received? checkbox + Save) representing the payment entry; empty future months are NOT rendered (keep current+past rule); caption updates to "Click any month cell to enter or correct the received amount. Newest months appear first."
3. **(Q4) Attribute parity** — Add Candidate form gains: Rating agency (e.g. CRISIL), Issuer type (Corporate Bond/NCD/SDI/Govt), Secured (Secured/Unsecured), Face value, Payout cycle (Monthly/Quarterly/Annual), Invested ₹. Watchlist table stays scannable (Company/ISIN, Rating, Coupon, Est. Yield, Broker, Status) + a `Details` toggle per row expanding a facts grid with ALL attributes (incl. Source note). My Holdings: add a matching compact attribute strip under the row (or confirm drawer shows all — design whichever is cleaner) so BOTH screens show identical information.
4. **(Q5) Dashboard statuses** — per-company chart rows gain status chips (Danger/On-going/Matured/Invalid) sorted Danger → On-going → Matured (Invalid last); add filter chips above the chart: All | Danger | On-going | Matured; note "sorted by priority — items needing attention first".
5. **(Q7) Email presets** — Settings > Email card: Provider dropdown (Gmail | Outlook / Microsoft 365 | Custom) autofilling: Gmail → smtp.gmail.com, port 587, TLS (note: 465/SSL alt); Outlook → smtp.office365.com, port 587, STARTTLS; Custom → empty fields. Below: collapsible "Setup guide" (Gmail: enable 2-Verification → create App Password at myaccount.google.com → paste 16-char app password, NOT your login password; Outlook: same app-password concept for personal accounts), a `Send test email` button with result banner (success/failure + plain-language hint: "Authentication failed = usually needs an App Password"), and a small troubleshooting list (wrong port, TLS required, spam folder).
6. **(Q9) Returns history** — Dashboard new section "Returns history": table Month | Interest received | Positions paid | Cumulative received — NEWEST month first, current month highlighted; plus a 2-KPI strip at top of Financial Goals ("Earned this month", "Total received") linking to Dashboard/#returns. (This is the PM-recommended placement: returns are portfolio-wide; Goals keeps goal progress + cross-link.)

## Constraints
Self-contained (inline CSS/JS, zero external refs); keep v5 markers working (My Holdings/Payouts/Watching/Matured/Received ₹/Add Position/Move to Portfolio/Hide amounts/Appearance); canonical sample data only; no banned tokens (Paisalo/Muthoottu/real ISINs xlsm); no comments in code.

## Self-check (paste)
wc -c; marker greps (each >=1): "v6", "Setup guide", "Send test email", "Returns history", "Earned this month", "newest month first", "Details", "Rated by" or "Rating agency"; banned/external greps clean; html.parser ok; diff-vs-v5 summary of sections added.

## REPORT
Path+bytes, per-change summary, self-check outputs, one-line summary.
