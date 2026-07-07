"""Four-tier similarity scan orchestration.

Pipeline (all compute-heavy stages run in C++ ``base.similarity``):

    Tier 1  exact       xxHash64 digest grouping                (O(N))
    Tier 2  perceptual  pHash/dHash/wHash + VP-tree candidates  (O(N log N))
    Tier 3  structural  SSIM + ORB/SIFT RANSAC verification     (candidates only)
    Tier 4  semantic    CLIP/MobileCLIP embeddings + HNSW       (O(N log N))

The scan produces a flat edge list (pairs with confidence + originating tier)
plus clusters from union-find over edges above ``confidence_threshold``.
``regroup()`` re-clusters the cached edges at a new threshold instantly, which
is what the GUI confidence slider calls.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .cache import SimilarityCache
from .config import (
    TIER_EXACT,
    TIER_PERCEPTUAL,
    TIER_SEMANTIC,
    TIER_STRUCTURAL,
    SimilarityConfig,
)
from .embedder import get_embedder

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, int], None]
CancelCb = Callable[[], bool]


@dataclass
class SimilarityEdge:
    a: str
    b: str
    confidence: float
    tier: str
    distance: float = 0.0  # tier-specific raw metric (hamming / 1-cos / 1-ssim)


@dataclass
class SimilarityReport:
    files: List[str] = field(default_factory=list)
    edges: List[SimilarityEdge] = field(default_factory=list)
    clusters: List[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class _UnionFind:
    def __init__(self):
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


class ScanCancelled(Exception):
    pass


class SimilarityEngine:
    def __init__(
        self,
        config: SimilarityConfig,
        cache: Optional[SimilarityCache] = None,
        progress_cb: Optional[ProgressCb] = None,
        cancel_cb: Optional[CancelCb] = None,
    ):
        self.config = config
        self.cache = cache or SimilarityCache(config.cache_path)
        self._progress = progress_cb or (lambda *_: None)
        self._cancelled = cancel_cb or (lambda: False)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _check_cancel(self):
        if self._cancelled():
            raise ScanCancelled()

    def _list_files(self) -> Tuple[List[str], set]:
        from backend.src.core.similarity_finder import SimilarityFinder

        cfg = self.config
        target_files = SimilarityFinder.get_images_list(
            cfg.target_dir, cfg.extensions, recursive=cfg.recursive
        )
        ref_set: set = set()
        files = list(dict.fromkeys(target_files))
        if cfg.reference_dir and os.path.isdir(cfg.reference_dir):
            ref_files = SimilarityFinder.get_images_list(
                cfg.reference_dir, cfg.extensions, recursive=cfg.recursive
            )
            ref_set = set(ref_files) - set(files)
            files.extend(p for p in ref_files if p in ref_set)
        return files, ref_set

    # ------------------------------------------------------------------
    # scan
    # ------------------------------------------------------------------

    def scan(self) -> SimilarityReport:  # noqa: C901
        import base

        cfg = self.config
        report = SimilarityReport()

        self._progress("Listing files", 0, 0)
        files, ref_set = self._list_files()
        report.files = files
        report.stats["file_count"] = len(files)
        report.stats["reference_count"] = len(ref_set)
        if len(files) < 2:
            return report
        self._check_cancel()

        # --- incremental hashing (feeds tiers 1 & 2) ----------------------
        self._progress("Checking cache", 0, len(files))
        fresh, stale = self.cache.partition_stale(files, cfg.hash_size)
        report.stats["cache_hits"] = len(fresh)
        report.stats["hashed"] = len(stale)

        if stale:
            self._progress("Hashing", 0, len(stale))
            # Hash in chunks so progress + cancellation stay responsive.
            chunk = 256
            for i in range(0, len(stale), chunk):
                self._check_cancel()
                part = base.similarity.compute_hashes(
                    stale[i : i + chunk], hash_size=cfg.hash_size, with_exact=True
                )
                self.cache.upsert_hashes(part, cfg.hash_size)
                self._progress("Hashing", min(i + chunk, len(stale)), len(stale))
            fresh, _still_stale = self.cache.partition_stale(files, cfg.hash_size)

        # In-memory hash table (only files that hashed successfully)
        hashed_paths = [p for p in files if p in fresh]
        xxh = {p: fresh[p]["xxh64"] for p in hashed_paths}
        ph = [fresh[p]["phash"] for p in hashed_paths]
        dh = [fresh[p]["dhash"] for p in hashed_paths]
        wh = [fresh[p]["whash"] for p in hashed_paths]

        edges: Dict[Tuple[str, str], SimilarityEdge] = {}

        def add_edge(a: str, b: str, conf: float, tier: str, dist: float):
            if a == b:
                return
            key = (a, b) if a < b else (b, a)
            prev = edges.get(key)
            if prev is None or conf > prev.confidence:
                edges[key] = SimilarityEdge(key[0], key[1], conf, tier, dist)

        # --- Tier 1: exact ------------------------------------------------
        if TIER_EXACT in cfg.tiers:
            self._progress("Tier 1: exact matches", 0, 0)
            by_digest: Dict[str, List[str]] = {}
            for p in hashed_paths:
                if xxh[p]:
                    by_digest.setdefault(xxh[p], []).append(p)
            for group in by_digest.values():
                for other in group[1:]:
                    add_edge(group[0], other, 1.0, TIER_EXACT, 0.0)
            self._check_cancel()

        # --- Tier 2: consensus perceptual hashing -------------------------
        if TIER_PERCEPTUAL in cfg.tiers and hashed_paths:
            self._progress("Tier 2: perceptual hashing (VP-tree)", 0, 0)
            pairs = base.similarity.hash_pairs_within(
                ph, dh, wh,
                hamming_threshold=cfg.scaled_hamming_threshold(),
                hash_size=cfg.hash_size,
            )
            for i, j, dist, conf in pairs:
                add_edge(hashed_paths[i], hashed_paths[j], conf, TIER_PERCEPTUAL,
                         float(dist))
            report.stats["perceptual_pairs"] = len(pairs)
            self._check_cancel()

        # --- Tier 4: semantic embeddings (before structural so structural
        #     can verify semantic candidates too) --------------------------
        if TIER_SEMANTIC in cfg.tiers and hashed_paths:
            self._progress("Tier 4: loading embedding model", 0, 0)
            embedder = get_embedder(cfg.embed_model)
            if embedder is not None:
                have, missing = self.cache.get_embeddings(hashed_paths, embedder.name)
                report.stats["embedding_cache_hits"] = len(have)
                if missing:
                    batch = 64
                    for i in range(0, len(missing), batch):
                        self._check_cancel()
                        self._progress("Tier 4: embedding", i, len(missing))
                        chunk_embeds = embedder.embed_batch(missing[i : i + batch])
                        self.cache.upsert_embeddings(chunk_embeds, embedder.name)
                        have.update(chunk_embeds)
                emb_paths = [p for p in hashed_paths if p in have]
                if len(emb_paths) >= 2:
                    self._progress("Tier 4: HNSW search", 0, 0)
                    dims = len(next(iter(have.values())))
                    index = base.similarity.HnswIndex(
                        dim=dims, M=cfg.hnsw_m,
                        ef_construction=cfg.hnsw_ef_construction,
                    )
                    matrix = np.stack([have[p] for p in emb_paths]).astype(np.float32)
                    index.add_items(matrix)
                    sem_pairs = index.pairs_within(
                        cfg.similarity_threshold, k=cfg.hnsw_k,
                        ef_search=cfg.hnsw_ef_search,
                    )
                    for i, j, cos in sem_pairs:
                        add_edge(emb_paths[i], emb_paths[j], float(cos),
                                 TIER_SEMANTIC, float(1.0 - cos))
                    report.stats["semantic_pairs"] = len(sem_pairs)
            self._check_cancel()

        # --- Tier 3: structural verification of uncertain candidates ------
        if TIER_STRUCTURAL in cfg.tiers and edges:
            uncertain = [
                e for e in edges.values()
                if e.tier != TIER_EXACT and e.confidence < 0.95
            ]
            uncertain.sort(key=lambda e: -e.confidence)
            uncertain = uncertain[: cfg.max_structural_pairs]
            self._progress("Tier 3: structural verification", 0, len(uncertain))
            for n, e in enumerate(uncertain):
                self._check_cancel()
                fm = base.similarity.match_features(
                    e.a, e.b, method=cfg.feature_method,
                    max_features=cfg.max_features, lowe_ratio=cfg.lowe_ratio,
                    ransac_threshold=cfg.ransac_threshold,
                )
                geo_conf = fm["confidence"] if fm["ok"] else 0.0
                if fm["ok"] and fm["inliers"] >= cfg.min_inliers:
                    geo_conf = max(geo_conf, 0.8)
                ssim = base.similarity.ssim(e.a, e.b, resize_to=cfg.ssim_resize)
                ssim_conf = max(0.0, ssim) if ssim >= cfg.ssim_threshold else 0.0
                structural = max(geo_conf, ssim_conf)
                if structural > e.confidence:
                    key = (e.a, e.b)
                    edges[key] = SimilarityEdge(
                        e.a, e.b, structural, TIER_STRUCTURAL, 1.0 - structural
                    )
                if n % 10 == 0:
                    self._progress("Tier 3: structural verification", n, len(uncertain))
            report.stats["structural_checked"] = len(uncertain)

        # --- directional filtering ----------------------------------------
        edge_list = list(edges.values())
        if ref_set:
            edge_list = [
                e for e in edge_list if not (e.a in ref_set and e.b in ref_set)
            ]
        report.edges = edge_list
        report.stats["edge_count"] = len(edge_list)

        # --- clustering -----------------------------------------------------
        report.clusters = self.regroup(report, cfg.confidence_threshold, ref_set)
        return report

    # ------------------------------------------------------------------
    # re-clustering (confidence slider — no rescan)
    # ------------------------------------------------------------------

    @staticmethod
    def regroup(
        report: SimilarityReport, confidence_threshold: float,
        ref_set: Optional[set] = None,
    ) -> List[dict]:
        uf = _UnionFind()
        kept = [e for e in report.edges if e.confidence >= confidence_threshold]
        for e in kept:
            uf.union(e.a, e.b)

        members: Dict[str, List[str]] = {}
        for e in kept:
            for p in (e.a, e.b):
                root = uf.find(p)
                bucket = members.setdefault(root, [])
                if p not in bucket:
                    bucket.append(p)

        edge_by_root: Dict[str, List[SimilarityEdge]] = {}
        for e in kept:
            edge_by_root.setdefault(uf.find(e.a), []).append(e)

        tier_rank = {TIER_EXACT: 4, TIER_STRUCTURAL: 3, TIER_PERCEPTUAL: 2,
                     TIER_SEMANTIC: 1}
        clusters = []
        ref_set = ref_set or set()
        for root, paths in members.items():
            if len(paths) < 2:
                continue
            cluster_edges = edge_by_root.get(root, [])
            confs = [e.confidence for e in cluster_edges]
            best_tier = max(cluster_edges, key=lambda e: tier_rank.get(e.tier, 0)).tier
            clusters.append({
                "id": f"cluster_{len(clusters)}",
                "paths": sorted(paths),
                "size": len(paths),
                "confidence": float(np.mean(confs)) if confs else 0.0,
                "min_confidence": float(min(confs)) if confs else 0.0,
                "tier": best_tier,
                "reference_paths": sorted(p for p in paths if p in ref_set),
            })
        clusters.sort(key=lambda c: (-c["confidence"], -c["size"]))
        for i, c in enumerate(clusters):
            c["id"] = f"cluster_{i}"
        return clusters
