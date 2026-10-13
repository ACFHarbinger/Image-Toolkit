# #754 What Changed overlay + guidance trajectory

Stacked on Muse's #752 (`dl-e-752-diff-apply` @ `af4852cb`). Taken over
from Qwen's slot (never claimed after the Gate E kickoff).

## What landed

- `backend/src/core/guidance_trajectory.py` (torch-free): applied
  node/field/old→new/reason, expected effect, Better/Same/Worse/Unsure
  verdicts, first+latest truncation (cap 5), structural steer after 3
  unresolved evaluations. `format_for_advisor()` is the next VLM-call
  payload. Sidecar JSON next to the variant workflow.
- `ComfyRunRecord.guidance_trajectory` surface field +
  `RunTracker.update_surface` / `ComfyUIManager.update_run_meta` so a
  later verdict patches the queued variant without rewriting history.
- Review overlay `gui/src/components/guidance/what_changed_overlay.py`
  under the reused `ImageCompareWindow` (not rebuilt). Diff & Apply
  attaches the trajectory to `run_meta` beside Muse's
  `parent_prompt_id` + `variant_label: assistant-suggested`.

## Checks

11 new backend + 5 new GUI; 35 backend + 23 GUI targeted green on the
touched files, plus 53 compare-canvas/upscale host tests still green.
`ruff` / `py_compile` clean. No suite / GPU / benchmark.

## Integration notes

#753 chips still slot into #752 `_add_row()` at Gate E integration —
this branch does not carry those two lines. Overlay and Diff & Apply
share Review; #750's vision panel is the other placement intersection.
