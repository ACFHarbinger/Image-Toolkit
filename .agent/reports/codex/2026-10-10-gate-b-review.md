# Gate B review — #763–#766

Disposition: changes requested. Reviewed together on branch `review/dl-gate-b` in
`~/Downloads/Data/Tests/dl-gate-b-review`. Original PR branches and main are unchanged.

## Fixed in the review branch

- #763: mount Train before publishing imported paths, so a cold runtime destination receives the handoff. Guard tag-review reentry against replacing a running QThread.
- #764: apply disclosure to the owning form row, including labels; preserve model-specific applicability and avoid traversing another generative tab's fields. Include negative prompt and batch size in the generation summary.
- #765: collect and restore settings through Train/Generate wrappers; copy nested configuration snapshots; exclude future output filenames from missing-input checks; form pins no longer pretend an input model is an output artifact.
- #766: call the actual TagRepo API; store completion tags separately from usage/category labels; invalidate pending token counts when clearing the model.
- Integration: resolve workspace/Run-page conflicts and wire PromptEdit.promptChanged to the configuration summary.

Ten new regression tests failed before these fixes and pass afterwards. The existing prompt, workspace, workspace-component and comparison tests plus those regressions pass: **59 passed in 2.07s**, offline/offscreen. The tokenizer failure-cache test now explicitly injects loader failure instead of relying on a nonexistent remote model while the GUI fixture mocks transformers. Cold handoff coverage subscribes the receiver only when navigation occurs.

## Remaining merge blockers

1. **#763, dataset selection:** `dataset_folder_from_paths` in `gui/src/tabs/models/delta/lora_train_tab.py:52` uses only the first supplied path and promotes an image to its entire parent directory. Library's “Sent N images” message therefore misrepresents what training consumes, and selections from other directories disappear. Preserve the exact selection in a dataset manifest/staging flow, or explicitly present and confirm the folder-wide scope before training.
2. **#763/#764, trigger contract:** `trigger_edit` is serialized and advertised by the summary but `start_training_thread` passes only `prompt_edit`; `_run_lycoris_training` writes that prompt as `data.trigger_word`. Wire the dedicated trigger through each supported backend and test the generated call/command. Decide how standard instance prompts incorporate it.
3. **#765, comparison surface:** filmstrip “thumbnails” are text labels; Review's `apply_pinned_run` only sets a QLabel to the run label/path. This is a configuration-pin scaffold, not an image comparison canvas. Actual artifact rendering and visual comparison still need implementation or explicit scope adjustment.

Additional follow-up: audit inline review teardown while tagging is active; the reentry guard does not establish cancellation/lifetime management when its owning tab is disposed. Real GPU training, frozen builds and visual interaction were not exercised. No benchmark or full suite was launched.

Evidence logs: `~/Downloads/Data/Tests/dl-gate-b-review-evidence/`.
