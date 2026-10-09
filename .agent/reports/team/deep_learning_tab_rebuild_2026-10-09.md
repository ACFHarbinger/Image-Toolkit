# Deep Learning Tab Rebuild — Team Brainstorm

**Participants:** Harbinger, Claude, and (invited) Codex, Gemini/Antigravity,
Grok, Meta's Muse, Mistral, Qwen, Cursor, Kimi, OpenCode, Hermes.

**Origin:** Harbinger wants the "Deep Learning" tab category remade from
scratch, not incrementally patched. This is a **proposal-collection round**
— nothing here is approved for implementation yet. Once proposals are in,
Harbinger + Claude pick the subset to build and update the roadmap +
GitHub issues accordingly. Follows this repo's "claim on the bus → wait
for the phase gate → then code" rule (see `.agent/bus/onboarding/README.md`
§4.2) — do not start implementing from your own proposal before that gate.

This is a **living document**. Append your proposal summary + a link to
your full writeup under §4 — don't rewrite other sections. Sign and date.

---

## 1. Goal — four pillars

Full rebuild of the "Deep Learning" tab category (today: Training,
Generation, Evaluation, Inference, ComfyUI sub-tabs — see §2) across:

1. **UI aesthetics + UX** — redesign the look and interaction flow of all
   five sub-tabs; not required to keep the current sub-tab split if a
   proposal argues for a different structure.
2. **Embedded browser for ComfyUI** — launch a Chromium-or-equivalent
   instance *inside* the app so the user can drive ComfyUI's own web UI
   without leaving Image-Toolkit (today it only opens in an external
   browser — see §2).
3. **Training/fine-tuning analysis tooling** — stats visualization to help
   the user train/fine-tune models and LoRAs: loss-landscape/loss-function
   geometry visualization, hyperparameter-change impact analysis, dataset
   augmentation guidance.
4. **OCR/LLM/VLM-assisted output analysis loop** — given an inference
   output image, its ComfyUI workflow (models used, their parameters,
   etc. or equivalent metadata), and the user's own feedback (what's wrong
   with the output, what they want instead), produce concrete guidance:
   which workflow parameter to change, which model/LoRA to swap in, how to
   adjust a LoRA's training dataset, etc. OCR covers reading text baked
   into generated images; LLM/VLM covers reasoning over the image +
   workflow + feedback together.

## 2. Current state (ground proposals in this, don't assume)

- Five sub-tabs today, registered in `gui/src/windows/main/_tab_registry.py`
  (`ml.training`, `ml.generation`, `ml.evaluation`, `ml.inference`,
  `ml.comfyui`).
- **ComfyUI integration**: `ComfyUIManager`
  (`backend/src/models/core/comfy_manager.py`) owns server lifecycle
  (start/stop/readiness) and has `load_workflow()` / `apply_overrides()`
  / `upload_image()` / `queue_workflow()` helpers against ComfyUI's HTTP
  API — but the GUI (`gui/src/tabs/models/gen/comfy_generate_tab.py`)
  only ever launches ComfyUI's web UI in an **external** browser; there is
  no in-app/embedded view today. `COMFYUI_DIR` resolves to the vendored
  `vendor/ComfyUI` submodule.
- **LoRA training**: legacy `LoRATuner` (V1, SDXL dual-encoder, default
  base `OnomaAIResearch/Illustrious-XL-v2.0`) plus a newer
  `LoRATunerV2`/LyCORIS path (LoCon/LoHa/LoKr) under
  `backend/src/models/tuning/`, driven by Hydra configs
  (`backend/config/training/`). `docs/moon/roadmaps/content_generation.md`
  §1.3 flagged a GUI gap (the train tab only wired to V1) — check current
  state before assuming it's still open.
- `docs/moon/roadmaps/content_generation.md` is the existing roadmap for
  this general area (image/video generation pipeline, model code). This
  initiative is specifically the **GUI tab rebuild + new analysis/guidance
  tooling layered on top** — not a redo of the underlying model code.

## 3. Process

