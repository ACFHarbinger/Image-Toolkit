# Parity Report: Web and Cloud (WP4 / #1109)

## Scope
Headless engines, fakes, handlers, and sidecar integration for:
- `web.crawler`
- `web.drive-sync`
- `web.media-loader`
- `web.entity-recon`
- `cloud.jobs`

## Changes
- `contracts/`: Added `DriveSyncExecuteParams`/`Result` and `MediaFetchParams`/`Result`. Regenerated all 37 contract artifacts and updated document hashes.
- `middleware/src/services/media_loader/fetch.py`: Implemented real URL fetch with destination directory validation and sanitized filenames.
- `middleware/src/services/drive_sync/sync.py`: Implemented file validation and vault-credential checks.
- `middleware/src/services/crawler/service.py`: Implemented download execution integration.
- `middleware/src/services/cloud_jobs/fake_service.py`: Built Gate B-compliant `create_fake_cloud_service` backed by `CloudJobStore` and `FakeProvider`.
- `middleware/src/sidecar/server.py`: Wired `drive_sync.sync`, `media_loader.fetch`, and lazy `_get_cloud_service` for `cloud_jobs.preview`/`submit`.

## Parity Gaps
PARITY-GAP web.crawler: live web crawler execution requires external booru network availability; offline/stub runner default.
PARITY-GAP web.drive-sync: OAuth token refresh dance requires browser redirect; headless fallback reads vault session keys.
PARITY-GAP web.media-loader: chunked resume and rate limiting are not ported.
PARITY-GAP web.entity-recon: live web reverse engine queries require paid API tokens; offline default.
PARITY-GAP cloud.jobs: live cloud provider dispatch guarded by Gate B; fake provider used.
