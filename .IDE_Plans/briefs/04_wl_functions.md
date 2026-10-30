# Brief 04 — wl-funcs — Atomic Functions + Pseudocode addenda v3 (watchlist)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverables (EXACTLY TWO files): docs/Atomic_Functions_addendum_v3.json and docs/Pseudocode_addendum_v3.json
Zero comments. No git. Nothing else.

READ: brainstorm D33/D34; docs/Atomic_Functions_addendum_v2.json + docs/Pseudocode_addendum_v2.json (envelope/field/style contracts; existing AF ids run to AF-51); docs/Watchlist_Architecture_Addendum_v1.json if present (parallel worker — if absent, derive from D33/D34 + src/ which IS in this worktree: db.py, alerts.py, notifications.py, mailer.py, queries.py, app.py).

FILE 1 — Atomic_Functions_addendum_v3 envelope: {id: Atomic_Functions_addendum_v3, kind: atomic_function, version: "v1.0", status: draft, project: 01_excel_dashboard, extends: Atomic_Functions_addendum_v2, atomic_functions: [AF-52..AF-60], coverage_map: {...}, change_record}
AFs (full v1 field contract each: name,purpose,inputs,outputs,triggers,preconditions,postconditions,fr_refs,element,depends_on,check_method):
- AF-52 watchlist_query (element queries): filters+search+sort+density over bonds (watch_state split), returns rows w/ computed next-payout + maturity countdown; fr_refs [FR-41]; deps [AF-01].
- AF-53 watchlist_summary (element queries): 4 stat tiles; fr_refs [FR-41]; deps [AF-52].
- AF-54 position_detail_drawer (element route_handlers): facts + schedule + actions payload; fr_refs [FR-42]; deps [AF-52].
- AF-55 move_to_holdings (element validators? route_handlers): watching->holding transition (validates D15 lock still — moving INTO holdings must re-check active-position lock; block with ERR-move-watching); fr_refs [FR-39]; deps [AF-39, AF-52].
- AF-56 watchlist_alerts_feed (element notifications): merge overdue/due-soon/maturity-soon cards with dedupe keys; fr_refs [FR-43]; deps [AF-46, AF-47].
- AF-57 settings_load (element queries): read alert_prefs keys + env-override merge (effective config view); fr_refs [FR-44, FR-45, FR-46]; deps [AF-01].
- AF-58 settings_save (element route_handlers): per-section upsert to alert_prefs; App Password write-once (blank keeps old); validate port/cycle enums; fr_refs [FR-44, FR-45, FR-46]; deps [AF-57].
- AF-59 test_email_send (element route_handlers): build synthetic event -> mailer.send_alert_email; surface ERR-smtp-unconfigured/ERR-test-email visibly; fr_refs [FR-44]; deps [AF-58, AF-48].
- AF-60 reset_and_backup (element route_handlers): DB file backup download; reset requires typed 'RESET' then re-init empty schema; fr_refs [FR-47]; deps [AF-01].
coverage_map EXACT keys: FR-39:[AF-55], FR-40:[AF-52] (field set consumed by query — plus note import maps in AF-03 addendum? NO - keep [AF-52]), FR-41:[AF-52,AF-53], FR-42:[AF-54], FR-43:[AF-56], FR-44:[AF-57,AF-58,AF-59], FR-45:[AF-57,AF-58], FR-46:[AF-57,AF-58], FR-47:[AF-60], FR-48:[] -> hmm FR-48 About is static: give FR-48:[AF-57], FR-49:[AF-52] ... FINAL: keys FR-39..FR-49 each non-empty EXCEPT none: map FR-38:[AF-52]? FR-38 is shell — static UI: still give [AF-54]? Cleaner: FR-38 -> ['AF-57']? USE JUDGEMENT: every key FR-38..FR-49 must exist and be non-empty; justify in change_record. (FR-40 import mapping: add AF-61? NO — keep 52-60; FR-40 -> [AF-52] as the read model.)

FILE 2 — Pseudocode_addendum_v3 envelope: {id: Pseudocode_addendum_v3, kind: pseudocode, version: "v1.0", status: draft, project: 01_excel_dashboard, extends: Pseudocode_addendum_v2, entries: [AF-52..AF-60 in order], d5_rule: <exact quote from Pseudocode_DK_Bond_Tracker_v1.json>}
Entry style per prior addenda: INPUT:/OUTPUT:/ERRORS: + numbered steps + complexity_note + edge_cases.
Highlight: AF-55 lock re-check on move; AF-57 env>stored precedence matrix; AF-58 write-once password; AF-60 RESET confirm + backup-before-wipe; AF-56 dedupe keys.

SELF-CHECK: AF ids exactly AF-52..AF-60 disjoint from AF-01..51; deps reference only real AFs; coverage keys exactly FR-38..FR-49 all non-empty; entries ids match AF list in order with INPUT/OUTPUT/ERRORS; d5_rule exact quote match vs v1 pseudocode doc.
REPORT: paths, AF table (id/name/wave? skip wave), coverage summary, self-check output.
