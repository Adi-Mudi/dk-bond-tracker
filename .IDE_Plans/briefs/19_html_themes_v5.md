# Brief 19 — Design v5: add the theme system (D40) to the approved design

Worker role: UI designer. Create EXACTLY ONE new file. NO git. No other files. Reply only the REPORT section.

## Deliverable

`.IDE_Plans/design_drafts/ui_frontend_design_v5.html`

Start from `.IDE_Plans/design_drafts/ui_frontend_design_v4.html` (approved 2026-10-31). v5 = v4 content UNCHANGED + the D40 multi-theme system. v4 file must stay untouched.

## D40 requirement (from brainstorm v2.3.0, CONFIRMED)

Three themes: **System** (follows OS), **Light** (default), **Dark**. Header switcher + Settings > Appearance. Token-based: every color via CSS custom properties. Persist in localStorage. Zero-flash (stored theme applied before first paint). Dark palette: near-black surfaces (no pure #000/#fff), desaturated accents, WCAG AA contrast.

## Implementation spec

1. **Tokens**: current palette stays the light set on `:root`. Add `html[data-theme="dark"]` overrides for ALL color vars:
   - `--bg:#0d1117; --card:#161b22; --text:#e6edf3; --muted:#8b949e; --border:#30363d; --accent:#58a6ff; --bar-muted:#30363d;`
   - chips: `--danger-fg:#ff7b72; --danger-bg:#2b1519; --ongoing-fg:#56d364; --ongoing-bg:#10251a; --matured-fg:#8b949e; --matured-bg:#21262d; --watching-fg:#79c0ff; --watching-bg:#12233d;`
   - Also tune `.btn`/`input` backgrounds: inputs use `var(--card)`, readonly uses `var(--bg)` — verify no hardcoded #fff/#f8f9fa remains outside the token block (`grep -n "#fff\|#f8f9fa\|#111827" v5` must show ONLY :root light tokens and intentional inline chart swatches — update `.chart-legend` swatches to use `var(--bar-muted)`/`var(--accent)` instead of hex).
2. **System mode**: `html[data-theme="system"]` resolves through `@media (prefers-color-scheme: dark)` — define `html[data-theme="system"]` dark overrides inside the media query (same values as dark). Light mode = `html[data-theme="light"]` explicitly (re-declare light tokens so explicit light beats OS dark).
3. **Header switcher**: in the `.header-actions` of EVERY view, before the Hide amounts button, add a small 3-segment control: `System | Light | Dark` (buttons, class `theme-seg`; active segment styled with accent like `.btn.active`). One control per view header — they all stay in sync (same pattern as privacy toggles).
4. **Settings > Appearance**: new card at the TOP of Settings view (above Email): three radio rows — System (follow OS), Light (default), Dark — plus caption "Theme is saved on this device."
5. **JS** (inside the existing IIFE):
   - pre-paint bootstrap: a tiny separate `<script>` BEFORE the main `<style>`-using body renders — actually place it as the FIRST element in `<head>` after meta: read `localStorage.getItem('dk-theme')` (default 'system'), set `document.documentElement.setAttribute('data-theme', value)`; for 'system', also `matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ...)` to re-resolve live.
   - in main IIFE: clicking a segment/radio sets data-theme, saves to localStorage, syncs active states across all segments + radios.
6. **Everything else unchanged**: all v4 screens, tables, canonical sample data, captions, the privacy mask, the Add Position form — byte-for-byte same content where possible.

## Constraints

- Self-contained: inline CSS/JS only, NO external URLs/CDN/fonts.
- Same canonical sample set as v4; banned tokens stay banned: `Paisalo|Muthoottu|INDEL|KRAZYBEE|1037142|56227|111638|INE420C|INE101Q|Returned|Completed|Home Plan` — note `Returned/Completed` must NOT appear anywhere (they are forbidden display labels; do not even mention them in captions).
- Labels unchanged: Received ₹, Matured, My Holdings, Payouts, Watching, Add Position, Move to Portfolio, Hide amounts.

## Self-check (run all, paste into REPORT)

```
F=.IDE_Plans/design_drafts/ui_frontend_design_v5.html
wc -c "$F"
for m in 'data-theme' 'dk-theme' 'prefers-color-scheme' 'System' 'Appearance' "My Holdings" Payouts Watching Matured "Received ₹" "Add Position" "Move to Portfolio" "Hide amounts" "localStorage"; do printf '%s=%s\n' "$m" "$(grep -c "$m" "$F")"; done
grep -nE "Paisalo|Muthoottu|INDEL|KRAZYBEE|1037142|56227|111638|INE420C|INE101Q|Returned|Completed|Home Plan" "$F" || echo "BANNED: clean"
grep -nE "https?://|cdn\.|googleapis|unpkg|jsdelivr" "$F" || echo "EXTERNAL-REFS: clean"
python3 -c "import html.parser; html.parser.HTMLParser().feed(open('$F',encoding='utf-8').read()); print('HTML-PARSE: ok')"
diff <(sed 's/data-theme="dark"//' "$F" | wc -c) <(wc -c < .IDE_Plans/design_drafts/ui_frontend_design_v4.html) >/dev/null && echo "size-compare: similar" || wc -c "$F" .IDE_Plans/design_drafts/ui_frontend_design_v4.html
```

All markers ≥1, BANNED clean, EXTERNAL-REFS clean, HTML-PARSE ok. Then render proof yourself (chrome exists):

```
google-chrome --headless --disable-gpu --no-sandbox --screenshot=/tmp/v5_dark.png --window-size=1440,960 "file://$PWD/$F" 2>/dev/null; echo shot-ok
```

(That renders default/System on a light OS — fine; report `shot-ok`.)

## REPORT

File path + bytes, marker block, self-check outputs, screenshot line, one-line summary of what changed vs v4.

BLOCK if anything is ambiguous.
