# HIE Restoration Tools — Chat

Date: 2026-08-12

Added two optional model contracts:

- `DeblurAdapter` for blind/non-blind image deblurring.
- `WatermarkRemovalAdapter` for mask-guided inpainting of user-owned/licensed
  images, requiring a user mask and explicit permission confirmation.

Both are preview-only, backend-neutral, and unavailable until verified model
weights/runtime configuration is supplied. They are registered in the default
pipeline without downloading weights or adding heavy dependencies.
