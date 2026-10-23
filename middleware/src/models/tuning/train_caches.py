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
    # ``vae-range:-1_1`` retires disk entries written when the cache fed the
    # VAE [0, 1] pixels. Those latents are not the live step's [-1, 1] encode.
    raw = f"{sample.image_path}|{tuple(sample.bucket)}|{base_model}|vae-range:-1_1"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _bucket_key(sample: Any) -> tuple[int, int]:
    """Spatial group for one encode chunk. ``base_pixels`` is the bucket size."""
    width, height = sample.bucket
    return int(width), int(height)


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

        grouped: dict[tuple[int, int], list[int]] = {}
        for index in pending:
            grouped.setdefault(_bucket_key(self._dataset.samples[index]), []).append(index)
        for indices in grouped.values():
            self._encode_bucket(indices)
        log.info(
            "Latent cache: %d disk hits, %d encoded%s",
            self.disk_hits, self.encoded, " (persisted)" if self._cache_dir else "",
        )

    def _encode_bucket(self, indices: Sequence[int]) -> None:
        """Encode one bucket. Mixed aspect ratios are different spatial sizes."""
        for start in range(0, len(indices), _ENCODE_CHUNK):
            chunk = list(indices[start : start + _ENCODE_CHUNK])
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


def encode_pixels_to_latents(tuner, pixels: torch.Tensor) -> torch.Tensor:
    """Encode CHW [0, 1] bucket pixels to scaled VAE latents.

    ``base_pixels`` is [0, 1]. The uncached step encodes ``pixel_values``,
    which the dataset has already mapped to [-1, 1]. Apply that same map
    here so a cached latent matches a live encode of the unaugmented image.
    """
    with torch.no_grad():
        px = (pixels * 2.0 - 1.0).to(device=tuner.accelerator.device, dtype=tuner.vae.dtype)
        latents = tuner.vae.encode(px).latent_dist.sample()
        return latents * tuner.vae.config.scaling_factor


def encode_caption(tuner, caption: str):
    """Encode a single caption string for TextEncoderOutputCache."""
    with torch.no_grad():
        if tuner.is_sdxl:
            embeds, pooled = tuner.encode_prompt_sdxl([caption])
            return embeds[0], pooled[0]
        tok = tuner.tokenizer_one(
            caption,
            padding="max_length",
            max_length=tuner.tokenizer_one.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        ids = tok.input_ids.to(tuner.text_encoder_one.device)
        return tuner.text_encoder_one(ids)[0][0]


def build_tuner_caches(tuner, dataloader) -> None:
    """Build the latent / text-encoder caches declared on ``tuner.cfg``."""
    cfg = tuner.cfg
    tuner._latent_cache = None
    tuner._te_cache = None
    tuner._te_dropout = 0.0
    dataset = getattr(dataloader, "dataset", None)
    if dataset is None or not hasattr(dataset, "samples") or not dataset.samples:
        return
    if getattr(cfg, "cache_latents", False):
        tuner._latent_cache = LatentCache(
            dataset,
            encode_fn=lambda px: encode_pixels_to_latents(tuner, px),
            images_dir=dataset.samples[0].image_path.parent,
            base_model=cfg.base_model_path,
            to_disk=bool(getattr(cfg, "cache_latents_to_disk", False)),
            device=tuner.accelerator.device,
            dtype=tuner.vae.dtype,
        )
        tuner._latent_cache.build()
        offload_to_cpu(tuner.vae)
    if getattr(cfg, "cache_text_encoder_outputs", False):
        if cfg.train_text_encoder_one or cfg.train_text_encoder_two:
            log.info("Text encoders are being trained; TE-output caching skipped")
        else:
            tuner._te_cache = TextEncoderOutputCache(
                deterministic_captions(dataset),
                embed_fn=lambda cap: encode_caption(tuner, cap),
            )
            tuner._te_dropout = float(getattr(dataset, "caption_dropout", 0.0))
            offload_to_cpu(tuner.text_encoder_one)
            if getattr(tuner, "text_encoder_two", None) is not None:
                offload_to_cpu(tuner.text_encoder_two)


def step_latents(tuner, batch: dict) -> torch.Tensor:
    """Step latents: cache lookup when cached, else a live VAE encode."""
    with torch.no_grad():
        if getattr(tuner, "_latent_cache", None) is not None:
            return tuner._latent_cache.lookup(batch["sample_index"])
        px = batch["pixel_values"].to(dtype=tuner.vae.dtype)
        latents = tuner.vae.encode(px).latent_dist.sample()
        return latents * tuner.vae.config.scaling_factor


def step_conditioning(tuner, batch: dict, bsz: int, device):
    """Step conditioning: TE cache lookup when cached, else live encoders."""
    if getattr(tuner, "_te_cache", None) is not None:
        return cached_conditioning(
            tuner._te_cache,
            batch["sample_index"],
            dropout=getattr(tuner, "_te_dropout", 0.0),
            is_sdxl=tuner.is_sdxl,
            batch=batch,
            bsz=bsz,
            device=device,
        )
    if tuner.is_sdxl:
        prompt_embeds, pooled = tuner.encode_prompt_sdxl(
            batch.get("prompt", [""] * bsz)
            if "prompt" in batch
            else tuner._ids_to_prompts(batch.get("input_ids_one"))
        )
        orig = batch.get("original_size", torch.tensor([[1024, 1024]] * bsz)).to(device)
        tgt = batch.get("target_size", torch.tensor([[1024, 1024]] * bsz)).to(device)
        ctl = batch.get("crop_top_left", torch.zeros(bsz, 2)).to(device)
        time_ids = torch.cat([orig, ctl, tgt], dim=-1).to(dtype=prompt_embeds.dtype)
        return prompt_embeds, {"text_embeds": pooled, "time_ids": time_ids}
    input_ids = batch["input_ids_one"].to(tuner.accelerator.device)
    with torch.no_grad():
        return tuner.text_encoder_one(input_ids)[0], None


__all__ = [
    "LatentCache",
    "TextEncoderOutputCache",
    "build_tuner_caches",
    "cached_conditioning",
    "deterministic_captions",
    "enable_attention_backend",
    "encode_caption",
    "encode_pixels_to_latents",
    "offload_to_cpu",
    "step_conditioning",
    "step_latents",
]
