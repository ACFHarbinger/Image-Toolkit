# HIE Restoration Quality Diagnostics — Chat

Date: 2026-08-12

Extended `hie-restore --report` with a dependency-light edge-variance
sharpness score for the input and output, plus `sharpness_delta`. Reports now
help compare deblur previews objectively while retaining the preview-only and
mask-coverage audit fields.
