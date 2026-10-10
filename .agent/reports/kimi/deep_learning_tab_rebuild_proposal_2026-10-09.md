# Deep Learning Tab Rebuild — Kimi's Proposal

Companion to `.agent/reports/team/deep_learning_tab_rebuild_2026-10-09.md`.
Proposal only; nothing here is approved to build. I read the bus thread, the
team brief, and the seven proposals already in (Claude, Codex, Mistral, Grok,
Gemini, Cursor, Muse), and re-verified the load-bearing claims in this checkout
myself. Where I agree — task-grouped second `ModuleCatalog` workspace behind an
experimental pref, spike-first embedded ComfyUI, wiring-before-building on
diagnostics, schema-validated guidance, honest controls — I say so in one line
and move on.

My contribution is five concrete additions nobody else proposed, all built on
data or components the repo already has, plus two micro-findings that sharpen
existing consensus items.

## 0. What I verified in this checkout (not live-run)

| Claim | Evidence | Consequence |
|---|---|---|
| LyCORIS Hydra command drops epochs/batch/LR/rank | `gui/src/tabs/models/delta/lora_train_tab.py:337-347` forwards only `model_id`, `images_dir`, `trigger_word`, `output_dir` | Confirms Codex/Grok; controls must forward or disable with reason. |
| Packaged-build LyCORIS refusal arrives **after** Start | `lora_train_tab.py:328-336` — the `sys.frozen` check runs inside the launch handler | Grok's capability-card "disabled reason" is the right fix; verified real. |
| `set_config()` silently retargets renamed combos | `gui/src/classes/base/base_generative_tab.py:37` persists `currentText()`; restore does `findText()` and **fails silently**, leaving index 0 | Cursor found persistence-by-label; the silent-index-0 fallback is the dangerous half — a renamed label silently loads the *wrong engine's* config. |
| Native file dialog on a known crash path | `gui/src/tabs/models/gen/comfy_generate_tab.py:367-369` (`_on_browse_image`) uses `QFileDialog` without `DontUseNativeDialog`; the safetensors inspector in the *same* train tab sets it | One-line drive-by fix. |
| `training_hooks.py` diagnostics exist, unwired | `DiagnosticsLogger` (`log_step`, `log_grad_norm`, `log_sample_grid`), `CrossAttnRecorder`, `lora_effective_rank`, `lora_delta_heatmap` all present | Confirms Mistral: pillar 3 starts with wiring. |
| Pillar 4 is fully greenfield | grep for tesseract/easyocr/paddleocr/manga-ocr/ollama/vllm over `backend/src` + `gui/src`: zero hits | Provider choice is a real blank slate, as Claude/Codex said. |
| The app already owns a tag vocabulary | `backend/src/database/unified/tag_repo.py` (`get_all_tags_with_categories`), `image_tags` table (`schema.sql:219`), `HybridCaptioner` with WD14 + Florence-2 and per-base-model `MODEL_PREFIXES` (`backend/src/models/data/captioner.py:240`) | Prompt tooling can be built on existing data — nobody proposed this. |
| No provenance or validation HTTP yet | `backend/src/models/core/comfy_manager.py` has `load_workflow`/`apply_overrides`/`upload_image`/`queue_workflow` but no `/history`, no `/object_info` | Both the provenance capture (Mistral/Cursor) and my pre-flight validation start from the same manager additions. |
| Guided-template surface is tiny | `configs/comfy_workflows/` holds exactly 2 templates | Validating guided modes against the live server is cheap and CI-fixture-able. |

## 1. Pillar 1 — UI/UX additions

### 1.1 Linked-cursor loss curve ↔ checkpoint filmstrip

A loss curve the user can scrub: cursor at step *s* shows the nearest
checkpoint ≤ *s* and its fixed-seed sample grid in the filmstrip. Today even a
wired curve is a picture; this makes "when did it collapse / when did it stop
improving" navigable. Implementation is a mouse-move handler mapping
x→step→checkpoint index on the polyline panel (Grok/Cursor consensus panel) —
no new widgets. Cost: near zero. Delight: high.

### 1.2 `PromptEdit` — one shared prompt component, vocabulary from the app's own data

Today prompt fields are bare `QLineEdit`s duplicated across four forms, while
the app owns a ranked tag corpus and captioning knowledge nobody surfaces at
generation time. One `QPlainTextEdit` subclass in `gui/src/components/`,
used by guided Generate and the guidance-loop feedback box:

