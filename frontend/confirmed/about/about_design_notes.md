# About — Design Notes (LOCKED 2026-11-25)

## Flow
First open = not-checked minimal card -> Check for updates (manual) or automatic launch check -> popup ONLY on newer version -> Later/Remind persists (update/dismiss route + prefs). About content = 4 thin rows, no nested boxes.

## Rulings
1. Previous design rejected: bloated -> rebuilt clean/minimal (developer Q2).
2. Auto popup required; never shown on current version (verified against about.py + updater).
3. Title branding fixed (Goals leak).
4. Approved 2026-11-25.

## Research
- src/views/about.py (APP_VERSION, BUILD_NOTES, check_for_updates/store_update_result, /update/dismiss), src/updater.py.
- Release-popup-on-launch behavior = v1.0.10 three pillars (skill GOOD #10).
