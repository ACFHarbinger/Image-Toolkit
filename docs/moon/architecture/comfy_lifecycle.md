# ComfyUI lifecycle (#736)

The shipped tier is **external-only**, following #729. No WebEngine view,
profile, pop-out window or WebChannel is created. A future embedded tier
must pass #729's filter, GPU-load, frozen-build and repeated-launch checks
before adding a dedicated localhost-scoped profile and registered window.

ComfyWorkspaceController.instance() is the shared coordinator for the
legacy ComfyUI tab and #739's Guided/Graph surface. Navigation and tab close
leave the service running. Application shutdown cancels pending startup
and stops only the process the manager launched.

| State machine | States | Source |
|---|---|---|
| Server | Stopped → Starting → Ready; failures → Disconnected | ComfyUIManager callbacks, forwarded as server_state_changed |
| View | NotCreated, Loading, Displayed, RendererFailed | Separate view_state_changed signal; external-only stays NotCreated |

Opening the system browser does not prove a page loaded, so it emits
browser_opened(url) without claiming Displayed. Browser-launch failure
does not restart or disconnect a healthy server.

## Actions

- **Start Server** launches the checkout's ComfyUI on loopback and probes
  /system_stats off the UI thread. If the requested port is occupied, an
  available port is selected and shown.
- **Connect Existing** probes the selected loopback port and acquires no
  process ownership. **Disconnect** leaves that server running.
- **Stop Server** terminates only the manager's stored subprocess.
- **Open in External Browser** remains visible, enabled when Ready.
- Disconnected services are probed periodically; reconnecting does not
  create or rebuild a view.

Lifecycle and workflow HTTP operations are serialized by the controller.
Stop cancels a pending readiness wait; network operations have finite
timeouts. Workers are retained until actual thread completion. Log stdout
is drained independently of the tab and displayed with a bounded history.

For #737, provenance polling stays in the manager and is independent of
browser state. For #739, reuse this coordinator rather than launching a
second server or tying stop() to a disposable destination page.

## Run provenance (#737)

Capture is a manager-side poller with no view coupling: whenever the
server is Ready, `/queue` and `/history?max_items=64` are polled off the
GUI thread and diffed by prompt id into bounded run records (executed
API-format graph, client id, outputs, terminal status, partial flag).
Any state change away from Ready stops the poller; records survive and
capture resumes on the next Ready without duplicating known ids. Runs the
user drives from an external browser are captured exactly like app-queued
runs, because both are only HTTP history.

- First successful poll baselines: the newest `BASELINE_RECORD_LIMIT`
  (32) history entries become records; older ids are marked seen and
  never re-emitted.
- `queue_workflow()` creates an optimistic Pending record immediately;
  the server-echoed graph from history is the provenance truth.
- A queued id that leaves the queue without ever reaching history closes
  as Interrupted with `partial=True` after a two-poll grace period.
- `subscribe_runs(listener)` is invoked on every record create/update
  from a worker thread — GUI consumers must marshal (the workspace
  controller forwards to `run_record_changed` for #739/#752).
- `get_run(prompt_id)` / `runs()` read captured records at any time,
  including after Stop.

## Pre-flight validation (#738)

`ComfyUIManager.validate_template(template)` checks a curated workflow
before Queue: node `class_type`s and their inputs are verified against
`GET /object_info`, and model-file inputs (`ckpt_name`,
`control_net_name`, `ipadapter_file`, …) are verified against the
server's file choice lists. A caller may supply `models_root` for local
fallback checks off the GUI thread. Attached servers may use another
installation or extra model paths; GUI validation never scans local disk.

`/object_info` is the expensive half, so the manager fetches it on a
worker thread at Ready, caches it until the server leaves Ready, and
notifies `subscribe_object_info` listeners — a `None` argument after
retries means unavailable and callers fail open. The controller forwards
this as `object_info_changed`. Queue buttons validate `build_workflow(mode, …)`
per guided mode on that signal, cache the issues per mode, and stay
disabled showing the first `TemplateIssue` while any issue is present;
checkpoint field edits revalidate. Tests validate against a recorded
`/object_info` pinned to the vendored `vendor/ComfyUI` revision
(`middleware/test/fixtures/comfy_object_info.json`; re-record on bump).

## Generate surface (#739, #740)

`GenerateSurface` is the Comfy tab (`ml.comfyui`) and the workspace
Generate destination's Comfy page. A Guided | Graph | Matrix switch sits
above one filmstrip. Guided is `build_workflow()` / `plan_guided_workflow()`.
Graph does not embed WebEngine: **Open in External Browser** is the
canvas, and a local JSON draft plus a node-override field queue through
the same `/prompt` path. Switching modes does not write the draft.
`GraphDraft.replace_text` refuses while the draft is dirty, so loading a
selected run cannot silently drop unsaved edits.

`ComfyUIManager.apply_overrides` raises `UnknownWorkflowNodeError` for
unknown node ids. The graph pane shows that message on the override
field. Run records carry `surface_mode`, `template_name`, and
`applied_overrides` (the map that was merged). History updates keep
those fields. `output_paths` is the captured filenames. The filmstrip
listens to `run_record_changed`.

Matrix mode picks one axis (seed, CFG, steps, LoRA weight, ControlNet
strength) and 3–9 values, hard-capped at 25. An axis stays disabled
unless the swept workflow contains its node. The guided LoRA mode uses
`configs/comfy_workflows/lora_generate.json` (`LoraLoader` strength_model).
**Sweep the graph draft** uses the external-graph JSON instead, so a
loaded LoRA graph is reachable without the template. `run_matrix_sweep`
loops `queue_workflow` and waits for terminal `/history/{prompt_id}` after
each submission. Failed, deleted, or disconnected jobs stop the sweep.
Cells share `parent_prompt_id` (the first prompt) and render at 512px.
Stop between cells is a flag checked before every cell, including the
first. The same gate stops on VRAM pressure (CUDA free memory under 15%;
CPU-only sessions are not pressure) or thermal pressure (GPU temperature
at or above 85C; a missing sensor is not pressure). **Promote cell to
run** clones the selected workflow at the guided width and height and
queues that single prompt with `surface_mode="promoted"`.

`GpuLease` / `gpu_lease` is in-process admission shared by Comfy
guided, graph, matrix, and promote submissions and by LoRA training,
LoRA generation, GAN training, and CBIR training. `machine_wide` is
false: opening the system browser notes an external session, and that
queue is not observable. The filmstrip is a scrollable strip plus a
scrollable matrix grid. Output thumbnails are fetched from Comfy `/view`
on a worker thread, capped at 2MB and at the 200-record retention.
Shutdown or disconnection stops waiting without interrupting an external
server's job.
