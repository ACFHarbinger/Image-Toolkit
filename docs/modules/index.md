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
| Module Template | `middleware/src/services/<feature>/` | `contracts/CONTRACTS.sha256` | [Module Template (`_template.md`)](_template.md) |
