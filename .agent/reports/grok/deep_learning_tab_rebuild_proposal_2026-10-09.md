# Deep Learning tab rebuild — Grok proposal

**Grok · 2026-10-09 · Proposal only. Nothing here is approved to build.**

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`.
Claude, Codex, and Mistral already cover the workspace shell, the
WebEngine spike, schema-checked guidance, and wiring `DiagnosticsLogger`.
This note adds the interaction model those three leave open, grounded in
the widgets that are on screen today.

## What the screen actually is

The Deep Learning category is five routes in
`gui/src/windows/main/_tab_registry.py`: Training, Generation,
Evaluation, Inference, ComfyUI. Training and Generation are not forms.
Each is a `QComboBox` over a `QStackedWidget`:

- `UnifiedTrainTab` swaps LoRA, R3GAN, and Basic GAN. The first label is
  "LoRA (Diffusion and GANs)" with item data `"anything"`.
- `UnifiedGenerateTab` swaps LoRA, SD3.5, R3GAN, and Basic GAN. ComfyUI
  is a separate route, so generation is split across two destinations
  that do not share a prompt, a seed, or an output list.
- Evaluation is only `R3GANEvaluateTab`. Inference is only
  `MetaCLIPInferenceTab`. Neither belongs in a LoRA workflow, and both
  are invisible until the user opens those titles.

`LoRATrainTab` then adds a second combo (Standard / LoCon / LoHa / LoKr).
Epochs, batch size, learning rate, and rank are visible for every
engine. `start_training_thread` puts them in the worker config.
`_run_lycoris_training` (`lora_train_tab.py`, the Hydra `Popen`) forwards
dataset, model id, trigger word, output dir, and engine only. A packaged
build finds out after Start, via a status string, that LyCORIS cannot
run. Completion is a `QMessageBox`. There is no curve.

CBIR training, which is not in this category, already has the panel
LoRA lacks: epoch `QProgressBar`, start/cancel, a 64-point `_SparkLine`
(`gui/src/tabs/models/delta/cbir_train_tab/_sparkline.py`), and metric
labels. That is the live-training UI to copy. `usage_charts.py` is a
bar chart for cloud usage and is the wrong primitive for a loss trace.

## 1. Capability cards instead of stacked combos

**What.** One Deep Learning workspace. The left rail is a list of
capability cards, one per tool the checkout can actually run:

| Card | Mounts | Shown only when |
|---|---|---|
| Train LoRA | current Standard path | always |
| Train LoCon / LoHa / LoKr | current Hydra path | source checkout, not a frozen build |
| Generate (guided) | SD3 / LoRA generate forms, plus Comfy `WORKFLOW_MODES` | weights or a Comfy server available |
| ComfyUI graph | embedded or external Comfy | server URL known |
| Evaluate R3GAN | current eval tab | the R3GAN stack imports |
| Classify (MetaCLIP) | current inference tab | the MetaCLIP stack imports |
| Train retrieval (CBIR) | current CBIR tab | always |

The card title is the task. The subtitle is the real model id
(`stabilityai/stable-diffusion-xl-base-1.0` when that is what the
Illustrious label selects). A card that cannot run stays visible and
disabled, with the reason on the card: "LyCORIS starts
`backend.controllers.hydra_dispatch` and needs a source checkout."

**Pain.** The user cannot tell which screen trains a character LoRA,
which screen is a GAN toy, and which screen is Comfy. Controls that do
not reach the process look editable. Failures arrive after Start.

**Shape.** A `Capability` record: id, title, model id, enabled predicate,
widget factory, and the list of config keys that factory's launcher
actually reads. The launcher refuses to start if the form contains a
key the launcher ignores. The LyCORIS command grows
`trainer.epochs`, `trainer.batch_size`, `optimizer.lr`, and `lora.rank`
only after those Hydra keys are confirmed in
`backend/config/training/`; until then the four spin boxes are disabled
on LoCon/LoHa/LoKr with the text "preset value, not taken from this
form." Friendly names and repo ids both stay on the card. Saved routes
`ml.training`, `ml.generation`, `ml.evaluation`, `ml.inference`, and
`ml.comfyui` remain as aliases onto cards so old sessions still open.

**Tradeoffs.** A card list is another navigation surface on top of the
module shell Codex and Mistral already propose. It earns that only if
it deletes the architecture combo. Hiding R3GAN and MetaCLIP inside
cards makes them harder to stumble into, which is the point, and it
requires the card list to be the full inventory so those tools are not
dropped.

## 2. One generate surface with two modes

**What.** Guided and Graph are modes of one Generate card, not two
products. Guided is the existing Comfy modes (pose, depth, canny,
IP-Adapter) plus the prompt, seed, and size fields. Graph is ComfyUI's
own canvas. Both write into the same filmstrip and the same run record.

**Pain.** A user who learns the four guided modes loses them the day
the embedded canvas becomes the Comfy tab. A user who edits the graph
cannot see the guided run that produced the image they want to extend.

**Shape.** A segmented control, Guided | Graph, above the canvas. The
run record stores `mode`, the template name or the workflow JSON, the
overrides `ComfyUIManager.apply_overrides` actually applied, and the
output paths. Switching mode keeps the prompt text and the selected
images. Graph stays disabled until the WebEngine spike Claude described
is clean; the button beside it is "Open in browser," which is today's
behavior. Unknown node ids in an override are a visible error.
`apply_overrides` currently ignores them.

**Tradeoffs.** `QWebEngineView` is a large native library in-process.
The external button stays for machines where the spike fails. Loading
the canvas lazily, on the first Graph visit, keeps Train from paying
Chromium startup. The view's lifetime follows the workspace, not the
mode switch, or a hidden Chromium process outlives the tab.

## 3. Training feedback that matches a run, not a dialog

**What.** Replace the success `QMessageBox` with the CBIR panel: a
determinate epoch bar, a live sparkline, a log pane, and Cancel that
stops the process. Under the sparkline, a checkpoint filmstrip. The
full loss series is stored with the run. The sparkline shows the last
64 points only as a live summary.

**Pain.** A finished LoRA leaves a modal and a status label. The user
cannot see whether loss flattened at epoch 2 or at epoch 5, and cannot
compare two ranks without opening TensorBoard, which the GUI never
starts (`diagnostics=None` on both launch paths; V1's
`use_tensorboard` is unread).

**Shape.** Standard LoRA training emits step events on a Qt signal
(step, epoch, loss, learning rate). The LyCORIS subprocess already
streams stdout; parse the trainer's step lines into the same event.
Append each event to `runs/<id>/events.jsonl` (the sink Mistral
described). The panel is a view of that file. Cancel for the subprocess
sends terminate to the process group, then kill after a short wait.
The in-process path keeps the existing cancel flag.

Hyperparameter impact is a table of completed runs whose dataset
directory hash matches: rank, learning rate, epochs, last loss, and one
sample thumbnail. Sorting that table is the analysis. A loss-landscape
slice is a separate button on a finished checkpoint, off by default,
because it is another GPU job.

Dataset guidance starts as a contact sheet of the chosen folder:
image count, caption-file coverage, duplicate file hashes, and extreme
aspect ratios. A "cluster with CLIP" action is a second step and spends
a GPU lease. It should call `backend/src/core/similarity/` when the
user asks, which is Claude's reuse, behind an explicit button.

**Tradeoffs.** Parsing LyCORIS stdout is brittle if the trainer log
format changes. The JSONL file is the contract; the parser can lag
without losing the in-process Standard path. A unicode sparkline will
not show a 2,000-step curve honestly. The stored series and a simple
polyline view do. Do not add a chart library for this.

## 4. Review by marking the image

**What.** Review opens an output and its run record. The user drags a
rectangle on the image and types a short label ("hand", "caption text",
"background"). OCR runs on the marked rectangle first, then on the full
frame if the user asks. The assistant sees the image, the marks, the
OCR strings, and the workflow JSON. It returns a list of edits, each
with `node_id`, `input_name`, `old_value`, `new_value`, and a one-line
reason.

**Pain.** "What is wrong with this image" in this app is spatial: a
hand, a line of text baked into the picture, a flat background. A chat
box throws that location away, and free text can name parameters the
workflow does not have.

**Shape.** Marks are normalized rectangles in the run record, so they
survive a window resize. The suggestion panel is a table, not a
paragraph. Apply writes a new workflow file and queues it; it does not
edit the run that produced the critique. A suggestion is dropped when
`node_id` is absent, when `old_value` does not match the workflow, or
when the node id is one `apply_overrides` would ignore. OCR text is
shown on the image as selectable overlays so the user can correct a
misread before the assistant runs. The assistant call is a button.
Nothing is sent on a timer.

R3GAN metrics and MetaCLIP stay as their own cards. Review does not
absorb them.

**Tradeoffs.** A vision model will invent LoRA advice from one image.
The table-and-validator limit makes that visible and rejectable. OCR on
stylized anime text will be wrong often; the overlay is how the user
catches that before it becomes a prompt edit. Hosting the model is a
separate decision (local VLM versus an API). This proposal does not
pick a provider. The first slice can ship marks, OCR, and the table
with the assistant button disabled.

## 5. A GPU lease the whole window can see

**What.** A single footer on the workspace: who holds the GPU, which
phase they are in, a stop control, and a one-line log tail. Train,
Generate, CLIP clustering, and a later landscape slice all take the
lease before they start. The button reads "Queued behind Train LoRA"
when the lease is held.

**Pain.** This process also runs stitching, galleries, and wallpaper.
LyCORIS adds a second Python. Two Start buttons today do not know about
each other. A modal at the end is the only completion signal, so the
user leaves the tab and cannot tell that training is still in the
child process.

**Shape.** An in-process `GpuLease` with a name, a pid (the child, when
there is one), and a state (running, stopping, idle). Cards subscribe.
The footer is the only progress UI that stays visible across cards.
Estimated VRAM is a label on the card from the model record, not a
hard block, until measurement exists. Stopping the lease is the same
action as Cancel.

**Tradeoffs.** A lease inside the GUI does not see an ASP benchmark
started from a terminal. The footer should say "tracked jobs" so it
does not pretend to be a full GPU scheduler. Killing a process group
can take a checkpoint mid-write; Stop means "stop after this step"
when the trainer honors it, and "terminate" only on a second press.

## 6. Run list, separate from the gallery

**What.** Runs are a list: time, card name, model id, one thumbnail,
last loss or seed. Selecting a row reloads the form and the filmstrip.
Thumbnails are decoded with a bounded `QImageReader`, on a worker.

**Pain.** Users retrain because they cannot find the settings of the
run they liked. The gallery stack is the wrong place to hang that
list. Gallery loading and its thumbnail scheduler are the crash history
this repo already has.

**Shape.** A `runs/<id>/record.json` next to the outputs the trainer
already writes. The list reads that directory. It does not import
`VirtualGallery` or the thumbnail scheduler.

**Tradeoffs.** A second thumbnail path can drift from the gallery's
color management. These thumbnails are identifiers for a run, and a
200-pixel decode is enough. The list will not show library tags.

## What to build first

1. Capability cards, disabled states, and LyCORIS controls that match
   the command line. No new charts and no browser.
2. CBIR-style progress on the Standard LoRA path, plus `record.json`
   and the run list.
3. Guided/Graph generate with the browser button still external, and
   the same filmstrip for both modes.
4. Embedded Graph only after the in-process WebEngine spike.
5. Marks, OCR overlays, and the suggestion table. The model call stays
   off until the validator is tested on `configs/comfy_workflows/`.
6. CLIP clustering and any loss-landscape slice, each as an explicit
   lease-holding action.

## Agreement, kept short

The WebEngine ban's stated JVM cause is gone; the spike still comes
before any embedded canvas. `DiagnosticsLogger` should be passed into
the train calls that already accept it. Guidance should be data checked
against the workflow JSON. This proposal does not replace those
recommendations. It says the first screen a user should see is an
honest card and a run they can reopen.

— Grok, 2026-10-09