- **Proposal-only.** Write up ideas, don't start building.
- File: `.agent/reports/<your-name>/deep_learning_tab_rebuild_proposal_2026-10-09.md`
  (lowercase dir matching your existing `.agent/reports/<name>/` folder —
  create one if you don't have it yet, e.g. `muse`, `mistral`, `qwen`,
  `kimi`, `hermes`).
- Cover whichever of the four pillars you have real, concrete ideas for —
  depth over forced coverage of all four. For each idea: what it is, the
  concrete user pain point it solves, a rough shape of the implementation,
  and known tradeoffs/risks (performance, VRAM/compute cost, embedding a
  browser engine's footprint, hallucination risk for the LLM/VLM guidance
  loop, etc.).
- Post a one-line pointer to your file on `.agent/bus/2026-10-09.md` when
  done, and append a short summary + the link under §4 below.
- Once proposals are in, Harbinger + Claude read all of them, add their
  own, select the subset to implement, and update
  `docs/moon/roadmaps/content_generation.md` (or a new dedicated roadmap
  doc, if the agreed scope warrants one) plus the GitHub project
  issues/milestone.

## 4. Proposals (append here as agents respond)

- **Claude** (2026-10-09):
  `.agent/reports/claude/deep_learning_tab_rebuild_proposal_2026-10-09.md`.
  Key finding worth everyone reading before starting on pillar 2: the
  documented reason `QWebEngineView` was banned in this app
  (`comfy_generate_tab.py`'s "intentionally NOT used" comment — a
  JPype-JVM/Chromium native-lib SIGSEGV) no longer applies — the JVM was
  removed from the product entirely in #435. `QWebEngineView` imports
  cleanly in the current `.venv`. Not proven safe yet (needs a live spike
  in-process, not just an import check), but the ban's actual root cause
  is gone. Also recommends: reuse `backend/src/core/similarity/`
  (CLIP+pgvector) for LoRA-dataset diversity analysis instead of building
  new infra, reuse `usage_charts.py`'s chart primitives for pillar 3, and
  constrain the LLM/VLM guidance loop's output to a schema validated
  against the real ComfyUI workflow JSON rather than trusting free text.

---

— Claude, 2026-10-09

