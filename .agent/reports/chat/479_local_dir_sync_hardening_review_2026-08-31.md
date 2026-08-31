# #479 Local Directory Sync — hardening review

**Date:** 2026-08-31 · **Reviewer:** Claude · **Target:** `a44f8a3f`
(`gui/src/helpers/web/cloud/local_dir_sync_worker.py`,
`gui/src/tabs/web/drive_sync_tab/{local_dir_sync_subtab,sync_data_subtab}/`)

## Subtabs are present (the "no subtabs" report is a stale process)

Verified on current `main`: `DriveSyncTab(...)` builds a `QTabWidget` with
**"Sync Data"** + **"Local Directory Sync"** (`_ui_builder.py` → `SyncDataSubtab`
/ `LocalDirSyncSubtab`). The main window renders tabs as plain QWidgets in a
`QScrollArea` (`_lifecycle.py:47`) — no QML path (`DriveSyncTab.qml` is dead
legacy). A running app started before `a44f8a3f` (14:14) won't show them;
restart `python backend/main.py`.

## Findings

### S1 — CRITICAL: exclude list missed live databases and path-leaking state

Real `~/.image-toolkit/` contains `library.db` + `library.db-wal` (4 MB, live
SQLCipher), `listings_secure.db`, `.slideshow_config.json` (absolute monitor
paths), `telemetry/`, `recovery/`, `cryptography/` (key material),
`storyboard-cache/`, `listing-images/`. The original `DEFAULT_EXCLUDES` caught
only `*.vault/*.p12/*.key`, `secrets/`, `*.log`, `thumbnail-cache/`.

Byte-syncing `library.db*` across devices with last-write-wins **corrupts the
database** (multi-writer DB replication is explicitly out of scope per roadmap
§4.20). The JSON/telemetry files **leak absolute host paths**.
`cryptography/` sitting next to `secrets/` is unguarded key material.

**Fixed here:** `DEFAULT_EXCLUDES` extended — `*.db/-shm/-wal/-journal`,
`*.sqlite*`, `cryptography/`, `telemetry/`, `recovery/`, `logs/`,
`.slideshow_config.json`, `.monitor_slideshow_daemon.json`,
`.phase_db_migration_state.json`, `.extraction_history.json`,
`storyboard-cache/`, `listing-images/`.

**Recommended follow-up (own issue):** flip to an **allowlist** — sync only
`config/`, `keybindings.json`, `user_theme.qss`, `preferences`, `assets/`
(minus `secrets/`). A denylist over a directory that gains new subdirs every
release is the wrong default for "don't upload the user's data."

### S2 — provider client re-authed per file

`_provider_client()` was constructed fresh in `_fetch_remote_listing` and in
every `_upload`/`_download` — a full OAuth / service-account handshake per
file. **Fixed:** cached on `self._client`, one build per `run()`, cleared in
`finally`.

### S3 — QThread could die without a `finished` signal

`_execute()` only caught exceptions around `_fetch_remote_listing` and
per-file. An error in `engine.build_plan()` (`os.walk`/`stat`) or
`_provider_client()` would propagate out of `run()` → GUI hangs waiting on
`finished`. **Fixed:** `run()` now has a top-level `except` that emits
`finished(False, …)`.

### S4 — minor

- `LocalDirSyncSignals` class is dead (`pass`) — remove.
- `build_plan` treats a file present both sides with `abs(mtime)<2s` and equal
  size as in-sync — fine, but a content hash on the tie (as the roadmap says)
  is not implemented; size+mtime only. Acceptable for v1; note it.
- No cancellation check inside `engine.build_plan()` for a very large tree.

## Status

S1/S2/S3 fixed in this pass (`local_dir_sync_worker.py`), `test_cloud_sync.py`
12/12 still green. S1 allowlist redesign + S4 items → follow-up issue.
