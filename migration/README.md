# Migration ledger (W0-18, #882)

`features.toml` is the inventory, parity gate, and docs index for the
PySide6 → Tauri migration. One record per capability (stitch is one record
with eight routes; Deep Learning one with five), never per route.

Rules of the road:

- **Edit the ledger, regenerate the doc.** `docs/migration/parity.md` is
  generated: `python migration/generate_parity.py` (or `--check` to verify
  freshness, as CI does).
- **CI enforces the ledger** via
  `middleware/validation/check_migration_ledger.py` (`just
  check-migration-ledger`): route coverage both ways against
  `middleware.src.shell.catalog`, path existence (live rows) and deletion
  (`pyside-deleted` rows), exactly-once ownership of every `gui/src` file,
  scenario presence, OS-checklist completeness, and the contracts-hash pin.
- **Status values:** `pyside-only` → `both` → `parity-passed` →
  `pyside-deleted`. Deleting a row requires green parity evidence, a ticked
  OS checklist, Harbinger's sign-off, and one deletion PR that removes only
  that row's PySide6 code and tests.
- **Route map:** each `[[feature.routes]]` row maps a legacy route (`from`)
  onto a catalog id (`to`); `alias` rows must match the catalog's own alias
  map (e.g. `experimental-dl`). New navigation has no `from`.
- **Exceptions:** a bounded `[[exception]]` (`feature`, `path`, `reason`,
  `issue`, `approved_by`, optional `expires`) is the only escape from the
  `gui/src` freeze and the additive-only migration rule (#884). Expired or
  incomplete records suppress nothing.
- **Contracts pin:** `[ledger].contracts_hash` must equal the `total` in
  `contracts/CONTRACTS.sha256`; bump it in the same PR that changes
  contracts (#874 coordination).

Per-record fields: `id`, `title`, `issue`, `wave`, `owner`, `status`,
`pyside`/`pyside_exclude`, `tauri`, `service`, `contract`, `docs`,
`scenarios`, `windows`, `capabilities`, `routes`, `os_checklist`, `notes`.
Path lists are existence-checked when present; `service` points at
`middleware/src/services/<feature>` once the row's wave builds it.
