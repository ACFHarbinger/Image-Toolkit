# Cloud Compute setup window (`cloud_setup`)

| Field | Value |
|---|---|
| **Capability ID** | `cloud_setup` |
| **Service Package** | `middleware/src/services/cloud_setup/providers.py` |
| **Frontend View** | `frontend/src/shell/CloudComputeSurface.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_setup.json` |
| **Contract SHA-256** | `e0bf52849356521d11f040d81e13f7007b74c54d6f03ea66a05819e10ddec22d` |

## Overview

The Cloud Compute setup window (T-04 / #920): providers, credentials,
request builder, and dashboards, opened from the header gear or a
shift-click on the Cloud Jobs control. The provider descriptor catalog
mirrors the Qt providers pane (`gui/src/windows/cloud/providers_pane.py`)
with `badge_color` carried as a theme-token name instead of a resolved
RGB value. The Request Builder is D4's (#992) and the dashboards are
D3's (#990), both mounted from this surface.

## Public Surface

- **Python Service API (`middleware/src/services/cloud_setup/providers.py`):**
  - `providers_result()` — the four-provider descriptor catalog (gcd,
    cloudflare, oracle, aws) in Qt pane order.
  - `provider_ids()` / `is_provider()` — catalog order and membership.
- **Bridge:** `cloud_setup.providers`.
- **Settings (`cloud_setup/profiles`, ACCOUNT scope):** per-provider
  non-secret setup config (region/endpoint preferences), registered in
  the settings extension catalog and written through the landed
  `settings` capability.
- **C++ Native Entrypoints (`import backend`):** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_setup.json`
- **Methods (`contracts/methods.toml`):** `cloud_setup.providers`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** tabs are `aria-pressed` buttons; the profile form
  is labeled inputs with a submit button (Enter saves); provider cards
  are semantic articles with definition lists.
- **Screen-reader notes & known gaps:** credentials never transit the
  bridge — the credentials tab states the vault path explicitly, and
  attaching real credentials rides the vault unlock (#918 / #879) with
  no password field rendered until then.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_cloud_setup_providers.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py -q
```
