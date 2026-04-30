"""
backend/src/pipeline/data_selection.py
========================================
Multi-stage data selection and deduplication for anime training datasets.

Stages
------
Stage 1: pHash near-duplicate clustering (Hamming distance ≤ 6)
Stage 2: Siamese-embedding furthest-point diversity sampling
Stage 3: Laplacian blur, NIQE/BRISQUE quality scoring
Stage 4: Optional active-learning logistic regressor on quality features

Usage
-----
    selector = DataSelector(db=db, siamese=siamese_loader)
    accepted = selector.run(candidate_image_ids, target_k=50)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    import cv2
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

try:
    import pyiqa
    _PYIQA_OK = True
except ImportError:
    _PYIQA_OK = False
    log.warning("pyiqa not installed — NIQE/BRISQUE scoring unavailable")

try:
    from sklearn.linear_model import LogisticRegression
    _SKLEARN_OK = True
except ImportError:
    _SKLEARN_OK = False


# ---------------------------------------------------------------------------
# Stage 1: pHash deduplication
# ---------------------------------------------------------------------------
def phash_hamming(a: int, b: int) -> int:
    """Hamming distance between two 64-bit pHash integers."""
    return bin(a ^ b).count("1")


def cluster_duplicates(
    phashes: dict[int, int],  # image_id → phash64 int
    threshold: int = 6,
) -> dict[int, list[int]]:
    """
    Greedily cluster image IDs whose pHash Hamming distance ≤ threshold.
    Returns {representative_id: [duplicate_id, ...]} (representative not in list).
    """
    ids = list(phashes.keys())
    assigned = set()
    clusters: dict[int, list[int]] = {}

    for i, a in enumerate(ids):
        if a in assigned:
            continue
        cluster = []
        for b in ids[i + 1:]:
            if b in assigned:
                continue
            if phash_hamming(phashes[a], phashes[b]) <= threshold:
                cluster.append(b)
                assigned.add(b)
        if cluster:
            clusters[a] = cluster
        assigned.add(a)

    return clusters


# ---------------------------------------------------------------------------
# Stage 2: Siamese diversity sampling (furthest-point)
# ---------------------------------------------------------------------------
def diverse_subset(
    embeddings: dict[int, np.ndarray],  # image_id → L2-normalised 512-d vector
    k: int,
) -> list[int]:
    """
    Select k image IDs that maximise pairwise cosine diversity via
    furthest-point sampling (greedy, O(n·k)).
    """
    ids = list(embeddings.keys())
    if len(ids) <= k:
        return ids

    vecs = np.stack([embeddings[i] for i in ids]).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / (norms + 1e-8)

    # Seed: the sample farthest from the centroid
    centroid = vecs.mean(axis=0)
    seed = int(np.argmax(np.linalg.norm(vecs - centroid, axis=1)))
    chosen = [seed]
    min_dist = 1.0 - vecs @ vecs[seed]

    while len(chosen) < k:
        nxt = int(np.argmax(min_dist))
        chosen.append(nxt)
        min_dist = np.minimum(min_dist, 1.0 - vecs @ vecs[nxt])

    return [ids[i] for i in chosen]


# ---------------------------------------------------------------------------
# Stage 3: Quality metrics
# ---------------------------------------------------------------------------
def laplacian_blur_var(img_bgr: np.ndarray) -> float:
    """
    Laplacian variance as sharpness proxy.
    Typical TV anime: ≥ 80 (sharp), < 50 (motion-blurred).
    """
    if not _CV2_OK:
        return 999.0
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class IQAScorer:
    """Wrapper around pyiqa for NIQE and BRISQUE scores."""

    def __init__(self, device: str = "cuda"):
        if not _PYIQA_OK:
            raise ImportError("pyiqa is required for IQA scoring (pip install pyiqa)")
        import torch
        self.device = device
        self.niqe = pyiqa.create_metric("niqe", device=torch.device(device))
        self.brisque = pyiqa.create_metric("brisque", device=torch.device(device))

    def score(self, img_path: str) -> tuple[float, float]:
        """Returns (niqe, brisque) — lower is better for both."""
        import torch
        from PIL import Image
        import torchvision.transforms.functional as TF
        with Image.open(img_path) as im:
            t = TF.to_tensor(im.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.no_grad():
            niqe_val = float(self.niqe(t))
            brisque_val = float(self.brisque(t))
        return niqe_val, brisque_val


# ---------------------------------------------------------------------------
# Stage 4: Active-learning quality regressor
# ---------------------------------------------------------------------------
class QualityRegressor:
    """
    Tiny logistic regressor trained on manually-labelled quality features.
    50–100 labelled examples typically suffice for good discrimination.

    Features: [blur_lap_var, niqe, brisque, fg_ratio, flat_field_norm]
    Label: 1 = keep, 0 = reject
    """

    def __init__(self, C: float = 1.0):
        if not _SKLEARN_OK:
            raise ImportError("scikit-learn is required for QualityRegressor")
        self.clf = LogisticRegression(C=C, max_iter=500)
        self._fitted = False

    def fit(self, features: np.ndarray, labels: np.ndarray) -> None:
        self.clf.fit(features, labels)
        self._fitted = True

    def predict(self, features: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.ones(len(features), dtype=int)
        return self.clf.predict(features)

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.ones((len(features), 2)) * 0.5
        return self.clf.predict_proba(features)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class DataSelector:
    """
    Parameters
    ----------
    db              : PgvectorImageDatabase (for embedding & quality queries)
    blur_min        : minimum Laplacian variance to accept
    niqe_max_pct    : reject worst N% by NIQE
    iqa_scorer      : optional IQAScorer instance
    quality_regressor: optional fitted QualityRegressor
    """

    def __init__(
        self,
        db=None,
        blur_min: float = 80.0,
        niqe_max_pct: float = 5.0,
        iqa_scorer: Optional[IQAScorer] = None,
        quality_regressor: Optional[QualityRegressor] = None,
    ):
        self.db = db
        self.blur_min = blur_min
        self.niqe_max_pct = niqe_max_pct
        self.iqa = iqa_scorer
        self.regressor = quality_regressor

    def run(
        self,
        candidate_ids: list[int],
        target_k: int,
        phashes: Optional[dict[int, int]] = None,
        embeddings: Optional[dict[int, np.ndarray]] = None,
    ) -> list[int]:
        """
        Full 4-stage pipeline.  Returns at most target_k image IDs.
        phashes and embeddings can be supplied directly or fetched from db.
        """
        ids = list(candidate_ids)
        log.info("DataSelector: starting with %d candidates, target=%d", len(ids), target_k)

        # ── Stage 1: pHash dedup ──────────────────────────────────────────
        if phashes is None and self.db is not None:
            phashes = self._fetch_phashes(ids)
        if phashes:
            clusters = cluster_duplicates(phashes, threshold=6)
            dupes = {d for dlist in clusters.values() for d in dlist}
            ids = [i for i in ids if i not in dupes]
            log.info("After pHash dedup: %d (removed %d duplicates)", len(ids), len(dupes))

        # ── Stage 2: Diversity sampling ───────────────────────────────────
        if len(ids) > target_k:
            if embeddings is None and self.db is not None:
                embeddings = self._fetch_embeddings(ids)
            if embeddings:
                ids = diverse_subset(
                    {i: embeddings[i] for i in ids if i in embeddings},
                    k=min(target_k * 2, len(ids)),  # over-select; quality will prune
                )
                log.info("After diversity sampling: %d", len(ids))

        # ── Stage 3: Quality filtering ────────────────────────────────────
        if self.iqa is not None and self.db is not None:
            ids = self._quality_filter(ids)
            log.info("After quality filter: %d", len(ids))

        # ── Stage 4: Active-learning regressor ───────────────────────────
        if self.regressor is not None and self.db is not None:
            ids = self._regressor_filter(ids)
            log.info("After regressor filter: %d", len(ids))

        return ids[:target_k]

    # ------------------------------------------------------------------
    def _fetch_phashes(self, ids: list[int]) -> dict[int, int]:
        if self.db is None:
            return {}
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, phash64 FROM image_embeddings WHERE image_id = ANY(%s)",
                    (ids,),
                )
                return {r[0]: r[1] for r in cur.fetchall() if r[1] is not None}
        except Exception as exc:
            log.warning("_fetch_phashes failed: %s", exc)
            return {}

    def _fetch_embeddings(self, ids: list[int]) -> dict[int, np.ndarray]:
        if self.db is None:
            return {}
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, siamese_512 FROM image_embeddings WHERE image_id = ANY(%s)",
                    (ids,),
                )
                return {r[0]: np.asarray(r[1], dtype=np.float32) for r in cur.fetchall() if r[1] is not None}
        except Exception as exc:
            log.warning("_fetch_embeddings failed: %s", exc)
            return {}

    def _quality_filter(self, ids: list[int]) -> list[int]:
        if self.db is None:
            return ids
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, blur_lap_var, niqe FROM image_quality WHERE image_id = ANY(%s)",
                    (ids,),
                )
                rows = cur.fetchall()
        except Exception:
            return ids

        niqe_vals = [r[2] for r in rows if r[2] is not None]
        niqe_threshold = np.percentile(niqe_vals, 100 - self.niqe_max_pct) if niqe_vals else float("inf")

        good = set()
        for image_id, blur, niqe in rows:
            if blur is not None and blur < self.blur_min:
                continue
            if niqe is not None and niqe > niqe_threshold:
                continue
            good.add(image_id)
        return [i for i in ids if i in good]

    def _regressor_filter(self, ids: list[int]) -> list[int]:
        if self.db is None or self.regressor is None:
            return ids
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, blur_lap_var, niqe, brisque, fg_ratio, flat_field_norm "
                    "FROM image_quality WHERE image_id = ANY(%s)",
                    (ids,),
                )
                rows = cur.fetchall()
        except Exception:
            return ids

        if not rows:
            return ids
        feats = np.array(
            [[r[1] or 0, r[2] or 0, r[3] or 0, r[4] or 0, r[5] or 0] for r in rows],
            dtype=np.float32,
        )
        preds = self.regressor.predict(feats)
        return [rows[i][0] for i, p in enumerate(preds) if p == 1]
