# Deep Learning Tab Rebuild — Muse Code's Proposal

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`
(read that first for the brief). Proposal-only; nothing here is approved for
implementation. I read the bus, the team brief, and the Claude / Codex /
Mistral / Grok / Gemini / Cursor proposals before writing this, plus the
current tab sources (`gui/src/tabs/models/`) and `docs/tutorials/deep_learning.md`.
Depth over coverage: I go concrete where I add something new and otherwise
name the proposal I agree with rather than restating it.

## 0. Position in one paragraph

Agree with the converged direction: task-grouped workspace (Train / Generate /
Review), spike-gated embedded ComfyUI, wiring-before-building on analysis,
schema-validated guidance. My contribution is the backbone that makes those
pieces compose: **every execution is a Run** (config snapshot + logs +
outputs + metrics, reloadable and re-queueable), provenance is captured over
HTTP rather than through the embedded view, and the existing app shell (rail,
`WindowManager`, `TelemetryStatusBar`, `EventHub` intents) is reused — no
second card rail, no GPU footer, no new windowing system. Details below.

## 1. UI/UX — three destinations in the existing shell

**Structure: Train / Generate / Review inside the current rail, not a new one.**
The five-tab row (Training / Generation / Evaluation / Inference / ComfyUI)
splits one workflow across too many places — "look at output, decide what to
change" currently spans Generation, Evaluation, and Inference. I propose three
destinations (agreeing with Claude/Codex here, against keeping the five):

- **Train** — LoRA (V1 + LyCORIS), GAN/R3GAN, Basic GAN, plus the analysis
  dashboard (§3). The architecture/capability picker lives *inside* the tab
  (Cursor's point — a top-level split would multiply destinations again).
  Capability cards state disabled reasons (Grok's point, e.g. missing VRAM or
  checkpoint) so a greyed-out option teaches instead of confusing.
- **Generate** — LoRA/SD3.5/GAN plus ComfyUI as **two modes of one surface**:
  Guided (form) and Graph (embedded browser, §2). One output gallery, one
  run list, regardless of mode — this is what makes A/B comparison possible.
- **Review** — merges Evaluation metrics, CLIP inference, and the
  OCR/LLM/VLM guidance loop (§4). Reviewing a run and acting on the advice
  (re-queue with a patched config) happen in one place.

**Runs rail (the backbone).** Every train/generate/eval/inference execution
produces a Run card: thumbnail, status, key params, headline metric. Clicking
reloads its effective config into the form; a re-queue button reproduces it.
Reuse `VirtualGallery` thumbnail-card components and the existing rail —
do not build a second rail or a gallery-scheduler-backed list (Grok/Cursor
both flagged the scheduler coupling; a plain list model owned by the
workspace is enough). Persist combo **ids, not labels** (Cursor's
`BaseGenerativeTab.collect()` finding — labels rot when the model list
changes; ids survive).

**Effective-config bar.** Above each form, one read-only line showing the
resolved config (base model id + trigger word + rank/epochs/batch/LR, or
workflow name + checkpoint). This is the cheapest provenance UI available:
it makes "which base was this LoRA trained on" visible *before* the user
generates with the wrong base — the most common LoRA footgun in the current
tabs, where Train and Generate each hold their own combo with no shared
state. Full provenance (Hydra snapshot, workflow `/history`) stays one click
deeper on the Run card.

**Empty states first.** Each destination gets a designed empty state ("No
runs yet — pick a capability → set dataset → Start"), because the current
tabs present a full form with no guidance on step one. Cheap, high-leverage,
and currently missing everywhere in this category.

**GPU state on the existing telemetry bar.** No new footer (agreeing with
Cursor against Grok's footer here): VRAM in-use, active job, and a cancel
affordance belong on `TelemetryStatusBar`, which already exists for exactly
this. A GPU Lease Arbiter (Gemini's proposal) can sit behind that indicator
later; the indicator itself is the P0 piece.

**What I explicitly do not propose:** a separate Prepare destination (dataset
work starts inside Train, per Mistral — a top-level Prepare fragments the
flow before runs exist); CBIR inside this workspace (stays out, per Cursor);
a new charting dependency (reuse `usage_charts.py` primitives + `FigureCanvas`
for the one landscape plot, per Claude).

## 2. Embedded browser — spike gate with pass criteria, then thin embedding

The documented `QWebEngineView` ban (`comfy_generate_tab.py:26-30`, JPype-JVM
SIGSEGV) lost its root cause when the JVM left the product (#435) — Claude's
finding, confirmed import-clean in the current `.venv`. I add the gate
criteria that decide it, since "spike first" needs a definition of done:

1. Construct `QWebEngineView` **in the real app process** (not a standalone
   script), load the vendored ComfyUI URL after `wait_until_ready()`.
2. 5–10 fresh launches; read crashes with the repo's existing tooling
   (`dev/resolve_qt_offset.py`, `crash.py` hs_err reader).
3. Measure idle + generating VRAM/RSS delta of the WebEngine process.
4. Verdict options: ship embedded-default, ship opt-in (external default),
   or keep external-only.

**Shape if the spike passes (deliberately thin):** `QWebEngineView` inside
the Graph mode pane on a **dedicated `QWebEngineProfile`** (disk cache off,
ComfyUI localhost URL allowlisted — this view browses one local server, not
the web), pointed at `ComfyUIManager.url`. "Open in External Browser" stays
as a permanent fallback. Pop-out goes through the existing `WindowManager`
as a registered window, not a bespoke floating frame. `comfy_bridge.js`
`QWebChannel` syncing (Gemini's proposal) comes **after** the plain embedded
view ships — HTTP `/history` provenance first (Mistral/Cursor), JS bridge
only when a concrete sync need (e.g. advice-driven node highlight) requires
it, since each injected bridge is new attack/maintenance surface.

**Known costs, named:** WebEngine raises install size and needs `ImageToolkit.spec`
datas entries (Cursor's finding — PyInstaller will silently ship a broken
embedded view without them); six docs files still ban WebEngine and need a
rewrite as a spike deliverable; platform-specific WebEngine failures (the
FFmpeg/VA-API crash class Claude cited) are why the external fallback never
goes away. Provenance capture must never depend on the embedded view
succeeding — `/history` polling is the contract, the view is just glass.

## 3. Training analysis — wire what exists, then two advisors

**P0 is wiring, not building** (Mistral's finding, which I verified exists in
spirit if not line-by-line: `backend/src/models/hooks/training_hooks.py`
ships `DiagnosticsLogger` + `CrossAttnRecorder` + `lora_effective_rank`, yet
the GUI launch paths don't surface them and V1's `use_tensorboard` is dead
config). Concretely:

- One **JSONL per-run event sink** (step, loss, LR, grad/weight norms,
  effective rank, VAE roundtrip, sample-grid paths) written by both GUI launch
  paths; the tab charts it with the reused `usage_charts.py` primitives.
  TensorBoard/W&B stay optional sinks, never the GUI's data source.
- **Effective-rank-over-checkpoints chart as the rank/alpha advisor.** This
  is the single highest-value novel chart: if effective rank saturates far
  below the chosen rank, the adapter is over-parameterized (shrink rank,
  save VRAM/file size); if it pins at the cap while loss still falls, rank
  is the bottleneck. No other proposal turns an existing metric into advice
  this directly.
- **Hyperparameter impact as small-multiples** (loss vs. step, one line per
  value, Hydra-driven sweeps) — the actual question ("did 1e-4 beat 5e-5?")
  answered without a parallel-coordinates widget (agreeing with Claude).
- **Loss geometry gated behind an explicit action.** 1-D slices along top-ΔW
  singular directions (Mistral's refinement of random directions — measures
  the subspace training actually moved in) plus Hutchinson trace as the cheap
  sharpness gauge (Gemini's estimator). Never background/automatic: one
  checkpoint, one button, cost estimate shown upfront.

**Dataset advisor (the other half of pillar 3).** Point the existing
`backend/src/core/similarity/` CLIP+pgvector stack at the LoRA dataset
(Claude's reuse — no new infra): cluster embeddings → thin-cluster callouts
(underrepresented pose/background), near-duplicate flags (the classic small-
dataset overfit cause), and, where captions exist, a tag co-occurrence table
(Gemini's entanglement engine, scoped down to "which two tags always appear
together and will therefore bleed"). Each finding offers a **one-click Hydra
override** (enable mirror/augmentation, drop duplicates, rebalance sampling)
rather than prose advice — guidance that can't be applied in one click won't
be applied. Overfitting early-warning (train/val gap + sample-grid cadence
from the wired diagnostics) completes the loop: dataset thinness predicts
risk, the gap confirms it, augmentation overrides fix it.

## 4. Guidance loop — two passes, schema-constrained, Diff & Apply

**Pipeline:** independent OCR step (baked-in/garbled text — useful alone) +
independent VLM critique step (anatomy, artifacts, style match, prompt
coverage) + workflow JSON (`/history`, never the embedded view) + user
free-text feedback → one LLM call that **must return a versioned schema**
(`workflow_param_changes[]` with `node_id/input/from/to/reason`,
`model_swap | null`, `dataset_guidance | null`). Two validators before
anything is shown (extending Claude/Mistral): (a) every referenced node/input
exists in the actual workflow JSON; (b) each claimed `from` value **equals**
the workflow's current value — a suggestion built on a misread of the
workflow is rejected, not rendered. CI fixtures over
`configs/comfy_workflows/` (Mistral) cover the validators with real graphs.

**The widget is the deliverable, not the text.** Render each suggestion as a
diff row (node · field · old → new · reason) with per-row Apply toggles and
one **Re-queue** button that queues the patched workflow through the existing
`queue_workflow()` path and registers the new Run alongside the old one —
this is what turns advice into the controlled A/B comparison Codex asked
for. Dataset guidance routes back to Train as a prefilled override (via the
existing `ImportPathsIntent`-style handoff, per Cursor), not as a dead
paragraph. Session filmstrip (Gemini) records prompt/param diffs between the
compared runs so "what changed" survives the session.

**Model choice deferred** (agreeing with Claude): local vs. hosted
OCR/VLM/LLM goes through the existing wrapper pattern as its own scoped
decision. One hard rule regardless of provider: **no silent auto-apply** —
every applied change is an explicit user action on an explicit diff row, and
every auto-queued run is labeled as assistant-suggested in its Run card.

## 5. Sequencing and acceptance gates

1. **Runs + effective-config bar + empty states** (P1 shell, no model work).
   Gate: reload any run card reproduces its config; ids persisted, not labels.
2. **WebEngine spike + verdict** (§2 gate). Gate: spike report with crash
   log, VRAM/RSS delta, and one of the three verdicts — no embedding UI
   before this lands.
3. **Diagnostics→JSONL wiring + rank advisor + dataset reuse** (P0 analysis).
   Gate: both GUI launch paths emit events; rank chart renders on a real run.
4. **Schema + validators + Diff & Apply + `/history` provenance** (guidance
   MVP, no JS bridge). Gate: fixture suite green; hallucinated-node
   suggestions rejected in tests; one-click re-queue produces a labeled run.
5. **Later / optional:** loss slices + Hutchinson gauge, JS bridge node
   highlight, lease arbiter, entanglement matrix.

Biggest risks, stated plainly: WebEngine platform fragility (mitigated by
permanent external fallback); analysis cost on user GPUs (mitigated by
explicit-action gating); LLM hallucination on parameters (mitigated by the
two validators + no-silent-apply rule, not by prompt engineering).

— Muse Code (powered by Meta Muse Spark), 2026-10-09
