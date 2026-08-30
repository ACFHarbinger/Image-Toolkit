# Image-Toolkit v1.0.0 — release plan

**Date:** 2026-08-31
**Owner (coordination):** Claude, via `.agent/bus/`
**Team:** Claude, Gemini (Agy), Grok, Chat (Codex), DeepSeek (OpenCode harness),
OpenCode (GLM 5.3)

## Harbinger decisions (2026-08-31)

| Question | Decision |
|---|---|
| Git divergence | **Investigated** (`main_divergence_investigation_2026-08-31.md`): `origin/main` had zero unique content, was a pre-blob-strip snapshot 6 days stale. **Force-pushed** — `origin/main` now == local `main` (`da54f66f`). Done. |
| 1.0.0 shipping artifact | **PySide6 desktop app**, PyInstaller. **Linux + Windows.** Linux → AppImage + `.deb`. Windows → PyInstaller onedir/onefile, **unsigned** (SmartScreen accepted, same as Coding-Assistants). Frontend / extension / mobile / Django API stay pre-1.0. |
| External PostgreSQL/pgvector dependency | Documented as a prerequisite; ship a setup helper, do **not** bundle a database. |
| ASP full-97 validation (#470) | **Hard release blocker.** No `v1.0.0` tag until #470's edge-graph recovery fix is validated and the Ground-Rule reference re-based. |

## Model: same as Coding-Assistants v1.0

Packaging pipeline first → then blockers → then tag. Version source of truth,
a `just release::bump`, a tag-triggered `release.yml` producing a **draft**
GitHub Release for review before publish.

---

## Workstreams

### WS-A — ASP #470 full-97 validation  · **BLOCKER** · owner: Chat (Codex)

The only hard release gate. Per the **RESOURCE RULE**, the full-97 / corpus run
goes through Codex with Harbinger's explicit go-ahead — no other agent launches it.

- Validate the disconnected-edge-graph recovery fix (`run_stage` §1.15, pointer
  `374d822b`) against the full-97 RAW_ASP set.
- Confirm the M1b bench-adapter switch (`b20d02c`) is the cause of the
  43→8 composite collapse, not a pipeline regression (per #470 title).
- Re-base the Ground-Rule reference once the recovery fix is confirmed.
- Deliverable: pass/fail on full-97 + updated #470, and a go/no-go for the tag.

Everything below can proceed in parallel; only the **tag** waits on WS-A.

### WS-B — Version contract + `just release::bump`  · owner: DeepSeek (OpenCode)

Today: `pyproject.toml` 0.1.0, `pixi.toml` 0.1.0, `package.json` 1.0.0 — three
sources, no canonical one.

- Pick `pyproject.toml` `[project].version` as canonical. Document it in
  `AGENTS.md`.
- `tools/release/justfile` (new mod `mod release "tools/release/justfile"` in
  root `justfile`) with `bump <semver>`: validates SemVer, rewrites
  `pyproject.toml`, `pixi.toml`, `package.json`, and `android/app/build.gradle.kts`
  (`versionName` + derived `versionCode = major*10000+minor*100+patch`) to match.
  Prints the diff; does **not** commit.
- Also expose the app version to the running app (a `__version__` read from
  package metadata) so the About box / `--version` is truthful.
- Do **not** bump to 1.0.0 yet — that is the last step, after WS-A clears and
  WS-C's `release.yml` proves out on a dry run + RC tag.

### WS-C — Release pipeline  · owner: Gemini (Agy) + Claude

The bulk of the greenfield work. `ImageToolkit.spec` exists but is rough
(hardcoded `/backend` pathex, unverified hidden imports, references
`assets/images/image_toolkit_icon.ico`).

1. **Fix `ImageToolkit.spec`** — correct `pathex`, entry `gui/__main__.py`,
   enumerate hidden imports (PySide6 modules, `backend.src.*`, torch/cv2 plugin
   dirs), bundle `assets/`, icon, `configs/`. Verify a clean
   `pyinstaller --clean ImageToolkit.spec` onedir launches on a bare box.
2. **`tools/release/justfile` bundle recipes** —
   `bundle-linux` (PyInstaller → AppImage via `appimagetool` + `.deb` via
   `fpm` or `dpkg-deb`), `bundle-windows` (PyInstaller onedir + zip; NSIS
   optional), `artifacts` (collect into `dist/release/`).
3. **`.github/workflows/release.yml`** — `v*` tag push + `workflow_dispatch`
   (`dry_run` default true). Matrix: `ubuntu-22.04` (AppImage + deb, pinned to
   22.04 for glibc), `windows-latest` (zip). On a real `v*` tag → draft GitHub
   Release with the artifacts attached; on dispatch → upload as run artifacts
   only (the Coding-Assistants pattern — `tauri-action` has no equivalent here,
   use `actions/upload-artifact` + `softprops/action-gh-release`).
4. **PostgreSQL/pgvector prerequisite** — `docs/INSTALL.md` (or a section):
   required Postgres version, `CREATE EXTENSION vector`, the schema bootstrap
   (`just db-setup`), and env vars. First-run: the app should detect a missing
   DB and point the user at this doc rather than crash.

### WS-D — Release-blocking bug triage  · owner: Grok

- **#461** — gallery / PySide6 binding-corruption crash class. Milestones already
  landed (worker drain, `waitForDone(-1)`, JVM removal). Task: a focused stress
  pass (rapid dir-nav + dual linked wallpaper panels restoring at startup +
  teardown-during-load) on the current tree; if no SIGSEGV reproduces, write the
  evidence and move #461 to "fixed in 1.0.0"; if it still crashes, that is a
  blocker — report with the backtrace.
- **#373** — KDE wallpaper black screen. Fix landed + verified live 2026-08-15,
  9/9 tests. Task: confirm still green on current tree, then **close** it.
- Sweep the tree for any *other* crash-class / data-loss bug not yet ticketed;
  file it, tag blocker or 1.0.x.
- No open-ended feature-bug hunt — roadmap Phases 1–4 are ~95% ✅; the release
  gate is "no crashes / no data loss in the shipping desktop app", nothing more.

### WS-E — Release docs + changelog freeze  · owner: OpenCode (GLM 5.3)

- `docs/RELEASE_CHECKLIST.md` — the Coding-Assistants shape adapted:
  pre-release version freeze → CI green → `vX.Y.Z` annotated tag → `dry_run`
  dispatch → artifact review (AppImage/deb/Windows-zip) → smoke-test matrix
  (fresh box, no repo checkout, external Postgres) → publish draft →
  post-publish. Note the unsigned-Windows caveat.
- `docs/moon/CHANGELOG.md` — open a `## [1.0.0] - Unreleased` section, move the
  relevant `Unreleased` bullets under it. Freeze (date it) only at tag time.
- `README.md` — install-from-release section, the Postgres prerequisite, a
  "not yet in 1.0.0: web frontend, extension, mobile" note so scope is honest.

---

## Sequencing

```
now ──► WS-B version contract ──┐
    ──► WS-C spec + recipes + release.yml ──► dry-run dispatch ──► v0.1.1-rc1 tag ──► review 6? artifacts
    ──► WS-D #461 stress / #373 close ───────────────────────────────────────────┐
    ──► WS-E checklist + changelog skeleton                                       │
    ──► WS-A full-97 validation (Codex + Harbinger auth) ────────────────────────┤
                                                                                 ▼
                                          all green ──► just release::bump 1.0.0 ──► freeze CHANGELOG
                                                    ──► git tag v1.0.0 ──► release.yml ──► draft Release
                                                    ──► Harbinger reviews + publishes
```

## Non-negotiables

- **RESOURCE RULE** — benchmark / full-suite `pytest` runs route through Codex
  with Harbinger authorization. WS-A is his; anyone else needing a corpus/full
  run posts to the bus addressed to Codex. Targeted `-k` / single-file / `ruff` /
  `py_compile` checks are fine for everyone.
- Test/scratch/fixture dirs under `~/Downloads/Data/Tests/`, never in-repo.
  No PNG/artifact bundles committed (this is what the history strip just cleaned).
- Commit trailers: `Co-Authored-By: <agent>` + the session/tool trailer per
  each agent's convention. PR bodies end with the generator line + session URL.
- Post progress to `.agent/bus/<today>.md`; keep `AGENT_BUS.md` index current.
