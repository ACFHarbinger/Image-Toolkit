# Deep Learning Tab Rebuild — Claude's Proposal

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`
(read that first for the brief). Proposal-only, nothing here is approved.

## 1. UI/UX

- Replace the flat 5-tab row (Training/Generation/Evaluation/Inference/
  ComfyUI) with a left-rail workflow layout, reusing the existing
  `ModuleDescriptor`/`ModuleHost` pilot contract from the Phase 1
  architecture work (`gui/src/modules/`) rather than inventing a new
  shell. Grouping by task, not by pipeline stage, fits the new tooling
  better: **Train** (LoRA/model training + the new analysis dashboard),
  **Generate** (SD/GAN/ComfyUI generation, now with the embedded browser),
  **Review** (new — merges Evaluation/Inference with the OCR/LLM/VLM
  guidance loop, since "look at what came out and decide what to change"
  is one workflow, not two).
- Persistent run-history rail: every train/generate run gets a card
  (thumbnail + key metrics/params), reusing the existing thumbnail-card
  components from `VirtualGallery`/`VirtualGalleryView` instead of a new
  widget. Clicking a card reloads its config — directly useful for the
  Review loop's "try the suggested change" step.
- Reuse `_BarChart`/`_GroupedBarChart` (`gui/src/windows/cloud/
  usage_charts.py`) as the base QPainter chart primitives for pillar 3
  rather than pulling in a new charting dependency — they already handle
  theming (`theme_api.color`) consistently with the rest of the app.

## 2. Embedded browser for ComfyUI — the documented blocker is gone, but needs a live re-check

`gui/src/tabs/models/gen/comfy_generate_tab.py:26-30` currently has:

```python
# QWebEngineView is intentionally NOT used here.
# Chromium (QtWebEngine) loads native libstdc++ via Vulkan/GBM at first render,
# which causes an RTTI __dynamic_cast SIGSEGV when JPype's JVM is already running
# in the same process ...
```

**That blocker's root cause no longer exists.** `backend/src/app.py`
(around the JPEG-plugin-priming comment) states plainly: "the JVM itself
has since been removed from the product entirely (see
`base/src/secret/README.md` and the C++ crypto module), which closed the
whole class [of JPype-JVM-vs-native-lib conflicts]" — JPype/the JVM is
gone project-wide (issue #435; `vault_manager.py` now uses a native
ctypes binding instead). I confirmed `import PySide6.QtWebEngineWidgets`
and `import PySide6.QtWebEngineCore` both succeed cleanly in this repo's
`.venv` right now, no separate dependency needed.

This doesn't *prove* embedding is safe — it means the specific documented
reason it was banned is gone, not that nothing else can go wrong (Qt
Multimedia's FFmpeg/VA-API path shows this project has more than one
native-lib-loaded-off-main-thread crash class, independent of the JVM
one). **Before anyone builds on this:** do a small, isolated live spike —
construct a bare `QWebEngineView` inside the real app process (not a
standalone script) and load ComfyUI's URL, run it 5-10 times fresh, check
for the SIGSEGV family this repo already has tooling for
(`dev/resolve_qt_offset.py`, `dev/tool/ui/views/crash.py`'s hs_err
reader). If clean, update the stale comment and ship the embedded view;
if not, we've learned something and the external-browser fallback stays
default. Whoever picks up this piece should do that spike *first*, before
writing the rest of the embedding UI.
- Shape if the spike is clean: a `QWebEngineView` inside the ComfyUI
  sub-tab (not a separate window), pointed at `ComfyUIManager.url` once
  `wait_until_ready()` returns true; keep "Open in External Browser" as a
  visible fallback button regardless, since some users will be on a build
  without WebEngine or will hit a platform-specific WebEngine issue.

## 3. Training/fine-tuning analysis tooling

- **Dataset diversity/coverage, not loss-landscape, first** — it's the
  highest-leverage, lowest-risk piece because the infrastructure already
  exists: `backend/src/core/similarity/` (CLIP embedder + pgvector) is
  already used for image similarity search elsewhere in the app. Point it
  at a LoRA dataset directory, cluster the embeddings, and surface: how
  many visually-distinct clusters exist, which clusters are thin (likely
  underrepresented pose/angle/background), and flag near-duplicate images
  (common cause of LoRA overfitting to one pose). This is a *reuse*, not
  a new subsystem.
- **Hyperparameter-impact visualization** — Hydra already drives training
  config (`backend/config/training/`), so a sweep is "run N trainings with
  one field varied, log final/best loss." Render as small-multiples line
  charts (loss vs. step, one line per hyperparameter value) using the
  reused chart primitives above, not a full parallel-coordinates widget
  initially — cheaper to build, answers "did this value help or hurt"
  directly, which is the actual question a user training a LoRA has.
- **Loss landscape geometry** — the most expensive, most research-flavored
  ask (filter-normalized random-direction interpolation around a
  checkpoint, à la Li et al. 2018). `matplotlib` is already a backend
  dependency; render via `FigureCanvasQTAgg` embedded in the tab rather
  than a hand-rolled 3D surface renderer. Flag as genuinely expensive per
  checkpoint (re-running forward passes along 2 random directions × N
  grid points) — gate it behind an explicit "Compute Loss Landscape"
  action the user triggers for one checkpoint, never automatic/background.

## 4. OCR/LLM/VLM-assisted guidance loop

- **Constrain the LLM's output, don't let it free-write parameter
  suggestions.** The single biggest risk named in the brief is
  hallucination on technical parameters. Define a small structured schema
  (e.g. `{"workflow_param_changes": [{"node_id", "input", "from", "to",
  "reason"}], "model_swap": {...} | null, "dataset_guidance": "..." |
  null}`) and validate every suggested node id/input against the actual
  ComfyUI workflow JSON the user ran (the exact shape
  `ComfyUIManager.load_workflow()`/`apply_overrides()` already produce/
  consume) before showing it — reject or flag any suggestion referencing a
  node/field that doesn't exist in that workflow, rather than trusting the
  model's text.
- **Pipeline shape:** OCR pass (any baked-in text in the output image) +
  VLM pass (describe/critique the image: anatomy, artifacts, style
  match) + the workflow JSON + the user's free-text feedback, all as
  context to one LLM call that must return the schema above. Keep OCR and
  VLM as separate, independently-callable steps (useful on their own —
  e.g. OCR alone to catch garbled generated text) rather than one monolith
  call.
- **Model choice is a separate decision, not part of this proposal** — this
  needs a wrapper-contract decision (reuse the existing model-wrapper
  pattern from the architecture work if it fits local/hosted VLM and LLM
  calls) and should probably get its own scoped sub-issue once the overall
  subset is picked, rather than being speced in detail here.

## 5. Sequencing note

Pillar 1 (dataset diversity) and pillar 2's *spike* are both cheap,
reuse-heavy, and de-risk the expensive pieces (loss landscape, the
LLM/VLM loop) early. I'd suggest doing those two first regardless of what
else makes the cut, independent of ownership.

— Claude, 2026-10-09
