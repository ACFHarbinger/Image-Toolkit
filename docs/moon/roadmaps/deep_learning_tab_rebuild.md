# Deep Learning Tab Rebuild

**Status:** LOCKED 2026-10-09 (Harbinger + Claude, from a ten-agent proposal
round). Tracking unit of record: GitHub milestone **Deep Learning Tab
Rebuild** (#11) and the `dl-rebuild-*` issues listed per item below
(tracking issue [#725](https://github.com/ACFHarbinger/Image-Toolkit/issues/725)).
This document is the design rationale and the ordered plan; use the issues
for status.

**Origin:** full rebuild of the Deep Learning tab category (today: Training,
Generation, Evaluation, Inference, ComfyUI sub-tabs) across four pillars —
UI/UX, an embedded ComfyUI browser, training/fine-tuning analysis tooling,
and an OCR/LLM/VLM-assisted output-guidance loop. Ten agents (Claude, Codex,
Mistral, Grok, Gemini/Antigravity, Cursor, Muse Code, Kimi, Qwen — OpenCode
and Hermes did not respond this round) independently wrote proposals,
converged heavily on architecture, and each added distinct findings/ideas.
Full proposals: `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`
and the per-agent files it links (`.agent/reports/<agent>/deep_learning_tab_rebuild_proposal_2026-10-09.md`).

This is not a redo of the underlying model code
(`docs/moon/roadmaps/content_generation.md` owns that) — it's the GUI tab
rebuild plus new analysis/guidance tooling layered on top of it.

---

## 1. Converged architecture

**One workspace, reusing the existing shell.** `gui/src/modules/dl_workspace.py`
becomes the second consumer of the `ModuleCatalog`/`WorkspaceDescriptor`/
`ModuleHandle` contract the shipped Stitch workspace already proves (behind
its own experimental pref, default off until Gate A lands). Four
destinations — **Train**, **Generate**, **Review**, **Runs** — replace the
flat five-route row (`ml.training` … `ml.comfyui` in `_tab_registry.py`,
kept as aliases so old sessions still open). No second navigation rail, no
new GPU footer, no new comparison canvas: reuse `NavigationRailWidget`,
`ContextInspectorPanel`, `TelemetryStatusBar`, `ImageCompareWindow`. The
engine/capability picker (LoRA/LoCon/LoHa/LoKr, SD3/R3GAN/GAN) lives
*inside* Train/Generate, not as a new top-level rail — Grok's original
capability-card proposal, refined down by Cursor/Muse/Qwen. R3GAN eval and
MetaCLIP inference become tools opened from Review. CBIR training stays
**out** of this category entirely; only its `_SparkLine` widget is reused.

**Correctness before new UI (Gate A).** Several real, independently
re-verified bugs must close first, because building a nicer UI on top of
silently-broken wiring just makes the breakage harder to notice:
LyCORIS/Hydra launch drops the visible epochs/batch/LR/rank controls;
`collect()`/`set_config()` persists combo *labels* and silently falls back
to index 0 on a miss; two "Illustrious" labels secretly resolve to the same
plain SDXL base checkpoint; a known native-dialog crash class is unpatched
on one `QFileDialog` call.

**Embedded ComfyUI is spike-gated, not assumed (Gate A.4 → C).** The
documented ban on `QWebEngineView` (a JPype-JVM/Chromium native-lib SIGSEGV)
lost its root cause when the JVM was removed from the product entirely
(#435) — independently re-derived by four agents, confirmed import-clean in
the current `.venv`. That doesn't prove embedding is *safe*, only that the
specific historical reason is gone. A concrete, falsifiable spike (repeated
in-process launches + mount-recycling + GPU-contention + a frozen-build
run) produces one of three verdicts — full embed / sandboxed opt-in /
external-only — and the UI ships whichever tier the spike actually
supports. **Provenance capture (`/history` polling) is decoupled from the
view on purpose**, so the guidance loop works identically regardless of the
spike's outcome.

**Training analysis starts as wiring, not new ML code (Gate D).**
`backend/src/models/hooks/training_hooks.py` already ships
`DiagnosticsLogger`, `CrossAttnRecorder`, `lora_effective_rank()`, and
`lora_delta_heatmap()` — independently found by Mistral, confirmed by Kimi/
Gemini/Qwen — but neither GUI launch path ever constructs one
(`diagnostics=None` on both). The entire training-visualization pillar
starts by wiring that in, before anything new is built on top.

**Guidance loop is schema-constrained, not free text (Gate E).** The single
biggest named risk across every proposal is an LLM/VLM hallucinating a
parameter that doesn't exist or misreading one that does. Every suggestion
must pass two hard validators — the referenced node/input exists in the
*actual* executed workflow JSON, and the claimed old value matches the
real current value — before it's ever shown to the user, backed by CI
fixtures over the two templates in `configs/comfy_workflows/`. No silent
auto-apply, ever.

## 2. Gates and issues

Each gate's issues should land before the next gate's UI work builds on top
of it (Gate B's workspace shell assumes Gate A's correctness fixes; Gate C's
embedding assumes Gate A.4's spike verdict; Gate E's guidance assumes Gate
C.2's provenance capture and Gate D's training signals).

### Gate A — Correctness & feasibility

| Issue | Deliverable |
|---|---|
| [#726](https://github.com/ACFHarbinger/Image-Toolkit/issues/726) | Fix LyCORIS/Hydra launch dropping epochs/batch/LR/rank |
| [#727](https://github.com/ACFHarbinger/Image-Toolkit/issues/727) | Persist combo-box config by id, not label; remove silent index-0 fallback |
| [#728](https://github.com/ACFHarbinger/Image-Toolkit/issues/728) | Drive-by fixes: model-id mislabeling display + missing `DontUseNativeDialog` |
| [#729](https://github.com/ACFHarbinger/Image-Toolkit/issues/729) | `QWebEngineView` in-process spike, 3-tier verdict, docs + packaging rewrite |

### Gate B — Workspace shell

| Issue | Deliverable |
|---|---|
| [#730](https://github.com/ACFHarbinger/Image-Toolkit/issues/730) | Register `dl_workspace` as the second `ModuleCatalog` workspace |
| [#731](https://github.com/ACFHarbinger/Image-Toolkit/issues/731) | Effective-config bar, empty states, progressive-disclosure tiers |
| [#732](https://github.com/ACFHarbinger/Image-Toolkit/issues/732) | Comparison Spine — persistent pinned-run strip across destinations |
| [#733](https://github.com/ACFHarbinger/Image-Toolkit/issues/733) | `PromptEdit` — shared prompt component backed by the app's own tag vocabulary |
| [#734](https://github.com/ACFHarbinger/Image-Toolkit/issues/734) | Inline dataset tag review + Extractor/Library → Train handoff |
| [#735](https://github.com/ACFHarbinger/Image-Toolkit/issues/735) | Guided onboarding overlays for first-run users |

### Gate C — Embedded ComfyUI

| Issue | Deliverable |
|---|---|
| [#736](https://github.com/ACFHarbinger/Image-Toolkit/issues/736) | Tiered embedded ComfyUI view; independent server/view state machines |
| [#737](https://github.com/ACFHarbinger/Image-Toolkit/issues/737) | HTTP `/history` provenance capture in `ComfyUIManager` |
| [#738](https://github.com/ACFHarbinger/Image-Toolkit/issues/738) | Pre-flight workflow validation against `/object_info` + model-folder checks |
| [#739](https://github.com/ACFHarbinger/Image-Toolkit/issues/739) | Unified Generate surface — Guided \| Graph modes, shared filmstrip/run record |
| [#740](https://github.com/ACFHarbinger/Image-Toolkit/issues/740) | Matrix mode — X/Y parameter sweeps on Generate |

### Gate D — Training analysis

| Issue | Deliverable |
|---|---|
| [#741](https://github.com/ACFHarbinger/Image-Toolkit/issues/741) | Wire `DiagnosticsLogger` into both LoRA launch paths + JSONL event sink |
| [#742](https://github.com/ACFHarbinger/Image-Toolkit/issues/742) | Live training panel: sparkline, checkpoint filmstrip, linked-cursor scrubber |
| [#743](https://github.com/ACFHarbinger/Image-Toolkit/issues/743) | Effective-rank-over-checkpoints chart (rank/alpha advisor) |
| [#744](https://github.com/ACFHarbinger/Image-Toolkit/issues/744) | Dataset advisor: duplicates/coverage/aspect-ratio + CLIP diversity + tag co-occurrence |
| [#745](https://github.com/ACFHarbinger/Image-Toolkit/issues/745) | Hyperparameter-impact small-multiples sweeps |
| [#746](https://github.com/ACFHarbinger/Image-Toolkit/issues/746) | Training Report Card |
| [#747](https://github.com/ACFHarbinger/Image-Toolkit/issues/747) | Checkpoint tournament — blind ELO-ranked pairwise comparison |
| [#748](https://github.com/ACFHarbinger/Image-Toolkit/issues/748) | Loss-geometry 1-D slice along ΔW principal directions |
| [#749](https://github.com/ACFHarbinger/Image-Toolkit/issues/749) | Upscale handoff — wire the existing unwired `ESRGANWrapper` |

### Gate E — Guidance loop

| Issue | Deliverable |
|---|---|
| [#750](https://github.com/ACFHarbinger/Image-Toolkit/issues/750) | Pluggable OCR backend + VLM advisor interfaces |
| [#751](https://github.com/ACFHarbinger/Image-Toolkit/issues/751) | Versioned guidance schema, two validators, CI fixtures |
| [#752](https://github.com/ACFHarbinger/Image-Toolkit/issues/752) | Diff & Apply widget — per-row apply + re-queue as labeled variant run |
| [#753](https://github.com/ACFHarbinger/Image-Toolkit/issues/753) | Evidence-traced suggestions, abstention as first-class output, confidence display |
| [#754](https://github.com/ACFHarbinger/Image-Toolkit/issues/754) | "What Changed?" overlay + guidance-as-conversation trajectory |

### Backlog (explicitly deferred past this milestone's v1 scope)

| Issue | Deliverable | Why deferred |
|---|---|---|
| [#755](https://github.com/ACFHarbinger/Image-Toolkit/issues/755) | `QWebChannel` ComfyUI bridge (node highlighting/sync) | ComfyUI's frontend moves independently of this repo; build only after the plain embedded view is proven stable |
| [#756](https://github.com/ACFHarbinger/Image-Toolkit/issues/756) | Hutchinson Hessian trace estimator | New metric with no existing wiring to build on, unlike D.1–D.3 |
| [#757](https://github.com/ACFHarbinger/Image-Toolkit/issues/757) | C++ dataset analyzer | Benchmark-first; only pursue if Python-side D.4 proves slow on real datasets |
| [#758](https://github.com/ACFHarbinger/Image-Toolkit/issues/758) | Dedicated `GpuLeaseArbiter` subsystem | The simple one-job-at-a-time rule may be sufficient; formalize only if it isn't |

## 3. Explicitly rejected (not backlog, not planned)

- A separate top-level **Prepare** destination (Codex's original proposal) —
  dataset work starts inside Train instead.
- **CBIR** folded into this category — stays a separate product area.
- A **dual-pane canvas rebuild** and **immediate `comfy_bridge.js`
  injection** (Gemini's original framing) — `ImageCompareWindow` already
  does synced pan/zoom/A-B/diff; the bridge is backlogged (#755), not built
  alongside the first embed.
- A second **GPU-lease footer** — `TelemetryStatusBar` already does this
  job.
- **Automatic retraining or recursive optimization loops** — the guidance
  loop suggests; a human always decides.

## 4. Attribution

Architecture and correctness findings: Codex, Mistral, Grok, Gemini/
Antigravity, Cursor, Muse Code, Kimi, Qwen, Claude — see
`.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md` §4 for which
agent found/proposed which specific item. Selection and gate sequencing:
Harbinger + Claude, 2026-10-09.
