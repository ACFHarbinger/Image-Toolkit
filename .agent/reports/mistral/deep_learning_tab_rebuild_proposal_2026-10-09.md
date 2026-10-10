# Deep Learning Tab Rebuild — Mistral's Proposal

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`.
Proposal only; nothing here is approved for implementation. I've read
Claude's and Codex's proposals and agree with their core direction
(task-grouped workspace, spike-first embedded browser, schema-validated
LLM output, execution correctness before automated advice). Rather than
restate those, this proposal adds what I found in the code that neither
of them covered, and builds on it.

## 0. Grounding findings (verified in this checkout, not run live)

1. **A training-diagnostics layer already exists and is not wired into
   the GUI paths.** `backend/src/models/hooks/training_hooks.py` ships
   `DiagnosticsLogger` (TensorBoard + W&B dual sink, `log_step`,
   `log_grad_norm`, `log_lora_weight_norms`, `log_vae_roundtrip`,
   `log_sample_grid`), plus three free-standing analysis helpers:
   `CrossAttnRecorder` (per-token cross-attention probability maps),
   `lora_effective_rank()` (SVD effective-rank of adapter weights), and
   `lora_delta_heatmap()` (per-layer ‖ΔW‖_F bar data). Only
   `backend/src/pipeline/anime_training_pipeline.py:461-473` ever
   constructs one. `LoRATunerV2.train(..., diagnostics=None)` and
   `FullFineTuner.train(..., diagnostics=None)` already accept a
   diagnostics object — but the GUI's two launch paths (V1
   `LoRATuner`, and `backend/controllers/hydra_dispatch.py` for the
   LyCORIS configs) never pass one. Consequence: **pillar 3's first
   milestone is wiring, not building.**
2. **V1's telemetry config is dead.** `LoRATunerConfig.use_tensorboard`
   / `use_wandb` (`lo_ra_tuner_config.py:99-102`) are consumed by
   nothing — V1's loss surfaces only through a tqdm postfix and prints.
   So even "show the loss curve for the run I just did" is impossible
   today regardless of charting UI.
3. **The workspace shell precedent is shipped, not just piloted.** The
   feature-flagged Stitch workspace (`gui/src/modules/stitch_workspace.py`,
   pref `EXPERIMENTAL_STITCH_WORKSPACE` in
   `gui/src/preferences/definitions.py:218`, issues #533/#535) already
   registers one host widget with multiple sub-routes through
   `ModuleCatalog` + `WorkspaceDescriptor`/`RouteDescriptor` +
   `ModuleHandle`. The DL rebuild can be the *second consumer* of that
   exact contract behind its own experimental pref key — which also
   stress-tests the contract with a non-trivial second use case, the
   stated purpose of the architecture work.
4. **Pillar 4 is fully greenfield.** No OCR, LLM, or VLM code exists
   anywhere in `backend/` or `gui/` (only an `openai/clip-*` HF model id
   in `cbir_tuner.py`). Model/provider choice is genuinely a separate
   scoped decision, as Claude and Codex both said; I add only the
   fixture-regression idea below.
5. Confirmed both prior proposals' grounding: the stale
   `QWebEngineView` ban comment (`comfy_generate_tab.py:26-30`) cites a
   JPype-JVM conflict whose cause was removed project-wide (#435); the
   tab already has a working "guided mode" (`build_workflow()` over
   curated templates in `configs/comfy_workflows/` + node-input
   overrides) that predates any embedding work.

## 1. Pillar 1 — UI/UX

Endorse the task-grouped workspace over the flat five-tab row; my one
structural argument with Codex's six-destination layout: **Prepare
doesn't need to be a top-level destination in the first cut.** Dataset
work (diversity, duplicates, captions) begins life as the left panel of
Train — the only flow that consumes it — and earns its own route when it
grows. Proposed routes for the new workspace, each a
`RouteDescriptor` against one DL workspace host:

| Route | Content |
|---|---|
| `dl.train` | Recipe form, dataset panel (diversity/duplicates), live curves + diagnostics, checkpoint strip |
| `dl.generate` | Guided mode (today's `build_workflow` flow) + embedded ComfyUI canvas |
| `dl.review` | Output grid, side-by-side compare, OCR/feedback, guidance loop |
| `dl.runs` | Run history: search, config diff, artifacts, "clone settings" |

(Evaluation's FID/KID/IS forms and MetaCLIP inference live inside
`dl.review` as tools, exactly as Codex proposed — they're 30-50-line
form tabs today, so folding costs nothing.)

Guardrails for the rebuild, given the September crash history in this
repo: no DL tab may own a worker or a browser view directly —
everything goes through queued signals onto widgets, and the embedded
view (like any QWebEngineView) must be constructed on the GUI thread
after the app event loop is running. The workspace host owns view
lifetime so route changes don't destroy an in-flight canvas (Codex
flagged this; it's the `ModuleHandle` cached-mount behavior — keep it).

## 2. Pillar 2 — Embedded ComfyUI

Agree with the spike-first plan and add one decoupling rule that makes
pillar 4 robust regardless of the spike's outcome: **provenance capture
must never depend on the embedded view.** ComfyUI's HTTP API already
exposes execution history (`/history`, `/queue`), so the run record
(executed API-format graph, inputs, outputs) should be captured by a
poller/subscription in `ComfyUIManager` — the `QWebEngineView` is only a
window onto the same server. Then:

- Embedding succeeds → user gets the in-app canvas, and the Review loop
  reads captured runs from history either way.
- Embedding fails or is unavailable → external-browser fallback still
  produces fully captured, reviewable runs. The guidance loop never
  degrades to "parse what the user did in a browser we can't see."

Second addition: the spike checklist should include **re-entering the
route repeatedly** (mount/unmount of the cached view) and **GPU
contention with a queued generation** — both are this repo's known crash
families (native libs, cross-thread), and a view that renders fine once
but SIGSEGVs on the fifth mount is worse than no view.

## 3. Pillar 3 — Training analysis (my main contribution)

Sequenced from cheapest/highest-leverage:

1. **Wire `DiagnosticsLogger` into both launch paths** (V1 + Hydra
   dispatch). Add one small extension first: a plain **JSONL event sink
   per run** alongside TensorBoard. TB event files are protobuf —
   awkward to read back into a Qt chart; a mirrored
   `<run_dir>/events.jsonl` (`{"step", "epoch", "loss", ...}` per line,
   appended in-process) makes live tailing and post-hoc charting
   trivial and keeps the GUI free of a TB parser. Delete the dead
   `use_tensorboard`/`use_wandb` V1 fields or wire them for real.
2. **Surface what the logger already records:** loss + grad-norm curves
   (raw and smoothed), VAE roundtrip drift, and the fixed-seed sample
   grid as a checkpoint filmstrip. These come free once (1) lands.
3. **Effective-rank-over-checkpoints chart** — run `lora_effective_rank()`
   (already implemented) on each saved checkpoint and plot rank
   utilization over training. This is a concrete, cheap answer to the
   hyperparameter question Harbinger actually asks ("is my rank/alpha
   too high or too low?"): a rank-64 adapter whose effective rank
   saturates at 9 is wasted capacity; one pinned at the max is
   under-parameterized. Pair with `lora_delta_heatmap` per-layer data
   to show *which* blocks the adapter is actually moving.
4. **Hyperparameter sweeps:** agree with Claude's small-multiples
   approach and Codex's one-field-varied discipline; the JSONL sink
   from (1) is the natural aggregation source. Each sweep is just N
   runs sharing a parent experiment id.
5. **Loss geometry, last, in adapter space with principal directions.**
   Endorse Codex's 1-D-slice-first and explicit-research-mode framing.
   My addition: for LoRA/LyCORIS, the interpolation directions should be
   the **top singular directions of the accumulated ΔW** (the SVD
   machinery in `lora_effective_rank` already computes them) rather than
   Li-style random filter-normalized directions. The leading ΔW
   singular directions are where training actually moved, so the slice
   is interpretable ("loss along the change I made") and cheaper to
   normalize (adapter space is small and the base is frozen). Record
   parameterization/directions/eval subset per Codex; label it a slice.

Dataset work (diversity/duplicates via `backend/src/core/similarity/`,
caption/tag stats, augmentation previews) — agree with both prior
proposals; nothing to add beyond the Train-panel placement above.

## 4. Pillar 4 — OCR/LLM/VLM guidance loop

Agree with the structured-schema approach and the validate-against-
workflow-JSON rule. Three additions:

1. **The `from` field must equal the actual current value.** Claude's
   schema validates that suggested `node_id`/`input` exist; add that the
   claimed old value must match what's really in the workflow JSON
   (type-coerced). A suggestion whose premise mismatches reality is
   evidence of hallucination and gets the whole response flagged, not
   silently patched. Cheap, and it converts "trust the LLM's reading of
   the workflow" into "the LLM must quote the workflow correctly."
2. **Ground the advice in measured signals, not just the image.** Feed
   the run's pillar-3 artifacts (final loss, grad-norm spikes, effective
   rank, loss-curve shape) into the guidance context alongside OCR/VLM
   output and the user's feedback. "Character looks burnt-out at weight
   1.0" plus "effective rank saturated at 6/32, loss plateaued at step
   400" licenses a *specific* dataset/rank/weight recommendation that
   neither signal supports alone. This is the natural joint between
   pillars 3 and 4 and is where the tool becomes more than a chatbot.
3. **Regression fixtures from the curated templates.** Build a "guidance
   pack": a handful of cases over `configs/comfy_workflows/` templates
   with known-broken variants (wrong checkpoint name, out-of-range CFG,
   nonexistent node) and assert the validator rejects/repairs them.
   Schema adherence and the `from`-match rule become CI-checkable
   without any live model call; the live-model test is then only about
   answer *quality*, which is the part that can't be CI'd.

OCR: greenfield (finding 4). Propose a pluggable `OcrBackend` interface
with the guidance loop depending only on the interface, one optional
backend implemented first, and OCR/VLM each independently invocable as
standalone Review tools (Claude's point, kept).

## 5. Sequencing proposal

1. Diagnostics wiring + JSONL sink (§3.1) — unblocks all of pillar 3
   and half of pillar 4's grounding; no new deps.
2. WebEngine live spike (§2), including mount-recycling and
   GPU-contention cases.
3. Workspace registration behind its own experimental pref (§1) with
   routes mapped to existing tab content — pure re-shelving first.
4. Dataset panel via similarity reuse (agreed with Claude).
5. Effective-rank + ΔW charts (§3.3-3.4), then sweeps.
6. Guidance loop with validator + fixtures (§4), loss geometry last.

Risks worth naming: JSONL tailing must stay off the GUI thread
(QFileSystemWatcher + worker read, same discipline as the thumbnail
scheduler work); effective-rank SVD on a checkpoint is seconds-cheap for
LoRA but not free on every step — checkpoint granularity only; and the
pillar-4 grounding in (§4.2) is only as honest as the run record, which
is why §2's API-side capture precedes it.

— Mistral, 2026-10-09
