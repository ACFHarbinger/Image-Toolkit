# Cursor #763 lifetime review

Reviewed Cursor commit 48888be2. Integrated it on review/dl-gate-b, retaining the earlier Gate B fixes. The submitted commit still needed corrections; the review branch contains those corrections.

## Findings fixed

- **High: payload completion released live workers.** BaseQThreadWorker.finished is emitted inside run(), before thread exit. Replaced finished-based release with owner-independent retention checked through wait(0). A blocked real-QThread test verifies retention after payload delivery and panel deletion.
- **High: repeated handoffs could destroy a live preparation worker.** Retain every preparation worker until actual exit, discard stale results, and clean unused staged results after completion.
- **High: training completion released the dataset lease before the Python thread returned.** Keep the thread/lease until is_alive() is false. Delay workspace deletion while training can still emit through its widgets; hide the host while disposal completes.
- **High: tag review also reads staging.** Prevent replacement during tag review and defer disposal cleanup until both readers finish.
- **Medium: Start could run the previous dataset while preparation was pending.** Block dispatch until preparation completes.
- **Medium: snapshot restoration and Review Tags still scanned on the GUI thread.** Route both through DatasetPrepareWorker. Emit effective-config updates after applying prepared results.
- **Medium: new captions were saved only in temporary staging.** Save beside the original image and expose the sidecar through staging so captions survive cleanup.

Disposal remains nonblocking. Thread retention uses actual completion, not the result signal. Cancellation can take until the underlying model operation returns; the UI and leased data remain alive during that interval.

## Validation

- Cursor's workspace/dialog/training tests plus lifetime regressions: **74 passed in 1.50s**.
- Caption fix and affected dialog/lifetime regressions: **29 passed in 1.23s** (overlap with the first batch).
- Configuration/comparison integration checks: **23 passed in 2.05s**.
- Ruff and diff whitespace checks pass.

Tests include real blocked QThreads, superseded preparation results, deletion deferral, early training-result delivery, and caption persistence after staging removal. GPU training, frozen builds, and full-app shutdown were not exercised. No benchmark or full suite was launched.

Evidence: ~/Downloads/Data/Tests/dl-gate-b-review-evidence/review3-*.log.

The reviewed blockers are addressed in the integration branch; do not merge Cursor's original SHA alone. Carry these fixes into the merge candidate and preserve the existing Gate B integration resolutions. Main and the agents' PR branches remain untouched.
