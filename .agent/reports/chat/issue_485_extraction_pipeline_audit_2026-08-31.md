# #485 extraction-pipeline audit

Controlled two-worker idle-pool measurement (same CV/video/Qt imports as a
queue worker): `fork` started in 0.015 s with 2.3 MiB mean child USS; `spawn`
took 0.702 s with 94.1 MiB mean USS. The small measurement does not support a
global spawn switch: it adds substantial startup and private-memory cost before
actual extraction. Retain Linux `fork`; profile real extraction-child RSS in a
separate authorized run before changing the process model.

Audit fixes in `QueueExecutionWorker`:

- Queued FFmpeg GIFs now use the direct worker's two-pass palette pipeline,
  avoiding the old split graph that buffered a full scaled range.
- The open-ended GIF `VideoCapture` probe releases on every path.
- MoviePy queue GIF clips close even when export raises.

Focused queue GIF tests pass (2/2). The start-method harness is
`backend/benchmark/bench_queue_pool_start.py`; it is a controlled microbenchmark,
not a corpus run.
