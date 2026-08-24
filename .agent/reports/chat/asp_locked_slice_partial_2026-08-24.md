# Locked renderer slice — partial baseline, 2026-08-24

Harbinger authorized the P1/P2 benchmark. The initial 21-case in-process
baseline was stopped after five cases because RSS retained across datasets
(3.6 → 5.8 GB) despite CUDA cache clearing. The runner was changed to one fresh
Python process per dataset; that reset baseline RSS to 0.85–1.12 GB per case.

After the user authorized termination of the Gradle/Java language services,
available memory rose to 20 GiB. The deterministic fresh-process baseline has
now completed all sixteen locked-slice baseline cases:

| case | result |
|---|---|
| 03 | Raw ASP |
| 05 | Raw ASP |
| 17 | Safe ASP, seam visibility gate |
| 37 | Safe ASP, seam visibility gate |
| 42 | Safe ASP, seam visibility gate |
| 78 | SCANS, affine ratio 3.26451 > 3 |
| 01 | SCANS, disconnected edge graph |
| 41 | Safe ASP, seam visibility gate (43.7 vs SCANS 2.4) |
| 65 | Safe ASP, composite banding gate (35.2 > 35.0) |
| 68 | Raw ASP |
| 74 | SCANS, disconnected edge graph |
| 28 | SCANS, affine min-gap 19.9941 < 20.3731 px |
| 67 | Raw ASP |
| 73 | SCANS, affine min-gap 17.8052 < 37.0111 px |
| 82 | SCANS, disconnected edge graph |
| 83 | SCANS, affine min-gap 14.7813 < 25.5123 px |

No P1 or P1+P2 case has run. The first stop was host pressure, not an ASP
crash: 31 GB RAM had only 4.5 GB free and 2 GB swap was full. With the services
terminated, each resumed case peaked at 3.58–3.73 GB RSS and the host remained
at about 20 GiB available. The remaining outputs live in the isolated,
recoverable temporary workspace recorded in `/tmp/asp-p1p2-locked-root`.

## P1 arm started

P1 uses `ASP_PLATE_SINGLE_POSE=1`, `ASP_PLATE_MULTIBAND=0`, and
`ASP_PLATE_EDGE_PRESERVE=0`. Test01 retained the baseline disconnected-graph
SCANS fallback. Test03 initially exposed a missing `os` import in the gated
plate-compositor branch; the narrow import repair passed the 4 focused plate
tests. The rerun completed Raw ASP with `plate_single_pose` active (RSS 3.51
GB). P1 is complete (16/16): Raw ASP is retained for 03 and 17; 01/74/82 use
the disconnected-graph fallback; 28/73/78/83 use affine safety fallbacks; and
05/37/41/42/65/67/68 use composite-gate fallbacks. Per-case peak RSS remained
at or below 3.84 GB.

## P1+P2 arm complete

P1+P2 uses `ASP_PLATE_SINGLE_POSE=1`, `ASP_PLATE_MULTIBAND=1`, and
`ASP_PLATE_EDGE_PRESERVE=1`. All 16 cases completed: Raw ASP is retained for
03 and 17; 01/74/82 use disconnected-graph SCANS; 28/73/78/83 use affine-safe
SCANS; and 05/37/41/42/65/67/68 use composite-gate fallbacks. Peak RSS was
3.85 GB. This is a routing/run-completion result only; it does not substitute
for the planned held-out quality inspection.
