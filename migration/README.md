# Migration ledger (W0-18 / #882)

`features.toml` is the source of truth for the PySide6 → Tauri migration:
**one record per capability**, not per route (stitch = one record covering
8 routes, DL = one record covering 4 routes plus the 5 legacy `ml.*`
pages). See `docs/moon/roadmaps/tauri_migration.md` §2 for the mechanics.

- Validator: `python middleware/validation/check_migration_ledger.py`
  (also `just check-migration-ledger`; runs in the CI lint job).
- Parity doc: `python migration/generate_parity.py` rewrites
  `docs/migration/parity.md`; `--check` fails on drift (CI lint job).
  Never edit the generated file.

## Record schema

```toml
[[feature]]
id = "system.convert"        # page/workspace: a #869 catalog id (middleware/src/shell/catalog.py);
                             # window: a dotted id NOT in the catalog (e.g. window.settings)
kind = "page"                # page | workspace | window
title = "Convert"
owner = "Kimi"               # agent name or "unclaimed"
wave = "wave-1"
issue = 894                  # tracking issue (int)
status = "pyside-only"       # pyside-only | both | parity-passed | pyside-deleted
routes = ["system.convert"]  # catalog ids owned: page → [its own id]; workspace → its route ids
                             # (the workspace's own id is implied); window → []
route_map = { convert = "system.convert" }  # old id → catalog id; must cover the catalog
                             # aliases (dl owns the ml.* → dl.* map) and every owned entry's
                             # legacy_frontend_id
pyside = ["gui/src/tabs/core/convert_tab.py"]  # paths/dirs/globs owning the Qt code
tauri = ["frontend/src/tabs/core/ConvertTab.tsx"]  # paths under frontend/
service = ""                 # middleware/src/services/<feature>/ once it exists, else ""
contract = ""                # capability from contracts/methods.toml once adopted, else ""
docs = ""                    # module doc path, required for parity-passed
scenarios = []               # parity scenario paths (migration/parity, #883)
os_checklist = [ { item = "…", platform = "linux", checked = false } ]  # platform: linux|windows|macos
```

`pyside` + `[[shared]]` must partition `gui/src/**/*.py`: exactly one
owner per file, no unowned file. `[[shared]]` entries (`{path, owner,
note}`) cover shell infrastructure with the owning Wave-0 issue in
`note`. Rows whose absorbed code lives in `middleware/src/` or
workspace controllers point `pyside` at their existing `gui/src` files
or `[]` if no standalone PySide6 surface remains (#867/#1039).

## Parity scenarios (#883)

`migration/parity/runner.py` loads a JSON scenario. `kind` is `differential`
(the entry's `pair(tmp)` returns legacy and service projections) or
`characterization` (the entry's `current(tmp)` against an `oracle` JSON file).
The comparison is `migration/parity/diff.py`. Entries must not import a UI.
The convert pilot's scenario is `migration/scenarios/system.convert.json`.

Playwright against the Vite build, with a page-level contract mock, is
`frontend/e2e/shell.spec.ts` and runs in the PR frontend job. `tauri-driver`
is `frontend/e2e/tauri-driver-smoke.sh`. The release workflow calls it. A
runner without the driver records a skip; `TAURI_DRIVER_REQUIRED=1` makes
that skip a failure. The PR job only runs the script's `--check`.

## Status lifecycle

`pyside-only → both → parity-passed → pyside-deleted`

- `both`/`parity-passed` require at least one parity scenario — unless
  `pyside` is empty (nothing to diff).
- `parity-passed` additionally requires `docs` and every `os_checklist`
  entry `checked = true`.

**Deletion gate** (one PR per row): parity evidence green, OS checklist
ticked, Harbinger sign-off; the PR deletes that row's PySide6 code and
tests plus any destructive migration, and nothing else. The row flips to
`pyside-deleted` in the same PR; its `pyside` paths are then exempt from
existence/ownership (check_migration_additive.py auto-allows destructive
steps inside them).

## `[[exception]]`

The bounded escape hatch for the `gui/src` freeze (#884) and the
additive-only schema guard (#884 / check_migration_additive.py, which
consumes these records). Fields: `feature`, `path` (exact or glob),
`reason`, `issue` (int), `approved_by`, optional `expires` (ISO date).
Expired or incomplete records do not suppress the guards; the validator
rejects expired records — remove them instead of letting them rot. A
spike no-go that keeps a row alive past its wave is also recorded here
(roadmap §2, "Spikes").

## Conventions and judgment calls

- **No-PySide-surface rows** (`developer.benchmarks`): the catalog marks
  the page `surfaces = ("frontend",)` — it exists only in the Tauri app
  (`frontend/src/tabs/apollo`), so `pyside = []` and the row starts at
  `both` with no scenarios required. It tracks the meta issue #864 since
  no dedicated issue exists.
- **stitch / manga / HIE**: absorbed into `middleware/src/` (#1035–#1039).
  The ledger points to any surviving `gui/src` controllers (e.g.
  `stitch_workspace.py`) and uses `pyside = []` where submodule Qt trees
  were retired. Only the workspace controllers
  (`stitch_workspace.py`, `dl_workspace.py`, `comfy_workspace_controller.py`)
  live in `gui/src/modules/` and are owned by their rows.
- **`gui/src/preferences/` stays `[[shared]]`** (#880 settings service
  keeps those keys/scopes); `window.settings` owns only
  `gui/src/windows/settings/`.
- **`gui/src/modules/pilots/`** (the log panel module) is owned by
  `window.logging` (#919), not by the shared shell infra.
- **Sampler subtab** is a subtab of the Convert tab, so
  `gui/src/tabs/core/sampler_subtab` belongs to `system.convert`;
  `gui/src/tabs/core/protos` (legacy extractor/wallpaper prototypes) is
  shared and is deleted with rows #905/#913.
