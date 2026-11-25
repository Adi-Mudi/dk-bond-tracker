# Settings — Design Notes (LOCKED 2026-11-25)

## Flow
Four sections as tabs (GENERAL active default) = the backend SECTIONS tuple (general, notifications, share, data). Factory defaults = empty-first state. No FAB; all controls inline. Email test, import/export, auto-fetch consent live in their sections.

## Rulings
1. Approved by developer (2026-11-25: "settings okay").
2. Research upgrade added: top search + suggestion chips (Appearance, Alerts, Backup, Auto-fetch).
3. Title corrected (branding leak fix).

## Research
- src/views/settings.py SECTIONS + prefs (privacy_on_startup, share flags, alert prefs), src/prefs.py, auto-fetch consent routes (ILF-12..14), email test.
- Mobile settings patterns: search-first, sectioned lists, switch rows.
