# Cloud offer when VRAM admission refuses

| Field | Value |
|---|---|
| **Capability ID** | `cloud_offer` |
| **Service Package** | `middleware/src/services/cloud_offer/` |
| **Frontend View** | `frontend/src/shell/RunInCloudOffer.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_offer.json` |
| **Contract SHA-256** | `f7decebc58560f91af1448b80d01a55b0df7965df43a1c409469b3ecbb344e67` |

## Overview

When a conservative VRAM estimate exceeds 90% of the device, `cloud_offer.prefill` returns the constructed JobSpec on `spec` plus a catalogue estimate. The offer view copies that spec into editable fields. Changing those fields does not save or submit. Gate B stays closed. The seed catalogue can be empty, so `estimate_known` may be false. An estimate inside the ceiling returns an empty `spec`.

## Public Surface

- **Python:** `offer_for_vram_refusal` in `middleware/src/services/cloud_offer/offer.py`.
- **Bridge:** `cloud_offer.prefill`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_offer.json`
- **Methods:** `cloud_offer.prefill`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** Owner, Estimated GB, Device GB, and Run in cloud instead are in the tab order. The button asks for a prefill. When an offer is shown, Title, Kind, Provider, Region, VRAM GB minimum, Runtime seconds, and Job id are editable and do not submit.
- **Screen-reader notes & known gaps:** the prefill summary is static text. It is not a live region.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_cloud_offer.py middleware/test/sidecar/test_server.py -q
```
