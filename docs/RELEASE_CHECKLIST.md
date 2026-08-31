# Release Checklist

A manual pass for cutting an Image-Toolkit desktop release (PySide6 app,
PyInstaller) from this repository. It pairs with the automated
`.github/workflows/release.yml` job; this checklist covers the steps that
need a human decision or a real machine.

Shipping artifact per the v1.0.0 decision: the **PySide6 desktop app** on
**Linux (AppImage + `.deb`) and Windows (zip, unsigned)**. PostgreSQL +
`pgvector` is an external prerequisite — see [`INSTALL.md`](INSTALL.md).

## 1. Pre-release

- [ ] **Release blockers cleared.** No open crash-class / data-loss issue
      against the shipping desktop app (v1.0.0 gate: #470 ASP full-97
      validation passed, #461 and #373 closed). Benchmark / full-suite runs
      that prove this go through Codex with Harbinger's authorization
      (RESOURCE RULE).
- [ ] **Version bump.** `just release::bump <semver>` rewrites the canonical
      root `pyproject.toml` `[project].version` and every derived source
      (`pixi.toml`, `package.json`, gradle `versionName`/`versionCode`, and
      the `backend`/`gui`/`git` member `pyproject.toml`s). It does **not**
      commit — review the printed diff before committing.
- [ ] **Changelog freeze.** In `docs/CHANGELOG.md`, retitle
      `## [1.0.0] - Unreleased` to `## [1.0.0] - YYYY-MM-DD` and move any
      post-freeze `## [Unreleased]` bullets that belong in this release.
      Do not delete history.
- [ ] **CI green on `main`** (`ci.yml`, `docs.yml`, `security.yml`).

## 2. Tag convention

- Cut a `vX.Y.Z` **annotated** tag on `main`, e.g.
  `git tag -a v1.0.0 -m "v1.0.0"`.
- Push the tag: `git push origin vX.Y.Z`. Pushing it triggers
  `.github/workflows/release.yml`, which builds the bundles and publishes a
  **draft** GitHub Release.

## 3. Dry run and rehearsal

- [ ] Dispatch `.github/workflows/release.yml` manually with `dry_run: true`
      (default). This builds every bundle and uploads them as run artifacts
      but **skips** the GitHub Release.
- [ ] Before the real tag, run one end-to-end rehearsal tag (e.g.
      `v0.1.1-rc1`) and confirm the draft Release is created with all
      artifacts attached, then delete the rehearsal release/tag. `-rc` in
      the tag marks the draft as a prerelease automatically.

## 4. Artifact review

The `release.yml` job publishes a **draft** GitHub Release. Confirm all
artifacts are attached (local equivalents land in `dist/release/`):

- [ ] `ImageToolkit-<version>-x86_64.AppImage`
- [ ] `image-toolkit_<version>_amd64.deb`
- [ ] `ImageToolkit-<version>-windows-x86_64.zip`
- [ ] `SHA256SUMS.txt` covering all of the above

## 5. Smoke-test matrix

Test each artifact on a real machine before publishing the draft — fresh
box, **no repo checkout**, external PostgreSQL:

- [ ] **AppImage** on an older-glibc distro (built on `ubuntu-22.04`; a
      newer-distro build would not run on older glibc).
- [ ] **`.deb`** install and remove (`dpkg -i` then `dpkg -r`, confirm no
      leftover config/units); launches from the desktop menu and via
      `image-toolkit`.
- [ ] **Windows zip** on Windows 10 and 11 — extract, run
      `ImageToolkitApp.exe`, accept the unsigned-SmartScreen prompt.
- [ ] **Database prerequisite**: with PostgreSQL 14+ / `pgvector` ≥ 0.5.0
      configured per [`INSTALL.md`](INSTALL.md), vector features connect;
      with no database reachable, the app still launches on local SQLCipher
      storage and points the user at the install guide instead of crashing.
- [ ] First-run vault creation and a conversion round-trip on each OS.

## 6. Publish and post-publish

- [ ] Promote the draft GitHub Release to public (or keep as a pre-release).
- [ ] Announce the release.
- [ ] Close the GitHub milestone associated with the release.

## 7. Known v1.0 caveats

- **Windows builds are unsigned.** Expect a SmartScreen warning on download
  and run ("More info" → "Run anyway"); the signing pipeline is deferred.
- **PostgreSQL + `pgvector` is not bundled.** Vector search, anime training
  pipelines, and legacy migration require an external database
  ([`INSTALL.md`](INSTALL.md)); the app degrades gracefully without it.
- **No macOS build** in this pipeline.
- **Web frontend, browser extension, mobile apps, and the Django API are
  not part of the release artifact** — pre-1.0 surfaces, built from source
  per the README.
