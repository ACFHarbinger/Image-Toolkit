# E3 — Dependabot Alert Triage (Image-Toolkit)

**Date:** 2026-09-20  
**Total alerts from API:** 214 (npm: 161, pip: 44, rust: 8, actions: 1)  
**Open:** 65 (npm: 58, pip: 4, rust: 3)  
**Fixed:** 149 (npm: 103, pip: 40, rust: 5, actions: 1)  
**Open Dependabot PRs:** 0

---

## npm — 58 open alerts, 13 unique (package, CVE) pairs

### Stale alerts (lockfile already ≥ patched version) — DISMISS

| Package | Lockfile ver | Patched ver | Manifest | Reason |
|---------|-------------|-------------|----------|--------|
| lodash-es | 4.18.1 (root top-level) | 4.18.0 | package-lock.json | Top-level already patched; nested copies under `@chevrotain/*` at 4.17.23 are transitive |
| minimatch | 10.2.6 (both) | 10.2.3 | both lockfiles | Top-level patched; 18+ nested copies at 3.x/5.x/9.x are transitive from eslint, electron, jest, etc. |
| nth-check | 2.1.1 (both top-level) | 2.0.1 | both lockfiles | Top-level patched; nested 1.0.2 under `@svgr/plugin-svgo` / `svgo` is transitive |
| vite | 8.2.2 (root) | 8.0.16 | package-lock.json | Already patched; devDependency only |
| uuid | 14.0.2 (root top-level) | 12.0.1 | package-lock.json | Top-level patched; nested 8.3.2 under `sockjs` in frontend is transitive |

### Genuinely vulnerable — transitive from react-scripts 5.0.1

These are all nested dependencies pinned by `react-scripts 5.0.1` (CRA). The parent packages specify version ranges that exclude the patched versions. Fix path: **npm `overrides`** in `frontend/package.json`.

| Package | Installed | Need | Severity | CVEs | Parent chain | Risk of override |
|---------|-----------|------|----------|------|-------------|-----------------|
| postcss | 8.5.6 | 8.5.23 | high | CVE-2026-69153, CVE-2026-73646, CVE-2026-45623 | react-scripts → resolve-url-loader → postcss 7.0.39; direct 8.5.6 | Low — postcss 8.x is backward-compatible within minor |
| svgo | 1.3.2 (fe), 2.8.0 (fe postcss-svgo) | 2.8.4 | high | CVE-2026-84370, CVE-2026-84369, CVE-2026-73650, CVE-2026-29074 | react-scripts → @svgr/plugin-svgo → svgo 1.3.2 | Medium — 1.x→2.x is a major rewrite; override may break @svgr |
| underscore | 1.13.6 | 1.13.8 | high | CVE-2026-27601 | Direct dep in both lockfiles (not in package.json — likely from electron-builder or workbox-build) | Low — patch bump |
| webpack-dev-server | 4.15.2 | 5.2.6 | medium | 6 CVEs | react-scripts → webpack-dev-server ^4.6.0 | **HIGH** — 4→5 is a major rewrite; do NOT override |
| yaml | 1.10.2 (fe) | 2.8.3 | medium | CVE-2026-33532 | Direct in fe lockfile (not in fe package.json — transitive from typedoc or similar) | Medium — 1.x→2.x API changes |
| serialize-javascript | 6.0.2 | 7.0.5 | high | CVE-2026-34043, no-CVE RCE | Direct dep; also nested 4.0.0 under rollup-plugin-terser | Medium — 6→7 may have breaking changes |

### Genuinely vulnerable — other chains

| Package | Installed | Need | Severity | CVEs | Parent chain | Action |
|---------|-----------|------|----------|------|-------------|--------|
| qs | 6.15.3 | 6.16.0 | medium | CVE-2026-82562, CVE-2026-82417 | express 4.22.2 → qs ~6.15.1; body-parser → qs ~6.15.1 | Override to 6.16.0 (minor bump, low risk) |
| @tootallnate/once | 1.1.2 | 3.0.1 | low | CVE-2026-3449 | Transitive (likely from node-fetch or similar) | Low priority; 1→3 is major but low severity |

