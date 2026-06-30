"""Build a FAISS index from a trained CBIR checkpoint.

Called after training completes (via the "Build FAISS Index" button in the GUI
or from the CLI) to encode the user's image library and persist the retrieval
index that :class:`~backend.src.core.cbir_search.LocalCBIRSearch` reads.

This module belongs here (models/tuning/) because it is a direct post-training
step: it consumes a CBIRModel checkpoint and produces the artefacts that the
retrieval layer reads.

Output files
------------
``<output_dir>/clip_index.faiss``
    FAISS IndexFlatIP (inner-product similarity on L2-normalised vectors).

``<output_dir>/clip_paths.json``
    JSON array mapping FAISS vector position → absolute image path.

``<output_dir>/cbir_build_meta.json``
    Snapshot of build parameters (checkpoint path, backbone, embed_dim, …).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import torch
import numpy as np

from backend.src.models.data.cbir_dataset import scan_images

log = logging.getLogger(__name__)

_DEFAULT_INDEX_DIR = Path.home() / ".image-toolkit" / "cbir_index"
_BATCH_SIZE = 64


def load_cbir_model(checkpoint_path: str):
    """Load a :class:`~backend.src.models.tuning.cbir_tuner.CBIRModel` from a
    saved checkpoint.

    Args:
        checkpoint_path: Path to a ``cbir_best.pt`` or ``cbir_final.pt`` file
            produced by :class:`~backend.src.models.tuning.cbir_tuner.CBIRTuner`.

    Returns:
        ``(model, config)`` where ``model`` is the loaded :class:`CBIRModel`
        in ``eval()`` mode and ``config`` is the saved training config dict.

    Raises:
        FileNotFoundError: If the checkpoint file does not exist.
        KeyError: If the checkpoint lacks the expected keys.
    """
    from backend.src.models.tuning.cbir_tuner import _build_model

    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    model = _build_model(
        backbone=cfg["backbone"],
        embed_dim=cfg["embed_dim"],
        proj_layers=cfg.get("proj_layers", 2),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    log.info(
        "Loaded CBIR model: backbone=%s embed_dim=%d epoch=%d R@1=%.3f",
        cfg["backbone"],
        cfg["embed_dim"],
        ckpt.get("epoch", -1),
        ckpt.get("best_recall_at_1", 0.0),
    )
    return model, cfg


def build_cbir_index(
    checkpoint_path: str,
    image_dir: str,
    output_dir: Optional[str] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[int, str]:
    """Encode every image in *image_dir* and write a FAISS retrieval index.

    Args:
        checkpoint_path: Path to a trained CBIR checkpoint (``.pt`` file).
        image_dir: Root directory to scan for images.
        output_dir: Directory where ``clip_index.faiss`` and
            ``clip_paths.json`` are written.  Defaults to
            ``~/.image-toolkit/cbir_index/``.
        on_progress: Optional callback ``(n_done, n_total) → None`` for
            progress reporting.

    Returns:
        ``(n_indexed, index_path)`` — number of images indexed and the path
        to the written ``.faiss`` file.

    Raises:
        ImportError: If ``faiss`` is not installed.
        FileNotFoundError: If no images are found in *image_dir*.
    """
    try:
        import faiss  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "faiss is not installed.  Add 'faiss-cpu>=1.7.4' to pyproject.toml."
        ) from exc

    out_dir = Path(output_dir) if output_dir else _DEFAULT_INDEX_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    model, cfg = load_cbir_model(checkpoint_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    preprocess = _make_preprocess(cfg["backbone"], cfg.get("image_size", 224))

    image_paths = scan_images(image_dir)
    if not image_paths:
        raise FileNotFoundError(f"No images found under: {image_dir}")

    log.info("Encoding %d images with backbone=%s…", len(image_paths), cfg["backbone"])
    t0 = time.perf_counter()

    embeddings: List[np.ndarray] = []
    valid_paths: List[str] = []

    for batch_start in range(0, len(image_paths), _BATCH_SIZE):
        batch_paths = image_paths[batch_start : batch_start + _BATCH_SIZE]
        tensors = _load_batch(batch_paths, preprocess)
        if tensors is None or tensors.size(0) == 0:
            continue

        with torch.no_grad():
            emb = model(tensors.to(device)).cpu().numpy()

        embeddings.append(emb)
        valid_paths.extend(batch_paths[: emb.shape[0]])

        if on_progress:
            on_progress(batch_start + len(batch_paths), len(image_paths))

    if not embeddings:
        raise RuntimeError("No images could be encoded — check that they are valid image files.")

    all_embs = np.concatenate(embeddings, axis=0).astype(np.float32)
    n_total, embed_dim = all_embs.shape

    # Normalise (models already L2-normalise output, but enforce for safety)
    norms = np.linalg.norm(all_embs, axis=1, keepdims=True).clip(min=1e-12)
    all_embs = all_embs / norms

    # Inner-product index = cosine similarity on unit vectors
    index = faiss.IndexFlatIP(embed_dim)
    index.add(all_embs)

    index_path = out_dir / "clip_index.faiss"
    paths_path = out_dir / "clip_paths.json"
    meta_path  = out_dir / "cbir_build_meta.json"

    faiss.write_index(index, str(index_path))

    with open(paths_path, "w", encoding="utf-8") as fh:
        json.dump(valid_paths, fh, ensure_ascii=False, indent=2)

    elapsed = time.perf_counter() - t0
    meta = {
        "checkpoint": str(checkpoint_path),
        "image_dir": str(image_dir),
        "backbone": cfg["backbone"],
        "embed_dim": embed_dim,
        "n_indexed": n_total,
        "build_time_s": round(elapsed, 2),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    log.info(
        "FAISS index written: %s  (%d vectors, %.1fs)",
        index_path, n_total, elapsed,
    )
    return n_total, str(index_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_preprocess(backbone: str, image_size: int):
    from backend.src.models.data.cbir_dataset import (
        make_clip_preprocess,
        make_imagenet_preprocess,
    )
    if backbone == "clip":
        return make_clip_preprocess(image_size)
    return make_imagenet_preprocess(image_size)


def _load_batch(paths: List[str], preprocess) -> Optional[torch.Tensor]:
    from PIL import Image as PILImage

    tensors = []
    for p in paths:
        try:
            with PILImage.open(p) as img:
                tensors.append(preprocess(img.convert("RGB")))
        except Exception as exc:
            log.warning("Skipping %s: %s", p, exc)

    if not tensors:
        return None
    return torch.stack(tensors)
