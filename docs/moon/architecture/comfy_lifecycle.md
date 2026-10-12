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
