# HIE CPU Restoration Baseline — Chat

Date: 2026-08-12

Added optional Pillow CPU runners behind the restoration job contract:

- `cpu_deblur_runner`: bounded UnsharpMask enhancement.
- `cpu_masked_inpainting_runner`: supplied-mask median-neighborhood fill.

These are conservative preview baselines, not neural restoration substitutes.
They create new output files, preserve the original, report progress, support
cancellation, and require the existing permission/mask checks for watermark
inpainting. Install with the `restoration` optional middleware extra.
