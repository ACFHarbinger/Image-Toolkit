# Dependency Policy

*Last updated: 2026-06-19. Establishes minimum version requirements, pinning policy, upgrade cadence, and the process for introducing new dependencies. See `moon/roadmaps/documentation.md §6.7B` for rationale.*

---

## Table of Contents

- [Version Requirements](#version-requirements)
- [Pinning Policy](#pinning-policy)
- [Upgrade Cadence](#upgrade-cadence)
- [Introducing a New Dependency](#introducing-a-new-dependency)
- [Removing a Dependency](#removing-a-dependency)
- [Security Vulnerabilities](#security-vulnerabilities)
- [Per-Stack Notes](#per-stack-notes)

---

## Version Requirements

| Stack | Runtime | Minimum Version | Rationale |
|-------|---------|----------------|-----------|
| Python | Runtime | 3.11+ | `tomllib` stdlib (used by `config.py`); `match` statement; `ExceptionGroup` |
| Rust | Compiler | 1.70+ | `OnceCell` stabilised; `let-else` stabilised |
| Node.js | Runtime | 18+ | Fetch API built-in; LTS lifecycle |
| npm | Package manager | 9+ | Workspaces support required |
| PostgreSQL | Database | 14+ | `pgvector` compatibility; `JSONB` path operators |
| pgvector | Extension | 0.5.0+ | HNSW index type (`CREATE INDEX USING hnsw`) |
| Android SDK | Mobile | API 26 (Android 8.0)+ | Jetpack Compose minimum target |
| iOS / Xcode | Mobile | iOS 16+ / Xcode 15+ | SwiftUI async/await; DocC support |
| Java / JVM | Crypto bridge | 11+ | JPype compatibility; `VaultManager` |

---

## Pinning Policy

### Python (`uv.lock` / `requirements.txt`)

- **Lockfile (`uv.lock`):** All transitive dependencies are pinned to exact versions via `uv lock`. This file is committed to the repository and is the authoritative pin for CI.
- **`env/requirements.txt`:** Uses `~=` compatible-release specifiers (e.g., `torch~=2.3`) for the major runtime dependencies. This allows patch-level upgrades without a full lockfile regeneration.
- **`env/dev_requirements.txt`:** Uses `>=` lower bounds only. Dev tools (ruff, mypy, pytest) upgrade freely within CI's weekly cache refresh.

```
# Good — compatible release in requirements.txt
torch~=2.3

# Bad — unpinned in requirements.txt
torch

# Correct — exact pin lives in uv.lock (generated automatically)
torch==2.3.1
```

### Rust (`Cargo.lock`)

- `Cargo.lock` is committed for the `base` binary and the Tauri `src-tauri` crate. Binaries always commit their lockfile.
- `Cargo.toml` uses `^` (caret) version requirements (Cargo default). This allows compatible updates within the same major version.
- Security patches may use `=` (exact) to pin while a fix propagates upstream.

### Node.js (`package-lock.json` / `npm workspaces`)

- `package-lock.json` at the project root and `frontend/package-lock.json` are both committed.
- `package.json` uses `^` (caret) for most dependencies and `~` for packages that historically break on minor updates.
- Electron's Node.js ABI pins `better-sqlite3` and similar native modules to exact versions. Do not loosen these.

---

## Upgrade Cadence

| Category | Response time | Process |
|----------|--------------|---------|
| **Security patch** (CVE with CVSS ≥ 7.0) | Within 7 days | Direct commit to `main`; no PR review gate required. Run `pip-audit` + `cargo audit` to verify. |
| **Security patch** (CVE with CVSS < 7.0) | Within 30 days | Normal PR process. |
| **Minor version** (new features, backwards-compatible) | Monthly sweep | Batch together with the first Monday of each month's routine maintenance. Update `uv.lock`, `Cargo.lock`, `package-lock.json` in a single PR. |
| **Major version** (breaking changes) | With migration plan | Create a `feat/upgrade-<package>-vN` branch. Update test suite. Document breaking changes in `CHANGELOG.md`. |
| **Python runtime** (e.g., 3.11 → 3.12) | After 6-month soak | Requires updating `pyproject.toml` `requires-python`, `uv.lock`, GitHub Actions matrix, and PyInstaller spec. |
| **Rust edition** (2021 → 2024) | With Rust stable release + 3 months | Run `cargo fix --edition`, audit `unsafe` usages. |

---

## Introducing a New Dependency

Before adding any new package, answer the following questions:

1. **Is it already available?** Check existing dependencies first — `numpy`, `opencv-python`, `scipy`, `torch`, `pillow` already cover most image and numerical tasks.
2. **What is the maintenance status?** Prefer packages with a release in the last 12 months, a responsive issue tracker, and >100 GitHub stars (or a major institution as maintainer).
3. **What is the transitive footprint?** Run `pip install --dry-run <package>` or `cargo tree -d <crate>` to enumerate transitive dependencies. Flag anything that pulls in `openssl`, `libstdc++`, or native libraries that could conflict with the existing JPype/PyO3 ABI layer.
4. **Does it have a compatible license?** Permitted licenses: MIT, Apache-2.0, BSD-2/3, MPL-2.0, ISC. Prohibited: GPL (except for tools, not linked into the app), LGPL without dynamic linking, SSPL, BSL. Check with `pip-licenses` or `cargo-deny`.
5. **Is there a security history?** Check [osv.dev](https://osv.dev/) and [deps.dev](https://deps.dev/) for known CVEs before adding.

Once approved, add to the correct requirements file and run `uv lock` / `cargo update` / `npm install` to update the lockfile. Document the addition in `CHANGELOG.md` under `Dependencies`.

---

## Removing a Dependency

1. Verify no code paths import the package: `grep -r "import <pkg>" backend/ base/ frontend/src/ app/`.
2. Remove from `requirements.txt` / `Cargo.toml` / `package.json`.
3. Regenerate the lockfile: `uv lock` / `cargo update` / `npm install`.
4. Run the full test suite.
5. Document the removal in `CHANGELOG.md` under `Dependencies`.

---

## Security Vulnerabilities

Run these checks before each release and in the weekly CI schedule:

```bash
# Python
pip-audit --requirement env/requirements.txt

# Rust
cargo audit

# Node
npm audit --audit-level=moderate

# Combined report
pip-audit -r env/requirements.txt -o json | python scripts/format_audit.py
```

If a vulnerability cannot be patched within the SLA (see Upgrade Cadence), document it in a `SECURITY_EXCEPTIONS.md` file with: CVE ID, CVSS score, affected version range, workaround/mitigation, and target fix date.

---

## Per-Stack Notes

### Python

- **PyTorch:** Pin to a specific CUDA version in CI to avoid downloading multiple CUDA runtime copies. Use `torch~=2.3+cu121` for RTX 3090 Ti / 4080 builds.
- **PySide6:** Pin to an exact minor version. PySide6 `6.x.y` and `6.x.(y+1)` can break binary compatibility on Linux. The JPype JVM bridge is sensitive to PySide6 minor releases.
- **maturin:** Used to build the PyO3 Rust extension. Pin to the same version locally and in CI to avoid ABI mismatches between the `.so` in the lockfile and the one CI builds.
- **Avoid at the top level of `anim/` or `compositing.py`:** `diffusers`, `transformers`, `accelerate`. These must be lazy-imported (see §3.10 in `performance.md`).

### Rust

- **pyo3:** The `abi3-py311` feature locks the extension to Python 3.11+. Do not downgrade this ABI target — it determines which Python versions can use the compiled `base` module.
- **rayon:** Thread pool is shared with the test suite. Avoid spawning additional rayon pools in tests; use `rayon::ThreadPoolBuilder::new().num_threads(1).build_global()` in test fixtures that need deterministic ordering.
- **image crate:** The `webp` feature is required. Do not enable the `jpeg_rayon` feature — it conflicts with the existing rayon pool under heavy parallelism.

### Node.js / Electron

- **Electron:** Only upgrade Electron minor versions that are also Node.js LTS versions. Electron 28+ (Node.js 18) is the baseline. Check `electron-builder` compatibility before upgrading.
- **react / react-dom:** Keep at the same minor version. React 19 canary APIs are used in `App.tsx`; do not downgrade to 18.
- **@tauri-apps/api:** Must match `tauri` crate version exactly. Upgrade both together.

### Android

- **Gradle plugin:** AGP (Android Gradle Plugin) version must match the Gradle wrapper version in `gradle/wrapper/gradle-wrapper.properties`. Check the compatibility matrix before upgrading either.
- **Kotlin:** Stay within the same minor series as the Jetpack Compose BOM. Compose 2024.x requires Kotlin 1.9+.

### iOS

- **Swift Package Manager:** Prefer SPM over CocoaPods for new dependencies. CocoaPods requires `pod install` on every clean build and is not reproducible across machines without a `Podfile.lock`.
