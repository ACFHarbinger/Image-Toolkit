# #739 / #740 — Generate surface and matrix sweeps

Branch `dl-c-739-generate-surface`, stacked on `dl-c-738-preflight-validation` (`4ed6f9e5`).

- `GenerateSurface` is `ml.comfyui` and the workspace Generate → Comfy page. Guided | Graph | Matrix share one filmstrip fed by `run_record_changed`.
- Graph stays external-only. The draft is not written on mode switch. Loading a run into a dirty draft is refused and the error is shown.
- `apply_overrides` / `apply_node_overrides` raise `UnknownWorkflowNodeError`. The graph override field shows that text.
- Run records keep `surface_mode`, `template_name`, `applied_overrides`, and sweep parent/axis/value across history updates. `output_paths` is the captured filenames.
- Matrix: one axis, 3–9 values, cap 25, preview 512px, one `GpuLease`, stop-between-cells, CUDA free-memory floor 0.15. Promote re-queues that cell at the guided width and height.

Targeted checks only (backend matrix/override/provenance tests, `test_generate_surface.py`, `test_comfy_generate_tab.py`, the workspace generate-page test). No suite or benchmark.

— Grok, 2026-10-12
