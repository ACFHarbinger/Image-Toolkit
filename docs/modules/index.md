# Module Documentation & Contract Hash Spine

Every migrated capability under `middleware/src/services/<feature>/` and `frontend/src/features/<feature>/` carries a module README in `docs/modules/<feature>.md` built from [`_template.md`](_template.md).

## Contract Freshness Invariant

Each module README declares two machine-verified metadata lines in its header table:

- **Contract Schema:** path to the capability's JSON Schema in `contracts/schemas/capability/<name>.json` (or `contracts/CONTRACTS.sha256` for aggregate spine modules).
- **Contract SHA-256:** the exact SHA-256 digest recorded in [`contracts/CONTRACTS.sha256`](../../contracts/CONTRACTS.sha256) for that schema (or the `total` hash).

CI runs `python middleware/validation/check_docs_freshness.py`, which verifies that:

1. Every `docs/modules/*.md` file (excluding `index.md` and `_template.md`) includes the required sections (`## Overview`, `## Public Surface`, `## Contract & Routing`, `## Accessibility & Known Gaps`, `## Verification`).
2. Every referenced contract hash in `docs/modules/*.md` matches the live digest in `contracts/CONTRACTS.sha256`. Any contract change without a corresponding module README update fails the CI build.

## Modules

| Capability | Service Path | Contract | Module Doc |
|---|---|---|---|
| System / Convert (`W0-17` / `P-01`) | `middleware/src/services/convert/` | `contracts/schemas/capability/system.json` | [Convert Service (`convert.md`)](convert.md) |
| Cloud Jobs (`#847`, `#848`, `#849`, `#850`) | `middleware/src/services/cloud_jobs/` | `contracts/schemas/capability/cloud_jobs.json` | [Cloud Jobs (`cloud_jobs.md`)](cloud_jobs.md) |
| Cloud offer (`#852`) | `middleware/src/services/cloud_offer/` | `contracts/schemas/capability/cloud_offer.json` | [Cloud offer (`cloud_offer.md`)](cloud_offer.md) |
| Settings (`#851`) | `middleware/src/settings/` | `contracts/schemas/capability/settings.json` | [Cloud Jobs settings (`settings.md`)](settings.md) |
| Library admin (`#899`, `#900`) | `middleware/src/services/library_admin/` | `contracts/schemas/capability/library_admin.json` | [Library admin (`library_admin.md`)](library_admin.md) |
| Library preview (`#895`) | `middleware/src/services/library_preview/` | `contracts/schemas/capability/library_preview.json` | [Library preview (`library_preview.md`)](library_preview.md) |
| Merge (`#903`) | `middleware/src/services/merge/` | `contracts/schemas/capability/merge.json` | [Merge (`merge.md`)](merge.md) |
| Similarity (`#904`) | `middleware/src/services/similarity/` | `contracts/schemas/capability/similarity.json` | [Similarity (`similarity.md`)](similarity.md) |
| Extractor (`#905`) | `middleware/src/services/extractor/` | `contracts/schemas/capability/extractor.json` | [Extractor (`extractor.md`)](extractor.md) |
| Image Stitching (`#914`) | `middleware/src/services/stitch/` | `contracts/schemas/capability/stitch.json` | [Image Stitching (`stitch.md`)](stitch.md) |
| Settings window (`#917`) | `middleware/src/services/prefs/` | `contracts/schemas/capability/prefs.json` | [Settings window (`prefs.md`)](prefs.md) |
| Desk (`#919`) | `middleware/src/services/desk/` | `contracts/schemas/capability/desk.json` | [Desk (`desk.md`)](desk.md) |
| Deep Learning (`#912`) | `middleware/src/services/dl/` | `contracts/schemas/capability/dl.json` | [Deep Learning (`dl.md`)](dl.md) |
| Cloud sync (`#908`) | `middleware/src/services/drive_sync/` | `contracts/schemas/capability/drive_sync.json` | [Cloud sync (`drive_sync.md`)](drive_sync.md) |
| Media loader (`#909`) | `middleware/src/services/media_loader/` | `contracts/schemas/capability/media_loader.json` | [Media loader (`media_loader.md`)](media_loader.md) |
| Authentication (`#918`) | `middleware/src/services/auth/` | `contracts/schemas/capability/auth.json` | [Authentication (`auth.md`)](auth.md) |
| Module Template | `middleware/src/services/<feature>/` | `contracts/CONTRACTS.sha256` | [Module Template (`_template.md`)](_template.md) |
