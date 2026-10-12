# Gate E review — #750–#754

**Not ready to declare Gate E complete.** Integration fixes are on
`review/dl-gate-e`; two end-to-end connections remain missing.

Reviewed Grok `91fd66909` (#784), Mistral `f6731761b` (#785),
Muse `af4852cba` (#786), Kimi `9f738434a` (#787), and Cursor
`7f8d6d76e` (#788), combined over main `b069c4de8`.
Worktree: `~/Downloads/Data/Tests/dl-gate-e-review`.

## Corrections

- **Grok / #750 — high:** cloud approval survived endpoint/model/note
  edits; standard urllib redirects could exceed the approved destination.
  Approval now resets on edits; redirects and implicit proxies are refused,
  remote cloud endpoints require HTTPS, URL credentials are rejected.
  Cloud payloads use the image's actual MIME type. The workspace now supplies
  its vault; decryption runs in the worker. Image changes invalidate queued
  results, and a deleted panel does not own the worker's signal object.
- **Mistral / #751 — high:** cached validation could patch a subsequently
  edited graph; destination types were unchecked; duplicate rows conflicted;
  a parameter change could bypass model availability checks.
  Apply rechecks the graph hash/premise, scalar values retain their types,
  integers retain full seed precision, duplicate rows are rejected, and model
  paths must match an installed relative path. Schema versions, hashes and
  nonfinite confidence values are checked.
- **Muse / #752 — high:** source IDs could escape the workflow directory,
  repeated variants overwrote files, checkbox changes re-enabled a pending
  submission, and failed/cancelled runs emitted success.
  Variant files are contained and unique; pending submissions lock their
  source, and completion is checked. Workflow/trajectory writes happen in
  the worker, with run-specific provenance and sidecars.
- **Kimi / #753 — medium:** unresolved or invented reference kinds inflated
  confidence; a missing tournament checkpoint silently became the leader.
  The displayed heuristic uses resolved local evidence, ignores advisor
  self-confidence, and marks unsupported artifacts unverified. Run references
  stay under the configured runs root; dataset handoffs accept image files,
  not directories or strings iterated as path lists.
  Evidence/abstention widgets are integrated into Diff & Apply, with their
  Train handoff connected. Artifact/path resolution is off the UI thread.
- **Cursor / #754 — high:** voting on an unknown variant modified the latest
  step; the overlay rendered the latest step even when another was selected;
  loaded trajectories could exceed their declared bound.
  Votes now require a matching variant, the overlay shows that step and its
  feedback, loaded history is capped, and sidecar replacement uses unique
  temporary files. Changing comparison images clears the old trajectory.

## Remaining landing blockers

1. **Grok + Mistral + Muse: structured suggestion producer.**
   Production code only defines `show_guidance()`; nothing calls it.
   The current VLM action produces descriptive observations, not a validated
   schema response. Implement the explicit request → parse → validate →
   display path against captured executed workflow provenance. Include
   `advisor_trajectory()` in subsequent requests; it currently has no caller.
   Evidence must distinguish artifact-backed observations from model claims.
2. **Cursor + Muse: matching comparison outputs.**
   A successful requeue updates the overlay without loading the parent and
   variant outputs into the comparison canvas. The pre-existing arbitrary
   pinned image(s) could receive a verdict for another run. Verdict buttons
   are now disabled in this host path until a provenance-bound pair loader
   exists. Implement off-thread output fetching, generation/lifetime checks,
   exact pair/variant identity, and then enable voting. Keep verdict
   persistence off the UI thread when connecting this path.

These are integration gaps, not failures covered by the standalone widget
tests. Do not close #750–#754 or announce the feedback loop complete based
on the current green tests.

## Validation

134 distinct targeted tests passed: 87 core guidance tests, 3 provenance
tests, and 44 GUI tests. Repeated subsets excluded. Ruff and diff checks
passed. Regression cases include approval edits, queued stale OCR results,
real loopback redirect refusal, wrong image suffix/MIME, stale apply,
fractional/boolean destinations, seed precision, duplicate rows, asset
traversal, fabricated evidence, missing checkpoints, unknown-variant votes,
bounded loaded history, unique variant files and failed submissions.

No full suite, benchmark, GPU/model/server run or live cloud call.
