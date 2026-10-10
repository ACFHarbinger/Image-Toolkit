# Gate B re-review — Cursor, Grok, Gemini

Reviewed Cursor 8e2f04f3 (#763), Grok d968db17 (#765), and Gemini f77b77f8 (#764) together with PromptEdit and the previous Codex fixes. Integration remains on review/dl-gate-b, under ~/Downloads/Data/Tests/dl-gate-b-review. Original branches and main are unchanged.

## Fixed during re-review

- Cursor: selected images with the same stem but different extensions collided on their staged .txt caption. Reserve caption stems as well as image filenames. Default staging now resides under ~/Downloads/Data/Tests/.
- Grok: unpinning did not refresh an already-open comparison canvas. Connect pin changes to comparison updates, preserve the canvas when paths are unchanged, expand home-relative paths, and hide the onboarding empty state when images exist.
- Gemini/Cursor: training model changes overrode the selected disclosure tier. Reapply the tier after setting model applicability.
- Gemini: LyCORIS displayed an instance prompt that the backend does not use, and showed no trigger when dispatch actually falls back to the prompt. Show the effective dispatched trigger instead.
- Resolved integration conflicts while retaining the earlier PromptEdit fixes and configuration wrappers.

The prior blockers are substantially addressed: selected subsets are staged, dedicated triggers reach both standard and LyCORIS calls, and Review now embeds ImageCompareWindow.

## Remaining changes requested

### High — staged datasets can be deleted during training (#763)

LoRATrainTab.start_training_thread passes the current staging directory into an untracked daemon thread. Browse, apply_imported_paths, _on_review_saved, and closeEvent can call _clear_staging while training is still reading it. Only Start is disabled; dataset handoffs and review remain available.

Give each running job ownership of its dataset directory until the worker actually finishes, or reject dataset replacement while running. Retain the thread/job handle; cancellation request alone does not establish that reads have stopped.

### High — inline review disposal is still unsafe (#763)

TagReviewPanel.stop_review calls stop_worker with its default join=True, which invokes unbounded QThread.wait on the GUI thread. Interruption is checked between images, so model loading or a current inference can block tab/dialog close.

Conversely, DeepLearningWorkspaceHandle.dispose calls host.deleteLater directly; deleting a parent does not deliver closeEvent to its descendant training tab. The new closeEvent cleanup therefore does not cover runtime disposal and can leave the worker running as its owner disappears. Wire explicit workspace disposal to nonblocking cancellation with retained worker ownership until actual thread completion. Avoid deleting the worker on BaseQThreadWorker's payload finished signal before run has returned.

### Medium — edited dataset and reviewed dataset can diverge (#763)

After a handoff, _review_tags prefers cached _dataset_paths even if the editable data_dir_edit is changed to another directory. Training reads the edited directory while Review Tags edits the old images. Invalidate/resolve the selection when the path changes and reject malformed or missing imported files before staging. The current resolver can create dangling image symlinks.

Also move directory scanning and staging off the GUI thread before treating this as suitable for large Library selections.

## Validation

- Workspace, config components, comparison, image comparison window and review regressions: **61 passed in 2.32s**.
- Training dispatch, tag-review dialog/worker and config components: **47 passed in 1.81s** (some config tests overlap the first run).
- New caption collision and unpin regressions reproduced failures before the fixes.
- Ruff and diff whitespace checks pass.
- Offline, offscreen targeted tests only. No GPU training, benchmark, full suite, frozen-build or interactive visual validation.

Evidence: ~/Downloads/Data/Tests/dl-gate-b-review-evidence/review2-*.log.
Disposition: Grok/Gemini corrections integrated and tested; Gate B remains changes requested for the dataset and worker lifetime issues above.
