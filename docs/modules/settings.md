# Cloud Jobs settings (`settings`)

| Field | Value |
|---|---|
| **Capability ID** | `settings` |
| **Service Package** | `middleware/src/settings/` |
| **Frontend View** | `frontend/src/views/cloudjobs/CloudJobsSettings.tsx` |
| **Contract Schema** | `contracts/schemas/capability/settings.json` |
| **Contract SHA-256** | `f7decebc58560f91af1448b80d01a55b0df7965df43a1c409469b3ecbb344e67` |

## Overview

The #880 settings service over the bridge (Gate D5 / #851). Keys route to
their ownership scope's store; the Cloud Jobs D5 surface — caps,
thresholds, admission, recovery/fallback, packing, retention,
notifications and regions — is one `CloudSettings` document under the
ACCOUNT-scoped `cloud_jobs/settings` key, editable in the `cloud.jobs`
window's Settings pane. The risk rule editor is not here: rules persist
in `cloud_jobs.db` and ride the jobs capability.

## Public Surface

- **Python Service API (`middleware/src/settings/service.py`, `cloud_jobs.py`):**
  - `SettingsService.get/set/get_many/validate`: scope-routed reads and
    validated writes (W0-16 catalog plus the `register_definitions`
    extension catalog, which keeps the frozen `gui/src` catalog untouched).
  - `cloud_settings_document/load_cloud_settings/save_cloud_settings`:
    whole-document read (defaults filled), validation and persistence for
    the Cloud Jobs key.
- **Sidecar handlers (`middleware/src/sidecar/handlers/settings.py`):**
  `settings.get`, `settings.set`, `settings.get_many` (one round trip for
  a form), `settings.set_many` (all-or-none; a rejected field saves
  nothing). Rejections are `settings.invalid_value`.
- **C++ Native Entrypoints (`import backend`):** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/settings.json`
- **Methods (`contracts/methods.toml`):** `settings.get`, `settings.set`, `settings.get_many`, `settings.set_many`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** every field is a labeled native control (input,
  select, checkbox) reachable by Tab; Save and Retry are buttons; the
  error phase renders before the loading branch with an `alert` role.
- **Screen-reader notes & known gaps:** labels are explicit (`htmlFor`);
  unit suffixes are separate text nodes. The regions editor's rows use
  `aria-label`; a live region announcing save outcomes is not wired yet.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/settings middleware/test/sidecar/test_settings_dispatch.py middleware/test/bridge/test_handshake_schema.py -q
```
