"""Background dataset indexing daemon.

Traverses a dataset laid out as ``/Dataset/FirstName_LastName/image.jpg``,
extracts an embedding per image and populates a C++ ``base.recon.IdentityIndex``
that maps each vector to its parent-directory label. Runs off the UI thread;
progress and cancellation are delivered through callbacks.
"""

import logging
import os
from typing import Callable, List, Optional, Tuple

import numpy as np

from .config import ReconConfig
from .embedder import embed, embedding_dim

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, int], None]
CancelCb = Callable[[], bool]

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


class DatasetIndexer:
    def __init__(
        self,
        config: ReconConfig,
        progress_cb: Optional[ProgressCb] = None,
        cancel_cb: Optional[CancelCb] = None,
    ):
        self.config = config
        self._progress = progress_cb or (lambda *_: None)
        self._cancelled = cancel_cb or (lambda: False)
        self.index = None
        self.stats: dict = {}

    def _label_for(self, path: str) -> str:
        """Parent directory name = FirstName_LastName."""
        return os.path.basename(os.path.dirname(path))

    def _collect(self) -> List[str]:
        root = self.config.dataset_root
        out: List[str] = []
        if not root or not os.path.isdir(root):
            return out
        walker = os.walk(root) if self.config.recursive else [
            (root, [], os.listdir(root))
        ]
        for dirpath, _dirs, files in walker:
            # Skip images sitting directly in the root — labels come from a
            # dedicated per-identity subdirectory.
            if os.path.abspath(dirpath) == os.path.abspath(root):
                continue
            for f in files:
                if os.path.splitext(f)[1].lower() in _IMG_EXTS:
                    out.append(os.path.join(dirpath, f))
        return out

    def build(self):
        import base

        images = self._collect()
        self.stats = {"images": len(images), "indexed": 0, "labels": 0}
        self._progress("Scanning dataset", 0, len(images))
        if not images:
            self.index = base.recon.IdentityIndex(dim=embedding_dim(self.config.embed_mode))
            return self.index

        dim = embedding_dim(self.config.embed_mode)
        vectors: List[np.ndarray] = []
        labels: List[str] = []
        paths: List[str] = []

        import cv2

        for i, path in enumerate(images):
            if self._cancelled():
                break
            img = cv2.imread(path)
            if img is None:
                continue
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            vec = embed(img, self.config.embed_mode)
            if vec is None:
                continue
            v = np.asarray(vec, dtype=np.float32).flatten()
            if v.shape[0] != dim:
                v = np.resize(v, dim)
            vectors.append(v)
            labels.append(self._label_for(path))
            paths.append(path)
            if i % 16 == 0:
                self._progress("Indexing", i, len(images))

        self.index = base.recon.IdentityIndex(dim=dim, ef_construction=200)
        if vectors:
            self.index.add_batch(np.stack(vectors), labels, paths)
        self.stats["indexed"] = len(vectors)
        self.stats["labels"] = len(set(labels))
        self._progress("Index ready", len(images), len(images))
        return self.index

    def query(self, embedding: np.ndarray) -> List[Tuple[str, str, float]]:
        if self.index is None:
            return []
        return self.index.query(
            np.asarray(embedding, dtype=np.float32).flatten().tolist(),
            k=self.config.top_k, ef_search=self.config.hnsw_ef_search,
        )
