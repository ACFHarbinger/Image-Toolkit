"""
backend/src/models/wd_tagger_wrapper.py
========================================
WD-1.4 (WaifuDiffusion Tagger) inference wrapper — §3.6.

Runs the WD tagger ONNX model locally to generate booru-style tags for anime /
manga images.  Supports any of the standard WD model variants hosted on
Hugging Face (SmilingWolf/wd-v1-4-*).  Tags above a configurable confidence
threshold are returned automatically; lower-confidence tags are returned
separately so callers can build a human-review queue (§4.4E).

Usage
-----
::

    tagger = WDTaggerWrapper()           # auto-detects GPU/CPU
    results = tagger.tag("image.png")
    # [{"tag": "1girl", "confidence": 0.98, "category": "general"}, ...]

    # Batch
    results = tagger.tag_batch(["a.png", "b.png"])

    # Custom threshold (default 0.35)
    results = tagger.tag("image.png", threshold=0.5)

Model download
--------------
The ONNX model file and CSV label map are downloaded from Hugging Face Hub on
first use (``huggingface_hub`` is already a dependency via the BiRefNet wrapper).
Default model: ``SmilingWolf/wd-v1-4-convnext-tagger-v2`` (ConvNeXt V2,
~300 MB, best accuracy/speed trade-off for 4× upscaled anime).

Environment variables
---------------------
``WD_TAGGER_MODEL_REPO``   Override the HF repo id (default above).
``WD_TAGGER_CACHE_DIR``    Override the local cache directory
                           (default ``~/.image-toolkit/models/wd_tagger``).
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.src.models.core.base import ModelWrapper, lazy_load

logger = logging.getLogger(__name__)

_DEFAULT_REPO = "SmilingWolf/wd-v1-4-convnext-tagger-v2"
_DEFAULT_CACHE = Path.home() / ".image-toolkit" / "models" / "wd_tagger"

# Tag categories as used in the WD label CSV
_CATEGORY_NAMES: Dict[int, str] = {
    0: "general",
    4: "character",
    9: "copyright",
}

# Minimum confidence applied when no threshold is given by the caller
DEFAULT_THRESHOLD: float = 0.35


class WDTaggerWrapper(ModelWrapper):
    """
    ONNX-based WD-1.4 tagger wrapper (§3.6, Options A + E).

    Parameters
    ----------
    device : str, optional
        Ignored for ONNX inference (CPU/GPU is selected by ONNX Runtime via
        the ``CUDAExecutionProvider`` / ``CPUExecutionProvider`` preference
        list).  Stored for API compatibility with other ModelWrapper subclasses.
    model_repo : str, optional
        Hugging Face repo id for the ONNX model.  Defaults to
        ``WD_TAGGER_MODEL_REPO`` env var or the ConvNeXt V2 model.
    cache_dir : str or Path, optional
        Local directory where the model files are cached.  Defaults to
        ``WD_TAGGER_CACHE_DIR`` env var or ``~/.image-toolkit/models/wd_tagger``.
    threshold : float
        Default confidence threshold for automatic tags.  Tags below this
        value are returned under the ``"below_threshold"`` key.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        model_repo: Optional[str] = None,
        cache_dir: Optional[str | Path] = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.model_repo: str = (
            model_repo
            or os.environ.get("WD_TAGGER_MODEL_REPO", _DEFAULT_REPO)
        )
        self.cache_dir: Path = Path(
            cache_dir
            or os.environ.get("WD_TAGGER_CACHE_DIR", str(_DEFAULT_CACHE))
        )
        self.threshold: float = threshold
        self._session = None          # onnxruntime.InferenceSession
        self._labels: List[dict] = []  # [{tag, category_id, category}, ...]
        self._input_name: str = ""
        self._input_size: int = 448    # model input resolution (square)
        super().__init__(device)

    # ── ModelWrapper contract ──────────────────────────────────────────────────

    @classmethod
    def is_available(cls) -> bool:
        """Return True when onnxruntime and huggingface_hub are importable."""
        try:
            import huggingface_hub  # noqa: F401
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        """Download (if needed) and load the ONNX model + label CSV."""
        if self.loaded:
            return

        try:
            import onnxruntime as ort
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise RuntimeError(
                "WDTaggerWrapper requires 'onnxruntime' and 'huggingface_hub'. "
                "Install them with: pip install onnxruntime huggingface-hub"
            ) from exc

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Download model + labels from HuggingFace (cached after first download)
        logger.info("WDTagger: loading model from %s", self.model_repo)
        model_path = hf_hub_download(
            repo_id=self.model_repo,
            filename="model.onnx",
            cache_dir=str(self.cache_dir),
        )
        csv_path = hf_hub_download(
            repo_id=self.model_repo,
            filename="selected_tags.csv",
            cache_dir=str(self.cache_dir),
        )

        # Build ONNX session — prefer CUDA, fall back to CPU
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "cuda" in self.device
            else ["CPUExecutionProvider"]
        )
        opts = ort.SessionOptions()
        opts.log_severity_level = 3  # suppress verbose ONNX logs
        self._session = ort.InferenceSession(
            model_path, sess_options=opts, providers=providers
        )
        self._input_name = self._session.get_inputs()[0].name

        # Infer input resolution from the model's input shape
        input_shape = self._session.get_inputs()[0].shape
        if len(input_shape) == 4 and isinstance(input_shape[2], int):
            self._input_size = input_shape[2]

        # Load tag label map
        self._labels = _load_labels(csv_path)
        logger.info(
            "WDTagger: loaded %d tags, input_size=%d, threshold=%.2f",
            len(self._labels),
            self._input_size,
            self.threshold,
        )

    def unload(self) -> None:
        self._session = None
        self._labels = []
        super().unload()

    # ── Public API ─────────────────────────────────────────────────────────────

    @lazy_load
    def tag(
        self,
        image_path: str,
        threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Tag a single image and return all tags above *threshold*.

        Parameters
        ----------
        image_path : str
            Path to the image file.
        threshold : float, optional
            Per-call override.  Falls back to ``self.threshold``.

        Returns
        -------
        list of dict
            Each dict has keys ``"tag"``, ``"confidence"`` (float 0–1), and
            ``"category"`` (``"general"``, ``"character"``, or ``"copyright"``).
            Sorted by confidence descending.
        """
        thresh = threshold if threshold is not None else self.threshold
        scores = self._run_inference(image_path)
        return _filter_tags(scores, self._labels, thresh)

    @lazy_load
    def tag_batch(
        self,
        image_paths: List[str],
        threshold: Optional[float] = None,
    ) -> List[List[Dict]]:
        """Tag multiple images, returning a list of results in path order."""
        thresh = threshold if threshold is not None else self.threshold
        results = []
        for path in image_paths:
            try:
                scores = self._run_inference(path)
                results.append(_filter_tags(scores, self._labels, thresh))
            except Exception as exc:
                logger.warning("WDTagger: failed to tag %s: %s", path, exc)
                results.append([])
        return results

    @lazy_load
    def tag_with_review(
        self,
        image_path: str,
        threshold: Optional[float] = None,
        review_threshold: float = 0.15,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Tag an image and split results into auto-accepted and review-queue tags
        (§4.4E confidence-threshold option).

        Returns
        -------
        (auto_tags, review_tags)
            *auto_tags*: tags with confidence >= threshold.
            *review_tags*: tags with review_threshold <= confidence < threshold.
        """
        thresh = threshold if threshold is not None else self.threshold
        scores = self._run_inference(image_path)
        auto = _filter_tags(scores, self._labels, thresh)
        review = _filter_tags(scores, self._labels, review_threshold, max_conf=thresh)
        return auto, review

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _run_inference(self, image_path: str) -> np.ndarray:
        """Load, preprocess, and run inference on *image_path*.

        Returns the raw output scores array, shape (num_labels,).
        """
        img = _load_and_preprocess(image_path, self._input_size)
        outputs = self._session.run(None, {self._input_name: img})
        return outputs[0][0]  # shape (num_labels,)


# ── Module-level helpers (no self state) ──────────────────────────────────────

def _load_and_preprocess(image_path: str, size: int) -> np.ndarray:
    """Load an image, resize to (size, size), and return float32 NCHW tensor."""
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    # Composite over white background (WD model was trained on white bg)
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    img = bg.convert("RGB")

    # Pad to square then resize (preserving aspect ratio with white padding)
    w, h = img.size
    max_dim = max(w, h)
    pad_img = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
    pad_img.paste(img, ((max_dim - w) // 2, (max_dim - h) // 2))
    pad_img = pad_img.resize((size, size), Image.BICUBIC)

    # WD model expects BGR float32, shape (1, H, W, C) — NOT NCHW
    arr = np.array(pad_img, dtype=np.float32)
    arr = arr[:, :, ::-1]         # RGB → BGR
    arr = np.expand_dims(arr, 0)  # (H, W, C) → (1, H, W, C)
    return arr


def _load_labels(csv_path: str) -> List[Dict]:
    """Parse the WD selected_tags.csv into a list of label dicts."""
    labels = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat_id = int(row.get("category", 0))
            labels.append({
                "tag": row["name"].replace("_", " "),
                "category_id": cat_id,
                "category": _CATEGORY_NAMES.get(cat_id, "general"),
            })
    return labels


def _filter_tags(
    scores: np.ndarray,
    labels: List[Dict],
    min_conf: float,
    max_conf: float = 1.0,
) -> List[Dict]:
    """Return label dicts for scores in [min_conf, max_conf), sorted by confidence."""
    results = []
    for i, score in enumerate(scores):
        if i >= len(labels):
            break
        conf = float(score)
        if min_conf <= conf < max_conf:
            results.append({**labels[i], "confidence": conf})
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results
