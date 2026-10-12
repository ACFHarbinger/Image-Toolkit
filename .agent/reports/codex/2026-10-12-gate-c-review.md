# Gate C review — Mistral, Kimi, Grok

Reviewed the linear stack through `c3cd43da`: #770 (`8d10e97e`),
#771 (`4ed6f9e5`), #772 (`c3cd43da`), based on #769 (`e7f4f7d5`).
Corrections are on `review/dl-gate-c`, worktree
`~/Downloads/Data/Tests/dl-gate-c-review`. Original PR branches are unchanged.

## Fixed

- **High — Matrix submitted every cell and released its lease before execution.**
  `run_matrix_sweep` now requires an execution-completion callback; the GUI
  waits on the manager's prompt-specific history. Failure, deletion, lost
  connection, or shutdown stops further submissions. The between-cell stop
  waits for the current execution; stop/VRAM checks include the first cell.
  A blocked-thread regression verifies that the lease remains held and no
  second prompt is submitted before completion.
- **Medium — history could never correct an inferred interruption.**
  History reconciliation now precedes queue-absence inference, enriches
  terminal records, and resets consecutive-absence counts when a prompt
  returns. A late optimistic submission cannot overwrite the executed graph.
  Graphs are copied at input/output boundaries to prevent consumer mutation.
  Cancelled pollers discard in-flight responses; callbacks may re-read records
  without deadlocking the provenance lock.
- **Medium — validation could remain stuck after reconnect.** A cancelled,
  blocked warmup no longer prevents a fresh request. Newly opened tabs also
  validate an already-warmed inventory. Default GUI validation uses the
  server inventory; explicit local-folder fallback remains available off-thread
  instead of recursively scanning the wrong installation on the GUI thread.
- **Medium — malformed inputs/overrides caused exceptions or silent drops.**
  Non-object inputs receive a validation issue; malformed override maps raise
  a visible error. Graph submission now applies cached preflight validation.
- **Medium — filmstrip retained every run indefinitely.** Retention is bounded
  at 200; replaced widgets are scheduled for deletion.
- Advanced samplers now receive `noise_seed`; non-finite float axes are
  rejected, and preview sweeps reject graphs without a supported latent-size
  node instead of silently executing at full size.

## Still required before #772 is complete

- **High — GPU coordination remains local to Comfy submission paths.** Training
  and other model jobs do not acquire this lease. External browser jobs are
  also outside it. Do not treat it as a machine-wide resource guarantee.
  Integrate with shared job admission before claiming exclusive GPU use.
- **Medium — #740 thermal-pressure stop is absent.** Only free-VRAM pressure is
  consulted. Supply a tested thermal signal and between-cell policy.
- **Medium — #739 has text buttons, not output thumbnails.** `OutputFilmstrip`
  shows filenames/status; it never retrieves `/view` images. Add bounded,
  off-thread thumbnail loading and a scrollable strip/grid.
- **Medium — LoRA weight cannot be used from the Matrix UI.** Its workflows
  come exclusively from the ControlNet/IP-Adapter guided templates, neither
  containing a LoraLoader. Permit a suitable selected workflow or provide a
  LoRA template; unsupported axes should not appear usable.

#770/#771 are acceptable with the corrections. #772 remains a draft requiring
changes for the outstanding acceptance gaps; no merge approval is implied.

## Validation

Targeted CPU-only checks: provenance 21, preflight 16, matrix 15,
Generate surface/guided 34, controller lifecycle 7 (93 total). Ruff and
`git diff --check` pass. No live ComfyUI/GPU execution, benchmark, or full suite.
