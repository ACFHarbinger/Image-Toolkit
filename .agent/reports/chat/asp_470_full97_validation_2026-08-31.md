# ASP #470 full-97 validation — 2026-08-31

**Result: recovery fix validated; Ground-Rule reference re-based.**

Canonical product-path validation at ASP `6188f43`, including recovery
`3983f76`, completed all 97 RAW_ASP cases. The execution host imposed a
30-minute process limit, so the benchmark ran as a 29-case initial segment
plus a checkpoint-resumed 68-case segment. Inputs, outputs, and log are at
`~/Downloads/Data/Tests/asp-470-full97-20260831/`.

| Outcome | Cases |
|---|---:|
| Raw ASP | 18 |
| Safe ASP | 43 |
| SCANS | 36 |
| `disconnected_edge_graph` | **0** |
| `no_valid_edges` | 15 |

The prior canonical baseline had 40 `disconnected_edge_graph` fallbacks and
8 Raw ASP outputs. Zero occurrences in this run validates #470's recovery
of a nonempty disconnected edge graph and raises Raw ASP to 18. It also
confirms the legacy 43-composite reference cannot be compared directly with
the post-M1b product runner.

The 15 `no_valid_edges` fallbacks are not recovered-graph failures: their
logs show filtering reduced the graph to zero edges after spatial dedup
(commonly only 2–3 retained frames), so there is no disconnected component
to reconnect. They remain a separate registration-yield problem.

Resources stayed below guardrails: final 9.15 GB RSS, 59.4% RAM, 4.3% VRAM;
no benchmark abort occurred.

The benchmark overwrites `_checkpoint.json` on resume, so the initial run
emitted only the 68-case JSON/report (`anime_stitch_20260831_014852.json`).
A monitored 1–29 re-capture produced `anime_stitch_20260831_022643.json`.
The two segments were merged into the ordered, 97-dataset reference
`anime_stitch_20260831_023504.json`; its manifest and full report are under
`~/Downloads/Data/Tests/asp-470-full97-20260831/output/`.
