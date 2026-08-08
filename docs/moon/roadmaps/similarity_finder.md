# Similarity Finder — Architecture

The former **Delete** tab is now the **Similarity Finder**: a tiered local
image-deduplication and similarity-clustering module spanning the C++ vision
core, the Python ML/orchestration backend, and the QML frontend.

## Detection tiers

| Tier | Signal | Engine | Index | Cost |
|------|--------|--------|-------|------|
| 1 — Exact | xxHash64 file digest | C++ (`base.similarity.xxh64_file[s]`) | hash-map grouping | O(N), I/O bound |
| 2 — Consensus hashing | pHash (DCT) + dHash + wHash (Haar), size 8/16/32 | C++ (`compute_hashes`, `consensus_confidence`) | **VP-tree** Hamming range search (`hash_pairs_within`) | O(N log N) |
| 3 — Structural | SSIM + ORB/SIFT (Lowe ratio + RANSAC homography) | C++ (`ssim`, `match_features`) | candidate pairs only (from tiers 2/4) | ~50–300 ms/pair, capped |
| 4 — Semantic | CLIP / MobileCLIP / ResNet-18 embeddings | Python (torch) + C++ **HNSW** (`HnswIndex`) | HNSW cosine kNN | O(N log N) |

All pair evidence is merged into one edge list `(a, b, confidence, tier)`.
Union-find over edges with `confidence ≥ confidence_threshold` produces the
clusters ("stacks"). The GUI **confidence slider** calls
`SimilarityEngine.regroup()` which re-clusters the cached edges instantly —
no rescan.

## Persistence & incremental scans

`~/.image-toolkit/similarity_cache.db` (SQLite, `backend/src/core/similarity/cache.py`):

```
file_index(filepath PK, modified_timestamp, file_size, xxh64,
           hash_size, phash, dhash, whash, embed_model, embedding BLOB)
```

A file is re-hashed only when `(mtime, size)` or the requested `hash_size`
changed; embeddings are recomputed only when the file changed or a different
model is selected. `prune_missing()` drops rows for deleted files.

## Cross-directory synchronization

`SimilarityConfig.reference_dir` enables directional scanning: files under
the Reference directory are protected — reference↔reference pairs are dropped,
reference↔target and target↔target pairs survive, and triage never proposes a
reference file for deletion.

## Smart triage

`triage.auto_select(paths, TriageRules, protected)` scores each cluster member
by weighted rules — resolution, file size, lossless-format ladder, EXIF
presence, path priority/deprioritisation substrings — and returns
`(keeper, discards)`. Besides deletion, `consolidate.consolidate_cluster()`
replaces duplicates with **hardlinks/symlinks** (atomic tmp-link + rename) to
reclaim space without breaking layouts.

## Directory structure

```
base/
  include/core/similarity.hpp          # public C++ API
  src/core/similarity/
    hashing.cpp                        # XXH64, pHash/dHash/wHash, consensus
    vptree.cpp                         # VP-tree (Hamming)
    hnsw.cpp                           # HNSW (cosine)
    visual.cpp                         # SSIM, ORB/SIFT+RANSAC, diff mask
    bindings.cpp                       # pybind11 → base.similarity
backend/
  src/core/similarity/
    config.py                          # SimilarityConfig + TriageRules (all GUI hyperparams)
    cache.py                           # SQLite incremental cache
    embedder.py                        # mobileclip → openclip → resnet18 fallback chain
    engine.py                          # 4-tier orchestration, regroup()
    triage.py                          # auto-selection rule engine
    consolidate.py                     # hardlink/symlink consolidation
  test/similarity/                     # 50 unit tests (C++ invariants, cache, engine, triage, links)
gui/
  src/helpers/core/similarity_scan_worker.py   # QThread worker
  src/tabs/core/similarity_tab.py              # SimilarityTab(DeleteTab) + ClusterListModel
  qml/tabs/core/SimilarityTab.qml              # main tab UI
  qml/components/
    ClusterStack.qml                   # album card (fanned stack, tier badge, confidence bar)
    BlinkComparator.qml                # Space-toggle A/B blink
    SwipeCompare.qml                   # draggable divider overlay
    DiffMaskView.qml                   # neon-green XOR difference mask
    TetheredViewport.qml               # synchronized zoom/pan panes
```

## Build changes

`base/CMakeLists.txt`:
- five new sources under `src/core/similarity/`;
- **RPATH fix**: an explicit `-Wl,-rpath,<pixi lib>` link option now forces the
  pixi lib dir ahead of `/usr/lib/x86_64-linux-gnu` (pixi's `libssl` must
  resolve pixi's `libcrypto`, not the older system one — this previously broke
  `import base` under pytest which prefers `build/base/`).

No new third-party dependencies: XXH64, the VP-tree and HNSW are implemented
in-repo; OpenCV provides DCT/SSIM/ORB/SIFT/RANSAC. Semantic embeddings use
whatever of `open_clip`/`torchvision` is installed and degrade gracefully
(semantic tier disables itself if torch is absent).

## Threading / FFI

- All C++ entry points release the GIL; batch hashing fans out with OpenMP.
- Scans run in a dedicated `QThread` (`SimilarityScanWorker`), progress and
  cancellation via Qt signals + `isInterruptionRequested()`.
- Embedding batches run in the worker thread; torch releases the GIL during
  forward passes. Model VRAM is freed (`unload_all`) after each scan.
- FFI is pybind11 (`base` extension) — the same safe boundary the rest of the
  toolkit uses.

## QML component architecture

`SimilarityTab.qml` — three panes:
1. **Settings** (left): target/reference selectors, tier toggles, and every
   hyperparameter — hash size (8/16/32), Hamming threshold, ORB/SIFT choice,
   max features, Lowe's ratio, RANSAC threshold, embedding model, semantic
   similarity threshold, triage rules — plus Scan/Cancel, Auto-Select,
   Delete Selected, Consolidate (auto/hardlink/symlink).
2. **Clusters** (center): confidence slider (live regroup) + `GridView` of
   `ClusterStack` albums fed by `ClusterListModel`.
3. **Detail** (right): member grid (★ = triage keeper, ✗ = marked for delete),
   pair pick mode, and the four comparators in a `TabBar`
   (Blink / Swipe / Diff / Tethered).

Backend object: `mainBackend.similarityTab` (alias `deleteTab` retained for
backward compatibility; `SimilarityTab` subclasses the old `DeleteTab`, so the
legacy widget-mode delete workflows keep working).
