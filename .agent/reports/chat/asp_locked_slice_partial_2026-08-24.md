# Locked renderer slice — partial baseline, 2026-08-24

Harbinger authorized the P1/P2 benchmark. The initial 21-case in-process
baseline was stopped after five cases because RSS retained across datasets
(3.6 → 5.8 GB) despite CUDA cache clearing. The runner was changed to one fresh
Python process per dataset; that reset baseline RSS to 0.85–1.12 GB per case.

After the user authorized termination of the Gradle/Java language services,
available memory rose to 20 GiB. The deterministic fresh-process baseline has
now completed eleven cases:

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

No P1 or P1+P2 case has run. The first stop was host pressure, not an ASP
crash: 31 GB RAM had only 4.5 GB free and 2 GB swap was full. With the services
terminated, each resumed case peaked at 3.58–3.73 GB RSS and the host remained
at about 20 GiB available. The remaining outputs live in the isolated,
recoverable temporary workspace recorded in `/tmp/asp-p1p2-locked-root`.
