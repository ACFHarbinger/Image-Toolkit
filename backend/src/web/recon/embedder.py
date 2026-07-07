"""Face / CLIP embedding for identity resolution.

``face`` mode uses InsightFace (ArcFace, 512d) when available; ``clip`` mode
reuses the Similarity Finder's embedding chain (MobileCLIP → OpenCLIP →
ResNet-18). Both fall back to a deterministic feature vector so the pipeline
and its tests run without the heavy models installed.
"""

import logging
from typing import Optional

import numpy as np

from .config import EMBED_CLIP, EMBED_FACE

logger = logging.getLogger(__name__)

_FACE_APP = {"app": None, "tried": False}


def _load_insightface():
    if _FACE_APP["tried"]:
        return _FACE_APP["app"]
    _FACE_APP["tried"] = True
    try:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffal_l")
        app.prepare(ctx_id=0, det_size=(640, 640))
        _FACE_APP["app"] = app
        logger.info("InsightFace (ArcFace) loaded")
    except Exception as e:
        logger.info("InsightFace unavailable (%s); using fallback face embedding", e)
    return _FACE_APP["app"]


def _fallback_embedding(image: np.ndarray, dim: int = 512) -> np.ndarray:
    """Deterministic, content-dependent embedding used when no model is present.

    A coarse multi-region color/gradient histogram — not identity-grade, but
    stable and discriminative enough to exercise the index end to end.
    """
    import cv2

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    img = cv2.resize(image[:, :, :3], (64, 64)).astype(np.float32) / 255.0
    feats = []
    for r in range(4):
        for c in range(4):
            block = img[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
            feats.extend(block.mean(axis=(0, 1)))          # 3
            feats.extend(block.std(axis=(0, 1)))           # 3
    vec = np.array(feats, dtype=np.float32)
    if vec.shape[0] < dim:
        vec = np.pad(vec, (0, dim - vec.shape[0]))
    vec = vec[:dim]
    n = np.linalg.norm(vec)
    return vec / n if n > 1e-8 else vec


def embed_face(image: np.ndarray) -> Optional[np.ndarray]:
    """Return a 512d face embedding for the largest detected face, or None."""
    app = _load_insightface()
    if app is not None:
        try:
            faces = app.get(image)
            if faces:
                faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                           reverse=True)
                emb = np.asarray(faces[0].normed_embedding, dtype=np.float32)
                return emb
            return None
        except Exception as e:
            logger.warning("InsightFace inference failed (%s); fallback", e)
    return _fallback_embedding(image)


def embed_clip(image: np.ndarray) -> Optional[np.ndarray]:
    """CLIP embedding for non-human / fictional subjects."""
    try:
        import tempfile

        import cv2

        from backend.src.core.similarity.embedder import get_embedder

        emb = get_embedder("mobileclip")
        if emb is not None:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                cv2.imwrite(tmp.name, image[:, :, [2, 1, 0]] if image.ndim == 3 else image)
                result = emb.embed_batch([tmp.name])
                if result:
                    return next(iter(result.values()))
    except Exception as e:
        logger.info("CLIP embedding unavailable (%s); fallback", e)
    return _fallback_embedding(image)


def embed(image: np.ndarray, mode: str) -> Optional[np.ndarray]:
    if mode == EMBED_FACE:
        return embed_face(image)
    if mode == EMBED_CLIP:
        return embed_clip(image)
    return _fallback_embedding(image)


def embedding_dim(mode: str) -> int:
    return 512
