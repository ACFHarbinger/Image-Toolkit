# Round 6: redo the Tauri UI to classic parity

Roles from 2026-10-27: Codex is out (usage). **Claude reviews, makes final edits and merges.** **Grok leads investigation and triage and delegates on the bus.** Grok and Gemini each run a swarm, in parallel. Mistral and others take what Grok hands out.

Evidence: `.agent/reports/parity/cross_check_2026-10-27.md`. Every Tauri page is partial; none has parity. Ledger rows stay `pyside-only` until parity is real.

## Decision

**Keep** the catalog ids, the JSON-RPC contracts, and the sidecar methods that already do real work: `convert.convert`, `merge.concatenate`, wallpaper set and slideshow, `extractor.probe`, the desk reads, and the HIE and CSG calls that reach a solver.
**Delete** the current desk-form pages as the product UI. Each page is deleted in the PR that replaces it, never earlier.
**Build** a new shell that follows the classic shape: category, tab, subtab, gallery, inspector.

## Work packages

| WP | Content | Owner swarm |
|---|---|---|
| 1 | Session and chrome: a window navigated by the 33 classic routes; shared folder picker, thumbnail gallery, selection, progress, cancel; the C++ vault session as the process that holds the database key (the React login flag is not that session) | **Grok** |
| 2 | System tools as the Qt workflows: directory batch for convert, codec and sampler; merge queue plus a real placement canvas; similarity directory scan; extractor video actions then image-sheet extras; wallpaper monitor graph after the static apply path | **Grok** |
| 3 | Library on a live store: listings editors, search with preview, scan that writes, management, data browser; preview wired to those galleries | **Grok** |
| 4 | Web and cloud: crawler that downloads, drive sync that authenticates, media loader that fetches, entity recon with an engine, cloud submit that reaches a provider | **Gemini** |
| 5 | Canvases: stitch's eight panels on the real workers; manga scribble, sequence and ARAP; hybrid editor viewport | **Gemini** |
| 6 | Deep learning (training, generation, evaluation, inference, ComfyUI as separate tools), then the settings window (account, profiles, gallery, logging, shortcuts) | **Gemini** (DL, ComfyUI); settings goes to **Grok** because it sits on WP1 |

## Order (parallel where it can be)

**Phase 1, now, both swarms at once**
- Grok: WP1 (shell, shared components, vault session). Everything on the Grok side waits for this.
- Gemini: the headless halves of WP4, WP5 and WP6: live engines and workers behind the existing sidecar methods or new ones, with tests and fakes, and no new UI. Stitch workers, manga solvers, HIE viewport data, DL run control, crawler, media loader, entity recon engine.

**Phase 2, after WP1's shared components land**
- Grok: WP2 and WP3 pages (WP3 also needs the vault session from WP1).
- Gemini: pages for WP4, WP5, WP6 on the new shell.

**Phase 3**
- Settings window (needs WP1 and the vault session).
- Cloud submit to a provider: needs Gate A's PASS and Gate B (#834 to #840), and any live or paid provider run needs Harbinger's explicit authorization. Build against the fake provider only until then.
- Delete the old desk-form pages, close parity gaps, then ledger sign-off row by row (Harbinger's checklist).

## Blockers to respect

- **Library, scan-write, management and data browser** need the C++ vault session from the T6 decision. Do not build them on the React login flag.
- **Drive sync and cloud credentials** need the vault from WP1.
- **Cloud submit** needs `cloud_service` set and Gate B.

## Missing features still to be found

The cross-check was a read-only pass; more features may be missing. Every agent, while working a page, compares the classic widget against the Tauri page and posts each gap on the bus as one line starting `PARITY-GAP <row-id>:` (use `PARITY-GAP?` if unsure) and adds it to `.agent/reports/parity/<row-id>.md`. **Grok reads the bus, merges duplicates, sizes the gaps and delegates with `PARITY-ASSIGN <row-id> -> <agent>` lines.** Take only what is assigned. Grok decides which gaps are real; Harbinger has the last word.

## Cleanup work that stays in this round

- **Grok:** `cargo` build and test, the GUI suite, lychee; triage of the 54 issues moved from the old repos (#1050 to #1103); review of the Dependabot and pixi PRs.
- **Gemini:** `tsc` and vitest clean, `ruff` on the moved stitching code, the three failing stitching tests, a `backend/` C++ build, reconcile the two HIE views, salvage `feat/w0-03-submodule-services` and `feat/a01-wallpaper`.

## Rules

- One PR per item against `main`. Claim on the bus first. No stacking.
- Run `tsc`, vitest on touched files, contracts, docs freshness, ledger and import-linter before pushing. Read merged TypeScript and `server.py`; auto-merge has corrupted them twice.
- Python stays Qt-free; no top-level `numpy`, `cv2` or `PIL` imports in service code (the staged sidecar has none).
- Post results as: what changed, what was run, what was not run.
- Claude reviews every PR before it lands and may push final edits to the branch.
