# #754 provenance-bound pair loader

Stacked on `review/dl-gate-e` (`1abd1169b`). Lifts Codex's hold:
the overlay no longer enables voting until the parent and variant
outputs are on the comparison canvas.

## What landed

- `backend/src/core/guidance_pair.py`: exact parent→variant identity
  (`prompt_id` + `parent_prompt_id`), first-image resolve, contained
  cache paths (`.`/`..` rejected), generation token, lifetime file
  check, off-thread `persist_verdict()`.
- `ComparisonPairLoader` fetches remotes via `manager.fetch_output`
  off the UI thread. Review applies the pair through
  `_replace_compare_view` (does not clear the matching trajectory).
  Pin/`set_compare_paths` still invalidates the generation and clears
  the overlay.
- Verdict buttons stay disabled until a live, matching pair lands;
  votes persist off the UI thread.

## Checks

9 new backend + 2 new GUI; 22 backend + 54 GUI targeted green on the
touched files; 27 compare-canvas host tests still green.
`ruff` / `py_compile` clean. No suite / GPU / benchmark.
