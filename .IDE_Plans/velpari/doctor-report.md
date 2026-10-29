# Velpari Doctor Report

Summary: 28 OK, 82 warnings, 38 errors, 32 info.

❌ Please fix the errors above. Each error item carries a `→ Fix:` hint.

## Action items

❌ Artifact frontmatter: PRD (grouped) missing frontmatter field(s): supersedes, sunset, deprecatedAt. → Fix: Republish the artifact: re-run its stage command, then `/velpari-rtm-approve` — frontmatter is auto-injected at publish time.
❌ Artifact frontmatter: brainstorm-currently-the-data-is-stored-in-an-xlsm-workbook-i-am-considerin.md (grouped) missing frontmatter field(s): supersedes, sunset, deprecatedAt. → Fix: Republish the artifact: re-run its stage command, then `/velpari-rtm-approve` — frontmatter is auto-injected at publish time.
⚠️ Multiplexer (required for /velpari-brainstorm v2.1): zellij known bug [pi-interactive-subagents Issue #19]: `zellij action close-pane` closes the FOCUSED pane, not the target.
❌ Web-tool lock: web-research (web-research.md) carries web tool(s): websearch, fetchurl. Only the `web-search-agent` agent may reach the web.
❌ Web-tool lock: Web-tool lock: 1 violation(s) across 10 agent file(s).
❌ Agent file integrity: doc-code-analyst.md: unknown tool(s) in `tools:`: glob → Fix: Fix the typo or remove the unknown tool.
❌ Agent file integrity: Agent file integrity: 1 error(s), 0 warning(s) across 10 file(s).
⚠️ Scout agents (.pi/agents/): rtm-requirement-tracer.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): rtm-test-case-linker.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): rtm-coverage-analyzer.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): rtm-consolidator.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): feasibility-tech.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): feasibility-schedule.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): feasibility-cost.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): feasibility-risk.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-style-selector.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-module-decomposer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-contract-definer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-data-flow-mapper.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-error-definer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-reviewer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): af-source-rtm.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): af-source-design.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): af-source-prd.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): af-source-feas.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): reviewer.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): pseudo-algorithm-extractor.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): pseudo-edge-case-handler.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): pseudo-complexity-analyzer.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): pseudo-consolidator.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): pseudocode-reviewer.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): testplan-strategy-designer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): testplan-unit-test-generator.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): testplan-integration-test-generator.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): testplan-coverage-tracer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): testplan-reviewer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): do-topology.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): do-risk.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): do-test.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): do-value.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-consistency-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-coverage-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-contract-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): design-finalizer.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): logging-standards-researcher.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): logging-architecture-designer.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ Scout agents (.pi/agents/): logging-compliance-mapper.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging. → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
❌ Stage skills: skills/velpari-brainstorm.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-prd.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-rtm.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-feasibility.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-architecture-generator.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-design.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-pseudocode.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-testplan.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-atomic-function.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-development-order.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-configure-requirements.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Stage skills: skills/velpari-design-logging.md MISSING → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ Official-extension readiness: package.json missing or unreadable at project root. → Fix: package.json is missing at the project root. Run doctor from inside the pi-velpari repo, or restore the file.

## Setup progress

✅ 1. Project files configured — done
✅ 2. Brainstorm completed — done
ℹ️ 3. PRD drafted — pending
   → Fix: Run `/velpari-prd` (after brainstorm).
ℹ️ 4. RTM built — pending
   → Fix: Run `/velpari-rtm` (after PRD).
ℹ️ 5. Requirements profile configured — pending (optional)
   → Fix: Run `/velpari-configure-requirements`.
✅ 6. First approve done — ready for the pipeline
ℹ️ Next: Run `/velpari-prd` (after brainstorm).

## Run state

✅ Run: 2026-09-27T13-04--currently-the-data-is-stored-in
   - Mission: "Currently, the data is stored in an XLSM workbook. I am considering migrating it to a SQLite database with a lightweight front end. My main goal is to have a solution that is easy to maintain, scalable as the data grows, and simple to work with in the future.

What would be your recommendation? Which approach would be the most practical and user-friendly?"
   - Current stage: drafting-prd
   - History entries: 3

## Config

✅ Config: VALID (projectName="DK_Bond_Tracker")

## Requirements profile

ℹ️ Profile: MISSING (run /velpari-configure-requirements)
   → Fix: Run `/velpari-configure-requirements` to capture the requirements profile.

## Doc/ artifacts

✅ 2 markdown file(s) under Doc/.
   - - brainstorm/brainstorm-currently-the-data-is-stored-in-an-xlsm-workbook-i-am-considerin.md
   - - requirements/PRD_DK_Bond_Tracker.md

## Grouped / legacy paths

✅ PRD: grouped (preferred layout)
   - path=/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/Doc/requirements/PRD_DK_Bond_Tracker.md
ℹ️ RTM: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ feasibility-study: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ design: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ pseudocode: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ test-plan: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ test-cases: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ atomic-functions: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).
ℹ️ development-order: missing (not yet produced by this run).
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).