- **Tag autocomplete** from `tag_repo` + `image_tags` frequency, with category
  icons; falls back to the canonical WD14 list when the library is empty.
- **Trigger-token chips**: dropdown of trigger words mined from run records
  (runs already store `trigger_word`) — "insert the LoRA I just trained" in
  two clicks, no typo'd activation tokens.
- **Token meter**: per-encoder counts for SDXL (CLIP-L + OpenCLIP-G) with the
  75-token boundary marked; warn instead of silently truncating.
- **Base-model prefix chip**: `HybridCaptioner.MODEL_PREFIXES` surfaced as an
  insertable chip that follows the selected checkpoint (`illustrious` →
  `masterpiece, best quality, absurdres`, …).
- **Train-time negative preset**: the negative prompt recorded on the trained
  run offered as the default for that LoRA — train/generate consistency, the
  most common silent character-drift footgun.

Tradeoffs: autocomplete queries debounced and off the GUI thread; vocabulary
staleness is acceptable (booru tags churn slowly). This component is also the
natural home for the guidance loop's "append to negative" patches (Gemini's
schema already emits them) — Apply writes into `PromptEdit`, not the graph
blindly.

### 1.3 Pre-flight validation for guided Comfy modes — "Queue" earns its enabled state

Grok's "failures arrive after Start" pain exists on the generation side too:
Queue is enabled whenever the server runs, and a missing checkpoint,
ControlNet file, or renamed node type fails *inside* ComfyUI after upload.

- `ComfyUIManager.validate_template(template) -> list[TemplateIssue]`: node
  types/inputs checked against `GET /object_info`; input files (`ckpt_name`,
  `control_net_name`, `ipadapter_file`) checked under the model folders
  beneath `COMFYUI_DIR`.
- Mode-combo rows get status: ready / missing node "X" (ComfyUI revision too
  old/new) / missing file "Y". Queue disabled per mode with the reason written
  out — capability honesty (Grok) applied to the Comfy surface.
- Validate once at server-ready, cache, invalidate on restart. With 2
  templates this is small, and CI-testable against an `/object_info` recording
  pinned to the vendored `vendor/ComfyUI` submodule revision.

### 1.4 Two drive-by correctness fixes

- `collect()`/`set_config()`: persist `itemData` + a config schema version; on
  restore, an unknown id keeps the engine default and shows a one-line
  migration note instead of silently falling back to index 0 (§0 row 3).
- `DontUseNativeDialog` on `comfy_generate_tab.py:367` (§0 row 4).

### 1.5 Visual / a11y micro-spec (short)

- Charts: categorical palette extended to 8 colorblind-safe slots from theme
  tokens; status never color-only — same rule for run-status chips (Codex's
  bar, applied consistently).
- Density: forms live in the inspector, but Train's live panel and Review's
  canvas stay image-first at ≥60% width down to 1280×800.
- Numbers: one formatting convention everywhere (loss at 4 sig figs, LR in
  scientific notation, VRAM in GiB) across charts, tables, and the
  effective-config sheet.

## 2. Pillar 2 — embedded ComfyUI

Endorse spike-first (Claude) with Cursor's packaging/docs gate and Muse's
explicit pass criteria; keep the `QWebChannel` bridge (Gemini) sequenced
*after* provenance and pop-out (Cursor/Muse). One addition: ship §1.3's
server-readiness validation in the same milestone as the spike — it uses the
same `/object_info` fetch a robust embed needs for health-checking, and it
makes Guided mode honest before the embedded view lands. If the spike fails,
Guided + validation + external button is still a coherent, trustworthy
surface.

## 3. Pillar 3 — training analysis additions

### 3.1 Checkpoint tournament (the piece I most want built)

**Pain:** after a LoRA run you get N checkpoints and zero guidance on which to
keep. Users eyeball folders or hand-build comparison grids.

- The inputs already exist: once `DiagnosticsLogger` is wired (Mistral),
  `log_sample_grid` produces fixed-prompt, fixed-seed grids per checkpoint.
