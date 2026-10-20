### Target Issue
<!-- Required. Exactly one issue number, e.g. Closes #123 -->
Closes #

### Component Impacted
<!-- Exactly one of the values below. Must match a Project Board "Component" option verbatim. -->
- [ ] Core: C++ Base
- [ ] Core: Python Backend
- [ ] UI: PySide6
- [ ] UI: Tauri Desktop
- [ ] UI: Mobile

### Priority
<!-- Exactly one of the values below. Must match a Project Board "Priority" option verbatim. -->
- [ ] Tier 1: Core Engine
- [ ] Tier 2: QA Prototype
- [ ] Tier 3: Production App
- [ ] Tier 4: Backburner

### Summary of Changes
<!-- What changed and why, in 1-3 bullet points. -->
-

### Dependencies
<!-- Other issues/PRs this depends on, or that depend on this. "None" if not applicable. -->

### Migration Guardrails (W0-20)
<!-- Required while both shells ship. See AGENTS.md. -->
- [ ] This PR does not add or change UI under `gui/src` (reviewed bugfixes only) — or the exception is recorded in `migration/features.toml`
- [ ] Schema changes are additive-only; no `DROP`/`RENAME`/column-type change against a live PySide6 table — or a bounded exception is recorded in `migration/features.toml`

### Test Plan
<!-- Bulleted checklist of how this was verified. -->
- [ ]

### Agent Declaration
<!-- Filled by the authoring agent. Leave "manual" if a human wrote this PR. -->
- Author: <!-- agent | manual -->
- Model / Agent ID: <!-- e.g. claude-sonnet-5, or "n/a" -->
- Autonomous: <!-- yes | no -->
