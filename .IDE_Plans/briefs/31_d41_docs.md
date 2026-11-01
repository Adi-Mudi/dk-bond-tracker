# Brief 31 — D41 document addenda (PRD/SRS/AF v5)

Worker: wl-doc5. Work ONLY in cwd (fix-watchlist). NO git. Reply only REPORT.

## Truth
`../.IDE_Plans/dk_bond_tracker_brainstorm_20261030.json` → **D41** (CONFIRMED, read full text + WHY — it embeds the smoke/MCP evidence). Templates: `docs/PRD_DK_Bond_Tracker_addendum_v4.json`, `docs/SRS_DK_Bond_Tracker_addendum_v4.json`, `docs/Atomic_Functions_addendum_v4.json` (continue each id sequence after v4's max: FR after 61, SR after v4 max, AF after v4 max).

## Deliverables (3 files, same shape as their v4 templates)

1. `docs/PRD_DK_Bond_Tracker_addendum_v5.json` — extends v4. Change Record: D41 patch wave; supersedes nothing structurally (v4 FRs intact). New FRs (continue numbering), each citing D41: coupon/est-yield allow 00.00 (still reject empty/garbage/negative); explicit field labels (exact strings "Purchase date (start date)", "End date", "Credit day — when the amount is credited each month") on Move-to-Portfolio AND Add Position; move-path insert validation parity with /add (tenure>=1, credit bounds — named 400, no partial writes); invalid-row render recovery (row shows Invalid chip + Remove action, pages never 500 on bad row data); broker detail field (bonds column, candidate+move+add forms, watchlist column, holdings drawer display).
2. `docs/SRS_DK_Bond_Tracker_addendum_v5.json` — extends v4: precise verifiable statements for each FR above (parse rules for 00.00; label strings exact; validation-before-insert = zero rows written on rejection; Invalid chip rendering with HTTP 200 guaranteed; broker TEXT nullable, roundtrip candidate→holding; Remove re-validates server-side).
3. `docs/Atomic_Functions_addendum_v5.json` — extends v4: AFs — validate-percent-zero, validate-move-inputs (parity), render-health-safe (per-row catch), remove-invalid-position, broker-persist (5 surfaces).

## Self-check (paste)
`python3 -c "import json;[json.load(open(f)) for f in (3 files)];print('JSON ok')"`; FR/SR/AF dup-grep across family (declaration-level, must be empty); banned-token grep (Paisalo|Muthoottu|INE101Q|xlsm) empty; D41 cited ≥3× per file.

## REPORT
Files+bytes, id ranges, self-check outputs, one-line summary. BLOCK on ambiguity.
