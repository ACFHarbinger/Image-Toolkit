# Cloud offer when VRAM admission refuses

| Field | Value |
|---|---|
| **Capability ID** | `cloud_offer` |
| **Service Package** | `middleware/src/services/cloud_offer/` |
| **Frontend View** | `frontend/src/shell/RunInCloudOffer.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_offer.json` |
| **Contract SHA-256** | `28c5f6853efc01b8a0a61eff1919345a94fef24f3b7cba5515ef80cd85c2013f` |

## Overview

When a conservative VRAM estimate exceeds 90% of the device, `cloud_offer.prefill` returns a JobSpec and a catalogue estimate. The method does not submit. Gate B stays closed. The seed catalogue can be empty, so `estimate_known` may be false.

## Public Surface

- **Python:** `offer_for_vram_refusal` in `middleware/src/services/cloud_offer/offer.py`.
- **Bridge:** `cloud_offer.prefill`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_offer.json`
- **Methods:** `cloud_offer.prefill`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** Owner, Estimated GB, Device GB, and Run in cloud instead are in the tab order. The button submits the form.
- **Screen-reader notes & known gaps:** the prefill line is static text. It is not a live region.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_cloud_offer.py middleware/test/sidecar/test_server.py -q
```
