# #750 — OCR and VLM interfaces

Branch `dl-e-750-ocr-vlm`, off `main` (`907b802c`). Codex had not claimed the issue after the Gate E kickoff.

- `backend/src/core/guidance_vision.py` defines `OcrBackend`, `VlmAdvisor`, `run_ocr`, and `run_vlm`. Later Gate E code should call those two functions. This issue does not add the #751 schema or validators.
- `TesseractOcrBackend` runs the `tesseract` binary with an argument list. A missing binary, a bad language tag, a timeout, or a non-TSV result becomes `OcrResult.unavailable`. A region crop is shifted back onto the source image.
- `ChatVlmAdvisor` is the one VLM backend. Local placement talks to a loopback `/api/chat` and takes the `vlm-advise` GPU admission. Any other host is refused unless placement is cloud. Cloud calls `POST /v1/chat/completions` only after `approved=True`. The departure preview reports the host and byte counts. It does not include the image or `guidance.vlm_api_key`.
- Review has standalone **Read text (OCR)** and **Describe image (VLM)** actions. The cloud button stays off until the preview is shown and the approval box is checked. Work runs off the GUI thread.

Targeted checks: 12 backend, 4 GUI (`--run-gui`), plus the two existing review-upscale tests. No suite, benchmark, or GPU run. Tesseract and the chat server are faked; a machine without the `tesseract` binary still gets a clear unavailable result.

— Grok, 2026-10-12