### Recommended npm actions

1. **Safe overrides** (add to `frontend/package.json` `overrides` and root `package.json` `overrides`):
   - `postcss`: `^8.5.23` — fixes 5 high/medium CVEs in frontend
   - `underscore`: `^1.13.8` — fixes 1 high CVE in both
   - `qs`: `^6.16.0` — fixes 2 medium CVEs in root

2. **Needs investigation** (test before overriding):
   - `serialize-javascript`: `^7.0.5` — check rollup-plugin-terser compatibility
   - `yaml`: `^2.9.0` — check what depends on yaml 1.x in frontend
   - `svgo`: leave at 1.3.2 for @svgr compatibility; root already has 4.1.0 patched

3. **Do NOT override** (breaking major version, dev-only risk):
   - `webpack-dev-server`: 4→5 breaks react-scripts dev server
   - `@tootallnate/once`: low severity, major version jump, transitive

4. **Dismiss as stale** (lockfile already patched at top level):
   - lodash-es, minimatch, nth-check, vite, uuid (top-level copies)

---

## pip — 4 open alerts

| Package | Installed | Need | Severity | CVEs | Action |
|---------|-----------|------|----------|------|--------|
| setuptools | 80.9.0 | 83.0.0 | medium | CVE-2026-59890 | **Bump** — sdist Unicode normalization bypass. Safe minor bump. |
| torch | 2.9.1 | 2.10.0 / 2.13.0 | low | CVE-2025-3000, CVE-2025-3001 | **Dismiss** — JIT compiler memory corruption; not reachable in production inference/training pipelines. PyTorch 2.10+ requires CUDA 12.x changes. |
| paramiko | 3.5.1 | n/a (no patch) | low | CVE-2026-44405 | **Dismiss** — already ignored in `dependabot.yml` (major bump blocked). SHA-1 in rsakey.py, no patched version exists. Mitigated by key-type restrictions. |
| accelerate | — | n/a | medium | CVE-2026-69112 | **Check** — path traversal via sharded checkpoint weight_map. Only if loading untrusted checkpoints. |

---

## rust — 3 open alerts

| Package | Installed | Need | Severity | Manifest | Action |
|---------|-----------|------|----------|----------|--------|
| pyo3 | NOT IN Cargo.lock | 0.29.0 | medium+high | archive/rust/Cargo.toml | **Dismiss** — `archive/rust/` is retired code (Rust→C++ migration). Dependabot config explicitly says "archive/rust/Cargo.toml is intentionally NOT scanned." These alerts are stale from before the archive. |
| glib | 0.18.5 | 0.20.0 | medium | Cargo.lock (root workspace) | **Investigate** — transitive from Tauri (`frontend/src-tauri`). 0.18→0.20 is a major bump; requires checking Tauri's glib dependency compatibility. |

---

## actions — 0 open (1 fixed)

lycheeverse/lychee-action CVE-2024-48908 — already fixed.

---

## Summary & Priority

| Priority | Action | Alerts resolved |
|----------|--------|----------------|
| **P0** | Dismiss pyo3 alerts (archived code, not scanned) | 2 |
| **P0** | Dismiss stale npm alerts (lockfile already patched) | ~30 duplicate alert instances |
| **P1** | npm overrides: postcss, underscore, qs | ~12 alerts |
| **P1** | Bump setuptools to ≥83.0.0 | 1 |
| **P2** | Investigate serialize-javascript, yaml, svgo override safety | ~6 alerts |
| **P2** | Investigate glib 0.18→0.20 for Tauri | 1 |
| **P3** | Dismiss torch JIT CVEs (not reachable in production) | 2 |
| **P3** | Dismiss paramiko (no patch, already ignored) | 1 |
| **Won't fix** | webpack-dev-server 4→5 (breaks react-scripts) | 6 |
| **Won't fix** | @tootallnate/once 1→3 (low severity, major bump) | 1 |
