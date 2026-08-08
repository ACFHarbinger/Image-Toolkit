# ASP Next-Generation AI & Optimization Roadmap

*Created 2026-08-08 following the comprehensive analysis and brainstorming session.*

**Objective.** To shatter the current performance ceiling of the Anime Stitch Pipeline (ASP) and minimize the artist workload by leveraging advanced Machine Learning (Deep Learning, Reinforcement Learning) and Mathematical Optimization (Swarm Intelligence, Evolutionary Algorithms). Furthermore, we aim to modernize the artist's experience with a hybrid GUI strategy and highly interactive tutorials.

## Phase 1: Mathematical Optimization (C++/CUDA)
**Goal:** Implement robust optimization for global alignment to avoid the local minima traps of Levenberg-Marquardt and GNC-TLS.
- **1.1 Swarm Intelligence for Bundle Adjustment:** Replace the outer LM loop in `base/src/bundle_adjust.cpp` with a CUDA-accelerated Particle Swarm Optimization (PSO) or Differential Evolution (DE) algorithm. Each particle will represent a full set of affine transformations, maximizing photometric consistency globally.
- **1.2 Performance Split:** These mathematical optimization models must be written entirely in C++/CUDA and exposed via `pybind11` to maintain the high-performance core constraint. 

## Phase 2: Machine Learning & Generative Models (Python/PyTorch)
**Goal:** Replace brittle static heuristics and traditional CV feature matchers with learning-based models that understand anime-style semantics.
- **2.1 Reinforcement Learning for Parameter Tuning:** Implement a PPO (Proximal Policy Optimization) agent to dynamically set pipeline variables per frame sequence (e.g., Cauchy loss scales, seam feather widths) rather than relying on UI sliders.
- **2.2 Deep Learning Feature Extraction:** Train or fine-tune models specifically for detecting features in low-texture, cel-shaded environments, avoiding the pitfalls of standard LoFTR/ALIKED.
- **2.3 Generative Stitching & In-painting:** Explore an anime-finetuned Diffusion Model (e.g., ControlNet conditioned on Canny edges) to hallucinate seamless connections across unresolvable pose gaps, eliminating "ghosting" artifacts and heavy manual masking.

## Phase 3: GUI Modernization & Dual-Track UI
**Goal:** Retain the rapid-prototyping capabilities of PySide6 while building toward a premium, cross-platform Tauri application.
- **3.1 PySide6 Aesthetic Overhaul:** Revamp the existing PySide6 desktop application with premium anime-style aesthetics (custom Qt stylesheets, smoother transitions) as the immediate testing ground for the ML/Optimization features.
- **3.2 Tauri Cross-Platform App:** Restart development on the scaffolded `frontend/` (Tauri/Rust) to serve as the ultimate, fully-fledged production GUI, unconstrained by Qt's styling limitations.

## Phase 4: Interactive Onboarding & Tutorials
**Goal:** Evolve beyond static markdown tutorials to zero-to-hero interactive training.
- **4.1 Interactive Step-by-Step Overlays:** Highlight relevant UI elements dynamically as the artist works within the `HybridStitchPanel`.
- **4.2 Built-in Video/GIF Guides:** Integrate animated guides directly into the tooltips of the PySide6 (and later Tauri) UI for immediate visual feedback.
- **4.3 Gamified Learning:** Introduce achievements and progress tracking for completing specific stitch types, edits, or overcoming known pose-gap challenges, drastically reducing artist frustration and training time.