## Working / published separation

✅ Working copies: 0 | Published docs: 2
   - Grouped categories (11): 
   - Project under audit: DK_Bond_Tracker

## PSRS validation

✅ PSRS validation (grouped): OK
   - PSRS validation: 0 error(s), 0 warning(s). Sections present: 20/20. FRs: 24 | NFRs: 13 | Helpers: 9 | Open questions: 3.
Document type: product-software-requirements | Version: 1.0.0 | Status: draft
Profile: basic@1.0.0 | Mission: "Currently, the data is stored in an XLSM workbook. I am considering migrating it to a SQLite database with a lightweight front end. My main goal is to have a solution that is easy to maintain, scalable as the data grows, and simple to work with in the future. What would be your recommendation? Which approach would be the most practical and user-friendly?" | Project: DK_Bond_Tracker

## RTM traceability

ℹ️ RTM not found — skipping traceability check.
   → Fix: Run `/velpari-rtm` after the PRD stage.

## Artifact frontmatter

❌ PRD (grouped) missing frontmatter field(s): supersedes, sunset, deprecatedAt.
   - Path: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/Doc/requirements/PRD_DK_Bond_Tracker.md
   → Fix: Republish the artifact: re-run its stage command, then `/velpari-rtm-approve` — frontmatter is auto-injected at publish time.
❌ brainstorm-currently-the-data-is-stored-in-an-xlsm-workbook-i-am-considerin.md (grouped) missing frontmatter field(s): supersedes, sunset, deprecatedAt.
   - Path: /mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/Doc/brainstorm/brainstorm-currently-the-data-is-stored-in-an-xlsm-workbook-i-am-considerin.md
   → Fix: Republish the artifact: re-run its stage command, then `/velpari-rtm-approve` — frontmatter is auto-injected at publish time.

## RTM data sidecar

ℹ️ RTM not found — skipping data sidecar check.
   → Fix: Run `/velpari-rtm` after the PRD stage.

## Trace-link fingerprints

ℹ️ Fingerprint check skipped — needs both the published PSRS and the RTM JSON sidecar.
   → Fix: Re-run `/velpari-rtm` (update mode) so the working copy gains the JSON sidecar, then `/velpari-feasibility-approve`.

## Phase consistency (PRD ↔ RTM)

ℹ️ Phase consistency check skipped — needs both the published PSRS and the RTM JSON sidecar.
   → Fix: Re-run `/velpari-rtm` (update mode) so the working copy gains the JSON sidecar, then `/velpari-feasibility-approve`.

## MVP coverage

ℹ️ MVP coverage check skipped — needs the published PSRS (with Phase column) and the RTM JSON sidecar.
   → Fix: Re-run `/velpari-rtm` (update mode) so the working copy gains the JSON sidecar, then `/velpari-feasibility-approve`.

## Feasibility v2

ℹ️ No published feasibility study yet.
   → Fix: Run the matching stage command to generate this artifact (e.g. `/velpari-prd`).

## Stale downstream artifacts

✅ No published artifact pairs to compare yet.

## Sequence hardening

✅ Stage gate: 9/9 stage commands gated.
✅ tool_call stage guard: 9 in-progress stage(s) locked to their run folder.
✅ Run lock: free.

## Multiplexer (required for /velpari-brainstorm v2.1)

✅ Multiplexer detected: zellij (env: ZELLIJ_PANE_ID)
   - Required for /velpari-brainstorm v2.0 visible subagents.
