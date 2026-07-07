# Entity Recon & Provenance — Architecture

A localized OSINT / identity-resolution tab (Web Integration category) that
moves the toolkit from image manipulation to entity reconnaissance, dataset
management and web provenance.

## Cross-language responsibilities

| Layer | Role | Where |
|-------|------|-------|
| C++ (`base.recon`) | HNSW **IdentityIndex** (embedding → `FirstName_LastName` + path), alpha-cutout hashing | `base/src/web/recon/` |
| Python | SAM 2 segmentation, face/CLIP embeddings, dataset indexing daemon, reverse-search dispatch, NER consensus, provenance export | `backend/src/web/recon/` |
| QML/Qt | three-pane UI, hover masking, bounding box, IPC to workers | `gui/qml/tabs/web/EntityReconTab.qml`, `gui/src/tabs/web/entity_recon_tab.py` |

> The original spec named **Rust** for the data/discovery engine. This repo
> completed its Rust→C++ migration (`archive/base_rust/`), so the native engine
> is implemented in C++ and reuses `base.similarity`'s HNSW rather than
> reintroducing a Rust toolchain.

## Pipeline

```
source image ──hover──▶ SAM 2 mask ──click──▶ alpha cutout
                                                 │
                            ┌── embed (ArcFace | CLIP) ──┐
                            ▼                            ▼
                  base.recon.IdentityIndex        base.recon.cutout_hash
                    (local HNSW query)             (provenance-cache key)
                            │                            │
          match ≥ threshold │                            │ (privacy off, no local match)
                            ▼                            ▼
                   "Method: ArcFace          ReverseSearchDispatcher
                    -> Local DB"             (SQLite cache + rate limit)
                                                     │ scrape titles/meta
                                                     ▼
                                             NER "Name Guesser"
                                             (gliner|spaCy|heuristic)
                                                     ▼
                                             cross-domain consensus
                                             "Method: Web Consensus"
```

## Key modules (`backend/src/web/recon/`)

- **config.py** — `ReconConfig`: dataset root, embed mode (`face`/`clip`),
  privacy mode, engines, rate limits, cache path, NER model, thresholds.
- **segmenter.py** — `segment_at_point` / `segment_bbox` / `alpha_cutout`;
  SAM 2 → SAM 1 → GrabCut → bounding-box fallbacks (all lazy).
- **embedder.py** — `embed_face` (InsightFace/ArcFace), `embed_clip` (reuses the
  Similarity Finder embedder chain), deterministic histogram fallback.
- **indexer.py** — `DatasetIndexer`: walks `/root/FirstName_LastName/img.jpg`,
  embeds each image, fills `base.recon.IdentityIndex` (label = parent dir).
- **dispatcher.py** — `ReverseSearchDispatcher` (privacy-gated), `ProvenanceCache`
  (SQLite keyed by cutout hash), `RateLimiter` (per-engine min interval).
- **consensus.py** — `extract_names` (NER) + `consensus_names`: a candidate must
  appear on ≥ `consensus_min_domains` distinct domains to win; ties break on
  total mentions.
- **engine.py** — `ReconEngine.resolve()` (local → web) and `suggest_batch()`
  for the Dataset Builder.
- **provenance.py** — `ProvenanceReport` + `export_provenance` (JSON/CSV).

## Production requirements (all implemented)

1. **Strict Privacy Mode** — a prominent toggle; when on, the dispatcher never
   touches the network (serves cache only) — 100% air-gapped.
2. **Rate limiting + SQLite caching** — requests keyed by the C++
   `cutout_hash`; a repeated cutout is served from cache to avoid IP bans /
   throttling; `RateLimiter` enforces a per-engine minimum interval.
3. **Provenance export** — JSON or CSV report of the trail + confidence.

## GUI (three panes)

- **Left** — source viewer; hovering runs `segment_at(x, y)` (throttled) and
  renders a translucent accent mask overlay; click confirms and resolves.
  "Box" mode switches to a manual marquee → `segment_bbox`.
- **Center** — identity card: `ConfidenceRing`, predicted name, origin badge
  (LOCAL DB / WEB CONSENSUS) and method string.
- **Right** — provenance trail (`provenanceModel`): local rows with
  "Open in File Manager", web rows grouped by domain with clickable links; plus
  the drag-and-drop **Dataset Builder** dropzone + "Approve All" bulk moves.

## Tests

`backend/test/recon/` (24): IdentityIndex resolution + distinct-label
collapsing + cutout hashing, consensus algorithm (cross-domain winner,
single-domain rejection), rate limiter, SQLite cache roundtrip, privacy-mode
gating (never calls network, serves cache), web-mode caching, end-to-end
indexing + local resolution + JSON/CSV export.

## Graceful degradation

SAM 2, InsightFace and gliner/spaCy are all lazy-loaded with offline
fallbacks (GrabCut, histogram embedding, regex NER), so the tab — and its
tests — run fully offline without the heavy weights installed.