- **UI:** "Start tournament" on a finished run → pairs of checkpoint grids
  shown *blind* (ids hidden) through the existing `ImageCompareWindow`
  (synced pan/zoom — Cursor's reuse, not a new canvas) → pick left/right/skip
  → ELO table with uncertainty on the run → "Promote winner" sets Generate's
  adapter and records provenance.
- **Fatigue cap:** ~12 comparisons per sitting, resumable, ties allowed; the
  UI states ELO needs ~10+ pairs before it means anything.
- **Why it matters beyond checkpoint picking:** the tournament outcome is a
  *measured preference signal*. Fed into the guidance loop (§4.1), it grounds
  advice like "checkpoint 6 wins blind while effective rank saturates at 9/64
  — try rank 16" — the loop citing evidence instead of one-image vibes.

### 3.2 Matrix mode — X/Y sweeps on the Generate surface

The generation-side counterpart to the training sweeps (Claude/Codex cover
training only). Pick one axis (seed / CFG / steps / LoRA weight / ControlNet
strength) × 3–9 values; queue all cells against one parent run; results land
as a grid in the filmstrip (each cell = a `prompt_id` from `/history`).

- UI: two axis pickers + value editor, cost estimate and cell cap before
  queue (Codex's resource-estimate discipline), grid layout in the filmstrip,
  "promote cell to run" (clones config at full res).
- Backend: a loop over the existing `queue_workflow()` with one input varied
  — no new execution machinery.
- Tradeoff: queue/VRAM explosion — cap cells (e.g. 25), one GPU lease,
  stop-between-cells under thermal/VRAM pressure.

### 3.3 Chart rendering hardening

For long runs: min/max-bucketed polyline downsampling (keeps spikes visible
at any zoom level; trivially simpler than LTTB and sufficient here) with
zoom-window refetch from the JSONL. 10k-step LoRA runs are normal; pushing
every point through a QPainter path is wasted work. Comparisons align by step
per Codex.

## 4. Pillar 4 — guidance loop additions

Endorse the versioned schema + two validators (Claude/Mistral/Muse) and the
fixture pack over `configs/comfy_workflows/` (Mistral). Three additions:

1. **Evidence-traced suggestions.** Extend the schema with `evidence[]`
   entries referencing real artifact ids (`run_id`, checkpoint index, dataset
   finding id, tournament result). The UI renders each suggestion's evidence
   as clickable chips — the user can inspect the *measured signal* behind a
   recommendation before applying it. This is Mistral's "ground advice in
   measured signals" made visible and mandatory, and it composes with §3.1.
2. **Abstention as a first-class output.** The schema permits
   `{"diagnosis": ..., "patches": [], "needs": ["more hand-angle variety"]}`
   — rendered as "insufficient evidence; capture these," routed to Train's
   dataset panel as a prefiltered pick-list (via the existing
   `ImportPathsIntent` handoff). Dead-ends become dataset guidance instead of
   forced parameter guesses (extends Codex's abstention point into the UI).
3. **Upscale handoff (small).** "Send to Upscale" on any output →
   `ESRGANWrapper` (exists, unwired — `backend/src/models/wrappers/esrgan_wrapper.py:137`)
   through the shared job adapter; result lands in the same run's filmstrip.
   Not part of the loop; just ends the copy-paste dance. (Note: fixes a gap
   Cursor flagged as evidence but no proposal claimed.)

## 5. Sequencing, slotted into the consensus gates

1. **Gate A (correctness):** §1.4 drive-bys + LyCORIS forwarding/disable
   (Codex/Grok). Hours, not weeks.
2. **Gate B (workspace):** shell + `PromptEdit` (§1.2 — vocabulary already
   in the DB) + pre-flight validation (§1.3 — needs `/object_info` in the
   manager, same fetch the embed health-check wants).
3. **Gate C (analysis):** diagnostics wiring + JSONL (Mistral) → linked
   scrubber (§1.1) + chart hardening (§3.3) → matrix mode (§3.2) →
   tournament (§3.1).
4. **Gate D (guidance):** schema + validators + fixtures → evidence chips
   (§4.1) + abstention routing (§4.2). Loss slices / Hutchinson stay the
   explicit-research tail (Mistral/Gemini/Codex).

## 6. Top risks

- **Autocomplete skew:** `image_tags` frequency reflects the library's
  content; mitigate with the WD14 canonical fallback. Acceptable.
- **Tournament fatigue/meaningfulness:** cap, resume, allow ties; show ELO
  uncertainty until ~10+ pairs.
- **Matrix queue abuse:** cell cap + cost estimate + queue-depth check.
- **`/object_info` drift vs. vendored ComfyUI rev:** fixture pinned to the
  submodule; re-record on bump (CI check).
- Overall blast radius is small: everything here reuses shipped components
  (`ImageCompareWindow`, `tag_repo`, `HybridCaptioner` knowledge, the
  manager's HTTP layer). The largest genuinely new surfaces are `PromptEdit`
  and the tournament view.

— Kimi, 2026-10-09
