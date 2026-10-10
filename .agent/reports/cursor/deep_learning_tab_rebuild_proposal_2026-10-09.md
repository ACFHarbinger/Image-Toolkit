# Deep Learning tab rebuild — Cursor proposal

**Cursor · 2026-10-09 · Proposal only. Nothing here is approved to build.**

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`.
Claude, Codex, Mistral, Grok, and Gemini already cover the workspace
shell, the WebEngine spike, schema-checked guidance, `DiagnosticsLogger`
wiring, capability honesty, and a ComfyUI JS bridge. This note adds the
**window and chrome** those five leave open: how the rebuilt tab lives
inside the existing shell, which widgets already exist, and which new
surfaces would duplicate them.

Cursor owns WindowManager (#528). The recommendation is shaped by that:
the Deep Learning category fails as a window, not as a missing trainer.

## Thesis

Do not invent a sixth navigation surface, a second GPU footer, a new
compare canvas, or a new inspector. The experimental runtime shell
already has `NavigationRailWidget`, `TopSegmentedRibbonWidget`,
`ContextInspectorPanel`, `TelemetryStatusBar`, `EventHub`, and
`WindowManager`. The rebuild should be the **second `ModuleCatalog`
workspace** (Stitch is the first) whose inner chrome is a destination
strip + a persistent header/footer, and whose heavy views pop out as
registered windows. Dataset tagging, A/B comparison, image preview, and
VRAM chips already ship. Wire them. Then add analysis and the assistant.

Agree with: task-grouped workspace behind an experimental pref; spike
`QWebEngineView` in-process before any embed UI; schema-validated
guidance; LyCORIS controls that match the command; JSONL run events;
HTTP `/history` provenance that does not depend on the embed.

Disagree with: Grok pulling CBIR into this category; Grok/Gemini adding
a GPU-lease footer that duplicates `TelemetryStatusBar`; Gemini
rebuilding a dual-pane canvas and injecting `comfy_bridge.js` in the
first cut; Codex making Prepare a top-level destination before the
Extractor → Train handoff exists.

## 0. Findings in this checkout (not live-run)

| Evidence | Consequence |
|---|---|
| `gui/src/classes/base/base_generative_tab.py` `collect()` stores `QComboBox.currentText()`. `LoRATrainTab.collect()` comments that this is intentional. Session save (`_save_tab_config.py`) persists those dicts. | Restored configs are **labels**, not model ids. Two Illustrious rows share `stabilityai/stable-diffusion-xl-base-1.0` and would round-trip as different names of the same weight. Persist `itemData` (or a stable field id) and show the friendly name separately. |
| `UnifiedTrainTab` / `UnifiedGenerateTab` persist `selected_model_index` (combo index), then stack LoRA / R3GAN / GAN (train) or LoRA / SD3 / R3GAN / GAN (generate). | Inserting a row, or a localized label change, silently retargets the saved session. Index is not a config key. |
| `application_catalog.py` still registers five `PageDescriptor`s (`ml.training` … `ml.comfyui`). Stitch is the only `WorkspaceDescriptor`. Stitch's handle still drives a `QTabWidget` (`stitch_workspace.py`). | Copying Stitch as-is gives nested tabs inside a category. The DL workspace should swap a content region, not wrap `UnifiedTrainTab` in another tab bar. |
| `NavigationRailWidget` already has `ModuleCategory.DEEP_LEARNING`. `TopSegmentedRibbonWidget` already paints category pills. `ContextInspectorPanel` is the right rail. `TelemetryStatusBar` already consumes `TelemetryUpdatedFact` (`vram_allocated_gb`, `task_count`). | A new left rail of capability cards and a new GPU footer fight chrome that shipped for this shell. |
| `EventHub` already defines `ImportPathsIntent`, `InspectImageIntent`, `SelectionChangedFact`, `NavigateIntent`. | Library → dataset and Extractor → Train are intents, not drag hacks and not a Comfy filesystem bridge. |
| `TagReviewDialog` + `TagReviewWorker` already page a dataset and write `.txt` sidecars in `HybridCaptioner` format. `LoRATrainTab._review_tags` opens it as a **modal**. | Prepare is not greenfield. Inline the dialog into Train's dataset panel; stop burying it behind a button that blocks the rest of the tab. |
| `ImageCompareWindow` already does synced pan/zoom, A/B overlay/crossfade, and a pixel-diff map. `ImagePreviewWindow` already does zoom/pan/batch next. Both `register_window()`. | Gemini's dual-pane canvas is a second compare widget. Host the existing window with a WindowManager role (`dl.compare`) from Review. |
| `ComfyUITab` queues a workflow and appends log lines. There is no output thumbnail, no filmstrip, no `InspectImageIntent`. Browse uses `QFileDialog.getOpenFileName` **without** `DontUseNativeDialog` (the safetensors inspector in the same train tab sets it). | The generate UX hole is "where did the image go?", not "we lack a node editor." Native-dialog crash class is still documented; this path skipped the patch. |
| `ImageToolkit.spec` has no QtWebEngine datas/binaries. `docs/ARCHITECTURE.md`, `README.md`, `docs/TROUBLESHOOTING.md`, `docs/moon/roadmaps/gui_ux.md`, `docs/moon/roadmaps/new_features.md`, and `.agent/skills/debug-crash.md` still say **never** use `QWebEngineView`. | An embed that lands in code but not in the constraint table will be refused by the next agent. Packaging and docs are spike deliverables, not follow-up. |
| `ModuleHostWidget` caches mounted widgets for the host lifetime and does not unmount. | Chromium, once constructed, stays resident when the user leaves Deep Learning. Pop-out and Unload must be explicit WindowManager-tracked actions. |
| CBIR lives under `gui/src/tabs/models/delta/cbir_train_tab/` and as a Reverse Search engine. It is **not** a `CLASSIC_TAB_ROUTES` Deep Learning entry. `_SparkLine` is a reusable widget in that package. | Copy the sparkline into Train. Do not move retrieval training into this category. |
| `content_generation.md` §3 is the video → character-LoRA pipeline. Extractor (`system.extractor`) already cuts frames. `ESRGANWrapper` exists and is not wired into any generate tab. `SafetensorsInspectorDialog` exists. | The product journey is Extractor → caption/review → train → generate → review. The tab rebuild should expose that path, not five architecture combos. |

## 1. UI/UX — workspace chrome, not a new product

### 1.1 Shell

Keep the app's category rail. Deep Learning becomes one catalog
workspace (`dl`) with four inner destinations, registered like Stitch
but **without** Stitch's inner `QTabWidget`:

| Route | Content | Primary action |
|---|---|---|
| `dl.train` | Recipe + dataset panel + live curves | Queue training |
| `dl.generate` | Guided form or Graph canvas + output filmstrip | Queue generation |
| `dl.review` | Selected output, marks, compare, guidance table | Queue variant |
| `dl.runs` | Run list (not the library gallery) | Open / clone |

R3GAN eval and MetaCLIP stay as **tools** opened from Review, not
top-level destinations. Classic ids `ml.training` … `ml.comfyui` remain
aliases onto the matching destination + tool.

Grok's capability cards belong **inside Train and Generate** as the
engine picker (LoRA / LoCon / LoHa / LoKr / SD3 / R3GAN), each showing
the real model id and a disabled reason. They are not the left rail.
A second rail on top of `NavigationRailWidget` is how this category
got five stacked combos in the first place.

`PrefKeys.EXPERIMENTAL_DL_WORKSPACE`, second consumer of
`WorkspaceDescriptor` / `ModuleHandle`. Default off until the WebEngine
spike and the LyCORIS forwarding fix land.

### 1.2 Layout

```text
[app NavigationRail]   Deep Learning · Train            [run name]
                       [Train] [Generate] [Review] [Runs]

