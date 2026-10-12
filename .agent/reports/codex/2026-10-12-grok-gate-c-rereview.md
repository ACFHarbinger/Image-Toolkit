# Grok #772 re-review

Reviewed `bf5148e5`, including prior Codex corrections `cb262ba7`.
Review fixes are on `review/dl-gate-c`, in
`~/Downloads/Data/Tests/dl-gate-c-review`; Grok's PR branch is unchanged.

## Corrections

- **High: single Comfy jobs released GPU admission at submission.** Guided,
  Graph, and Promote now wait for terminal history before releasing, just as
  Matrix does. Shutdown cancellation reaches the wait. Tests assert another
  training job cannot acquire admission during execution.
- **High: thumbnail byte limits did not bound decoded memory.** The GUI decoded
  and retained full-resolution pixmaps for up to 200 outputs. Decode now runs
  in the thumbnail worker, rejects dimensions over 16 million pixels, and
  retains only images scaled to 72 pixels. Pending fetches are capped at 200.
  Destruction during an in-flight fetch no longer emits through a deleted view.
- **Medium: generation cleanup exceptions stranded the admission lock.** Release
  now runs even if GAN unload raises; a regression exercises this path.
- **Medium: graph sweeps ignored the override field.** They now use the same
  strict parser as Graph submission and carry those overrides into run metadata.
- **Medium: previews always requested the output directory.** Fetches preserve
  the captured output type, including `temp`. HTTP requests use Comfy's WebP
  preview option; oversized responses are rejected rather than silently truncated.
- Corrected the LoRA training test: its MagicMock previously replaced the
  admitted training body, so its assertion inside GAN training never ran.

## Verdict and limits

Grok's thermal stop, reachable LoRA workflow, axis enablement, and scrollable
thumbnail surface address the earlier feature gaps. Carry these review fixes
before merging #772; `bf5148e5` alone still has the blockers above.

Admission covers the paths wired here (Comfy submissions, LoRA training and
 generation, GAN training, CBIR training). It is not a blanket guard for every
model tool, another process, or external browser jobs. Cancelling/disconnecting
an external Comfy job does not terminate its server-side execution. Thermal
monitoring currently reads the first NVIDIA GPU; no sensor means no thermal
stop. Large/unsupported previews may have no thumbnail.

Validation: 20 backend matrix tests; 50 GUI tests across Generate surface,
guided Comfy, and GPU admission (70 distinct tests). Ruff/diff checks pass.
All checks were CPU-only with mocked execution/sensors; no live Comfy/GPU run,
benchmark, or full suite. No merge or retarget performed.
