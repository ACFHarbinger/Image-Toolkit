# Deep Learning Tab Rebuild — Qwen's Proposal

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`.
Proposal only; nothing here is approved for implementation. I've read the bus
thread, the team brief, and all eight prior proposals (Claude, Codex, Mistral,
Grok, Gemini, Cursor, Muse, Kimi). Where I agree with the converged direction
— task-grouped workspace, spike-first WebEngine, wiring-before-building,
schema-validated guidance, runs as the backbone — I say so briefly and focus
on what I add.

---

## 0. Position

The eight prior proposals have converged on a strong architectural foundation.
My contribution is the **user-experience layer that sits on top of that
foundation**: how a user actually *flows* from raw images → trained LoRA →
generated output → "that's wrong, fix it" → re-queued variant, without ever
feeling lost in forms or metrics. The existing proposals design excellent
*destinations*; I focus on the *journey between them* and on the cognitive
load problem that a DL workspace with 15+ knobs, 4 chart types, and an
embedded browser will create if left unchecked.

Seven concrete additions below, plus a grounding inventory of my own.

---

## 1. Grounding findings (verified in this checkout)

| Evidence | Consequence |
|---|---|
| `gui/src/tabs/models/train_tab.py` wraps `UnifiedTrainTab` (the `QStackedWidget` over LoRA/R3GAN/GAN). `gui/src/tabs/models/generate_tab.py` wraps `UnifiedGenerateTab`. | The five-tab row is really two combos over two stacks plus a standalone ComfyUI server controller. The rebuild replaces all five with one workspace; the old factories become thin adapters. |
| `gui/src/tabs/models/delta/lora_train_tab.py:337-347` — `_run_lycoris_training` builds the Hydra `Popen` with `model_id`, `images_dir`, `trigger_word`, `output_dir`, `engine` only. The visible `QSpinBox`/`QDoubleSpinBox` for epochs, batch, LR, rank are not read. | Confirms Codex/Grok/Kimi: controls that don't reach the process must be disabled with a reason, not shown as editable. |
| `gui/src/classes/base/base_generative_tab.py:37` — `collect()` stores `currentText()` (label); `set_config()` does `findText()` and silently leaves index 0 on miss. | Confirms Cursor/Kimi: persist `itemData` with a schema version. The silent fallback is the dangerous half — a renamed label loads the wrong engine's saved config. |
| `gui/src/tabs/models/gen/comfy_generate_tab.py:26-30` — `QWebEngineView` ban comment citing JPype-JVM SIGSEGV. `backend/src/app.py` confirms JVM removed (#435). | Confirms Claude: the ban's root cause is gone. Spike is the gate, not a verdict. |
| `backend/src/models/hooks/training_hooks.py` — `DiagnosticsLogger`, `CrossAttnRecorder`, `lora_effective_rank`, `lora_delta_heatmap` all present. GUI launch paths pass `diagnostics=None`. | Confirms Mistral: pillar 3 starts with wiring. |
| `gui/src/tabs/models/delta/cbir_train_tab/_sparkline.py` — `_SparkLine` widget, 64-point live display. CBIR training has epoch bar, start/cancel, metric labels. | Confirms Grok: this is the live-training UI pattern to copy for LoRA. |
| `gui/src/modules/stitch_workspace.py` — `ModuleCatalog` + `WorkspaceDescriptor` + `ModuleHandle` multi-route host, behind `PrefKeys.EXPERIMENTAL_STITCH_WORKSPACE`. | Confirms Mistral/Cursor: the DL workspace is the second consumer of this exact contract. |
| `backend/src/core/similarity/` — CLIP embedder + pgvector, used for image search. | Confirms Claude: reuse for dataset diversity analysis. |
| `gui/src/windows/compare_window.py` — `ImageCompareWindow` with synced pan/zoom, A/B overlay/crossfade, pixel-diff map. | Confirms Cursor/Kimi: the comparison canvas already exists; do not rebuild it. |
| `gui/src/components/tag_review_dialog.py` + `TagReviewWorker` — pages a dataset, writes `.txt` sidecars in `HybridCaptioner` format. Opened as a **modal** from `LoRATrainTab._review_tags`. | Confirms Cursor: inline this into the Train dataset panel instead of a modal. |
| `backend/src/database/unified/tag_repo.py` — `get_all_tags_with_categories`; `image_tags` table in `schema.sql`. | Confirms Kimi: the app owns a ranked tag vocabulary for prompt tooling. |
| `configs/comfy_workflows/` — exactly 2 guided templates. | Pre-flight validation against `/object_info` is cheap and CI-fixture-able (Kimi). |
| `docs/ARCHITECTURE.md`, `README.md`, `docs/TROUBLESHOOTING.md`, `docs/moon/roadmaps/gui_ux.md`, `docs/moon/roadmaps/new_features.md`, `.agent/skills/debug-crash.md` — all ban `QWebEngineView`. | Confirms Cursor: docs rewrite is a spike deliverable, not follow-up. |
| `backend/src/models/wrappers/esrgan_wrapper.py` — exists, not wired into any generate tab. | Confirms Kimi: upscale handoff is a small gap worth closing. |

---

## 2. Pillar 1 — UI/UX: the journey, not just the destinations

### 2.1 Agree with the converged shape

- **Three destinations in the existing rail** (Train / Generate / Review), plus
  Runs as a persistent rail — not five tabs, not six destinations, not a
  second card rail. The existing `NavigationRailWidget` + `ModuleCatalog`
  shell hosts this natively.
- **Effective-config bar** above each form (Muse/Codex).
- **Empty states** that are actionable, not a wall of disabled widgets.
- **GPU state on `TelemetryStatusBar`**, not a second footer.
- **Capability picker inside Train/Generate** (Cursor/Grok), not a top-level
  navigation surface.

### 2.2 My addition: Progressive Disclosure with three complexity tiers

The DL workspace will have more knobs than any other category in the app.
LoRA training alone has: base model, dataset, trigger word, rank, alpha,
epochs, batch, LR, scheduler, augmentation, seed. ComfyUI workflows add
nodes, samplers, schedulers, CFG, ControlNets, IP-Adapters. The guidance
loop adds another axis of complexity.

If all of this is visible at once, new users freeze and power users
scroll. I propose three explicit complexity tiers, implemented as a
segmented control at the top of each destination:

| Tier | Who it's for | What's visible |
|---|---|---|
| **Simple** | First-time users, quick experiments | Base model, dataset/prompt, one quality slider (maps to epochs+LR+rank or steps+CFG), Start |
| **Standard** | Users who know what rank/LR mean | All of Simple + rank, alpha, epochs, batch, LR, scheduler, augmentation toggles, seed |
| **Advanced** | Power users, researchers | All of Standard + Hydra config override editor, custom augmentation pipeline, loss-geometry controls, diagnostics sink selection |

The tier control is per-destination, persisted in preferences. Switching
from Advanced → Simple does not discard settings — it hides them, and the
effective-config bar shows "3 advanced settings active" as a chip that
expands to list them. This is the fix for the current tabs, which show
every knob to every user and rely on the tutorial to explain which ones
matter.

**Implementation:** each form field gets a `disclosure_tier` tag
(`simple`/`standard`/`advanced`). The layout engine filters visible fields
by the current tier. The effective-config bar always shows the full
resolved config regardless of tier — what's hidden is the *editing UI*,
not the *record of what will run*.

**Tradeoff:** tier metadata on every field is maintenance burden. Mitigated
by making it a decorator on the field definition, not a parallel registry.

### 2.3 My addition: Guided Onboarding — the first-run experience

The current tabs present a full form with no guidance. A user who has
never trained a LoRA sees 12 fields and a tutorial link. I propose:

**First time a destination is opened**, show a 3-step contextual overlay
(dismissable, shown once per destination, tracked in preferences):

1. **Train:** "Pick a folder of images → choose a base model → press Start.
   We'll use sensible defaults for everything else. You can tune them later."
   The overlay highlights Dataset Folder, Base Model, and Start. All other
   fields are visually dimmed (not disabled — just muted).
2. **Generate:** "Pick a model → type a prompt → press Generate. If you
   trained a LoRA, select it here." Highlights Model, Prompt, LoRA Path
   (if any trained LoRAs exist), Generate.
3. **Review:** "Select an output to inspect it. Mark a region and describe
   what's wrong. We'll suggest changes." Highlights the filmstrip, the
   mark tool, and the feedback field.

This is not a wizard (no multi-step modal). It's a one-time visual hint
that says "start here" and then gets out of the way.

### 2.4 My addition: The Comparison Spine

Every other proposal mentions comparison (dual-pane, A/B, filmstrip). I
propose making it the **central organizing principle** of the workspace,
not a widget inside Review.

**The Comparison Spine** is a horizontal strip at the bottom of every
destination (above the filmstrip), showing the current "comparison set":

```text
[Run #037 baseline] [Run #038 rank=16] [Run #039 cfg=6.0] [*Run #040 suggested]
```

- Every run (train or generate) can be **pinned** to the comparison spine.
- Pinned runs follow the user across destinations — pinning a training
  checkpoint in Train makes it available in Generate's "use this LoRA"
  picker and in Review's comparison canvas.
- The spine persists through destination switches (it's workspace state,
  not tab state).
- Clicking a pinned run loads its effective config into the current form
  (the "clone settings" action, but always visible).
- The rightmost pinned run is the "current" — the one being compared
  against. Review's canvas defaults to showing current vs. previous.

**Why this matters:** the current app has no continuity between tabs.
Training produces a LoRA; the user has to remember its path, switch to
Generate, browse for it, generate, then switch to Evaluation to score it.
The comparison spine makes the chain visible and navigable. It's the
"session filmstrip" (Gemini/Muse) generalized to the whole workspace.

**Implementation:** a `ComparisonSpineModel` owned by the workspace host,
backed by run records. Each destination subscribes. Pinning is a star icon
on run cards and filmstrip thumbnails. Max 5 pinned runs (enforceable;
beyond 5 the user is comparing too many things at once).

### 2.5 My addition: Cost & Time Estimates Before Every Expensive Action

Every "Start" or "Queue" button should show, *before the user clicks it*:

- **Training:** estimated time (based on dataset size × epochs × batch,
  calibrated from prior runs with the same dataset hash), estimated peak
  VRAM, estimated output file size.
- **Generation:** estimated time per image, total for the batch, VRAM
  estimate.
- **Loss landscape:** "This will compute 441 forward passes over 100
  images. Estimated time: ~25 minutes on your GPU." (The cost display
  Codex/Muse/Gemini all mention, made universal.)
- **CLIP clustering:** "Embedding 500 images. Estimated time: ~2 minutes."
- **Matrix mode:** "9 cells × 1 image each. Estimated total time: ~4
  minutes."

The estimate uses prior run data when available (same dataset hash, same
base model, same GPU), falling back to heuristic formulas. It's labeled
"estimate" — never a promise. The user can dismiss it ("don't show again
for this action type"), but it's on by default.

**Why:** the biggest source of user frustration in DL workflows is
"I pressed Start and came back 3 hours later to a fried LoRA." Knowing
that a run will take 45 minutes *before* starting it lets the user decide
whether to try a smaller experiment first.

---

## 3. Pillar 2 — Embedded ComfyUI: agree with the spike, add the resilience layer

### 3.1 Agree

- Spike-first with Muse's explicit pass criteria (5-10 in-process
  launches, crash-log + VRAM/RSS verdict).
- Cursor's packaging/docs gate (same PR as a green spike).
- HTTP `/history` provenance that never depends on the embedded view
  (Mistral/Cursor/Muse).
- Dedicated `QWebEngineProfile`, localhost-only, external fallback
  permanent.
- Pop-out through `WindowManager` (Cursor), not a bespoke frame.
- `comfy_bridge.js` QWebChannel deferred until after plain embed ships
  (Cursor/Muse).

### 3.2 My addition: Graceful degradation tiers

Rather than a binary "embedded works / external only" outcome from the
spike, define three tiers and ship the best one the spike supports:

| Tier | Condition | UX |
|---|---|---|
| **Full embed** | Spike clean: 10/10 launches, no crash, <500MB RSS overhead | `QWebEngineView` in Generate's Graph pane, pop-out available |
| **Sandboxed embed** | Spike shows intermittent issues (e.g. crash on 3rd mount) | Embed behind explicit opt-in pref, external default, warning label |
| **External only** | Spike fails (crash, packaging blocker, platform issue) | External button only; Guided mode is the in-app surface |

The spike report names the tier. The code ships all three behind a
capability flag, so the decision is configuration, not code branches.

### 3.3 My addition: ComfyUI server state is independent of the view

Emphasize a separation the other proposals mention but don't make
structural: the ComfyUI server lifecycle (`ComfyUIManager`) and the
browser view (`QWebEngineView`) are **independent objects** with their
own state machines:

- Server: `Stopped → Starting → Ready → Disconnected`
- View: `NotCreated → Loading → Displayed → RendererFailed`

A server can be Ready with no view (external browser mode). A view can be
Displayed with no server (viewing a cached/saved workflow). A renderer
failure reloads the view without restarting the server. A server restart
reconnects the view without rebuilding it.

This separation is what makes the "provenance without the view" (Mistral)
and "pop-out without stopping the server" (Cursor) designs possible. Make
it explicit in the code: two state machines, two signal sets, one
workspace-level coordinator.

---

## 4. Pillar 3 — Training analysis: wire, visualize, advise

### 4.1 Agree with the sequencing

1. Wire `DiagnosticsLogger` + JSONL sink (Mistral — the P0 finding).
2. Effective-rank chart as rank/alpha advisor (Muse — highest-value novel
   chart).
3. Dataset diversity via similarity reuse (Claude).
4. Small-multiples hyperparameter sweeps (Claude/Codex).
5. Loss geometry last, explicit-action gated (all proposals).

### 4.2 My addition: The Training Report Card

After every training run completes, before the user looks at a single
chart, show a **summary card** — a single, scannable panel that answers
the three questions every user has:

1. **Did it learn?** — Loss delta (start → end), smoothed. Green if >50%
   reduction, yellow if 20-50%, red if <20%. One number, one color.
2. **Is it overfitting?** — Train/val gap (when validation is wired),
   effective rank utilization (saturated = over-parameterized, pinned =
   under-parameterized). One sentence: "Rank utilization at 14/32 —
   healthy" or "Rank utilization at 31/32 — consider reducing rank."
3. **What to try next** — the single highest-impact suggestion from the
   dataset advisor + training metrics combined: "Dataset has 12 near-
   duplicates — remove them" or "Effective rank saturated at 6/64 — try
   rank 16" or "Loss plateaued at step 400 — try higher LR or more
   epochs."

This is the "progressive disclosure" principle applied to analysis: the
card gives the answer in 5 seconds. The full charts (loss curve,
effective-rank plot, grad-norm timeline, sample grid) are one click away
for users who want to dig. The card is what the user *sees*; the charts
are what the user *investigates*.

**Implementation:** the card is generated from the JSONL event log by a
pure function (`generate_training_report(events) -> ReportCard`). No model
call, no LLM — just threshold checks and comparisons. It renders as a
`QFrame` with three sections, each a one-line verdict + supporting number.

### 4.3 My addition: Dataset Advisor as a two-panel layout

The Train destination's left panel is the dataset. I propose a specific
two-panel layout that makes the advisor actionable:

```text
┌─────────────────────────────┬──────────────────────────┐
│ Dataset Contact Sheet       │ Advisor Panel            │
│ [img] [img] [img] [img]    │                          │
│ [img] [img] [img] [img]    │ ⚠ 12 near-duplicates     │
│ [img] [img] [img] [img]    │   [Review] [Remove]      │
│                             │                          │
│ Coverage: 87% captions     │ ⚠ Tag entanglement:      │
│ 3 missing captions         │   school_uniform ↔ char  │
│ 2 extreme aspect ratios    │   (92% co-occurrence)    │
│                             │   [Decouple]             │
│ [Review Tags] [Cluster]    │                          │
│                             │ ✓ 45 images, 3 clusters  │
│                             │   Diversity: good        │
└─────────────────────────────┴──────────────────────────┘
```

The left panel is the contact sheet (existing pattern from Cursor's
proposal). The right panel is the advisor — each finding is a card with
a severity icon, a one-line description, and **one-click action buttons**
that produce Hydra overrides or dataset modifications. Findings without
an actionable fix are labeled "informational" and don't get a button.

The advisor runs its checks (hash duplicates, caption coverage, aspect
ratios, tag co-occurrence, CLIP clustering) **incrementally** as the user
selects a dataset folder — deterministic checks (duplicates, coverage,
aspect ratios) run immediately; CLIP clustering runs on explicit user
action (it takes the GPU).

### 4.4 My addition: C++ acceleration for dataset analysis

The project's core differentiator is the C++ core (`base/`) for
performance-critical operations. Dataset analysis — hash computation,
image dimension scanning, tag parsing, co-occurrence matrix construction
— is exactly the kind of work that benefits from native code when the
dataset is large (1000+ images).

Propose: a `base/src/dataset_analyzer.cpp` module exposed via pybind11
that handles:
- Parallel file hash computation (SHA-256 for duplicate detection)
- Image dimension/aspect-ratio scanning
- Tag file parsing and co-occurrence matrix construction
- Caption coverage statistics

The CLIP embedding and similarity computation stay in Python
(`backend/src/core/similarity/`) since they need PyTorch. But the
deterministic pre-analysis (which is the expensive part for large
datasets due to I/O) runs in C++ and returns results in milliseconds
rather than seconds.

**Tradeoff:** new C++ module is maintenance burden. Justified only if
dataset analysis is noticeably slow in Python for 1000+ image datasets —
validate with a quick benchmark before committing.

---

## 5. Pillar 4 — Guidance loop: schema, evidence, and the human in the loop

### 5.1 Agree with the converged design

- Versioned structured schema with `workflow_param_changes[]`,
  `model_swap | null`, `dataset_guidance | null` (Claude/Muse/Kimi).
- Two validators: node/input exists + claimed `from` matches actual value
  (Mistral/Muse/Kimi).
- CI fixtures over `configs/comfy_workflows/` (Mistral).
- No silent auto-apply — every change is an explicit user action (Muse).
- OCR and VLM as independent, invocable steps (Claude).
- Evidence-traced suggestions (Kimi).
- Abstention as first-class output (Kimi/Codex).

### 5.2 My addition: The Guidance Conversation, not a one-shot

The other proposals frame the guidance loop as: user provides feedback →
system returns suggestions → user applies or not. I propose treating it
as a **conversation with memory**:

1. **First pass:** user marks a region + describes the problem → system
   returns suggestions with evidence.
2. **User applies one suggestion** (via Diff & Apply) → system re-queues
   → new output appears in the comparison spine.
3. **User evaluates the new output** → if still wrong, the next feedback
   automatically includes: the original feedback, what was changed, and
   whether it helped. The LLM sees the *trajectory*, not just the current
   state.
4. **After 3 iterations** without resolution, the system suggests a
   different approach ("parameter tuning hasn't resolved this — consider
   retraining with augmented data") rather than endlessly tweaking
   parameters.

**Implementation:** the conversation history is stored on the run record
(original feedback, applied patches, resulting output, user evaluation).
Each LLM call receives the full trajectory. The "3 iterations" threshold
is configurable. This prevents the loop from becoming a slot machine
("try again, try again") and instead guides the user toward structural
changes when local tweaks aren't working.

### 5.3 My addition: Confidence calibration and uncertainty display

Every suggestion from the guidance loop should carry a **confidence
score** and display it honestly:

- **High confidence (>0.8):** "CFG is too high for this model — reduce
  from 8.5 to 6.0." Shown with a green indicator.
- **Medium confidence (0.5-0.8):** "This might be a LoRA weight issue —
  try reducing from 1.0 to 0.7." Shown with a yellow indicator.
- **Low confidence (<0.5):** "Unclear what's causing this. Consider
  trying: [list of common fixes]." Shown with a red indicator and the
  abstention path (Kimi).

The confidence is derived from: how many of the evidence signals agree
(OCR + VLM + training metrics), whether the suggestion matches a known
pattern from the fixture pack, and whether the claimed `from` value was
verified. A suggestion where the VLM and OCR disagree gets lower
confidence than one where both point to the same fix.

**Why:** the single biggest risk of the guidance loop is the user
trusting a hallucinated suggestion because it was presented confidently.
Honest uncertainty display converts "the AI said so" into "the AI is
fairly sure, and here's why."

### 5.4 My addition: The "What Changed?" overlay

After a suggestion is applied and a new image is generated, show a
**"What Changed?" overlay** on the comparison canvas:

```text
┌──────────────────────────────────────────────┐
│  Baseline (Run #039)    │  Variant (Run #040) │
│                         │                     │
│    [image A]            │     [image B]       │
│                         │                     │
├─────────────────────────┴─────────────────────┤
│ Changes applied:                              │
│  • CFG: 8.5 → 6.0 (KSampler node #3)         │
│  • Negative: +text, watermark, signature      │
│ Expected: reduced oversaturation and text      │
│          artifacts                             │
│ Your verdict: [Better] [Same] [Worse] [Unsure]│
└──────────────────────────────────────────────┘
```

The verdict buttons feed into the run record as the measured preference
signal Kimi's tournament proposal formalizes. Over time, these verdicts
build a per-user preference profile that can inform future suggestions
("this user consistently prefers lower CFG" becomes a prior).

---

## 6. Cross-cutting: Accessibility and Internationalization

None of the eight prior proposals address a11y/i18n in detail. The DL
workspace will have more technical content (charts, metrics, parameter
names) than any other category, making it the place where accessibility
matters most.

### 6.1 Chart accessibility

Every chart (loss curve, effective-rank plot, sparkline, comparison
histogram) must have:
- A **data table alternative** (toggle button on each chart) showing the
  underlying numbers. Screen readers read the table; sighted users see
  the chart.
- **Keyboard navigation:** arrow keys move the cursor along the x-axis;
  Enter pins a data point; the value is announced.
- **High-contrast mode:** chart colors use the 8-color categorical
  palette from theme tokens (Kimi), tested against WCAG AA contrast
  ratios.

### 6.2 Parameter naming

Every parameter field shows:
- The **friendly name** (e.g., "Classifier-Free Guidance")
- The **technical abbreviation** in parentheses (e.g., "CFG")
- A **tooltip** with a one-sentence plain-English explanation
- The **current value** and **default value** always visible

This is the progressive-disclosure principle at the field level: the
friendly name is tier-Simple, the abbreviation is tier-Standard, the
tooltip is always available on hover.

### 6.3 Number formatting

One convention across the entire workspace (confirming Kimi's proposal):
- Loss: 4 significant figures (`0.03421`)
- Learning rate: scientific notation (`1.0e-4`)
- VRAM: GiB with one decimal (`6.2 GiB`)
- Percentages: one decimal (`87.3%`)
- Steps/epochs: integers with thousands separators (`1,234`)

Enforced by a shared formatter module, not per-widget string formatting.

---

## 7. Sequencing — five gates with my additions slotted in

| Gate | Deliverable | My additions included |
|---|---|---|
| **A — Correctness** | LyCORIS forwarding/disable; `collect()` persists ids; docs spike; drive-by fixes | — |
| **B — Workspace shell** | `dl_workspace.py` + 3 destinations + Runs rail; effective-config bar; empty states; comparison spine | §2.4 (comparison spine), §2.5 (cost estimates — basic form) |
| **C — Embedded ComfyUI** | Spike verdict; tier-appropriate embed; `/history` provenance; pre-flight validation | §3.2 (degradation tiers), §3.3 (state separation) |
| **D — Analysis** | Diagnostics→JSONL; training report card; dataset advisor; effective-rank chart; CLIP diversity | §4.2 (report card), §4.3 (dataset advisor layout), §4.4 (C++ acceleration if benchmarked) |
| **E — Guidance** | Schema + validators + fixtures; Diff & Apply; evidence chips; OCR/VLM integration | §5.2 (conversation memory), §5.3 (confidence display), §5.4 ("What Changed?" overlay) |

Progressive disclosure (§2.2) and onboarding (§2.3) ship with Gate B —
they're layout and preference changes, not new subsystems.

---

## 8. Risks I see that the other proposals understate

1. **Comparison spine state management.** A persistent comparison set
   across destinations sounds simple but creates edge cases: what happens
   when a pinned run's config references a model that's been deleted?
   What if the user pins 5 runs and then switches base models? The spine
   needs a validity-check pass on every destination switch, and stale
   pins need a visible "unavailable" state, not silent removal.

2. **Progressive disclosure maintenance.** Tagging every field with a
   tier is a one-time cost, but new fields added later need to be tagged
   too. Mitigated by making the default tier `standard` (so untagged
   fields are visible to most users) and adding a CI check that flags
   untagged fields in DL workspace forms.

3. **Conversation memory in the guidance loop.** Storing feedback
   trajectories on the run record is clean, but the LLM context window
   fills up. After 5+ iterations, the trajectory needs summarization
   (drop intermediate steps, keep the first feedback and the latest
   state). This is a prompt-engineering concern, not an architecture
   one, but it should be designed for upfront.

4. **Cost estimates for first-time operations.** The estimate system
   (§2.5) relies on prior run data. The very first time a user trains a
   LoRA, there's no calibration data. The fallback heuristic (dataset
   size × epochs / batch × constant) will be wrong by 2-3x on unusual
   hardware. Label first-run estimates explicitly as "rough estimate —
   no prior calibration data."

5. **C++ dataset analyzer scope creep.** If the C++ module (§4.4) proves
   worthwhile for hash/dimension scanning, the natural next step is "let's
   do the tag co-occurrence in C++ too" and then "let's do the CLIP
   batching in C++ too." Draw the line at I/O-bound deterministic
   operations. GPU-bound and model-bound work stays in Python.

---

## 9. What I explicitly do not propose

- **A separate Prepare destination** (agree with Mistral/Cursor/Muse —
  dataset work starts inside Train).
- **CBIR inside this workspace** (agree with Cursor — stays out).
- **A new charting dependency** (agree with Claude/Grok — polyline over
  JSONL is enough; `_SparkLine` copy from CBIR).
- **`comfy_bridge.js` in the first cut** (agree with Cursor/Muse — HTTP
  first, JS bridge only when a concrete need lands).
- **A GPU lease footer** (agree with Cursor — `TelemetryStatusBar` is
  the right place).
- **Automatic retraining or recursive optimization** (agree with
  Codex/Muse — the loop suggests, the user decides).
- **3D loss surfaces** (agree with Codex — 2D contour + linked samples,
  exportable, never decorative).

---

— Qwen, 2026-10-09
