# Locked-slice review image regeneration — 2026-08-26

Completed the 16-case baseline/P1/P1+P2 review bundle at
`locked_renderer_exports_2026-08-24/`: 48 labelled PNGs.

The 13 previously missing cases were regenerated using isolated fresh Python
processes, fixed seed 1729, native thread caps of one, deterministic mode, and
per-dataset resource guards. Runs were serialized. Host RAM stayed below the
80% guardrail; per-process RSS finished below 3.9 GB.

The final control reruns were reproducible across arms:

- test74: disconnected-edge-graph SCANS fallback.
- test28: affine-invalid SCANS (`19.9941 < 20.3731` px min gap).
- test83: affine-invalid SCANS (`14.7813 < 25.5123` px min gap).
- test73: affine-invalid SCANS (`17.8052 < 37.0111` px min gap).

All four produced byte-identical baseline, P1, and P1+P2 PNGs. The export is
for locked-slice human review; it makes no quality-acceptance claim and changes
no renderer behavior.
