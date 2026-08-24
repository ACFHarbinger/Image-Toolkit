# Locked renderer slice — partial baseline, 2026-08-24

Harbinger authorized the P1/P2 benchmark. The initial 21-case in-process
baseline was stopped after five cases because RSS retained across datasets
(3.6 → 5.8 GB) despite CUDA cache clearing. The runner was changed to one fresh
Python process per dataset; that reset baseline RSS to 0.85–1.12 GB per case.

Six isolated deterministic baseline cases completed before the host approached
the 80% RAM guardrail:

| case | result |
|---|---|
| 03 | Raw ASP |
| 05 | Raw ASP |
| 17 | Safe ASP, seam visibility gate |
| 37 | Safe ASP, seam visibility gate |
| 42 | Safe ASP, seam visibility gate |
| 78 | SCANS, affine ratio 3.26451 > 3 |

No P1 or P1+P2 case ran. The stop was host pressure, not an ASP crash:
31 GB RAM has only 4.5 GB free and 2 GB swap is full. Before another arm, free
external memory (notably the 2.6 GB `rust-analyzer` and VS Code Java/Gradle
services) and re-check capacity. The remaining outputs live in the isolated,
recoverable temporary workspace recorded in `/tmp/asp-p1p2-locked-root`.
