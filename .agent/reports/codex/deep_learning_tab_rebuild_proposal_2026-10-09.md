# Deep Learning workspace — Codex proposal

**Codex · 2026-10-09 · Proposal only; no implementation approval implied.**

## Recommendation

Build a workspace around **Prepare → Train → Generate → Review**, with shared
**Runs** and **Models & resources** views. Preserve existing inference and GAN
evaluation tools as explicit destinations within Review. The central product
promise should be: every result has inspectable inputs, every proposed change
can be compared with its baseline, and expensive work has a visible owner.

Prioritize reliable run capture, resource scheduling, and embedded ComfyUI
before automated advice or expensive loss geometry. This complements
[Claude's proposal](../claude/deep_learning_tab_rebuild_proposal_2026-10-09.md):
I agree with its reuse and structured-guidance direction, but would give dataset
preparation its own destination and make execution correctness the first gate.
This is future scope, not an additional requirement for release 1.0.0.

## 1. Findings in the current checkout

Paths below are relative to the repository root. These are code observations,
not claims of successful live execution.

| Evidence | Consequence for the rebuild |
|---|---|
| `gui/src/windows/main/_tab_registry.py` registers Training, Generation, Evaluation, Inference, and ComfyUI separately. | Preserve saved routes and existing capabilities while presenting a coherent workflow. |
| `gui/src/tabs/models/delta/lora_train_tab.py` exposes Standard plus LoCon/LoHa/LoKr; the latter launch `backend.controllers.hydra_dispatch`. | V2/LyCORIS exposure already exists. The team brief's possible missing-GUI assumption should not become duplicate work. |
| The LyCORIS dispatch receives dataset, model, trigger, output, and engine, but not the visible epochs, batch size, learning rate, or rank values. | A parameter shown as editable must reach the selected engine, or be disabled with an explanation. Display the effective configuration before launch. |
| Two entries labelled Illustrious in that tab resolve to `stabilityai/stable-diffusion-xl-base-1.0`. | Model cards must show the actual identifier and revision; friendly names must not conceal mismatches. |
| The separate `gui/src/helpers/models/lora_training_worker.py` still calls V1 and declares an unemitted progress signal. | Consolidate execution adapters and define real progress events; do not animate a fabricated percentage. |
| `comfy_generate_tab.py` opens an external browser; some worker paths call `setEnabled()` directly. Its stop handler calls a manager method that can wait ten seconds. | GUI updates must arrive through queued signals; startup, stop, and network operations belong off the GUI thread. |
| `backend/src/models/core/comfy_manager.py` starts its own process, uploads inputs, and queues API graphs. `apply_overrides()` silently ignores unknown node IDs. | Reuse it behind an expanded service contract, but add strict validation for assistant-authored patches. Queue acceptance is not successful completion. |
| The manager refuses packaged local launch without its source tree; its current interface has no attach-to-existing-server operation. | Connecting to a server must be a first-class capability before the packaged UI advertises it. |
| `meta_clip_inference_tab.py` supplies classification inputs; `r3gan_evaluate_tab.py` exposes FID/KID/precision-recall/IS settings. | Review must retain task-specific tools, not reduce all evaluation to a generation critique chatbot. |
| `gui/src/modules/{descriptor,host}.py` supplies lazy module construction and cached mounted views. | Reuse the shell; explicitly manage worker/browser lifetime because changing routes does not destroy a mounted view. |

The bus reports that the JVM conflict behind the historical WebEngine ban was
removed. `backend/src/app.py` corroborates removal of the JVM. That makes an
embedding spike reasonable; it does not establish rendering or packaging safety.

## 2. Navigation and visual design

Use one Deep Learning workspace within the existing module shell, with child
routes rather than a second independent application shell.

| Destination | Main content | Primary action |
|---|---|---|
| Prepare | Dataset grid, caption editor, duplicate/coverage review, split preview | Save dataset version |
| Train | Recipe, effective configuration, live curves, checkpoint previews | Queue training |
| Generate | Guided controls or embedded ComfyUI canvas, output filmstrip | Queue generation |
| Review | Synchronized comparisons, regional feedback, OCR, inference and evaluation tools | Create experiment |
| Runs | Searchable history, queue, configuration diffs, artifacts | Open or clone run |
| Models & resources | Installed models, capabilities, device occupancy, server connections | Load/unload or connect |

Suggested desktop composition:

```text
Deep Learning   [Project / experiment]           [GPU status] [Queue: 2]
┌──────────┬───────────────────────────────────┬──────────────────────┐
│ Prepare  │ Breadcrumb / run name             │ Context inspector    │
│ Train    │                                   │ Inputs / settings    │
│ Generate │ Image, workflow canvas, or charts  │ Changes / evidence   │
│ Review   │                                   │                      │
│ Runs     │                                   │ [Primary action]     │
│ Models   ├───────────────────────────────────┴──────────────────────┤
│          │ Selected outputs / checkpoint filmstrip                 │
└──────────┴──────────────────────────────────────────────────────────┘
            [Current job and phase] [Stop after current item] [Logs]
```

Use existing theme tokens, restrained borders, readable spacing, and an
image-first canvas. The inspector collapses on narrow windows; layouts should
remain usable at 1280×800 and enlarged text. Avoid tiny chart labels and status
encoded only by color. Provide keyboard navigation, visible focus, labelled
icons, accessible names, and textual/table alternatives to charts.

Keep basic controls visible and put engine-specific detail under Advanced.
Show units, defaults, and a reset action beside consequential settings.
Persist panel sizes and selected routes through the existing preference owner.
A new project starts with actionable choices: select a dataset, open a workflow,
or inspect an existing result. Missing models offer an explicit installation
step with size and destination; opening a tab must not download weights.

Map legacy routes to the corresponding destination/tool and migrate saved
configuration by stable engine/field IDs, not combo-box indices. Keep old
configurations importable with a migration preview and clear unsupported fields.

## 3. Runs and resource management: the foundation

**Pain:** settings and artifacts are scattered, failures are hard to reproduce,
and independent GPU jobs can exhaust the laptop's resources.

Introduce a Qt-independent job service with GUI signal adapters. Each engine
publishes supported settings, progress phases, cancellation behavior, and
checkpoint/resume capability. Use supervised worker processes for heavyweight
model execution; a widget owns a subscription, not the computation.

A run record should contain a run ID and parent experiment, effective config,
dataset manifest/hash and split, input/output paths, model identifiers and
revisions, adapter weights, application/backend versions, seeds, device/precision,
workflow snapshot, event timestamps, exit reason, metrics, and user ratings.
Preserve both the ComfyUI editor workflow and executed API graph where available;
they are different representations. Imported results with incomplete metadata
must say **partial provenance**. A seed alone is not a reproducibility guarantee.

Persist artifacts and an append-only event journal in the selected project
folder; use PostgreSQL for searchable catalogue records, not SQLite. Folder
journals are recovery artifacts, not a competing settings database. Record an
output only after it is complete, and recover interrupted runs as interrupted.
Separate **clone settings**, **rerun**, and **resume checkpoint**: resume is only
available when the adapter can restore the required optimizer/scheduler/RNG state.

Default to one heavy job per GPU, shared by training, generation, captioning,
VLM review, and research analyses. Account for external GPU users and CPU RAM as
well. Show estimated demand as an estimate and actual peak demand after a run.
Expose balanced and conservative profiles with explicit settings; changing a
profile creates a recorded configuration change.

A stop request enters **Stopping** until the worker exits. A hung worker gets a
bounded shutdown path; no automatic retry loop for repeated OOMs. On restart,
reconcile live process identity and server prompt IDs before offering a retry,
so reconnecting does not submit the same job twice. Pause is advertised only at
boundaries the engine actually supports. Thermal telemetry may delay the next
job where available; never silently change system power settings.

Unload models at engine transitions and terminate disposable workers when idle.
Do not present `empty_cache()` as a general VRAM fix: it releases unused cached
blocks, not memory held by live tensors. See the [PyTorch CUDA memory notes](https://docs.pytorch.org/docs/stable/notes/cuda).
The tradeoff of isolation is model reload latency; an explicit warm-model policy
can follow measured stability, with a visible Unload action.

## 4. Embedded ComfyUI with a native wrapper

**Pain:** switching to an external browser breaks the relationship between the
workflow, queued run, outputs, and subsequent review.

Offer **Guided** and **Workflow canvas** views of Generate. Guided mode edits
known supported templates; the canvas embeds ComfyUI itself. Do not rebuild its
node editor. Switching modes must not silently overwrite unsaved graph edits.
For arbitrary graphs, show unsupported guided fields as read-only and keep the
canvas authoritative until a fresh snapshot has been captured.

Prototype `QWebEngineView` in the real application and packaged build, initially
behind a capability flag. Exercise Wayland/X11, high-DPI input, file upload,
WebSocket progress, server restart, GPU contention, navigation away/back, and
application shutdown. Measure startup time and RAM/VRAM against an external
browser baseline; importing WebEngine alone is not an acceptance test.

Keep server state separate from browser state: **Stopped / Starting / Ready /
Disconnected** versus **Loading / Displayed / Renderer failed**. A renderer
failure should offer reload without resubmitting a workflow. Qt exposes renderer
termination and navigation handling through [QWebEnginePage](https://doc.qt.io/qtforpython-6.8/PySide6/QtWebEngineCore/QWebEnginePage.html).

Use a dedicated profile, retain the browser sandbox, and scope navigation to the
configured server; external links open externally. Downloads/uploads have clear
local destinations. No general filesystem or shell bridge is needed. Custom-node
installation remains an explicit environment change, never a side effect of an
assistant recommendation.

Support **Start managed server** and **Connect to existing server**. Stop only
servers the app owns; disconnecting from an external server must not kill it.
Add capability discovery, completion/history reconciliation, and cancellation
through version-tested API adapters. Keep Open externally available if embedding
fails or is unavailable. Cost: another Chromium runtime, packaging complexity,
and browser/GPU memory overhead; unload the view only after preserving edits.

## 5. Training and dataset analysis

### Dataset workbench

Reuse the caption/tag tooling and `backend/src/core/similarity/` for duplicate
candidates and diversity exploration. Begin with deterministic checks: unreadable
files, dimensions, aspect ratios, missing captions, duplicate hashes, and split
leakage. For video-derived datasets, group related frames by source/scene before
splitting so adjacent frames do not inflate validation results.

Add caption editing, trigger-token consistency, tag-frequency charts, and an
embedding neighborhood browser. A sparse cluster is a review cue, not proof of
a missing pose or identity. Let users inspect examples and confirm semantic
labels. Show augmentation previews with matched captions; flipping text,
asymmetric character features, or directional labels may invalidate a sample.
Save changes as a dataset version rather than overwriting originals. Embedding
and caption jobs share the same compute queue as training.

### Training dashboard and controlled comparisons

Display loss, learning rate, validation metrics when supported, gradient norms
when instrumented, throughput, RAM/VRAM peaks, checkpoints, and fixed-prompt
sample grids. Distinguish raw and smoothed curves; show the smoothing setting.
Align comparisons by step, examples seen, or elapsed time. Keep missing metrics
explicitly unavailable, never zero. Reuse theme/chart infrastructure where it
fits, but existing bar charts alone do not supply interactive time series,
linked cursors, or large-history downsampling.

An **Experiment from this run** action freezes the dataset/split, base model,
prompt suite, and seeds, then varies one field. Show differences before queuing
and a paired output grid afterwards. Start with small manually defined sweeps;
require a run-count and resource estimate before launch. Observational history
can show associations, but should not claim that a hyperparameter caused an
improvement when other inputs changed. Repeated seeds and user ratings are more
useful than declaring a winner from one final loss value.

### Loss geometry: explicit research mode

Offer a one-dimensional checkpoint slice before a two-dimensional contour/surface.
For LoRA, begin in the trainable adapter parameter space with the base frozen;
record parameterization, normalization, directions, scales, checkpoint, evaluation
subset, and fixed diffusion noise/timesteps. Never mutate a live trainer to sample
the surface. A 21×21 grid requires 441 loss evaluations over the chosen subset,
so show cost, progress, cancellation, and cached results.

The [Li et al. loss-landscape work](https://arxiv.org/abs/1712.09913) motivates
normalized directions, but an adapter-space slice needs its own validation. Label
it as a slice, not the full loss landscape or a guarantee of generalization.
Prefer an exportable contour plot plus linked sample outputs to a decorative 3D
surface. Schedule this after useful training telemetry exists.

## 6. Assisted output review

**Pain:** “the text is wrong” or “the character looks different” does not tell
the user which workflow or dataset change to try.

1. Select an output and its run, or import an image and attach its workflow.
2. Mark a region and state the intended result. Provide quick feedback labels
   such as text accuracy, identity, composition, or unwanted artifacts.
3. Show evidence: OCR transcription with boxes and editable corrections, relevant
   workflow nodes, model/adapter metadata, and VLM observations kept separate
   from the user's own feedback.
4. Return at most three ranked experiments. Each includes the observation,
   proposed change, expected benefit, uncertainty, and a test that could disprove it.
5. Preview a config/workflow diff, then **Queue variant**. Compare the baseline
   and variant with synchronized pan/zoom, a slider or side-by-side mode, and
   optional blind A/B labels. Record the user's preference and reason.

A useful recommendation might propose testing a lower adapter weight when identity
or style is over-applied; it must reference the actual installed node and current
value. It should not assert that a single image proves overtraining. OCR should
show detected and requested text separately; uncertain transcription needs review.

Structured suggestions should carry `run_id`, workflow hash, evidence references,
node ID, input name, expected old value, proposed value, reason, and validation
status. Validate node/input existence, types, ranges, links, installed assets,
and base-model compatibility. Recheck the workflow hash before applying; reject
stale patches rather than modifying a graph the user has since edited. Do not
use the manager's permissive `apply_overrides()` as the validation boundary.

Treat prompts, captions, workflow metadata, and OCR text as untrusted content;
they cannot authorize tools, scripts, downloads, or filesystem changes. A model
swap can only select an installed compatible asset or create an explicit proposed
installation. Missing workflow metadata yields limited advice, not invented
parameters. Local/cloud analysis is an explicit user choice with a preview of
what leaves the machine; credentials stay in VaultManager. Local VLM inference
must wait for GPU availability rather than compete with the generator.

Dataset advice links back to a proposed Prepare change set and examples to review.
No automatic retraining or recursive optimization loop in the initial release.
The main tradeoff is slower, testable advice instead of unrestricted automation.

## 7. Proposed delivery gates

| Stage | Deliverable | Acceptance evidence |
|---|---|---|
| A — correctness and feasibility | Effective-config audit, model identity cleanup, job contract, embedded-browser spike | Every exposed control maps to execution; no worker-thread widget mutations; browser render/reconnect/close works in the real app and package. |
| B — first usable workspace | Routes, Prepare basics, Train/Generate adapters, run history, queue, embedded canvas | One small dataset-to-training-to-generation-to-review journey; old configs migrate; cancel/crash recovery retains artifacts and does not duplicate submissions. |
| C — useful analysis | Curves, checkpoint grids, configuration diffs, bounded sweeps, OCR and regional feedback | Comparisons preserve inputs; missing data is explicit; large histories remain responsive. |
| D — assisted experiments | Schema-validated VLM/LLM suggestions and approval/diff UI | Invalid and stale patches rejected; recommendations evaluated against a fixed set of human-reviewed cases, with abstention recorded. |
| E — research extras | Adapter loss slices, richer augmentation analysis, optional warm workers | Cost measured on target hardware; numerical repeatability checked; research output clearly labelled. |

Tests should cover adapter settings, lifecycle transitions, workflow validation,
provenance, and migration with small fixtures. Live checks must cover navigation
during work, cancellation, low resources, ComfyUI disconnection, renderer failure,
and restart recovery. Full suites and corpus runs still follow the repository's
Codex/Harbinger resource authorization rule. None were launched for this proposal.

Decisions for proposal selection: adopt the six destinations or a more compact
rail; choose the supported packaged-server connection story; decide whether cloud
analysis belongs in the first release; select the first trainer/generator pair
for the complete journey. Specific new model providers and automatic optimization
should remain later decisions, after this foundation is demonstrated.
