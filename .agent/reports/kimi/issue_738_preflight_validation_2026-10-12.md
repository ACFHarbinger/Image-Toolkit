# #738 — Pre-flight workflow validation (Gate C.3)

Delivered as draft PR #771, commit `4ed6f9e5`, branch
`dl-c-738-preflight-validation`, worktree `~/Downloads/Data/Tests/dl-c-738`.
Stacked on `dl-c-737-history-provenance` (#770, `8d10e97e`) like Mistral
stacked on #769; retarget to `main` after #769/#770 merge. Single-commit
diff against the current base.

## What shipped

- `backend/src/models/core/comfy_validation.py` (new, pure):
  `validate_template(template, object_info, *, models_root)` —
  - node `class_type` vs `/object_info` keys (`missing_node`);
  - template inputs must cover the class's `required` set and stay within
    `required|optional|hidden` (`missing_input` / `unknown_input`);
  - model-file inputs (`MODEL_FILE_FOLDERS`: ckpt_name, control_net_name,
    ipadapter_file, vae_name, lora_name, clip_name, unet_name, …) resolved
    against the server's choice list when the spec declares one, else
    against the folders under `COMFYUI_DIR/models` (recursive posix
    relative listing, mirroring `folder_paths.get_filename_list`).
- `ComfyUIManager`: `/object_info` fetched on a worker thread at Ready
  (`comfy-object-info`), cached until the server leaves Ready, cleared on
  stop/disconnect/restart; `subscribe_object_info` listener (worker
  thread; `None` after 3 retries = fail open), `get_object_info()`,
  `validate_template()` (raises RuntimeError when no cache; tests can pass
  a recording via `object_info=`).
- `ComfyWorkspaceController`: `object_info_changed` Signal forward,
  getattr-guarded like #737's `subscribe_runs`.
- `ComfyUITab`: Queue button per guided mode — `Checking workflow
  compatibility…` while the warmup is in flight, `Ready`, or disabled with
  the first `TemplateIssue` (`+N more`, full list in tooltip). Per-mode
  issue cache; base-checkpoint edit revalidates all modes, extra-checkpoint
  edit only the current mode, mode switch revalidates with mode defaults;
  cache cleared on leaving Ready; Queue click with cached issues logs and
  refuses. Fail-open when `/object_info` never answers (log line, button
  enabled) — blocking generation on a validation hiccup is worse than the
  status quo it replaces.
- `backend/test/fixtures/comfy_object_info.json`: recording pinned to
  vendored ComfyUI `0ea188c6` (core classes per the fork's `nodes.py`
  INPUT_TYPES) + ComfyUI_IPAdapter_plus classes (`IPAdapterModelLoader`,
  `IPAdapterAdvanced`) the ipadapter template needs; re-record on bump.
- Contract doc `docs/moon/architecture/comfy_lifecycle.md` §Pre-flight
  validation (#738) — named integration surface for #739.

## Design notes / evidence

- File-folder mapping is per input name, not per node class, because the
  vendored `folder_paths.py` at `0ea188c6` has no `ipadapter` folder (the
  IPAdapter pack registers it) and `clip_name` means `clip_vision` for
  `CLIPVisionLoader` but `text_encoders`/`clip` for `CLIPLoader` — union
  check covers both.
- `LoadImage.image` / `SaveImage.filename_prefix` are deliberately not in
  `MODEL_FILE_FOLDERS`: the image is uploaded at queue time and the prefix
  is free text. Enum widgets (sampler_name etc.) are not file-checked.
- When the server declares a choice list it is authoritative and the
  local listing is skipped (`continue`) — avoids false positives against
  Connect-Existing servers using `extra_model_paths.yaml`.
- Warmup race (fetch in flight while state leaves Ready) covered by a real
  test: stop event re-checked under `_object_info_lock` before storing.

## Validation

- 16 new backend tests (`test_comfy_preflight.py`): both shipped
  templates clean against the recording; missing node/input/file; local
  fallback incl. nested subdirs; offline models-root-only mode; manager
  cache lifecycle via live stdlib HTTP stub; listener `None` on fetch
  failure; warmup/state-change race.
- 9 new GUI tests in `test_comfy_generate_tab.py`; controller test's fake
  `Manager` grew `subscribe_object_info`/`get_object_info`/
  `validate_template` (tab calls them at Ready).
- Targeted only: 52 passed `backend/test/models/test_comfy_*.py`,
  33 passed comfy GUI/controller tests with `--run-gui`; ruff/py_compile
  clean. No suite/benchmark/GPU run.
