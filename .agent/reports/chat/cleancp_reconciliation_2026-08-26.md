# CleanCP reconciliation — 2026-08-26

Compared the two historical implementations before any merge:

| Revision | Integration | Result |
| --- | --- | --- |
| `0363410` prototype | Imports `asp_backend.alignment.registration_telemetry.edge_graph_components`; runs only for an empty or disconnected filtered graph | Not mergeable: that module no longer exists in the ASP tree. |
| `43d83eb` restoration, extended by `465328c` | Self-contained component calculation; records recovery telemetry; also triggers on missing adjacent links | Current implementation. |

The current helper preserves the prototype's MAD point cleanup, span-normalized
translation consensus, and all-frame connectivity acceptance rule. It replaces
only the unavailable telemetry dependency with an equivalent local helper and
adds the required before/candidate/after missing-adjacent-edge counts.

`run_stage.py` is intentionally aligned with the current helper: with the
default-off `ASP_CLEANCP_RESOLVE=1`, it attempts recovery for an empty graph,
a disconnected graph, or a connected graph missing an adjacent link. This is
the `asp_test94` fragmentation scope; the affine ratio gate is unchanged.

Verification: `test_cleancp_recovery.py` — 3 passed; both CleanCP files
compiled. No benchmark was launched and no behavior-changing splice was made.
