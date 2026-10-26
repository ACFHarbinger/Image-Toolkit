# Round 6: parity audit, remaining Tauri work, CI repair

Roles from 2026-10-27: Codex is out (usage). **Claude reviews, makes final edits and merges.** **Grok** leads investigation and triage and delegates on the bus; Grok and Gemini each run a swarm, in parallel. Mistral and the others take rows Grok hands out.

## Why this round exists

The Tauri pages were built from the new UI, which was never checked against the PySide6 app. Features the old app has may be missing. A ledger row cannot become `pyside-deleted` until its parity gaps are zero or explicitly accepted by Harbinger.

## Parity audit (both swarms, in parallel)

For every ledger row you own (list below), compare the PySide6 original (`pyside` paths in `migration/features.toml`) with the Tauri view, control by control:

- every button, field, menu, shortcut, drag/drop target, context menu, setting and persisted option
- every background action (daemons, workers, progress, cancel, error states)
- every keyboard and accessibility behaviour

Write one file per row: `.agent/reports/parity/<row-id>.md` with a table `item | PySide6 | Tauri | status (ok / missing / differs)`. Do not fix anything while auditing.

**Mark every gap on the bus**, one line each, starting with `PARITY-GAP <row-id>:` and a one-sentence description. Anything you are unsure about gets `PARITY-GAP? <row-id>:`. Do not leave a gap only in your report file.

**Grok triages.** Grok reads the bus, merges duplicates, decides which gaps are real, sizes them, and delegates them by posting `PARITY-ASSIGN <row-id> -> <agent>` lines. Agents take only what was assigned to them, one PR per gap or per row, against `main`, no stacking. Gaps Grok rejects are listed in the row's report as `accepted-by-grok`; Harbinger has the final word.

## Work split

### Grok swarm
Audit: `library.listings`, `library.search`, `library.preview`, `library.scan`, `library.management`, `library.data-browser`, `system.convert`, `system.merge`, `system.similarity`, `system.extractor`, `cloud.jobs`, `window.settings`, `window.auth`, `window.logging`, `developer.logs`, `developer.metadata`, `window.cloud-compute`.
Build:
- Placement canvas (Merge) and frame-slice canvas (Extractor) on the shared canvas host (#1001); both still on PySide6.
- Triage and delegation of all `PARITY-GAP` lines (Grok's own job, ahead of building).
CI repair: `cargo` build and test, the GUI pytest suite, lychee (links to archived repos and `moon/` paths).

### Gemini swarm
Audit: `web.crawler`, `web.requests`, `web.drive-sync`, `web.media-loader`, `web.reverse-search`, `web.entity-recon`, `dl`, `system.wallpaper`, `stitch`, `editor.hybrid`, `manga.colorization`, `manga.animation`, `manga.puppeteering`, `developer.benchmarks`.
Build:
- Reconcile the two HIE editor views (`HieEditorTab` is wired; `HieEditorView` is not).
- Review `feat/w0-03-submodule-services` and `feat/a01-wallpaper` (pushed as WIP): salvage, make `cv2`/`numpy` imports lazy, open PRs or delete.
CI repair: `tsc` and `vitest` clean, `ruff` on the moved stitching code (about 143 findings), the three failing stitching tests (`test_audit_recomputes_strip_banding`, `test_gui_progress_pipeline_still_subclasses_without_session_override`, `test_compute_all_metrics_emits_strip_banding`), and configure and build `backend/` once (C++ test CMake paths now point to `backend/src/asp`).

### Shared
- The 54 issues moved from the old repos (#1050 to #1103): Grok triages on the bus (keep, fold into the roadmap, or close); no agent starts one without an assignment.
- Dependabot and pixi PRs (#1004, #1006, #1007, #1032, #1048, #1049, #1104): Grok reviews, Claude merges.

## Rules

- One PR per item against `main`. Claim on the bus before editing.
- Run `tsc`, vitest on touched files, contracts, docs freshness, ledger and import-linter before pushing. Auto-merges of TypeScript and `server.py` have corrupted code twice: read the merged result.
- Python stays Qt-free and lazy on `numpy`, `cv2`, `PIL` imports at module level (the staged sidecar has none of them).
- No behaviour changes in cleanup PRs. Do not touch another agent's uncommitted worktree.
- Post results on the bus as: what changed, what was run, what was not run.
- Claude reviews every PR before it lands and may push final edits to the branch.

## Not in this round

Cloud Jobs gates A to G (#824 track), the OS checks (Harbinger's checklist), and the PySide6 deletion (#921), which waits for zero `pyside-only` rows or recorded exceptions.
