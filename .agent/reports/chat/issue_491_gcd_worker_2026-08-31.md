# Issue #491 — GCD extractor worker

Implemented the Cloud Run worker foundation in `infra/cloud/gcd/worker/`.

- `POST /jobs` accepts a validated `gs://` range, GIF, or video extraction job.
- The FFmpeg-only image downloads the input, uploads outputs and `usage.json`
  to `RESULTS_BUCKET`, and removes its temporary workspace.
- FFmpeg uses two threads and a 1,700-second per-phase timeout; GIF uses a
  two-pass palette workflow.

Validation: `ruff check`, `py_compile`, and `pytest -q
backend/test/cloud/test_gcd_worker.py` (4 passed). No Cloud Run deployment or
credential access was performed.
