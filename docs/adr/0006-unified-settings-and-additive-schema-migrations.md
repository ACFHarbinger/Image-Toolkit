# ADR-0006: Shared Scoped Settings Service and Additive-Only Schema Migrations

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#880](https://github.com/ACFHarbinger/Image-Toolkit/issues/880), [#884](https://github.com/ACFHarbinger/Image-Toolkit/issues/884)

## Context

During migration coexistence, users may run both the PySide6 GUI and the Tauri GUI against the same `~/.image-toolkit/` directory. Divergent preference stores or destructive SQLite schema changes would break the coexisting shell.

## Decision

1. **Single shared settings service (#880):** Both GUIs use one settings service preserving existing keys and scopes (`DEVICE`, `ACCOUNT`, `SESSION` from `gui/src/preferences/store.py`), performing optimistic conflict detection, and backing up legacy configuration files before migrating.
2. **Additive-only schema migrations while PySide6 rows live (#884):** While a capability's PySide6 row is still active (`status != "pyside-deleted"`), database migrations may only add tables, columns, or indexes and backfill data. `DROP`, `RENAME`, and column-type narrowing on live tables are rejected by `middleware/validation/check_migration_additive.py` in CI unless covered by a deletion PR or a bounded `[[exception]]` in `migration/features.toml`.

## Consequences

- Switching between PySide6 and Tauri during Wave 0–9 never corrupts user preferences or breaks `library.db` / `cloud_jobs.db` compatibility.
- Destructive schema cleanup is deferred to each capability's PySide6 deletion PR.
