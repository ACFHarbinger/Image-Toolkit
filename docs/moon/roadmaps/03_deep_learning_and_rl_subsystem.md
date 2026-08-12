# Roadmap 03: Deep Learning & Reinforcement Learning Subsystem

## Executive Summary
This roadmap defines the AI capabilities in `middleware/models/` and `middleware/policies/`. HIE incorporates state-of-the-art Deep Learning models for interactive matting, inpainting, and super-resolution, paired with an interactive Reinforcement Learning (RL) Assistant Policy trained on artist editing actions. End-to-end composition of these capabilities belongs in `middleware/pipeline/`.

---

## Technical Specifications

### 1. Deep Learning Neural Tools (`middleware/models/`)
- **Neural Alpha Matting:** BiRefNet and FastSAM integration for instant sub-pixel alpha mask generation around complex subjects (hair, fur, glass).
- **Generative Inpainting & Outpainting:** Prompt-driven or stroke-guided neural fill for object removal and non-destructive canvas boundary extension.
- **AI Super-Resolution:** Real-ESRGAN upscaling nodes integrated into non-destructive layer graphs.
- **Image Deblurring:** Optional blind/non-blind restoration adapter and cancellable job boundary for motion/defocus blur.
- **Consent-Gated Watermark Inpainting:** User-mask-guided logo removal for owned/licensed assets, with explicit permission confirmation and preview-only proposals.

### 2. Reinforcement Learning Co-Pilot (`middleware/policies/`)
- **RL Environment Sequence:**
  1. **Phase 1 Target — Localized Retouching (Interactive Brush Assistant):** RL policy trained via Gymnasium to assist artists with local dodging, burning, edge sharpening, and localized tone adjustments.
  2. **Phase 2 Target — Global Tone & Exposure Retouching:** RL policy for automated global color grading and dynamic range balancing.
  3. **Phase 3 Target — Crop & Composition Optimizer:** RL policy for auto-cropping and visual balance maximization.
- **Interactive Reinforcement Loop:** Accepts real-time reward/penalize feedback from artists to fine-tune RL agent actions to specific artist styles.

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Output Deliverables |
|---|---|:---:|---|
| **Phase 3.1** | BiRefNet & SAM Alpha Matting Model | High | `middleware/models/matting.py` |
| **Phase 3.2** | Real-ESRGAN Super-Resolution Model | Med | `middleware/models/superres.py` |
| **Phase 3.3** | Interactive Brush RL Retouching Policy (Phase 1 Target) | High | `middleware/policies/brush_assistant.py` & Gymnasium Env |
| **Phase 3.4** | Global Tone RL Retouching Policy (Phase 2 Target) | Med | `middleware/policies/tone_agent.py` |
| **Phase 3.5** | Crop & Composition RL Policy (Phase 3 Target) | Low | `middleware/policies/crop_agent.py` |
| **Phase 3.6** | Deblur Restoration Adapter & Job Contract | High | `middleware/models/deblur.py`, `middleware/jobs/restoration.py` |
| **Phase 3.7** | Consent-Gated Watermark Inpainting Adapter | High | `middleware/models/watermark.py`, `middleware/jobs/restoration.py` |
| **Phase 3.8** | CPU Restoration Preview Baseline | Med | `middleware/jobs/cpu_restoration.py`, `middleware/pyproject.toml` (`restoration-opencv` UV extra) |