┌──────────────────────────────┬─────────────────────────┐
│ Image-first canvas           │ ContextInspectorPanel   │
│ dataset grid / curves /      │ (existing right rail,   │
│ guided form / graph /        │  DL pages added)        │
│ selected output + marks      │  recipe / evidence /    │
│                              │  suggested patch        │
├──────────────────────────────┴─────────────────────────┤
│ filmstrip: outputs or checkpoints                      │
└────────────────────────────────────────────────────────┘

TelemetryStatusBar (existing): GPU chip · queue · Stop · log tail
```

The inspector already collapses; keep that. Target 1280×800 with the
inspector stacked under the canvas rather than clipped. All new QSS
goes through `theme_api` (`qss(...)`, `color(...)`) — the September
crash was a reminder that tab-local palettes do not survive a theme
pass.

Header is a breadcrumb (workspace · destination · run), not another
architecture combo. Footer is **not new**: publish `TelemetryUpdatedFact`
from the job adapter via `QtEventBridge` (the status bar already
forwards off-thread samples this way). Add a Stop control and a one-line
job name to that bar when a DL job holds the GPU. A second "GPU lease
footer" would hide the moment the user opens Library.

### 1.3 Interaction model

- **Handoffs, not copy-paste.** Extractor "Send frames to Train" publishes
  `ImportPathsIntent(module_id="dl", paths=...)`. Library selection
  publishes `SelectionChangedFact`; Train's dataset panel offers "Add
  selected". Review "Open in editor" uses `InspectImageIntent`. Generate
  "Compare with previous" opens `ImageCompareWindow` and
  `register_window(..., role="dl.compare")` so background-hide and
  shutdown see it.
- **No success `QMessageBox`.** Training finished is a run card, a
  status-bar chip, and a checkpoint thumbnail. Modals are for errors the
  user must acknowledge.
- **Effective config sheet** before Start: every control the form shows,
  the value the launcher will actually send, and a disabled note for
  anything the engine ignores. LyCORIS epochs/batch/LR/rank stay disabled
  until `hydra_dispatch` forwards them (Codex/Grok). The sheet is the
  fix for `collect()` persisting labels.
- **Inline tag review.** Replace the modal `TagReviewDialog.exec()` with
  the same widget hosted in Train's dataset splitter. Caption sidecars
  stay the HybridCaptioner format. Trigger token is a dedicated field,
  not the instance-prompt line (`_review_tags` already warns about that
  mix-up).
- **Output filmstrip is Generate's missing widget.** Poll
  `ComfyUIManager` `/history` (Mistral) and append completed images.
  Clicking one publishes `InspectImageIntent` and fills Review. Guided
  and Graph share this filmstrip (Grok's two modes of one surface).
- **Keyboard.** Ctrl+Enter queues the primary action; Esc requests Stop;
  `[` / `]` walk the filmstrip; Ctrl+Shift+C pops compare. Visible
  focus rings; chart axes have a table alternative (Codex's a11y bar).

### 1.4 Visual density

The current tabs are `QFormLayout` stacks with a bold "Model
Architecture" label. The rebuilt destinations should look like Stitch's
working panels: image occupies the majority, forms live in the
inspector, logs are a collapsible drawer. Capability picker uses the
real Hugging Face / checkpoint id as subtitle text, never only
"Illustrious XL V2.0 (Base SDXL)". Empty states are actionable ("Select
a dataset folder", "Start ComfyUI", "Open a run") and must not download
weights on tab open.

## 2. Embedded ComfyUI — view, not source of truth

### 2.1 Spike, packaging, docs

Claude's JVM finding stands; the ban comment is stale. The spike is
still the gate, and it has three extra acceptance checks this proposal
adds because they are WindowManager/packaging problems:

1. Construct `QWebEngineView` on the GUI thread after the event loop
   starts, load `ComfyUIManager.url`, route away and back 10 times
   (cached mount, no destroy), then **Unload** and reconstruct.
2. Pop the same view into a `QMainWindow` registered with
   `WindowManager` role `dl.comfy`. Background-hide, app shutdown, and
   `visible_taskbar_windows()` must treat it as a real window, not a
   leaked Chromium process.
3. Frozen `ImageToolkit.spec` run: QtWebEngine process + resources
   present; missing WebEngine degrades to Guided + "Open in Browser"
   without import-time crash.

If any of those fail, Guided stays the in-app generate surface and
Graph is the existing external button. HTTP `/history` capture still
ships (Mistral) so Review works either way.

**Docs gate, same PR as a green spike:** rewrite the "Never use
`QWebEngineView`" rows in `docs/ARCHITECTURE.md`, `README.md`,
`docs/TROUBLESHOOTING.md`, `gui_ux.md`, `new_features.md`, and
`.agent/skills/debug-crash.md` to "allowed for ComfyUI after spike X,
external browser remains the fallback." Leave the ban in place until
that rewrite. Agents read those files first.

### 2.2 Pop-out is the large-canvas UX

ComfyUI's graph wants a monitor, not a pane beside an inspector. Default
embed is a pane in Generate's Graph mode. **Pop out** moves the view to
a WindowManager-tracked window; the tab keeps the filmstrip and the
server controls. Closing the pop-out docks it back; it does not stop
the server. Disconnect vs Stop follows Codex: stop only owned processes.

Do not inject `comfy_bridge.js` in the first cut. ComfyUI's frontend
moves independently of this repo (`vendor/ComfyUI`). A QWebChannel
bridge that highlights node `#3` will break on their next graph
refactor. First cut: HTTP queue + `/history` + a native overlay listing
node id / title / current input (from the API graph, not from the DOM).
Gemini's bridge is a later enhancement **after** provenance and pop-out
are stable, and only if the spike's profile can load a `QWebEngineScript`
without turning off the Chromium sandbox.

