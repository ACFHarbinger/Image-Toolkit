# #479 e2e — Local Directory Sync dry-run + live exclude check

**Date:** 2026-08-31
**Owner:** Grok

## What ran

Scratch tree shaped like `~/.image-toolkit/` (allowed `theme.qss` +
`config/ui.json`; forbidden `*.vault`, `*.p12`, `library.db*`,
`listings_secure.db`, `cryptography/`, `secrets/`, `logs/`, `telemetry/`,
`thumbnail-cache/`, `.slideshow_config.json`).

| Step | Result |
|---|---|
| Engine exclude plan | only the two allowed files upload; remote `library.db` / `*.vault` never download |
| Worker dry-run (FakeDrive) | `upload_file` never called |
| Worker live (FakeDrive) | `upload_file` called only for `theme.qss` and `config/ui.json` |
| Live Google Drive | **not run** — no `IT_GDRIVE_ACCESS_TOKEN` in the environment; the on-disk vault at `~/.image-toolkit/*.vault` is encrypted and was not unlocked |

Tests: `gui/test/web/test_local_dir_sync_e2e.py` — 3 passed, 1 skipped
(`test_live_gdrive_dry_run_then_sync_excludes_secrets`).

## How to run the live Drive arm

Needs a Drive v3 access token (service-account or OAuth). Does **not** read
the account vault.

```
IT_GDRIVE_ACCESS_TOKEN='ya29...' \
  python -m pytest gui/test/web/test_local_dir_sync_e2e.py -k live_gdrive -q
```

Creates a unique remote folder `.itk-e2e-479-<pid>` (not the user's real
`.image-toolkit`), dry-runs (must stay empty), then live-syncs and asserts
the listing contains the two allowed files and none of the forbidden
suffixes/DBs.

## Gaps

- Live Drive not exercised on this box. FakeDrive covers the worker's
  `_execute` / `_upload` path; it does not prove GoogleDriveFileClient's
  REST calls against a real project.
- #482 (denylist → allowlist) is still the follow-up; this pass only
  verifies the current denylist keeps the named secret classes out.
