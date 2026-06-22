# Troubleshooting Guide

*Last updated: 2026-06-19. Supersedes `docs/TROUBLESHOOT.md` (SIGSEGV-only). Expanded to cover PySide6/Qt crashes, ASP pipeline errors, Rust/PyO3 build failures, Hydra CLI issues, mobile build failures, and database problems.*

---

## Table of Contents

- [PySide6 / Qt Crashes (SIGSEGV)](#pyside6--qt-crashes-sigsegv)
- [ASP Pipeline Errors](#asp-pipeline-errors)
- [Rust / PyO3 Build Failures](#rust--pyo3-build-failures)
- [Hydra CLI Configuration Errors](#hydra-cli-configuration-errors)
- [Database (PostgreSQL / pgvector)](#database-postgresql--pgvector)
- [Tauri / Frontend Build Failures](#tauri--frontend-build-failures)
- [Mobile Build Failures](#mobile-build-failures)
- [Test Suite Issues](#test-suite-issues)
- [Developer Best Practices](#developer-best-practices)

---

## PySide6 / Qt Crashes (SIGSEGV)

### `__dynamic_cast` failure in `libstdc++.so.6`

**Symptom:** Application terminates during directory browsing, gallery loading, or startup. Crash log (`hs_err_pid*.log`) shows:
```
C [libstdc++.so.6+0xc1e25] __dynamic_cast+0x35
```

**Root causes and fixes:**

**1 — Unsafe Signal Lifecycle in `QRunnable` (Shiboken)**

Context: `LoaderWorker` and `BatchLoaderWorker` use `setAutoDelete(True)` and own a `signals` `QObject` member.

When `run()` returns, the worker is immediately deleted by Qt. If `Signal.emit()` is in-flight, the `signals` object is destroyed before delivery completes.

Fix: Add `self.signals.deleteLater()` in a `finally` block at the end of `run()`. This schedules deletion *after* pending signals are handled.

**2 — QFileDialog with GTK portal + JPype JVM**

Context: `QFileDialog.getExistingDirectory()` without `DontUseNativeDialog` loads the GTK portal dialog on Linux.

Cause: GTK brings in its own `libstdc++`. Combined with JPype's JVM native bindings, RTTI symbol conflicts cause `__dynamic_cast` to segfault.

Fix: **Always** pass `QFileDialog.Option.DontUseNativeDialog` to all `QFileDialog` calls.

```python
# Correct
path = QFileDialog.getExistingDirectory(
    self, "Select folder", "",
    QFileDialog.Option.DontUseNativeDialog
)
```

**3 — `QWebEngineView` + JPype JVM**

Cause: Chromium initialises its Vulkan/GBM renderer lazily on first paint, loading native `libstdc++` that conflicts with JPype's JVM bindings. Log line just before crash: `"Fallback to Vulkan rendering in Chromium"`.

Fix: **Never** use `QWebEngineView` or any `QtWebEngine` widget. Open URLs with:

```python
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
QDesktopServices.openUrl(QUrl("https://example.com"))
```

**4 — `QPixmap` created in a worker thread**

Cause: `QPixmap` is not thread-safe. Creating it in a `QThreadPool` worker triggers Shiboken's internal type system crash.

Fix: Emit `QImage` from workers (thread-safe). Convert to `QPixmap` only in the main thread slot:

```python
# Worker thread — OK
self.signals.image_loaded.emit(QImage(path))

# Main thread slot — OK
pixmap = QPixmap.fromImage(q_image)
label.setPixmap(pixmap)
```

**5 — Incomplete Worker Cleanup during Tab Closure**

Context: Closing `ConvertTab` or `GalleryTab` while background workers are active.

Fix: Override `closeEvent` in every tab that uses long-running workers. Call `worker.wait()` or `QThreadPool.globalInstance().waitForDone()` before returning.

**6 — JNI/JPype Threading Race during Startup**

Context: Concurrent access to `VaultManager` (JPype JVM) from multiple threads at startup.

Fix: A `threading.RLock` in `VaultManager` serialises all JNI calls. If you see this crash, check that `VaultManager` is not being called from worker threads without acquiring the lock.

---

### `libpyside6.abi3.so.6.10` crash in `__dynamic_cast` on tab switch

**Symptom:** Fatal crash when switching to any tab that contains a `QWebEngineView` for the first time.

**Cause:** Same as root cause #3 above. See the fix there.

---

## ASP Pipeline Errors

### `ValueError: Not enough inliers` / `alignment_failed`

**Context:** Stage 7b (bundle adjustment / geometric filter) or Stage 8 (ECC refinement) rejects too many edges.

**Diagnosis:**
```bash
# Run with verbose logging
ASP_LOG_LEVEL=DEBUG python -m backend.src.animation.pipeline <args>

# Check the stage trace JSON (written to output dir)
cat output/trace.json | python -m json.tool | grep -A5 "stage_7"
```

**Common causes and fixes:**

| Cause | Fix |
|-------|-----|
| Animated hold frames not filtered | Enable dHash hold detection: `ASP_HOLD_DHASH_THRESH=4` |
| Horizontal scroll detected as vertical | Check `_detect_scroll_axis` output in trace; ensure frames are vertically scrolling content |
| Feature matching failed (blank areas, solid colour) | Lower `ASP_POSE_WINDOW_PX` or switch to phase-correlation-only mode |
| Too few adjacent edges survive quality gate | Lower `HIGH_CONF_EDGE_THRESH` from 0.65 to 0.55 in `asp_config.toml` |

---

### Pipeline falls back to SCANS on every test

**Symptom:** `fallback_reason` in benchmark results is always `alignment_failed:*` or `ratio=*`.

**Diagnosis:** Check `ASP_COV_MIN_MULTI_PCT` — if the canvas coverage gate is too strict, multi-frame coverage is below 30% and the pipeline falls back immediately.

```bash
# Relax coverage gate
ASP_COV_MIN_MULTI_PCT=0.15 python -m backend.src.animation.pipeline <args>
```

Other common causes:
- `STATIC_EDGE_MIN_DISP_PX=50` is too high for slow-scroll content → lower to 20.
- All frames are nearly identical (animation hold) → enable temporal variance filter: `ASP_TEMPORAL_VAR_THRESH=1e-3`.

---

### Ghost / double-image artifact in output

**Symptom:** Characters appear doubled or blurred at the seam boundary.

**Diagnosis:**
```bash
# Check ghosting score in benchmark output
python backend/benchmark/run_single.py --test-id <ID> | grep ghosting
```

**Fixes in priority order:**

1. Enable bg-mask-aware DSFN ramp (S20, default ON): `ASP_SGM_PROXY=0` to rule out SGM proxy interference.
2. Check `_seam_gate_vote_counts` in trace — if the ensemble gate is not firing, the seam cost map may be routing through foreground.
3. Try Poisson seam blending: `ASP_POISSON_SEAM=1` (adds 1–3 s/seam, CPU).
4. Increase minimum feather: set `FEATHER_MIN=120` in `asp_config.toml`.

---

### `RuntimeError: Canvas too large` / `CANVAS_MAX_DIM exceeded`

**Cause:** The computed panorama canvas exceeds `CANVAS_MAX_DIM` (set in `backend/src/constants/animation.py`).

**Fix:** Reduce the input image resolution before stitching, or increase the constant (memory-bound):

```python
# backend/src/constants/animation.py
CANVAS_MAX_DIM = 32768  # increase from default 16384
```

---

### `asp_config.toml` key not taking effect

**Cause:** Environment variables take precedence over TOML config by default (`setdefault` semantics in `load_asp_config`).

**Fix:** Unset the environment variable or use `override_env=True` in the loader:

```python
from backend.src.animation.config import load_asp_config
load_asp_config("asp_config.toml", override_env=True)  # TOML wins over env
```

Or: set the value directly in the environment (env always wins by default):
```bash
unset ASP_HOLD_THRESHOLD
```

---

## Rust / PyO3 Build Failures

### `ModuleNotFoundError: No module named 'base'`

**Cause:** The PyO3 Rust extension has not been compiled for the active Python environment.

**Fix:**
```bash
source .venv/bin/activate
cd base
maturin develop --release
```

If `maturin` is not installed:
```bash
pip install maturin
```

---

### `maturin develop` fails: `abi3-py311 feature requires Python 3.11+`

**Cause:** The active Python interpreter is < 3.11.

**Fix:** Activate the correct environment:
```bash
source .venv/bin/activate
python --version  # must be 3.11+
```

---

### `cargo build` fails: `error: linking with cc failed`

**Ubuntu/Debian — missing system libraries:**
```bash
sudo apt install -y \
  libssl-dev pkg-config \
  libpqxx-dev \
  libgumbo-dev \
  nlohmann-json3-dev \
  libcxxopts-dev
```

**macOS:**
```bash
brew install openssl@3 pkg-config
export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig"
```

---

### `pyo3` version mismatch: `Python API version mismatch`

**Cause:** The compiled `.so` was built with a different pyo3 version than the one in `Cargo.lock`.

**Fix:**
```bash
cd base
cargo clean
maturin develop --release
```

---

### `rayon` thread pool panic in tests

**Symptom:** Tests in `backend/test/animation/` hang or panic with "cannot recursively acquire rayon global lock".

**Cause:** Multiple rayon thread pools being initialised in parallel test workers.

**Fix:** Run tests with `--skip-gpu` and the `pytest-xdist` work-steal distribution:
```bash
pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu
```

---

## Hydra CLI Configuration Errors

### `HydraException: Key 'command' not found in config`

**Cause:** The `command` key is missing from `backend/config/base.yaml` or was not passed on the CLI.

**Fix:** Pass the command explicitly:
```bash
python -m backend.dispatcher command=train
```

Or add a default in `backend/config/base.yaml`:
```yaml
defaults:
  - _self_

command: train
```

---

### `omegaconf.errors.ConfigAttributeError: Key 'xyz' is not in struct`

**Cause:** Hydra is in strict struct mode and you are trying to add an undeclared key.

**Fix:** Declare the key in the config schema or use `+` prefix to append:
```bash
python -m backend.dispatcher +new_key=value
```

---

### `config_path` resolution failure: `Expected config_path ... to be under ...`

**Cause:** The `config_path` in `@hydra.main` is relative to the Python file, not the working directory.

**Fix:** Always run the dispatcher from the project root, or use an absolute path:
```bash
# From project root
python -m backend.dispatcher

# NOT: python backend/dispatcher.py (wrong cwd)
```

---

### ComfyUI not starting (`command=comfyui`)

**Check 1:** Is ComfyUI installed?
```bash
ls ComfyUI/main.py
```

**Check 2:** Port conflict:
```bash
lsof -i :8188
python -m backend.dispatcher command=comfyui comfyui.port=8189
```

**Check 3:** GPU not available to ComfyUI:
```bash
python -m backend.dispatcher command=comfyui comfyui.cpu=true
```

---

## Database (PostgreSQL / pgvector)

### "DB Offline" / red indicator in GUI header

**Check 1:** PostgreSQL is running:
```bash
sudo systemctl status postgresql   # Linux
brew services list                 # macOS
```

**Start if stopped:**
```bash
sudo systemctl start postgresql    # Linux
brew services start postgresql@14  # macOS
```

**Check 2:** Credentials in `.env` match the database:
```bash
psql postgresql://toolkit_user:your_password@localhost:5432/image_toolkit
```

**Check 3:** pgvector extension installed:
```sql
\c image_toolkit
SELECT * FROM pg_extension WHERE extname = 'vector';
-- If empty: CREATE EXTENSION IF NOT EXISTS vector;
```

---

### `pgvector` extension not found after install

```bash
# Rebuild pgvector against the running PostgreSQL version
cd /tmp
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=$(pg_config --bindir)/pg_config
sudo make install PG_CONFIG=$(pg_config --bindir)/pg_config
```

Then in psql:
```sql
\c image_toolkit
CREATE EXTENSION IF NOT EXISTS vector;
```

---

### Migration fails: `relation already exists`

**Cause:** A previous migration run was interrupted partway through.

**Fix:** Check which migrations have already been applied:
```bash
psql postgresql://toolkit_user:pass@localhost:5432/image_toolkit -c "SELECT * FROM _sqlx_migrations ORDER BY version;"
```

Manually mark the failed migration as complete if it was partially applied, or roll it back:
```bash
cd frontend/src-tauri
sqlx migrate revert
sqlx migrate run
```

---

## Tauri / Frontend Build Failures

### `webkit2gtk-4.1 not found`

```bash
sudo apt install libwebkit2gtk-4.1-dev
```

### `Cannot find module 'react-dom/client'`

```bash
cd frontend
npm install --save-dev @types/react-dom
```

### `failed to run custom build command for 'openssl-sys'`

```bash
# Ubuntu/Debian
sudo apt install libssl-dev pkg-config

# macOS
brew install openssl@3
export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig"
```

### TypeScript type errors from `@tauri-apps/api`

**Cause:** `@tauri-apps/api` version in `package.json` does not match the `tauri` crate version in `src-tauri/Cargo.toml`.

**Fix:** Upgrade both to the same version simultaneously:
```bash
cd frontend
npm install @tauri-apps/api@<version>
# Update src-tauri/Cargo.toml tauri = "<version>"
cargo update -p tauri
```

### Electron `app.asar` not found / blank window

```bash
cd frontend
npm run build          # Build React first
npm run start-electron # Then launch Electron
```

Do not run `npm run electron` without first building React — it points to `build/index.html` which does not exist until after `npm run build`.

---

## Mobile Build Failures

### Android: `SDK location not found`

**Fix:** Set `ANDROID_HOME` in `local.properties` (not committed to git):
```
# local.properties
sdk.dir=/home/<user>/Android/Sdk
```

### Android: `Execution failed for task ':app:compileDebugKotlin'`

Check the Kotlin / AGP compatibility matrix. The AGP (Android Gradle Plugin) version in `build.gradle.kts` must match the Gradle version in `gradle/wrapper/gradle-wrapper.properties`.

```bash
./gradlew --version  # shows Gradle version
# Check https://developer.android.com/studio/releases/gradle-plugin for AGP compatibility
```

### Android: Build succeeds but app crashes on launch

Enable verbose ADB logging:
```bash
adb logcat -s "ImageToolkit" "*:E"
```

Common cause: `ANDROID_SDK_ROOT` not available at runtime, causing `JNI_OnLoad` to fail for native libraries.

### iOS: `No signing certificate found`

**Fix:** Open Xcode → Preferences → Accounts → add your Apple ID → download certificates. Then re-run `xcodebuild`.

For CI builds (no interactive Xcode): use `xcodebuild CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO` for simulator-only builds.

### iOS: `Module 'ImageToolkit' not found` in tests

```bash
xcodebuild clean -project app/ImageToolkit.xcodeproj -scheme ImageToolkit
xcodebuild test   -project app/ImageToolkit.xcodeproj -scheme ImageToolkit \
  -destination 'platform=iOS Simulator,name=iPhone 15'
```

---

## Test Suite Issues

### Tests hang / system becomes unresponsive

**Cause:** One of the §3.10 test-suite freeze root causes. All 5 are fixed; see `moon/roadmaps/performance.md §3.10–§3.15` for the full analysis.

**Safe invocation:**
```bash
# Fast, no GPU — always safe
pytest backend/test/animation/ --skip-gpu

# Parallel workers — safe after §3.12 fix
pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu

# Full suite (all backend modules) — requires §3.15 non-animation audit
# Only run after auditing all non-animation module imports for ML singletons
pytest backend/test/ --skip-gpu -n auto
```

**Never run:**
```bash
pytest backend/test/          # without --skip-gpu on machines with GPU
pytest backend/test/gui/      # PySide6 tests require a display; drain RAM
```

### `ImportError` collecting tests

**Cause:** A module-level import failed (possibly a missing optional dependency).

**Fix:**
```bash
# Find the failing import
pytest backend/test/animation/ --collect-only 2>&1 | grep "ERROR\|ImportError"

# Check import times to identify which module is slow/failing
python backend/src/utils/check_import_times.py
```

### `pytest-forked` not found

```bash
pip install pytest-forked pytest-xdist
```

---

## Developer Best Practices

1. **Signal Safety** — Use `deleteLater()` on all `QObject` members of `QRunnable` when `setAutoDelete(True)` is set.
2. **Graceful Tab Exit** — Always override `closeEvent` and halt active `QThread` / `QProcess` workers before the widget is destroyed.
3. **Bridge Synchronisation** — Serialise all JPype (JVM) and PyO3 (Rust) calls from worker threads using the appropriate lock.
4. **No Native Dialogs on Linux** — Pass `QFileDialog.Option.DontUseNativeDialog` to every `QFileDialog` call while JPype is active.
5. **No `QWebEngineView`** — Open URLs via `QDesktopServices.openUrl()`. The Chromium/Vulkan renderer conflicts with the JVM.
6. **Lazy ML imports** — Never import `diffusers`, `transformers`, `torch`, or large ML libraries at module level in `animation/` modules. Use lazy imports inside functions.
7. **Thread-local GPU state** — Do not share CUDA tensors across thread pool workers. Each QRunnable that uses a GPU model should have its own `torch.no_grad()` context.