Dedicated `QWebEngineProfile`, navigation scoped to the configured
server, external links via `QDesktopServices`. No general filesystem
bridge. Library images enter through `ImportPathsIntent` →
`ComfyUIManager.upload_image()`, which already exists.

## 3. Training / analysis — wire, then show, then research

Order matches Mistral; chrome details:

1. **Correctness.** Forward LyCORIS epochs/batch/LR/rank or disable the
   spin boxes. Persist `itemData`. Show the Illustrious row's actual
   repo id. Pass `DiagnosticsLogger` into both GUI launch paths. Mirror
   to `runs/<id>/events.jsonl`.
2. **Live panel.** Copy `_SparkLine` (last 64 points) + a determinate
   epoch bar from CBIR. Full series stays in the JSONL. Checkpoint
   filmstrip under the sparkline. Cancel: terminate process group, then
   kill; in-process path keeps the existing flag. No fabricated
   percentage (`lora_training_worker.py`'s unemitted progress signal
   stays deleted, not animated — Codex).
3. **Dataset panel on Train.** Contact sheet, caption coverage, hash
   duplicates, extreme aspect ratios. "Review tags" is the inlined
   `TagReviewDialog`. CLIP cluster / similarity reuse
   (`backend/src/core/similarity/`) is an explicit button that takes
   the GPU through the same job adapter. Do not auto-embed on folder
   pick.
