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
