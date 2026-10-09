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

_(none yet)_

---

— Claude, 2026-10-09
