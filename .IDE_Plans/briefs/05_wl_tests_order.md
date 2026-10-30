# Brief 05 — wl-tests — Test Plan + Development Order addenda v3 (wave 2)

Workspace: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/fix-watchlist
Deliverables (EXACTLY TWO files): docs/Test_Plan_addendum_v3.json + docs/Development_Order_addendum_v3.json
Zero comments. No git. Nothing else.
WAIT: only start after PM prompts you (wave 2 — PRD/SRS/arch/AF must exist first).

READ when starting: docs/PRD_DK_Bond_Tracker_addendum_v3.json, docs/SRS_DK_Bond_Tracker_addendum_v3.json, docs/Watchlist_Architecture_Addendum_v1.json, docs/Atomic_Functions_addendum_v3.json, docs/Development_Order_addendum_v2.json (envelope + existing wave structure; existing TC ids run to TC-84; AF ids to AF-60).

FILE 1 — Test_Plan_addendum_v3 envelope: {id: Test_Plan_addendum_v3, kind: test_plan, version: "v1.0", status: draft, project: 01_excel_dashboard, extends: Test_Plan_addendum_v2, test_cases: [...], test_bindings: [...], change_record, strategy}
test_cases TC-85..TC-104 (EXACTLY 20): cover every FR-38..FR-49 (>=1 each): shell/status-bar counts (TC), tab switch + move-to-holdings incl. D15-lock block on move (TC-xx lock conflict), field persistence + yield-label, filter/sort/density, drawer payload, alerts feed dedupe + dismissal keeps history, SMTP save masked/write-once + env override precedence, test-email unconfigured named error, alert prefs toggles, general prefs (default credit day validation 1-28), import Excel new fields mapping, backup download + reset typed-confirm wrong-word rejection, privacy mask on watchlist+settings, status bar email indicator, maturity 30/7/1 scan + dedupe, offline scan (no new network imports), performance: watchlist_query 150x96 < 0.5s LOCAL, end-to-end: add -> watch -> move -> pay -> alert chain. Types from enum; level LOCAL (at most 1 REMOTE owner-manual with justification).
test_bindings: >=1 per FR-38..FR-49 (requirement_id = FR id exactly; covers full|partial).

FILE 2 — Development_Order_addendum_v3 envelope: {id: Development_Order_addendum_v3, kind: development_order, version: "v1.0", status: draft, project: 01_excel_dashboard, extends: Development_Order_addendum_v2, wave_insertions: [...], topology_note, change_record}
Place AF-52..AF-60 topo-correctly into existing waves W0-W7 (deps: AF-01 W0, AF-39 W2, AF-38/47/48 W4, AF-46 W2): suggested: AF-52/53 W3 (query), AF-54 W4, AF-55 W4, AF-56 W4, AF-57/58/59 W4 (settings), AF-60 W5 — VERIFY topo yourself (dep wave <= own wave), adjust if needed. Assign all TC-85..104 disjoint across the insertion waves by scenario (test_gate_map with TC titles verbatim from file 1). topology_note: every edge's inequality stated.

SELF-CHECKS: TC ids exactly TC-85..TC-104 sequential; enums valid; bindings == FR-38..49 coverage exact; AF ids exactly AF-52..60, disjoint from AF-01..51, deps real; topo inequalities hold; every TC placed once; titles match verbatim.
REPORT: paths, TC list (one-liners), wave table, self-check output.
