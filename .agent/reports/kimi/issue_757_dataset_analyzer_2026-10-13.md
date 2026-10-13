# #757 — C++ dataset analyzer: benchmark-first verdict (NOT NEEDED)

Date: 2026-10-13. Owner: Kimi. Branch: `dl-757-dataset-analyzer`.

## Question

Issue #757 (deferred, benchmark-first): Gate D.4's deterministic dataset
checks (`backend/src/core/dataset_advisor.py::scan_dataset` — sha256 hashing,
PIL header dimension probe, caption sidecar read, frame-group keying,
duplicate grouping, co-occurrence construction) might be "noticeably slow on
1000+ image datasets", in which case a `base/src/dataset_analyzer.cpp`
pybind11 module would move that I/O-bound pre-analysis into the C++ core.
The issue forbids building it speculatively.

## Method

`backend/benchmark/bench_dataset_analyzer.py` (this PR): generates a
synthetic dataset under `~/Downloads/Data/Tests/ds-analyzer-bench` and times
the shipped `scan_dataset` via the house `BenchmarkManager`:

- 1200 files / 1.10 GB: 1136 "normal" images (70% JPEG q88, 20% PNG lvl1,
  10% WebP; 512×512 up to 3840×2160, gradient+noise content so files
  compress realistically), 20 byte-exact duplicates, 3×8 identical
  frame-bursts, 10 extreme-aspect (4:1), 10 corrupt/unreadable,
  danbooru-style caption sidecars (~93% coverage, ~60% carrying the trigger
  token "ohwx").
- `scan_cold_no_hash_cache` ×3 — every file re-stat + re-hashed + probed
  (first-open worst case; hash cache disabled).
- `scan_warm_hash_cache` ×5(+1 warmup) — the panel's repeat-scan path: a
  populated mtime/size-validated hash cache skips re-hashing.
- One instrumented cold scan attributes wall time to `_probe` (hash+dims),
  `_read_captions`, `_duplicate_groups`, `_cooccurrence_findings`.

Environment: single CPU-only Python process, no GPU/torch (dataset_advisor
is torch-free by design), dataset on the same NVMe as the repo. Fixture
generation is seeded (`np.random.default_rng(757)`) and cached on disk
(marker `.bench_fixture_v2.json`); `--regenerate` rebuilds.

## Results

Cold scan, no hash cache (1200 files / 1.10 GB):

| metric | value |
|---|---|
| avg | 1.437 s (3 iters; min 1.047 s, max 2.181 s) |
| per image | ~1.2 ms/image avg (0.94 ms on the instrumented run) |

Warm scan, populated hash cache: **avg 0.051 s** for all 1200 files
(min 0.033 s, max 0.070 s) — the advisor panel's re-scan path after a
trigger-token edit is effectively instant.

Instrumented cold-scan attribution:

| phase | time | share |
|---|---|---|
| `_probe` (sha256 + PIL dims) | 1.073 s | 95.4% |
| `_read_captions` | 0.014 s | 1.2% |
| `_duplicate_groups` | 0.001 s | 0.1% |
| `_cooccurrence_findings` | 0.005 s | 0.4% |
| **total** | **1.125 s** | findings=11 (sanity: dups, bursts, extremes, unreadable, captions all detected) |

## Verdict: not noticeably slow — C++ module not warranted, closing #757

- The cold worst case is ~2.2 s for 1200 realistic files, typical ~1 s,
  warm re-scan ~51 ms. `scan_dataset` already runs off the GUI thread in
  `AdvisorScanWorker` with progress + cancel, so this is a short progress
  bar, never a freeze.
- 95.4% of cold time is `_probe`. Micro-measurement of its two halves over
  the same corpus: sha256 alone 0.724 s (1.52 GB/s — plain OpenSSL
  single-thread throughput) + PIL header probe 0.277 s (0.231 ms/file);
  `stat` is noise (0.002 ms/file). The sum (~1.00 s) matches the 1.07 s
  `_probe` phase, so there is no hidden Python-loop tax.
- What could a C++ `dataset_analyzer.cpp` actually save? At best it fuses
  hash + header parse into one buffered pass and drops the PIL binding
  overhead: roughly the 0.28 s PIL phase plus maybe ~0.1 s of glue — call
  it ~0.3–0.4 s on a cold scan of this size, and **zero on the warm path**
  (0.05 s floor is stat syscalls). Hashing itself would call the same
  OpenSSL EVP routines through pybind11. That is not worth a new native
  surface, CMake plumbing, and parity tests for a background worker that
  finishes in about a second.
- Per the issue's own decision rule and the delegation ("If it isn't
  [slow], post the numbers and close the issue as not needed"), #757 is
  closed as not needed. The committed benchmark makes this re-checkable
  whenever the advisor gains new checks.

## Support limits

- Synthetic corpus, not a scraped real-world dataset (generation is seeded
  and reproducible; sizes/formats/mix chosen to match wallpaper-training
  corpora).
- 1200 images here; scaling is linear in file count at fixed per-file
  sizes. Per-file costs dominate: sha256 of 1.1 GB runs at 1.52 GB/s
  (0.724 s), the PIL header probe adds 0.231 ms/file, and `stat` is
  negligible — the measured ~1.2 ms/image is ~0.9 ms hashing + ~0.3 ms
  header/glue, with no meaningful pure-Python overhead left to reclaim.
- No CLIP/diversity timing: out of scope per the issue (stays Python
  regardless); no GPU, no suite runs, single authorized benchmark process.
