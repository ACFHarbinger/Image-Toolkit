# Issue #476 — audit frozen-bundle path assumptions (findings + fixes)

Date: 2026-08-31 · Owner: DeepSeek (flash) · Status: done, committed

## Bundle-layout reality (what "resolves" means under PyInstaller)

Two facts drive every verdict below:

1. **Data files are real files under `sys._MEIPASS`; pure-Python modules are
   inside the PYZ archive.** PyInstaller sets a PYZ module's `__file__` to a
   *virtual* path `_MEIPASS/<pkg path>/<mod>.py` that does not exist on disk
   (`pyimod02_importers.py`). `os.path.dirname(__file__)`-relative resource
   reads still work *only* because the current `ImageToolkit.spec` collects
   the sibling resources (QSS, SQL, QML, YAML, …) as data under the same
   relative path, which makes the parent directory exist. This is fragile but
   verified green on the shipped bundle; it is why the audit's standard is
   "must resolve under `sys._MEIPASS`", not "must use `dirname(__file__)`".
2. **`ROOT_DIR` is the bundle root when frozen** (`backend/src/constants/paths.py`
   already keys off `sys._MEIPASS`). Anything that *writes* under `ROOT_DIR`
   is a bundle-write hazard: the AppImage mount is read-only, and the
   onedir `_internal/` is replaced on every update. Writes belong in
   `~/.image-toolkit/`.

## Audit table (runtime paths only; tests/benchmarks/scripts excluded)

| # | Location | Expression | Frozen verdict |
|---|---|---|---|
| 1 | `backend/src/constants/paths.py` | `ROOT_DIR` parents[3] | OK — already `_MEIPASS`-aware |
| 2 | `gui/src/constants/paths.py` | `ROOT_DIR` parents[3] | OK by layout; made explicit + `SCREENSHOTS_DIR` fixed (below) |
| 3 | `gui/src/windows/main/_tray.py` | icon `__file__`→`assets/images` | OK — assets bundled |
| 4 | `gui/src/styles/__init__.py` | QSS `dirname(__file__)/qss` | OK — `**/*.qss` bundled |
| 5 | `backend/src/database/unified/session.py` | `schema*.sql` beside module | OK — `**/*.sql` bundled |
| 6 | `backend/src/models/core/comfy_manager.py` | `WORKFLOWS_DIR`→`configs/comfy_workflows` | OK — configs bundled |
| 7 | `gui/src/tabs/models/gen/comfy_generate_tab.py` | `_WORKFLOWS_DIR` parents[5] | OK — configs bundled |
| 8 | `backend/src/_version.py` | fallback root `pyproject.toml` | OK — bundled at bundle root |
| 9 | `backend/src/constants/paths.py` | `CRYPTO_LIB_FILE` `build/crypto` | OK — native lib bundled |
| 10 | `gui/src/constants/paths.py` | `RECOMMENDATION_ENGINE_DIR`→`submodules/CRE` | OK — submodules bundled wholesale |
| 11 | `backend/src/web/search_engines/common.py`, `web/clients/tineye_client.py` | `backend/config/api_keys.yaml` | NOT bundled (dir is not a package; file gitignored). Degrades to env-only — correct, secrets must not ship |
| 12 | `backend/src/models/wrappers/birefnet_wrapper.py` | `vendor/BiRefNet` | NOT bundled → falls back to HF download |
| 13 | `backend/src/core/image/_engines.py` | `vendor/Overmix/build/OvermixCli` | NOT bundled → raises a clear error (pre-existing guard) |
| 14 | `gui/src/windows/settings/_credentials.py` | `ROOT_DIR/"backup"` **write** | **FIXED** → `~/.image-toolkit/backup` |
| 15 | `gui/src/tabs/web/image_crawler_tab/manager.py` | `SCREENSHOTS_DIR` **default write dir** | **FIXED** → `~/.image-toolkit/screenshots` when frozen |
| 16 | `system_display_subtab/_daemon.py` | spawns `backend/.../slideshow_daemon.py` + `sys.executable` | **FIXED guard** — daemon is a separate Python process, unsupported in the packaged app |
| 17 | `monitor_display_subtab/_slideshow_daemon.py` | same for `monitor_slideshow_daemon.py` | **FIXED guard** |
| 18 | `image_crawler_tab/_webdriver.py` | spawns `backend/scripts/manage_webdriver.py` + `.venv` python | **FIXED guard** |
| 19 | `backend/src/models/core/comfy_manager.py::start()` | `sys.executable` + `COMFYUI_DIR/main.py` | **FIXED guard** — ComfyUI server launch needs a source checkout |
| 20 | `gui/src/tabs/models/delta/lora_train_tab.py` | `sys.executable -m backend.controllers.hydra_dispatch` cwd=`ROOT_DIR` | **FIXED guard** |
| 21 | `gui/src/windows/settings/_reset_state.py::_sync_vault_to_assets` | writes `assets/secrets` **write** | **FIXED guard** — repo-template workflow is source-only |
| 22 | `gui/__main__.py` | `repo_root` | OK — already `_MEIPASS`-aware |
| 23 | `backend/main.py` | `repo_root` parents | dev-only entry (not the bundle entry) |
| 24 | `backend/src/utils/display/*_daemon.py` | `_ROOT` parents[4] sys.path | daemon scripts are source-only by design |

## Fixes (all frozen-guarded — source-checkout behavior unchanged)

- `gui/src/constants/paths.py` — `ROOT_DIR` now mirrors the backend constant
  (`sys._MEIPASS` / executable dir when frozen); `SCREENSHOTS_DIR` moves to
  `~/.image-toolkit/screenshots` when frozen so the crawler's default
  screenshot dir never writes into the bundle.
- `gui/src/windows/settings/_credentials.py` — credential export writes to
  `~/.image-toolkit/backup` instead of `ROOT_DIR/backup`; test updated.
- Wallpaper slideshow daemon (both `system_display_subtab` and
  `monitor_display_subtab`) — clear "unavailable in the packaged build"
  dialog instead of "Daemon script not found at …".
- Managed WebDriver toggle — clear log message instead of launching the app
  binary against a non-existent script.
- `ComfyUIManager.start()` — raises a clear error when frozen (server launch
  needs a source checkout; connecting to an already-running server still
  works).
- LyCORIS training — clear status/error instead of `sys.executable -m`.
- `_reset_state._sync_vault_to_assets` — clear warning; the repo-template
  sync is a source-only workflow.

## Residual risks (documented, not fixed)

- Subprocess-launched features (#16–20) are genuinely incompatible with a
  PyInstaller bundle (they need a standalone Python + real `.py` scripts).
  The proper fix is a second embedded bundle or in-process re-exec with a
  `--daemon` argv; scoped out of a path-resolution audit.
- `backend/config/`, `vendor/` are intentionally not bundled (secrets; or
  external tools); all consumers already degrade/raise cleanly.
- The whole-`submodules/` data bundle includes each submodule's `.git` (the
  spec copies the tree wholesale) — size bloat, not a correctness issue.
