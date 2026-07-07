"""Local embedding models for Tier 4 (semantic) similarity.

Model selection (``SimilarityConfig.embed_model``):
    "mobileclip"  — MobileCLIP-S0 via open_clip (fast, small)
    "openclip"    — ViT-B-32 via open_clip (stronger, slower)
    "resnet18"    — torchvision ResNet-18 feature extractor (always available
                    when torch is installed; same backbone as the legacy
                    Siamese scan)

All models are lazy-loaded singletons; ``unload()`` frees VRAM after a scan.
Embedding generation runs in Python worker threads (torch releases the GIL
during forward passes); indexing/search happens in C++ (base.similarity.HnswIndex).
"""

import logging
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_ACTIVE: Dict[str, "BaseEmbedder"] = {}


class BaseEmbedder:
    name = "base"
    dim = 0

    def embed_batch(self, paths: List[str], batch_size: int = 16) -> Dict[str, np.ndarray]:
        raise NotImplementedError

    def unload(self):
        pass


class _TorchEmbedder(BaseEmbedder):
    """Common torch batching loop; subclasses provide model + preprocess."""

    def __init__(self):
        self._model = None
        self._preprocess = None
        self._device = None

    def _load(self):
        raise NotImplementedError

    def embed_batch(self, paths: List[str], batch_size: int = 16) -> Dict[str, np.ndarray]:
        import torch
        from PIL import Image

        if self._model is None:
            self._load()

        out: Dict[str, np.ndarray] = {}
        batch_tensors, batch_paths = [], []

        def flush():
            if not batch_tensors:
                return
            stacked = torch.stack(batch_tensors).to(self._device)
            with torch.no_grad():
                feats = self._forward(stacked)
            feats = feats.float().cpu().numpy()
            for p, v in zip(batch_paths, feats, strict=False):
                out[p] = np.asarray(v, dtype=np.float32).flatten()
            batch_tensors.clear()
            batch_paths.clear()

        for path in paths:
            try:
                with Image.open(path) as img:
                    tensor = self._preprocess(img.convert("RGB"))
            except Exception as e:
                logger.warning("Embedding skipped for %s: %s", path, e)
                continue
            batch_tensors.append(tensor)
            batch_paths.append(path)
            if len(batch_tensors) >= batch_size:
                flush()
        flush()
        return out

    def _forward(self, batch):
        return self._model(batch)

    def unload(self):
        if self._model is not None:
            del self._model
            self._model = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


class OpenClipEmbedder(_TorchEmbedder):
    """open_clip image tower. Used for both "openclip" and "mobileclip"."""

    def __init__(self, arch: str, pretrained: str, name: str, dim: int):
        super().__init__()
        self.arch = arch
        self.pretrained = pretrained
        self.name = name
        self.dim = dim

    def _load(self):
        import open_clip
        import torch

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.arch, pretrained=self.pretrained
        )
        model.to(self._device).eval()
        self._model = model
        self._preprocess = preprocess

    def _forward(self, batch):
        return self._model.encode_image(batch)


class ResNetEmbedder(_TorchEmbedder):
    """torchvision ResNet-18 with the classifier head removed (512-dim)."""

    name = "resnet18"
    dim = 512

    def _load(self):
        import torch
        import torchvision.models as models

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        weights = models.ResNet18_Weights.DEFAULT
        model = models.resnet18(weights=weights)
        model.fc = torch.nn.Identity()
        model.to(self._device).eval()
        self._model = model
        self._preprocess = weights.transforms()


def get_embedder(model_name: str) -> Optional[BaseEmbedder]:
    """Return a cached embedder, falling back gracefully:
    mobileclip → openclip → resnet18 → None (semantic tier disabled)."""
    order = {
        "mobileclip": ["mobileclip", "openclip", "resnet18"],
        "openclip": ["openclip", "resnet18"],
        "resnet18": ["resnet18"],
    }.get(model_name, ["resnet18"])

    for candidate in order:
        if candidate in _ACTIVE:
            return _ACTIVE[candidate]
        try:
            if candidate == "mobileclip":
                import open_clip  # noqa: F401

                emb = OpenClipEmbedder(
                    "MobileCLIP-S0", "datacompdr", "mobileclip", 512
                )
            elif candidate == "openclip":
                import open_clip  # noqa: F401

                emb = OpenClipEmbedder("ViT-B-32", "laion2b_s34b_b79k", "openclip", 512)
            else:
                import torch  # noqa: F401
                import torchvision  # noqa: F401

                emb = ResNetEmbedder()
            _ACTIVE[candidate] = emb
            if candidate != model_name:
                logger.info("Embed model '%s' unavailable, using '%s'.", model_name, candidate)
            return emb
        except ImportError:
            continue
    logger.warning("No embedding backend available — semantic tier disabled.")
    return None


def unload_all():
    for emb in _ACTIVE.values():
        emb.unload()
    _ACTIVE.clear()