✅ pi-interactive-subagents: 3.7.2
⚠️ zellij known bug [pi-interactive-subagents Issue #19]: `zellij action close-pane` closes the FOCUSED pane, not the target.
   - During the brainstorm stage, do NOT manually focus a subagent pane. cmux/tmux/wezterm are not affected.
   - cmux/tmux/wezterm are not affected.

## Sub-agent extension

✅ pi-interactive-subagents 3.7.2 installed (≥ 3.7.2).

## Stray files

✅ No stray tmp_* helper files in project root or runs/.

## Web-tool lock

❌ web-research (web-research.md) carries web tool(s): websearch, fetchurl. Only the `web-search-agent` agent may reach the web.
   - Having two agents reach the web confuses the orchestra about who owns external knowledge.
   - Remove `websearch`, `fetchurl` from the agent's `tools:` list, or rename the agent to `web-search-agent`.
❌ Web-tool lock: 1 violation(s) across 10 agent file(s).

## Agent file integrity

❌ doc-code-analyst.md: unknown tool(s) in `tools:`: glob
   - Known tools: askuserquestion, bash, edit, fetchurl, find, grep, intercom, ls, read, subagent, taskcreate, taskexecute, taskget, tasklist, taskoutput, taskstop, taskupdate, websearch, write
   → Fix: Fix the typo or remove the unknown tool.
❌ Agent file integrity: 1 error(s), 0 warning(s) across 10 file(s).

## Scout agents (.pi/agents/)

✅ extractor.md (brainstorm) frontmatter OK
✅ prd-checker.md (brainstorm) frontmatter OK
✅ rtm-checker.md (brainstorm) frontmatter OK
✅ web-search-agent.md (brainstorm) frontmatter OK
✅ fr-extractor.md (prd) frontmatter OK
✅ nfr-checker.md (prd) frontmatter OK
✅ helper-detector.md (prd) frontmatter OK
✅ consolidator.md (prd) frontmatter OK
⚠️ rtm-requirement-tracer.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ rtm-test-case-linker.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ rtm-coverage-analyzer.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ rtm-consolidator.md (rtm) MISSING — will auto-bootstrap on first /velpari-rtm.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ feasibility-tech.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ feasibility-schedule.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ feasibility-cost.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ feasibility-risk.md (feasibility) MISSING — will auto-bootstrap on first /velpari-feasibility.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-style-selector.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-module-decomposer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-contract-definer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-data-flow-mapper.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-error-definer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-reviewer.md (architecture-generator) MISSING — will auto-bootstrap on first /velpari-architecture-generator.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ af-source-rtm.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ af-source-design.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ af-source-prd.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ af-source-feas.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ reviewer.md (atomic-function) MISSING — will auto-bootstrap on first /velpari-atomic-function.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ pseudo-algorithm-extractor.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ pseudo-edge-case-handler.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ pseudo-complexity-analyzer.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ pseudo-consolidator.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ pseudocode-reviewer.md (pseudocode) MISSING — will auto-bootstrap on first /velpari-pseudocode.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ testplan-strategy-designer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ testplan-unit-test-generator.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ testplan-integration-test-generator.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ testplan-coverage-tracer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ testplan-reviewer.md (testplan) MISSING — will auto-bootstrap on first /velpari-testplan.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ do-topology.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ do-risk.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ do-test.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ do-value.md (development-order) MISSING — will auto-bootstrap on first /velpari-development-order.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-consistency-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-coverage-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-contract-checker.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ design-finalizer.md (final-design) MISSING — will auto-bootstrap on first /velpari-final-design.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ logging-standards-researcher.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ logging-architecture-designer.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
⚠️ logging-compliance-mapper.md (design-logging) MISSING — will auto-bootstrap on first /velpari-design-logging.
   → Fix: Run any `/velpari-<stage>` command to trigger auto-install, or place the file manually at `.pi/agents/<id>.md`.
ℹ️ Scout agents summary: 48 scouts across 11 stages (brainstorm, prd, rtm, feasibility, architecture-generator, atomic-function, pseudocode, testplan, development-order, final-design, design-logging) — 40 missing, 0 with bad frontmatter.

## Agent mapping (agents.json)

ℹ️ No agents.json — all 42 roles use bundled defaults.

## Stage skills

❌ skills/velpari-brainstorm.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-prd.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-rtm.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-feasibility.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-architecture-generator.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-design.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-pseudocode.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-testplan.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-atomic-function.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-development-order.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-configure-requirements.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
❌ skills/velpari-design-logging.md MISSING
   → Fix: Restore the skill markdown from the bundled `skills/` directory or git history.
ℹ️ Stage skills summary: 12 checked (brainstorm, prd, rtm, feasibility, architecture-generator, design, pseudocode, testplan, atomic-function, development-order, configure-requirements, design-logging), 12 contract issue(s).

## Secret scan (NFR-04)

✅ No secrets detected across 13 file(s) in 4 locations.

## Official-extension readiness

❌ package.json missing or unreadable at project root.
   → Fix: package.json is missing at the project root. Run doctor from inside the pi-velpari repo, or restore the file.

## Available scans (SCAN gate)

ℹ️ Scan "code" is NOT available. Reason: no codePaths configured in files.json.
ℹ️ Scan "doc" is NOT available. Reason: no inputDocuments configured in files.json.
✅ Scan "community" is available.
ℹ️ SCAN-gate picker will offer: community. The developer always chooses (v2.1: no default).

## Sub-agent generator completeness

ℹ️ extractor: bundled default (extractor.md) — run /velpari-generate-sub-agents to produce a project-specific copy.
ℹ️ prd-checker: bundled default (prd-checker.md) — run /velpari-generate-sub-agents to produce a project-specific copy.
ℹ️ rtm-checker: bundled default (rtm-checker.md) — run /velpari-generate-sub-agents to produce a project-specific copy.
ℹ️ web-search-agent: bundled default (web-search-agent.md) — run /velpari-generate-sub-agents to produce a project-specific copy.
✅ Sub-agent generator summary: 4 brainstorm role(s) checked (current generator v1); 0 error(s), 0 warning(s).

## Design readiness (Phase 1)

ℹ️ No design artifact yet (readiness check skipped).

## Shape compatibility

ℹ️ Path: fresh (no prior designs published).

## Logging plan (Doc/observability/logging-plan_<project>.md)

ℹ️ Logging plan: MISSING (optional — no compliance overlay active).
   → Fix: Optional: run /velpari-design-logging to produce a logging architecture plan at Doc/observability/logging-plan_<project>.md.
