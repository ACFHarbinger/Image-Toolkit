# Backlog re-review — 2026-10-14

Reviewed Gemini `3628e37e8` (#794), Cursor `8e87562ab` / `fcaf4a4e1` (#797), and Mistral's local `140cc19a5` / `bbf5efc53` on `dl-756-gpu-validation`. Kimi #796 remains `e529afaf7`; no new implementation to re-review.

## Findings and edits

- **Gemini:** Asynchronous upload results could overwrite a newer image selection or mode, or arrive after closing the tab. Added request invalidation and QObject-bound result/error slots. Unknown graph image tokens previously went through the local-file upload path on queue; retain observed server tokens and reuse them. Only known server tokens may be sent directly; missing local paths are not tokens. Added regressions. Explicit view deletion resolves the previously reproduced combined-test teardown crash in this run.
- **Gemini validation limit:** The new HTTP/WebEngine fixture serves a mock graph, not an installed ComfyUI frontend. Its upload endpoint is not exercised by that fixture. Renamed the test to make its scope clear. Real frontend/upload compatibility remains unverified.
- **Cursor:** Production admission calls now provide estimates. Fixed ignored latent batch size and the assumption that tiled ESRGAN holds no full image on GPU: its implementation moves the entire fp32 RGB input to the device. These formulas are uncalibrated, use fp16 weight assumptions despite some fp32 loaders, map Flux/SD3 to SDXL, and omit custom-node/ControlNet costs. Conservative admission compares total capacity, not current free VRAM; balanced does not reject based on the estimate. Treat as a heuristic, not an OOM-prevention guarantee. The previously missing call-site wiring is addressed, but memory-fit acceptance remains open.
- **Mistral:** Integrated the CLIP tokenizer sentinel clamp; added handling/tests for absent or invalid metadata. Read-only logs show both training arms completed exit 0 and the diagnostic OOM was caught. Corrected the report's contradictory claim that OOM warnings were absent: `train_a.log:175` and `:178` contain them. Removed the unmeasured claim that SDXL fits nowhere. Keep Hessian probes disabled by default. The report asserts direct Harbinger authorization; this session did not perform or independently establish that approval chain.
- **Kimi:** Previous safety corrections and interpretation limits stand. No rerun or new changes.

## Verification

53 bridge/Generate tests passed with process exit 0. 39 CPU tests passed across estimator, lease arbiter, and tokenizer clamp. Ruff and whitespace checks passed. 7 GPU-admission GUI tests passed with exit 0. No full suite, benchmark, model download, or GPU job launched in this review.

PR #798 remains draft pending real ComfyUI acceptance and calibrated memory-admission scope. Mistral's artifacts support fail-soft behavior on this device, not successful 512px curvature measurement.
