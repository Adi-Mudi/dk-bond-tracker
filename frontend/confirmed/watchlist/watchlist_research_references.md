# Watchlist — Research References (Locked package)

## UI / UX research
- Material Design 3 — chips inline/scroll, small top app bar, content-first compact layouts (used for shell + filter rows). m3.material.io/components/chips, /components/top-app-bars
- Dense mobile list patterns — two-line rows (name + identifier), frozen identifier column, monospace IDs never truncated: setproduct.com data-table guide, jamesrossjr responsive tables (sticky first column + horizontal scroll), pixel-show dense dashboards (mono/tabular numbers).
- Typeahead/autocomplete pattern — predefined broker list + free-entry fallback (standard combobox behavior).
- Community handoff research (states/a11y/why-layer) for the 12-item lock checklist: storyflow.so, desisle.com, eleken.co, gfx-art.org, idealogic DoR.

## Backend logic mirrored (src/)
- `views/watch.py` — WATCH_FORM_FIELDS (16), FETCH_STATES (idle/checking/found/notfound/offline), ONLINE_FACT_FIELDS (auto-filled), watch_form_values validation, ERR-watch-dup duplicate rule.
- `db.py` — `watch_state` (holding|watching), `credit_day` (interest credit day), qty, watch_investment, broker/source fields.
- `status.py` / `alerts.py` — Danger derivation + rating-watch escalation (notification block).
- D43 shared ordering (AF-81 sort_key_appwide), extended by the developer 4-tier rule (Danger > Maturing > On-going > Matured).

## Stitch sources
- Final board screen: `82d410aa4aeb43a3b05fd4faf82174df` (project `17110477162175329772`), HTML-only export; edit chain retained in session (5 board iterations + page iterations superseded by single-file rule).
