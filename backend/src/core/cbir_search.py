"""Content-Based Image Retrieval using CLIP embeddings and FAISS.

Dependencies (add to pyproject.toml):
    faiss-cpu>=1.7.4          # or faiss-gpu for CUDA acceleration
    sentence-transformers>=2.6.0
    Pillow>=10.0.0            # already present

The FAISS index and path manifest are expected at:
    ~/.image-toolkit/cbir_index/clip_index.faiss
    ~/.image-toolkit/cbir_index/clip_paths.json

Both artefacts are written by the indexing pipeline (pooled_image_database.py or
a dedicated build-index script).  This module handles retrieval only.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from backend.src.web.models import ReverseSearchResult

log = logging.getLogger(__name__)

_DEFAULT_INDEX_DIR = Path.home() / ".image-toolkit" / "cbir_index"
_INDEX_FILE = "clip_index.faiss"
_PATHS_FILE = "clip_paths.json"
_CLIP_MODEL_NAME = "clip-ViT-B-32"


class LocalCBIRSearch:
    """Retrieves visually similar local images via CLIP + FAISS nearest-neighbour search.

    The CLIP model and FAISS index are loaded lazily on the first call to
    :meth:`search` so that import time stays near-zero.

    Args:
        index_dir: Directory containing ``clip_index.faiss`` and
            ``clip_paths.json``.  Defaults to ``~/.image-toolkit/cbir_index/``.
        model_name: sentence-transformers model identifier for the CLIP encoder.
        top_k: Default number of neighbours to return.

    Raises:
        FileNotFoundError: If the FAISS index or paths file is missing.
        ImportError: If ``faiss`` or ``sentence_transformers`` is not installed.
    """

    def __init__(
        self,
        index_dir: Optional[Path] = None,
        model_name: str = _CLIP_MODEL_NAME,
        top_k: int = 20,
    ) -> None:
        self._index_dir = Path(index_dir) if index_dir else _DEFAULT_INDEX_DIR
        self._model_name = model_name
        self._default_top_k = top_k

        self._model = None       # sentence_transformers.SentenceTransformer
        self._index = None       # faiss.Index
        self._paths: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        image_path: str,
        top_k: Optional[int] = None,
    ) -> List[ReverseSearchResult]:
        """Find the ``top_k`` most visually similar images in the local index.

        Args:
            image_path: Absolute path to the query image.
            top_k: Number of results to return.  Defaults to the value set in
                ``__init__``.

        Returns:
            List of :class:`~backend.src.web.models.ReverseSearchResult` sorted
            by descending similarity score.  An empty list is returned when the
            index is unavailable or the query image cannot be encoded.
        """
        k = top_k if top_k is not None else self._default_top_k

        try:
            self._ensure_loaded()
        except (FileNotFoundError, ImportError) as exc:
            log.error("CBIR search unavailable: %s", exc)
            return []

        embedding = self._encode_image(image_path)
        if embedding is None:
            return []

        distances, indices = self._index.search(embedding, k)
        return self._build_results(distances[0], indices[0])

    def is_index_available(self) -> bool:
        """Return ``True`` if the FAISS index artefacts exist on disk."""
        return (
            (self._index_dir / _INDEX_FILE).is_file()
            and (self._index_dir / _PATHS_FILE).is_file()
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Lazily load the CLIP model and FAISS index (once per instance)."""
        if self._index is not None:
            return

        index_path = self._index_dir / _INDEX_FILE
        paths_path = self._index_dir / _PATHS_FILE

        if not index_path.is_file():
            raise FileNotFoundError(
                f"FAISS index not found: {index_path}\n"
                "Run the index-build step (pooled_image_database.py --build-index) first."
            )
        if not paths_path.is_file():
            raise FileNotFoundError(f"Path manifest not found: {paths_path}")

        try:
            import faiss  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "faiss is not installed.  Add 'faiss-cpu>=1.7.4' to pyproject.toml."
            ) from exc

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed.  "
                "Add 'sentence-transformers>=2.6.0' to pyproject.toml."
            ) from exc

        log.info("Loading CLIP model '%s'…", self._model_name)
        self._model = SentenceTransformer(self._model_name)

        log.info("Loading FAISS index from %s…", index_path)
        self._index = faiss.read_index(str(index_path))

        with open(paths_path, encoding="utf-8") as fh:
            self._paths = json.load(fh)

        log.info("CBIR ready — %d vectors indexed.", self._index.ntotal)

    def _encode_image(self, image_path: str) -> Optional[np.ndarray]:
        """Return an L2-normalised CLIP embedding for *image_path*.

        Returns ``None`` on failure so callers can return an empty result list
        instead of propagating the exception.
        """
        try:
            from PIL import Image  # type: ignore[import-untyped]

            with Image.open(image_path).convert("RGB") as img:
                embedding = self._model.encode(
                    img,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            return embedding.reshape(1, -1).astype(np.float32)
        except Exception as exc:
            log.warning("Could not encode image '%s': %s", image_path, exc)
            return None

    def _build_results(
        self,
        distances: np.ndarray,
        indices: np.ndarray,
    ) -> List[ReverseSearchResult]:
        """Convert raw FAISS output into :class:`ReverseSearchResult` objects.

        FAISS inner-product distances on unit vectors equal cosine similarity,
        so they are already in [0, 1] when ``normalize_embeddings=True`` is used.
        """
        results: List[ReverseSearchResult] = []
        for dist, idx in zip(distances, indices):
            if idx < 0 or idx >= len(self._paths):
                continue
            path = self._paths[int(idx)]
            resolution = self._get_resolution(path)
            results.append(
                ReverseSearchResult(
                    url=path,
                    engine="local_cbir",
                    score=float(np.clip(dist, 0.0, 1.0)),
                    resolution=resolution,
                    title=Path(path).name,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    @staticmethod
    def _get_resolution(path: str) -> str:
        """Return a ``"WxH"`` string without loading the full pixel data."""
        try:
            from PIL import Image

            with Image.open(path) as img:
                w, h = img.size
            return f"{w}x{h}"
        except Exception:
            return "Unknown"
