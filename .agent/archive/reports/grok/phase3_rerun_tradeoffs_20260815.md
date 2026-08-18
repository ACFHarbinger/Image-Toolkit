# Phase 3 — Rerun vs OTel vs native inspector (trade-offs)

**Date:** 2026-08-15  
**Agent:** Grok  
**Ask:** Claude's Phase 3 feasibility scope. Harbinger asked for the
trade-off analysis *before* locking an architecture. No implementation.

**Locked (Harbinger, 2026-08-15):** **A+B**. Opt-in Rerun `.rrd` sidecar
plus OTel spans/metrics, behind a `TelemetrySink` on `PipelineSession`.
**C** (native JSON/NPZ inspector in M6/`/journal`) is a fully optional
roadmap entry — not scheduled, not low-priority, not a blocker. **D**
(Rerun WASM in `docs/website`) is rejected.

## What Phase 3 actually wants logged

From `analytics_and_interpretability.md` §3 and the Q3 roadmap:

| Entity | Natural home after M1 | Size / rate |
|---|---|---|
| BA camera poses / (pseudo) Points3D | `_bundle_adjust_affine` output + `PipelineSession` artifacts | tiny (N×2×3 affines; anime pans are 2D) |
| LoFTR match residual heatmaps | `_pairwise_match` edges + optional dense residual maps | medium–large (per pair) |
| Seam FFT / Sobel / cost corridor | `_seam_freq_profile`, graph-cut cost maps | medium (per overlap) |
| Stage timings, VRAM peak, gain-clamp residual, seam energy | already named as OTel metrics in roadmap §19 | tiny |

Important geometric honesty: ASP's current BA is a **2D affine / translation
chain**, not a calibrated pinhole reconstruction. Logging `Transform3D` +
`Pinhole` + `Points3D` is a *visualization metaphor* (cameras on a plane,
inliers as 2D points lifted to z=0). It is not COLMAP. The report and any
viewer caption must say that, or we will teach the wrong mental model.

## The four options, scored

### A — Opt-in `.rrd` sidecar only

`rerun-sdk` is a `desktop_quality` extra. A `RerunSink` adapter on
`PipelineSession` (post-M1) writes poses, match lines, and seam tensors to
`run.rrd`. Open in the native Rerun viewer. No website embed. Not on
`laptop_balanced`.

| | |
|---|---|
| **For** | Purpose-built for this data. Zero change to the shipped laptop profile. Matches the earlier "Rerun is never a required package" lock. Smallest implementation. |
| **Against** | Second app to install. Not the journal/M6 surface Gemini is building. Easy to rot if nobody on the team actually opens `.rrd` files. |
| **Cost** | ~1–2 days for a sink + three log sites once M1a session exists. `rerun-sdk` is a heavy binary wheel (native viewer + arrow). Do not add it to the base extra. |
| **Perf** | Logging affines is free. Dense LoFTR residual tensors and full-res seam cost maps are the tax — downsample or log on `desktop_quality` only. |

### B — Rerun + OTel dual-write

Same as A for spatial CV, plus the §19 spans/metrics
(`stage_duration`, `vram_peak_bytes`, `gain_clamp_residual`,
`seam_cut_energy`) on a single `Telemetry.emit(...)` façade.

| | |
|---|---|
| **For** | Right split: Rerun is bad at fleet anomaly queries; OTel/Prometheus/Honeycomb-style BubbleUp is bad at "show me this seam FFT." One emission API, two backends. |
| **Against** | Two new dependencies, two failure modes, two things to keep in version lockstep. OTel without a collector is just JSON files with extra ceremony. |
| **Cost** | A plus ~1 day for a thin OTel meter/tracer wrapper. Collector/Grafana is **not** in-repo ops — emit to a local OTLP file or stdout until someone actually runs a collector. |
| **Perf** | Metrics are free. Spans around CUDA stages must not synchronize the device just to timestamp. |

### C — Skip Rerun, native inspector first

Dump the same entities as JSON / NPZ / PNG next to `last_session` and
render them in the M6 / `/journal` widgets already committed (diff loupe,
pose scrubber, 3D layer stack). Rerun becomes an optional *importer* later
if someone wants the desktop viewer.

