# Dispatch and delivery review — 2026-10-26

Base: `origin/main` at `5ad85c5f9`. Read the October 25–26 bus, including the WIP warning and latest team handoffs. No merges or branch deletions performed.

## Fixes

`fix/codex-oct26-review`:

- Sidecar: every catalog method has a route. Removed the second traversal of system-page handlers; retained `_UNHANDLED` so a legitimate `None` result does not fall through. Added late-route/None-result regression coverage.
- Wallpaper: daemon translates contract styles into desktop names while preserving Qt style names; discovers monitors when bridge config has no Qt geometry; repeated Start retains the live process.
- Wallpaper view restores verified running state and offers Stop after reopening.
- Includes reviewed #1033 and #1034 repairs: one Rust settings module declaration, deduplicated catalog-view code, correctly typed manga mocks.

Pushed separately on `feat/w0-03-submodule-services`:

- `9e19a729a`: lazy ASP/CSG image dependencies; uint32 CSG luminance arithmetic; exclusive output temporary file, preserving pre-existing `.partial` files/symlink targets.
- `d2f01d474`: HIE refuses media export when IPC only supplies a document description; preserves existing output instead of writing JSON under an image extension.
- `2b5ddaa0d`: CRE indexes through the canonical embedding model instead of incompatible SHA-derived vectors. Missing embedder fails before insertion. Tests inject an embedder; no model download/inference.
- ASP rejects a delegate without a runnable operation instead of reporting success.

## Disposition

| Delivery | Review result |
|---|---|
| `feat/a01-wallpaper` (`ce226376d`) | Superseded by landed #1026/#1031. Do not merge unchanged: lacks `running` config projection and presenter integration now on main. Its service tests pass, but the integration defects above required follow-up fixes. |
| `feat/w0-03-submodule-services` | Safety fixes pushed. Remains WIP: reconcile with landed HIE/CSG before landing. In particular, preserve main's editor session/export safeguards and CSG delegate wiring; do not replace them wholesale with the old branch. |
| Grok #1033 (`69d2cc237`) | No introduced defect found; duplicate module removal builds and six selected window-registry tests pass. Included in follow-up branch. |
| Mistral #1034 (`7a95b73a7`) | No introduced defect found; TypeScript and 10 manga tests pass. Included in follow-up branch. |
| Gemini #1040 (`728b3a555`) | Docs/ledger-only; no actionable issue found. Docs freshness and ledger pass. |
| Gemini #1041 (`c439b54f4`) | No actionable introduced issue found in the ASP sync; service, registration-gate and canvas checks pass. No corpus/benchmark run. |
| Dependabot #1004 (`3e80aee12`) | No actionable issue found in Happy DOM patch/lock update. Exact 21.0.4 installation and DOM smoke pass. |
| Dependabot #1005 (`5c3fb3e69`) | No actionable issue found in Vite patch updates. Both clean installs pass; dev app builds. HIE build fails on missing optional embed dependencies and absent JSX configuration; same failures reproduce with base manifests/lockfile. Not a clean HIE build sign-off. |
| Dependabot #1006 (`484eafb84`), #1007 (`93418df0f`) | No actionable issue found in the transitive lock updates. Tested together: clean install, extension TypeScript check and Chrome production build pass. |

## Validation

Individual targeted files/checks only:

- Follow-up: server 18; stdio sidecar 14; wallpaper service 13; slideshow bridge config 5; CSG delegate 6; wallpaper/presenter UI 11.
- WIP: ASP 11; CSG 11; safety 3; HIE 14; CRE 10.
- ASP sync: service 9; registration gate 2; canvas 46.
- Original wallpaper branch: service 11.
- Grok: six selected Rust window-registry tests. Mistral: 10 manga UI tests and TypeScript.
- Follow-up TypeScript, Ruff on changed Python, whitespace, contract regeneration check (37 outputs), docs freshness, migration ledger and Tauri security pass. #1040 docs/ledger and #1041 docs/ledger/contracts also pass.

No full suites, benchmarks, model inference, provider calls or live desktop wallpaper/tray verification. OS checklist boxes and Gate B remain unchanged. Scratch build logs are under `~/Downloads/Data/Tests/oct26-dependabot/`.
