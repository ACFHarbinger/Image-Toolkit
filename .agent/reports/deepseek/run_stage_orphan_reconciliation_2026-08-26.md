# run_stage.py orphaned-lineage reconciliation plan

**Status:** Scoping/plan only — no code. Execution is blocked on Codex's
`registration_gate.py` + `registration_telemetry.py` recovery landing first
(the deferred-min-gap gate and telemetry hunks reference them).

**Orphan reference:** `recovered-orphaned-asp-work` (`df71697`).
**Current:** `submodules/ASP` HEAD (`cb5d46e`); `run_stage.py` is 999 lines
and is the pre-reconciliation version.

## Orphaned diff (`HEAD..recovered-orphaned-asp-work -- run_stage.py`, 257/-45)

Per-hunk disposition against the current tree:

| # | Orphaned hunk | Depends on | Status |
|---|---|---|---|
| 1 | `_stage4_memory_snapshot()` (psutil/CUDA) + Stage-4 mask-memory artifact | none | **To-do** (self-contained) |
| 2 | `_pair_proposal_telemetry` dict + `_pairwise_match_with(proposal_telemetry=...)` + adjacent-survival/components telemetry | `edge_graph_components` from registration_telemetry | **Blocked** on Codex's `registration_telemetry.py` |
| 3 | `collect_registration_telemetry(...)` (post-filter + post-BA) | `registration_telemetry.py` | **Blocked** |
| 4 | CleanCP recovery (current `ASP_CLEANCP_RESOLVE` guard + telemetry shape) | CleanCP (already reconciled by Codex, `43d83eb`) | **Reconcile shape** — current tree has it; the orphaned version records `cleancp_recovery` into `_pair_proposal_telemetry` |
| 5 | Wave correction Stage 7.2 | `_wave_correction.py` | **Already landed** (Claude `e068b50`) — only comment diff |
| 6 | `_affine_health` artifact with `_affine_gap_stats` + `missing_adjacent_edge_count` | `_affine_gap_stats` (removed import in orphan) | **Decide**: current tree imports `_affine_gap_stats` and records the richer artifact (line 46/506); the orphan removes it and restructures. The current richer artifact is likely authoritative — confirm before reconciling. |
| 7 | `_deferred_min_gap` + `ASP_DEFER_MIN_GAP_TO_REGISTRATION_GATE` + `RegistrationRiskGate().evaluate(...)` | `registration_gate.py` | **Blocked** on Codex |
| 8 | PANORAMA fallback with `ASP_DISABLE_PANORAMA_FALLBACK` | none | **To-do** — NOT in current tree (verified); orphan adds the disable guard |
| 9 | `_pairwise_match_with` P2 overlap wiring (`ASP_OVERLAP_PROPOSAL`, `extra_proposals`, `bg_masked_matching`) | `_overlap_proposal.py` (recovered by Antigravity) + `_pairwise.py` (already supports `extra_proposals`) | **To-do** once gate lands (or independently — no dep on the gate) |
| 10 | `bg_masked_matching` kwarg in `_pairwise_match_with` | `ASP_BG_MASKED_MATCHING` (recovered) | **To-do** |

## Execution order (once Codex lands the gate + telemetry)

1. Add `_stage4_memory_snapshot()` + Stage-4 mask-memory artifact (self-contained).
2. Wire `_pairwise_match_with`: pass `proposal_telemetry`, `extra_proposals`
   (P2 overlap), `bg_masked_matching`; record adjacent-survival + components.
3. Restore the post-filter/post-BA `collect_registration_telemetry` calls
   (needs `registration_telemetry.py`).
4. Reconcile the `_affine_health` artifact (gap stats + deferred-min-gap field).
5. Add `_deferred_min_gap` + the `ASP_DEFER_MIN_GAP_TO_REGISTRATION_GATE`
   block (needs `registration_gate.py`).
6. Confirm PANORAMA `ASP_DISABLE_PANORAMA_FALLBACK` already present; keep.
7. Verify: targeted `backend/test/core/pipeline/` + `test_alignment/` green
   (no bench run — reconciliation is code motion + telemetry).

## What is NOT in scope

- CleanCP semantics (already reconciled by Codex — do not re-merge its
  prototype; the current `43d83eb` version is authoritative).
- Wave correction (already landed, `e068b50`).
- Any benchmark / full-suite run (RESOURCE RULE).