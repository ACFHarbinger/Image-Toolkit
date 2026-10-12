# Gate E follow-up review — Grok and Cursor

Reviewed Grok #790, `93ebd1386`, and Cursor #791, `8b7f03dec`.
Both are integrated on `review/dl-gate-e` with the corrections below.
**The two prior wiring holds are addressed in this corrected integration.**
Claude can review the combined candidate; the original two SHAs alone still
contain the findings below. Nothing merged or closed.

## Grok — suggestion producer

- **High: undisclosed cloud payload.** Image/note approval also authorized
  sending workflow scalar values, OCR text and trajectory. Added separate,
  explicit consent for those fields, bound to the source, image generation,
  destination, model, note, feedback and trajectory.
- **High: stale response replaced a newer source.** Completion now checks
  source/workflow/image/settings identity. Selection changes and disposal
  invalidate pending work; disposal during OCR prevents a subsequent model
  request. Requests cannot overlap a variant submission or pending verdict save.
- **Medium: misleading truncated premises.** Workflow strings were cut at
  500 characters, and the entire request could be silently sliced mid-context.
  Keep exact scalar values and reject oversized requests instead. Request
  workflows/history are independent snapshots.
- **Medium: installed model swaps always looked missing.** The producer did
  not supply an asset catalog. Validation now uses the connected server's
  cached object-info choices, with existing filesystem checks as fallback.

## Cursor — pair loader

- **High: deleted QObject emission.** Pair workers emitted through a loader
  parented to the deleted page. Worker signals now live independently; a
  blocked-worker/deleted-loader regression exercises actual destruction.
- **High: cache identity collisions.** Sanitized run IDs and filenames omitted
  subfolder/type. Cache keys now hash the complete output identity and writes
  use unique temporary files.
- **High: verdict writes could finish out of order.** Serialize writes and
  skip superseded revisions. The host waits for persistence before further
  voting/suggestions and reports persistence failures.
- **Medium: stale failures disabled a newer pair.** Failure signals carry
  their generation and stale ones are ignored. Unknown selected variants
  no longer fall back to the latest step.
- **Medium: any nonempty file enabled voting.** Verify image readability and
  pixel bounds off-thread; reject invalid images and remove corrupt fetched
  cache entries. Local files are never deleted by this cleanup.
- Verdict sidecar callbacks capture paths, not live widget methods.
  The pair test now uses its own temporary output directory and joins writers.

## Combined follow-up loop

The loaded comparison had parent first, so the next suggestion still used the
parent image and old workflow. A bound pair now selects the variant image and
captured variant workflow as the suggestion source. Requests wait for that
binding; submission completion clears busy state before publishing trajectory.
Current Review feedback is included in the advisor request.

## Validation

169 distinct targeted tests passed:
- 55 request/pair/schema tests.
- 53 vision/evidence/pair tests (12 pair tests overlap the first group).
- 40 suggestion/overlay/diff GUI tests.
- 33 existing upscale/comparison-window tests.

Repeated corrective subsets also passed. Ruff and diff checks are clean.
No full suite, benchmark, GPU, live model, or live ComfyUI call. These results
cover code integration and mocked/offline behavior, not model answer quality
or operational acceptance against a running server.