- **Codex** (2026-10-09):
  [Full proposal](../codex/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Recommends Prepare/Train/Generate/Review with shared Runs and Models views,
  effective-config provenance and supervised GPU jobs before automated advice,
  an embedded ComfyUI feasibility gate, controlled comparisons, and validated
  assistant-authored experiments. Confirms LyCORIS GUI exposure already exists;
  identifies missing forwarding of visible epochs/batch/LR/rank controls on that
  path and two Illustrious labels pointing to the SDXL base ID. Includes layout,
  migration, resource tradeoffs, and staged acceptance gates. Proposal only.

- **Mistral** (2026-10-09):
  [Full proposal](../mistral/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Agrees with the Claude/Codex direction (task-grouped workspace, spike-first
  embedding, schema-validated guidance, correctness before advice). New finding
  both proposals missed: `backend/src/models/hooks/training_hooks.py` already
  ships a `DiagnosticsLogger` (TB+W&B, grad norms, LoRA weight norms, VAE
  roundtrip, sample grids) plus `CrossAttnRecorder`, `lora_effective_rank`
  (SVD of adapter weights), and `lora_delta_heatmap` — but only
  `anime_training_pipeline.py` wires it; both GUI launch paths pass
  `diagnostics=None`, and V1's `use_tensorboard`/`use_wandb` are dead config.
  Pillar 3 therefore starts with wiring, not building. Adds: a JSONL per-run
  event sink for GUI charting; an effective-rank-over-checkpoints chart as a
  rank/alpha advisor; loss-geometry 1-D slices along top singular directions
  of accumulated ΔW instead of random directions; provenance capture via
  ComfyUI's HTTP `/history` so the guidance loop never depends on the embedded
  view succeeding; a validator rule that a suggestion's claimed old value must
  match the actual workflow JSON; and CI-checkable guidance fixtures over
  `configs/comfy_workflows/`. Proposes the DL workspace as the second
  `ModuleCatalog` workspace behind its own experimental pref (Stitch is the
  shipped precedent), with dataset work starting inside Train rather than as a
  top-level Prepare destination. Proposal only.

- **Grok** (2026-10-09):
  [Full proposal](../grok/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  The visible bug is the architecture combo: Training and Generation are
  stacked widgets, ComfyUI is a separate route, and LyCORIS still shows
  epochs/batch/LR/rank that `_run_lycoris_training` does not forward.
  Proposes capability cards with disabled reasons, Guided|Graph as modes
  of one generate surface, the existing CBIR epoch bar and `_SparkLine`
  as the live train panel, a run list that does not use the gallery
  scheduler, review by rectangle marks plus OCR on the mark, and a GPU
  lease footer. Landscape plots and CLIP clustering stay explicit
  follow-up jobs. Proposal only.

- **Gemini / Antigravity** (2026-10-09):
  [Full proposal](../gemini/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Agrees with the `ModuleCatalog` workspace shell, spike-first WebEngine, and
  schema-validated guidance. Focuses on the missing interactive glue:
  (1) A `QWebChannel` IPC bridge (`comfy_bridge.js`) inside the embedded
  ComfyUI view to enable bi-directional parameter syncing, native drag-and-drop
  from the Library Database, and active node focusing/panning triggered by
  AI advice;
  (2) A dual-pane canvas with interactive ROI bounding-box selection, AB split-wipe,
  and a session filmstrip tracking parameter diffs;
  (3) A Dataset Tag Entanglement Engine (co-occurrence matrix + CLIP coverage)
  to prevent character LoRA feature entanglements before training;
  (4) Practical training geometry via Hutchinson's Hessian trace estimator
  for fast generalization/sharpness scoring without multi-hour grid searches;
  (5) An interactive "Diff & Apply" tuning prescription widget that validates
  patches against the real graph and offers one-click re-queueing;
  (6) A GPU Lease Arbiter to enforce exclusive VRAM allocation between training
  and generation. Proposal only; no implementation launched.

- **Cursor** (2026-10-09):
  [Full proposal](../cursor/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Agrees with the workspace shell, spike-first WebEngine, schema-validated
  guidance, and diagnostics wiring. Adds window/chrome findings the others
  missed: `BaseGenerativeTab.collect()` persists combo *labels* not ids;
  `ImageCompareWindow`, `ContextInspectorPanel`, `TelemetryStatusBar`,
  `TagReviewDialog`, and `EventHub` intents already exist; docs still ban
  `QWebEngineView` in six places; `ImageToolkit.spec` has no WebEngine
  datas. Proposes four destinations inside the existing rail (not a second
  card rail), capability picker *inside* Train/Generate, GPU state on the
  existing status bar, ComfyUI pop-out via WindowManager, HTTP `/history`
  before any `comfy_bridge.js`, and Extractor/Library handoff through
  `ImportPathsIntent`. CBIR stays out of this category; copy `_SparkLine`
  only. Proposal only; nothing implemented.

- **Muse Code** (2026-10-09):
  [Full proposal](../muse/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Backbone proposal: every execution is a reloadable/re-queueable Run;
  Train/Generate/Review in the existing rail (no second rail, no GPU footer —
  GPU state on `TelemetryStatusBar`); capability picker inside tabs, combo ids
  not labels, effective-config bar, designed empty states. WebEngine spike
  with explicit pass criteria (5–10 in-process launches, crash-log + VRAM/RSS
  verdict: embedded-default / opt-in / external-only); dedicated profile,
  localhost-only, permanent external fallback, `/history` provenance decoupled
  from the view. Analysis starts with Diagnostics→JSONL wiring; effective-rank
  chart as rank/alpha advisor; dataset reuse via similarity stack with
  one-click Hydra overrides; loss slices + Hutchinson gated behind explicit
  action. Guidance loop: OCR + VLM passes, versioned schema, two validators
  (node exists, claimed-`from` matches workflow), Diff & Apply widget with
  labeled re-queue, no silent auto-apply. Sequenced in five gates.
  Proposal only; nothing implemented.

- **Kimi** (2026-10-09):
  [Full proposal](../kimi/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Agrees with the converged direction (workspace shell, spike-first WebEngine,
  wiring-before-building, schema-validated guidance). Re-verified the shared
  findings in the checkout and adds: (1) two sharpened micro-findings —
  `set_config()`'s silent index-0 fallback on renamed combo labels, and the
  Comfy browse dialog missing `DontUseNativeDialog`; (2) `PromptEdit`, one
  shared prompt component backed by the app's own `tag_repo` vocabulary,
  run-record trigger chips, SDXL per-encoder token meter, and
  `HybridCaptioner.MODEL_PREFIXES`; (3) pre-flight template validation
  against ComfyUI `/object_info` + model-folder file checks so Queue is only
  enabled when the mode can actually run; (4) a linked-cursor loss curve ↔
  checkpoint filmstrip scrubber; (5) a **checkpoint tournament** — blind
  pairwise A/B over the wired per-checkpoint sample grids via the existing
  `ImageCompareWindow`, ELO-ranked, feeding measured preference into the
  guidance loop as evidence-traced suggestions; (6) **matrix mode** (X/Y
  generation sweeps) as the Generate-side counterpart to training sweeps;
  (7) an upscale handoff wiring the existing unwired `ESRGANWrapper`.
  Slotted into the consensus A–D gates; largest new surfaces are `PromptEdit`
  and the tournament view. Proposal only; nothing implemented.

- **Qwen** (2026-10-09):
  [Full proposal](../qwen/deep_learning_tab_rebuild_proposal_2026-10-09.md).
  Focuses on the user-experience layer over the converged architecture.
  Agrees with three-destination workspace, spike-first WebEngine,
  wiring-before-building, schema-validated guidance. Adds seven contributions:
  (1) **progressive disclosure** — three complexity tiers (Simple/Standard/
  Advanced) per destination to manage the knob explosion; (2) **guided
  onboarding** — one-time contextual overlays for first-run users; (3) the
  **Comparison Spine** — a persistent strip of pinned runs that follows the
  user across destinations, making the train→generate→review chain navigable;
  (4) **cost & time estimates** before every expensive action, calibrated from
  prior runs; (5) **graceful degradation tiers** for embedded ComfyUI (full/
  sandboxed/external-only) instead of a binary spike verdict; (6) the
  **Training Report Card** — post-run summary answering "did it learn?
  overfitting? what next?" in 5 seconds; (7) **guidance as conversation** with
  trajectory memory, confidence calibration, and a "What Changed?" overlay.
  Also proposes C++ dataset analysis for I/O-bound operations and a11y/i18n
  hardening for charts and parameter naming. Proposal only; nothing
  implemented.

---

## 5. Decision (Harbinger + Claude, 2026-10-09) — LOCKED

All nine proposals (Claude's + eight agents'; OpenCode and Hermes did not
respond) read and synthesized. Convergence was unusually strong — most
agents built directly on each other's findings rather than diverging. The
selected scope, full design rationale, gate sequencing, and rejected/
backlogged items now live in their own dedicated roadmap doc:
**`docs/moon/roadmaps/deep_learning_tab_rebuild.md`**, tracked as GitHub
milestone **Deep Learning Tab Rebuild** (#11), tracking issue
[#725](https://github.com/ACFHarbinger/Image-Toolkit/issues/725), with 33
further issues (#726–#758) across Gates A–E plus 4 explicit backlog items.
Don't duplicate that document here — this entry is a pointer.

In brief: the converged workspace architecture (second `ModuleCatalog`
workspace, Train/Generate/Review/Runs, reusing the existing shell — no new
rail/footer/canvas), the correctness-first gate (LyCORIS param forwarding,
combo id persistence, model-id mislabeling), the spike-gated embedded
ComfyUI view with provenance decoupled from it, wiring `training_hooks.py`
before building new analysis UI, and the schema-validated two-validator
guidance loop were all adopted close to as proposed. Three open forks were
decided with Harbinger directly: Qwen's Comparison Spine and progressive-
disclosure tiers, and Kimi's checkpoint tournament, are all **in v1 scope**
(not backlogged). Gemini's immediate `QWebChannel` bridge, a dual-pane
canvas rebuild, a separate GPU-lease footer, a top-level Prepare
destination, CBIR folding, and automatic retraining loops are **rejected**
or **backlogged** — see the roadmap doc §3/§2's backlog table for the
reasoning on each.

— Claude, 2026-10-09

