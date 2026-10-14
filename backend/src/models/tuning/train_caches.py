"""Training memory caches (#756 H4 follow-up) — wire the profile flags.

`xformers`, `cache_latents`, `cache_latents_to_disk`, and
`cache_text_encoder_outputs` are declared in the training profiles but
were consumed by nothing. This module is the consumption side; V2 wires
it with thin calls so the LoC-bloated tuner grows minimally.

Documented semantic costs (kohya-style tradeoffs, logged once at build):

- **Latent caching** encodes the dataset's *deterministic* bucket
  transform (`LoRADatasetV2.base_pixels`) — stochastic photometric
  augmentations (BiRefNet/BaSiC/anime augs) are skipped for cached
  samples. After caching, the VAE is offloaded to CPU.
- **Text-encoder-output caching** freezes the *deterministic* caption
  per sample (shuffle_tags / tag_dropout are ignored while cached);
  `caption_dropout` still works per step by swapping in a cached
  empty-caption embedding. Skipped when the text encoders are being
  trained (they must stay live). Encoders are offloaded after caching.
- **xformers** is opportunistic: try the memory-efficient attention
  backend, fall back to PyTorch SDPA with one logged line.
"""
from __future__ import annotations

import contextlib
import hashlib
import logging
import random
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import torch

log = logging.getLogger(__name__)

_ENCODE_CHUNK = 4
_DISK_CACHE_DIRNAME = ".itk_latent_cache"


def enable_attention_backend(unet, use_xformers: bool) -> bool:
    """Try xformers memory-efficient attention; SDPA fallback is fine.

    PyTorch 2.x SDPA is already memory-efficient by default, so this is
    an opportunistic upgrade, not a correctness switch.
    """
    if not use_xformers:
        return False
    try:
        unet.enable_xformers_memory_efficient_attention()
        log.info("xformers memory-efficient attention enabled")
        return True
    except Exception as exc:
        log.info("xformers unavailable (%s); PyTorch SDPA remains active", exc)
        return False


