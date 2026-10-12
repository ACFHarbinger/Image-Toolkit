# Gate D review — Mistral, Muse, Kimi

Reviewed #775 (`4ee486bf`), #776 (`f3199845`), #774 (`8cf207bd`, including
`b130e95c`), and #777 (`4d185cfb`). Combined on `review/dl-gate-d` in
`~/Downloads/Data/Tests/dl-gate-d-review`. The integration merge preserves
both diagnostics and advisor Hydra arguments where the branches conflicted.
Main and original PR branches are unchanged.

## Corrections

**Mistral / #741**

- Declared `logging.run_dir` in Hydra's base config. The submitted command
  otherwise fails composition before launching training; tested real Hydra
  composition without starting training.
- Run IDs include a nonce; creating an existing run directory fails instead
  of replacing its record and mixing appended events with a previous run.
- Unwritable diagnostics sinks and terminal record-write failures no longer
  suppress training or its completion signal. Packaged LyCORIS rejection
  finalizes its record; relative subprocess output paths resolve from its cwd.
- Event tails reject stale reads after switching runs, preserve changes seen
  while a read is busy, and use byte offsets for partial UTF-8 lines.
- Trigger vocabulary excludes running/failed/cancelled records (legacy records
  without status remain compatible).

**Kimi / #744 and #746**

- Exclusion/restoration uses the original handoff, including explicit file
  selections. It cannot silently return to an earlier folder or reuse a staging
  directory that cleanup removes. New handoffs clear old exclusions; excluding
  everything clears the training input. Guards run before changing exclusions.
- Scan and clustering no longer invalidate one another's results. Removed
  redundant permanent worker retention; progress uses a Qt receiver slot;
  superseded worker errors are ignored. Hashing streams input and the embedder
  unloads before releasing admission. Bad caption encoding does not abort scans.
- Report generation/file reading runs in a retained worker. Completion-slot
  metadata matches the three-value signal; tests exercise actual delivery.
- Short loss curves no longer compare the same head/tail window. Sparse
  validation is compared to training at corresponding steps; malformed steps
  are skipped and non-finite losses produce an explicit bad verdict.

**Muse / #749**

- Remote download, decoding, and snapshot writes run off the GUI thread.
  Upscale inputs use original `/view` bytes, not capped lossy WebP thumbnails;
  temporary output types are preserved. Snapshots use unique filenames and
  are encoded as PNG rather than saving arbitrary bytes with a PNG extension.
- Fixed RGB888 row-padding handling for widths not divisible by four.
- Existing upscale outputs are preserved; exclusive reservation prevents
  overwrite races and source replacement is rejected. Empty output writes
  report failure. ESRGAN cache entries are removed before admission release.
- Deleted views cannot receive runner signals. Fixed thumbnail queue eviction
  after its tuple format changed from prompt-first to local/remote-tag-first.

- Added a local output filmstrip to legacy LoRA Generate: upscale sources
  and results appear together, with the result selected, instead of reporting
  only a filename in a message box.

## Limits

Review currently targets the first comparison image, as its tooltip states.

No live GPU/model/download test was performed. GPU admission remains limited
to cooperating in-process paths; the existing upscaler's large-image memory
behavior was not benchmarked. The original download has a 64 MiB cap. These
checks do not establish GPU memory or thermal suitability on this laptop.

## Checks

170 distinct targeted checks passed: 62 backend, 108 GUI. Coverage includes
Hydra composition, diagnostics failure, record collisions, report arithmetic,
exclusion/restore, stale event tails, odd-width image decoding, overwrite
protection, off-thread remote handoff, and model-cache release. Ruff and
`git diff --check` pass. No full suite, benchmark, or training run.

Carry the review corrections when integrating these PRs; the submitted heads
alone retain the issues above. No merge or retarget was performed.