| | |
|---|---|
| **For** | No new native dependency. Same artifacts feed the public Lab Notes and the artist review screen. Avoids building a viewer nobody but us can open. Honest about the 2D-affine-not-pinhole issue (we control the caption). |
| **Against** | We re-implement a worse Rerun for spatial scrubbing. Match-line and residual-heatmap widgets are real work. Easy to under-build and call it done. |
| **Cost** | Higher calendar time than A, but it is work Gemini/M6 already owe. Incremental if `PipelineSession.artifacts` already holds paths. |
| **Perf** | We choose the resolution. No WASM download on the marketing site. |

### D — Full Phase 3 as written (Rerun WASM in `docs/website`)

`rerun-sdk` + embed the Rerun WebAssembly viewer, stream `.rrd` over the
network.

| | |
|---|---|
| **For** | Closest to the written Phase 3. Impressive. One viewer for local and web. |
| **Against** | Supply-chain and binary-size hit on `docs/website`. WASM viewer is a product, not a widget — fights the Optic Lab / Distill article surface. `laptop_balanced` must still not require it; easy to "just add it to the site build." Streaming `.rrd` of residual tensors is a bandwidth foot-gun. Caption risk: pinhole gizmos on a 2D stitch. |
| **Cost** | Highest. Also the option most likely to leak corpus frames into a public static host if we are sloppy about which `.rrd` is committed. |
| **Perf** | Worst default. Only defensible for a *local* `desktop_quality` debug build, not the GitHub Pages journal. |

## Integration points (architecture-independent)

These are the same three call sites no matter which viewer wins. That is
why this work is **behind M1 / M2.5a**, not ahead of them.

1. **`PipelineSession`** — already landed (M1a). Add an optional
   `TelemetrySink` protocol: `on_stage`, `on_artifact`, `on_tensor(name,
   array, meta)`. Rerun, OTel, and a JSON/NPZ sink all implement it.
   Do not import `rerun` from `run_stage.py`.
2. **`_bundle_adjust_affine` / Stage 7** — log the 2×3 affines as a
   polyline of camera origins on the canvas plane. Optional: lift
   inlier matches to `z=0` points. Label: "2D canvas, not a 3D reconstruct."
3. **`_pairwise_match` / Stage 5–6** — log sparse match lines always;
   dense residual heatmaps only when `desktop_quality` or an explicit
   `ASP_TELEMETRY_DENSE=1`.
4. **`_seam_freq_profile` / composite** — log the 1D FFT + a downsampled
   cost-map PNG. Full-res cost tensors stay on disk, not in the session
   digest.

Parent `backend_dispatch.py` stays thin: pass `telemetry_sink=` through
when the canonical API grows.

## Dependency and profile rules (already locked, restated)

- `rerun-sdk` is never a `laptop_balanced` required package.
- Dense tensors are opt-in.
- No third-party frames inside a committed `.rrd` / NPZ that
  `docs/website` can serve.
- Telemetry must not change pixels. Sinks observe `PipelineSession`; they
  do not sit on the image path.

## Locked decision (Harbinger, 2026-08-15): A+B

Implement, in this order, after M1 adapters exist (M2.5a may start the
analytics half in parallel):

1. `TelemetrySink` protocol on `PipelineSession` — `on_stage`,
   `on_artifact`, `on_tensor(name, array, meta)`. `run_stage.py` must not
   import `rerun` or `opentelemetry`.
2. **A — `RerunSink`:** write `run.rrd` when a `desktop_quality` extra /
   explicit flag is on. Desktop Rerun viewer only. Caption every
   `Transform3D` / `Points3D` view as a 2D-canvas metaphor, not a pinhole
   reconstruct.
3. **B — `OtelSink`:** spans + the four named metrics
   (`asp.stage.duration_ms`, `asp.vram.peak_bytes`,
   `asp.gain.clamp_residual`, `asp.seam.cut_energy`). First backend is
   local OTLP file or stdout. A collector/Grafana/Honeycomb is optional
   ops, not an in-repo deliverable.

**C is fully optional.** A native JSON/NPZ/PNG inspector that re-implements
Rerun's spatial scrubbing inside M6 / `/journal` is recorded as an
unscheduled extra. It does not sit on the M2.5 / M6 issue list, does not
get a priority, and does not block A+B or outreach Distill widgets (those
widgets keep using approved derived assets, which is a different surface).

**D stays rejected.** Do not embed the Rerun WASM viewer in
`docs/website`. Do not add `rerun-sdk` to `laptop_balanced` or to the
website package.

No code in this pass.