def _cache_key(sample: Any, base_model: str) -> str:
    raw = f"{sample.image_path}|{tuple(sample.bucket)}|{base_model}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class LatentCache:
    """Per-sample VAE latents over the deterministic bucket transform.

    Memory dict keyed by sample index; optional ``.npz`` persistence under
    ``<images_dir>/.itk_latent_cache/`` so warm runs encode nothing.
    """

    def __init__(
        self,
        dataset,
        *,
        encode_fn: Callable[[torch.Tensor], torch.Tensor],
        images_dir: str | Path,
        base_model: str,
        to_disk: bool,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> None:
        self._dataset = dataset
        self._encode_fn = encode_fn
        self._to_disk = to_disk
        self._device = torch.device(device)
        self._dtype = dtype
        cache_dir = Path(images_dir) / _DISK_CACHE_DIRNAME
        self._cache_dir = cache_dir if to_disk else None
        if to_disk:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                self._cache_dir = None  # read-only images dir: memory-only
        self._paths: list[Path | None] = []
        self._latents: list[torch.Tensor | None] = []
        self.disk_hits = 0
        self.encoded = 0
        for sample in dataset.samples:
            key = _cache_key(sample, base_model)
            path = (self._cache_dir / f"{key}.npz") if self._cache_dir else None
            self._paths.append(path)
            self._latents.append(None)

    def build(self) -> None:
        """Load disk hits, then encode only the misses, in chunks."""
        pending: list[int] = []
        for index in range(len(self._latents)):
            path = self._paths[index]
            if path is not None and path.is_file():
                try:
                    latent = np.load(path)["latent"]
                except (OSError, ValueError, KeyError):
                    latent = None
                if latent is not None:
                    self._latents[index] = torch.from_numpy(latent).to(
                        device=self._device, dtype=self._dtype
                    )
                    self.disk_hits += 1
                    continue
            pending.append(index)

        for start in range(0, len(pending), _ENCODE_CHUNK):
            chunk = pending[start : start + _ENCODE_CHUNK]
            pixels = torch.stack([self._dataset.base_pixels(i)[0].to(self._dtype) for i in chunk])
            latents = self._encode_fn(pixels)
            for offset, index in enumerate(chunk):
                latent = latents[offset].to(device=self._device, dtype=self._dtype)
                self._latents[index] = latent
                self.encoded += 1
                path = self._paths[index]
                if path is not None:
                    with contextlib.suppress(OSError):
                        np.savez(path, latent=latent.detach().cpu().float().numpy())
        if pending:
            log.info(
                "Latent cache: %d disk hits, %d encoded%s",
                self.disk_hits, self.encoded, " (persisted)" if self._cache_dir else "",
            )

    def lookup(self, indices: Sequence[int]) -> torch.Tensor:
        return torch.stack([self._latents[int(i)] for i in indices])


class TextEncoderOutputCache:
    """Per-sample embeddings of the deterministic caption.

    ``embed_fn(caption)`` returns the conditioning the training step
    needs: hidden states for SD1.5, ``(embeds, pooled)`` for SDXL. The
    empty caption is cached too so caption dropout stays a per-step
    decision. Callers must NOT be training the text encoders.
    """

    def __init__(self, captions: Sequence[str], *, embed_fn: Callable[[str], Any]) -> None:
        self._items: list[Any] = []
        self._empty = embed_fn("")
        unique: dict[str, Any] = {}
        for caption in captions:
            if caption not in unique:
                unique[caption] = embed_fn(caption)
        for caption in captions:
            self._items.append(unique[caption])
        log.info(
            "Text-encoder output cache: %d samples, %d unique captions "
            "(shuffle_tags/tag_dropout frozen; caption_dropout still per step)",
            len(captions), len(unique),
        )

    def batch(
        self, indices: Sequence[int], *, dropout: float, generator: random.Random | None = None
    ) -> list[Any]:
        rng = generator or random
        out = []
        for index in indices:
            if dropout > 0 and rng.random() < dropout:
                out.append(self._empty)
            else:
                out.append(self._items[int(index)])
        return out


def deterministic_captions(dataset) -> list[str]:
    """The caption per sample with all per-step randomness disabled —
    what the TE cache freezes. Mirrors `_build_caption`'s assembly
    without dropout/shuffle/tag-drop."""
    captions = []
    for sample in dataset.samples:
        tags = list(sample.pruned_tags)
        if dataset.trigger_word and (not tags or tags[0] != dataset.trigger_word):
            tags.insert(0, dataset.trigger_word)
        caption = ", ".join(tags)
        if sample.caption and sample.caption not in tags:
            caption += ". " + sample.caption
        captions.append(caption)
    return captions


def cached_conditioning(
    cache: TextEncoderOutputCache,
    indices,
    *,
    dropout: float,
    is_sdxl: bool,
    batch: dict,
    bsz: int,
    device,
):
    """Assemble the step's conditioning from the TE cache, mirroring the
    uncached path's defaults (SDXL micro-conditioning included)."""
    items = cache.batch(indices, dropout=dropout)
    if not is_sdxl:
        return torch.stack(items), None
    embeds = torch.stack([item[0] for item in items])
    pooled = torch.stack([item[1] for item in items])
    orig = batch.get("original_size", torch.tensor([[1024, 1024]] * bsz)).to(device)
    tgt = batch.get("target_size", torch.tensor([[1024, 1024]] * bsz)).to(device)
    ctl = batch.get("crop_top_left", torch.zeros(bsz, 2)).to(device)
    time_ids = torch.cat([orig, ctl, tgt], dim=-1).to(dtype=embeds.dtype)
    return embeds, {"text_embeds": pooled, "time_ids": time_ids}


def offload_to_cpu(module) -> None:
    """Free a model's VRAM after its outputs are cached. Safe no-op on CPU."""
    try:
        if any(p.is_cuda for p in module.parameters()):
            module.to("cpu")
            torch.cuda.empty_cache()
    except Exception as exc:  # pragma: no cover - offload is best-effort
        log.debug("offload failed (%s); continuing", exc)


__all__ = [
    "LatentCache",
    "TextEncoderOutputCache",
    "cached_conditioning",
    "deterministic_captions",
    "enable_attention_backend",
    "offload_to_cpu",
]
