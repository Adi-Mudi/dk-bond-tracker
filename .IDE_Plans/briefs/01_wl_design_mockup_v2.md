# Brief 01 — wl-design — Watchlist Mockup v2 (Settings screen)

Workspace (cwd for all work): /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverable (EXACTLY ONE new file): .IDE_Plans/design_drafts/watchlist_standalone_mockup_v2.html
Constraint: v1 file stays UNTOUCHED (frozen reference). Zero external deps (inline CSS/JS, system fonts). Zero comments. No git. Only this one file.

SOURCE: read .IDE_Plans/design_drafts/watchlist_standalone_mockup_v1.html fully — v2 = v1 PLUS the Settings additions below (everything in v1 kept as-is except where noted).

USER DECISION D34 (binding): Settings screen must exist with mailing detail + configuration. Sidebar "Settings" is a real nav destination.

ADDITIONS:
1. Sidebar: keep Settings item; add hover/active-ready styling (v1 already has the item).
2. NEW full screen section id="screen_settings" titled "Settings" with tab-like sub-nav (left inner rail or top pills): 
   a. Email Alerts: fields SMTP host (smtp.gmail.com), Port (465 SSL dropdown 465/587 STARTTLS), Username (you@gmail.com), App Password (masked ••••••••••••, never displayed back — note "stored locally, never shown again"), Recipient (alert email), From name; buttons [Test Email] (accent) + [Save]; status badge "Not configured" (red-dot) — plus a green "Configured" example badge; honest note: "credentials stay on this machine (local DB); env vars SMTP_USER/SMTP_APP_PASSWORD still override".
   b. Alert Preferences: toggles (on/off switches): Payout reminder 3 days before; Overdue on credit day+1; Maturity alerts 30 / 7 / 1 days; Daily status sweep time (select 00:00-23:00); In-app bell always on (locked, disabled toggle with hint).
   c. General: Default credit day for new positions (1-28 select); Privacy mode on startup (toggle OFF); Currency format (Indian ₹ 10,37,142.01 — fixed radio); Table density (Compact/Comfortable radio, matches watchlist); Theme (Dark — selected; Light — disabled "coming later").
   d. Data: [Import from Excel...] secondary button (file note), [Export backup (.db)] secondary, Default CSV scope select (Current view / Full ledger), Danger zone: [Reset local database] red outline + confirm hint.
   e. About: version v1.0 (watchlist redesign preview), build notes line, "100% offline — no accounts, no cloud" badge, link-text "Open local data folder".
3. Status bar: right side gains "Settings: 1 email alert rule active" (or "Email: not configured" in muted/red) to show integration.
4. Design-notes footer: add bullet "Settings: SMTP + alert prefs + general + data + about; credentials local-only, masked".
5. A slim top ribbon stays: "Watchlist Redesign — Mockup v2 (+ Settings) — for approval".

SELF-CHECK (run, report output):
python3 - <<'EOF'
p='/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist/.IDE_Plans/design_drafts/watchlist_standalone_mockup_v2.html'
h=open(p,encoding='utf-8').read()
for k in ['screen_settings','App Password','Test Email','Alert Preferences','Maturity alerts','Default credit day','Export backup','Reset local database','Not configured','no accounts, no cloud','My Holdings','INE101Q07BS1','Settings:']:
    assert k in h, k
assert 'http://' not in h and 'https://' not in h and 'cdn.' not in h
print('OK v2:', len(h), 'bytes')
EOF

REPORT (your final reply): path, bytes, self-check output, list of settings sections created.