4. **Compare runs.** Table of completed runs sharing a dataset-dir hash:
   rank, LR, epochs, last loss, one thumbnail. That is hyperparameter
   impact until someone runs a one-field sweep (Codex).
5. **Loss geometry last**, 1-D adapter-space slice on ΔW principal
   directions (Mistral), explicit cost, never a live-trainer mutation.

`usage_charts.py` is a cloud bar chart. Do not use it for a loss trace
(Grok). A polyline over JSONL is enough; no new charting dependency.

## 4. Review loop — marks on windows that already exist

Review is not a chatbot tab. It is: pick an output from the filmstrip
(or import an image + workflow JSON) → mark regions on
`ImagePreviewWindow` / the in-pane canvas → optional OCR on the mark →
optional assistant button.

Marks are normalized rectangles stored on the run record (Grok). OCR
overlays are editable before anything is sent. The assistant returns a
**table** of patches (`node_id`, `input`, `from`, `to`, `reason`)
validated against the executed API graph: node exists, `from` matches
current value (Mistral), asset is installed, workflow hash unchanged.
Apply writes a new workflow and queues a **variant**; it does not edit
the parent run. Compare parent vs variant through `ImageCompareWindow`
(synced pan/zoom, optional blind labels). Preference + reason go on the
run record.

First shippable slice: marks + OCR overlay + empty patch table, assistant
button disabled, fixtures over `configs/comfy_workflows/` (Mistral).
Provider choice is a later issue. Prompts, OCR text, and captions are
untrusted content and cannot authorize downloads or shell. Local VLM
waits for the GPU the same way training does.

R3GAN FID/KID and MetaCLIP stay reachable as Review tools. They are not
absorbed into the critique prompt.

## 5. Jobs and windows

One heavy GPU job at a time, shared by train, generate, CLIP cluster,
VLM, and landscape slices. The adapter publishes `TelemetryUpdatedFact`;
cards disable with "Queued behind Train LoRA". Stop is one control on
the status bar. This is Grok's lease without a second footer.

Workers are not owned by a destination widget. The workspace handle
owns subscriptions; `ModuleHost` will keep the widget mounted, so
dispose of the WebEngine view only on Unload / workspace dispose /
app shutdown, and drop the pop-out via WindowManager's `destroyed`
path (the same weakref + `destroyed` double-guard #528 already uses).

Do not hang the run list on `VirtualGallery` or `ThumbnailScheduler`
(Grok, and the crash history). Bounded `QImageReader` on a worker for
200 px run thumbnails.

## 6. What to build first

1. Docs + packaging spike for WebEngine; LyCORIS forwarding / disable;
   `collect()` persists ids. No new charts, no assistant.
2. `dl_workspace.py` + four destinations + experimental pref. Capability
   picker inside Train/Generate. TelemetryStatusBar job chip. Run
   `record.json` + JSONL + sparkline on Standard LoRA.
3. Guided | Graph generate, shared filmstrip, HTTP `/history`, external
   browser still default for Graph.
4. Embedded Graph pane + Pop out window after a green spike.
5. Inline tag review; Extractor/Library `ImportPathsIntent`.
6. Marks, OCR overlays, patch table, `ImageCompareWindow` from Review.
7. CLIP cluster, effective-rank chart, 1-D loss slice — each an explicit
   GPU job. QWebChannel only if (4) is boringly stable.

## Agreement, kept short

Schema-validate guidance. Spike before embed. Wire `DiagnosticsLogger`.
HTTP provenance independent of the view. Honest controls. This proposal
does not replace those. It says the first screen should reuse the shell
this team already built, pop ComfyUI out through WindowManager, and
stop opening a modal when a LoRA finishes.

— Cursor, 2026-10-09
