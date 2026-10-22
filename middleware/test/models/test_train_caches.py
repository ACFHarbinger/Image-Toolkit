"""#756 H4 wiring: the training memory caches (train_caches.py) + dataset hooks.

CPU-only: real PIL images in tmp_path, stub encoders/VAEs — no model
downloads, no GPU. The V2 loop integration is smoke-checked via the
decision helpers; a live GPU run is reported on the bus separately.
"""
import random
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from middleware.src.models.tuning.lo_ra_tuner_config import LoRATunerConfig
from middleware.src.models.tuning.train_caches import (
    LatentCache,
    TextEncoderOutputCache,
    cached_conditioning,
    deterministic_captions,
    enable_attention_backend,
    encode_pixels_to_latents,
    offload_to_cpu,
)


def _image(path, size=(64, 64), color=(120, 40, 200)):
    Image.new("RGB", size, color).save(path)


@pytest.fixture
def samples(tmp_path):
    paths = []
    for i in range(5):
        path = tmp_path / f"img_{i}.png"
        _image(path, color=(20 * i, 40, 60))
        paths.append(path)
    return [
        SimpleNamespace(
            image_path=p, bucket=(64, 64), original_size=(64, 64),
            pruned_tags=[f"tag{i}", "common"], caption="",
        )
        for i, p in enumerate(paths)
    ], tmp_path


class _FakeDataset:
    def __init__(self, samples):
        self.samples = samples
        self.trigger_word = "mychar"
        self.caption_dropout = 0.0

    def base_pixels(self, idx):
        img = torch.full((3, 64, 64), float(idx + 1) / 16.0)
        return img, (0, 0)


def _identity_encode(pixels):
    return pixels.mean(dim=(2, 3), keepdim=False)  # (N, 3) "latents"


# ---------------------------------------------------------------------------
# LatentCache
# ---------------------------------------------------------------------------


def test_latent_cache_encodes_each_sample_once(samples):
    (items, tmp_path) = samples
    dataset = _FakeDataset(items)
    calls = []

    def encode(pixels):
        calls.append(pixels.shape[0])
        return _identity_encode(pixels)

    cache = LatentCache(
        dataset, encode_fn=encode, images_dir=tmp_path,
        base_model="some/model", to_disk=False, device="cpu", dtype=torch.float32,
    )
    cache.build()
    assert cache.encoded == len(items)
    assert cache.disk_hits == 0
    assert sum(calls) == len(items)  # chunked, no double encodes
    latents = cache.lookup([0, 2, 4])
    assert latents.shape == (3, 3)
    assert torch.allclose(latents[0], torch.full((3,), 1 / 16.0))


def test_latent_cache_disk_round_trip_skips_encoding(samples):
    (items, tmp_path) = samples
    dataset = _FakeDataset(items)

    def encode(pixels):
        raise AssertionError("warm run must not encode anything")

    cache = LatentCache(
        dataset, encode_fn=_identity_encode, images_dir=tmp_path,
        base_model="some/model", to_disk=True, device="cpu", dtype=torch.float32,
    )
    cache.build()
    assert cache.encoded == len(items)

    # Second build over the same dir: everything is a disk hit.
    cold_values = [t.clone() for t in cache._latents]
    cache2 = LatentCache(
        dataset, encode_fn=encode, images_dir=tmp_path,
        base_model="some/model", to_disk=True, device="cpu", dtype=torch.float32,
    )
    cache2.build()
    assert cache2.disk_hits == len(items)
    assert cache2.encoded == 0
    assert torch.allclose(cache2.lookup(range(len(items))), torch.stack(cold_values))
    assert (tmp_path / ".itk_latent_cache").is_dir()


def test_latent_cache_encodes_each_bucket_on_its_own(tmp_path):
    """Mixed aspect ratios must not be stacked into one VAE batch."""
    buckets = [(64, 64), (64, 64), (32, 64), (96, 64), (64, 48)]
    items = []
    for i, bucket in enumerate(buckets):
        path = tmp_path / f"mix_{i}.png"
        _image(path, size=bucket)
        items.append(SimpleNamespace(
            image_path=path, bucket=bucket, original_size=bucket,
            pruned_tags=[], caption="",
        ))

    class _BucketDataset(_FakeDataset):
        def base_pixels(self, idx):
            width, height = self.samples[idx].bucket
            img = torch.zeros(3, height, width)
            return img, (0, 0)

    seen = []

    def encode(pixels):
        seen.append(tuple(pixels.shape))
        return pixels.mean(dim=(1, 2, 3), keepdim=True)

    cache = LatentCache(
        _BucketDataset(items), encode_fn=encode, images_dir=tmp_path,
        base_model="some/model", to_disk=False, device="cpu", dtype=torch.float32,
    )
    cache.build()
    assert cache.encoded == len(items)
    assert seen == [(2, 3, 64, 64), (1, 3, 64, 32), (1, 3, 64, 96), (1, 3, 48, 64)]
    assert cache.lookup([0, 1]).shape[0] == 2


def test_encode_pixels_matches_the_uncached_vae_range():
    seen = {}

    class _Vae:
        dtype = torch.float32

        class config:
            scaling_factor = 0.5

        def encode(self, pixels):
            seen["pixels"] = pixels.detach().clone()

            class _Dist:
                def sample(self):
                    return pixels

            return SimpleNamespace(latent_dist=_Dist())

    tuner = SimpleNamespace(
        accelerator=SimpleNamespace(device=torch.device("cpu")),
        vae=_Vae(),
    )
    pixels = torch.zeros(2, 3, 4, 4)
    pixels[0] = 0.0
    pixels[1] = 1.0
    latents = encode_pixels_to_latents(tuner, pixels)
    assert torch.equal(seen["pixels"][0], torch.full((3, 4, 4), -1.0))
    assert torch.equal(seen["pixels"][1], torch.ones(3, 4, 4))
    assert torch.allclose(latents, seen["pixels"] * 0.5)


def test_latent_cache_keys_change_with_bucket_and_model(samples):
    (items, tmp_path) = samples
    dataset = _FakeDataset(items)
    first = LatentCache(
        dataset, encode_fn=_identity_encode, images_dir=tmp_path,
        base_model="model-a", to_disk=True, device="cpu", dtype=torch.float32,
    )
    first.build()
    rebucketed = _FakeDataset([
        SimpleNamespace(
            image_path=items[0].image_path, bucket=(32, 32),
            original_size=(64, 64), pruned_tags=[], caption="",
        )
    ])
    second = LatentCache(
        rebucketed, encode_fn=_identity_encode, images_dir=tmp_path,
        base_model="model-a", to_disk=True, device="cpu", dtype=torch.float32,
    )
    second.build()
    assert second.disk_hits == 0  # different bucket → different key
    third = LatentCache(
        _FakeDataset(items[:1]), encode_fn=_identity_encode, images_dir=tmp_path,
        base_model="model-b", to_disk=True, device="cpu", dtype=torch.float32,
    )
    third.build()
    assert third.disk_hits == 0  # different base model → different key


# ---------------------------------------------------------------------------
# TextEncoderOutputCache + conditioning
# ---------------------------------------------------------------------------


def test_te_cache_dedupes_and_swaps_dropout(samples):
    (items, _tmp) = samples
    captions = [f"{i} girl, common" for i in range(5)]
    captions[4] = captions[3]  # one duplicate
    embed_calls = []

    def embed(caption):
        embed_calls.append(caption)
        return torch.full((4,), float(len(embed_calls)))

    cache = TextEncoderOutputCache(captions, embed_fn=embed)
    # 4 unique captions + 1 empty for dropout — the duplicate was deduped.
    assert len(embed_calls) == 5

    rng = random.Random(7)
    kept = cache.batch([0, 3, 4], dropout=0.0, generator=rng)
    # captions[3] and captions[4] are the same string → one shared embedding.
    assert torch.equal(kept[1], kept[2])

    dropped = cache.batch([0, 1, 2], dropout=1.0, generator=rng)
    assert all(torch.equal(item, cache._empty) for item in dropped)

    # Seeded dropout is reproducible.
    a = cache.batch(range(5), dropout=0.5, generator=random.Random(3))
    b = cache.batch(range(5), dropout=0.5, generator=random.Random(3))
    assert all(torch.equal(x, y) for x, y in zip(a, b, strict=True))


def test_cached_conditioning_shapes():
    # SDXL path: items are (embeds, pooled) pairs.
    cache = TextEncoderOutputCache(
        ["a", "b"], embed_fn=lambda c: (torch.ones(77, 8), torch.full((32,), 2.0))
    )
    embeds, kwargs = cached_conditioning(
        cache, [0, 1], dropout=0.0, is_sdxl=True,
        batch={}, bsz=2, device="cpu",
    )
    assert embeds.shape == (2, 77, 8)
    assert kwargs["text_embeds"].shape == (2, 32)
    assert kwargs["time_ids"].shape == (2, 6)  # default micro-conditioning

    # SD1.5 path: plain hidden states, no micro-conditioning.
    cache15 = TextEncoderOutputCache(["a"], embed_fn=lambda c: torch.zeros(77, 8))
    states, no_kwargs = cached_conditioning(
        cache15, [0], dropout=0.0, is_sdxl=False, batch={}, bsz=1, device="cpu",
    )
    assert states.shape == (1, 77, 8)
    assert no_kwargs is None


def test_deterministic_captions_freeze_the_assembly(samples):
    (items, _tmp) = samples
    dataset = _FakeDataset(items)
    captions = deterministic_captions(dataset)
    assert captions[0] == "mychar, tag0, common"
    # Reproducible: no per-step randomness participates.
    assert deterministic_captions(dataset) == captions


# ---------------------------------------------------------------------------
# Attention backend + offload
# ---------------------------------------------------------------------------


def test_xformers_is_opportunistic():
    class Good:
        def enable_xformers_memory_efficient_attention(self):
            self.enabled = True

    class Bad:
        def enable_xformers_memory_efficient_attention(self):
            raise ModuleNotFoundError("No module named 'xformers'")

    class NoMethod:
        pass

    good = Good()
    assert enable_attention_backend(good, True) is True
    assert good.enabled
    for stub in (Bad(), NoMethod()):
        assert enable_attention_backend(stub, True) is False  # SDPA fallback, logged
    assert enable_attention_backend(Good(), False) is False  # flag off: untouched


def test_offload_to_cpu_is_noop_on_cpu_modules():
    module = torch.nn.Linear(2, 2)
    offload_to_cpu(module)  # CPU params: nothing to do, no crash
    assert module.weight.device.type == "cpu"


# ---------------------------------------------------------------------------
# Config + dataset integration
# ---------------------------------------------------------------------------


def test_config_flags_default_off_and_present():
    cfg = LoRATunerConfig()
    assert (cfg.xformers, cfg.cache_latents, cfg.cache_latents_to_disk, cfg.cache_text_encoder_outputs) == (
        False, False, False, False,
    )


def test_build_tuner_passes_the_flags(monkeypatch, samples):
    import middleware.src.pipeline.anime_training_pipeline as pipeline

    captured = {}

    class _StubTuner:
        def __init__(self, config):
            captured["cfg"] = config

    monkeypatch.setattr(pipeline, "LoRATunerV2", _StubTuner)
    cfg = {
        "model": {"model_id": "some/model"},
        "training": {
            "method": "peft",
            "xformers": True,
            "cache_latents": True,
            "cache_latents_to_disk": True,
            "cache_text_encoder_outputs": True,
        },
        "optimizer": {},
        "output_dir": "out",
    }
    tuner = pipeline._build_tuner(cfg)
    assert isinstance(tuner, _StubTuner)
    built = captured["cfg"]
    assert built.xformers and built.cache_latents
    assert built.cache_latents_to_disk and built.cache_text_encoder_outputs
    assert built.base_model_path == "some/model"


class _StubTokenizer:
    model_max_length = 77

    def __call__(self, caption, **kwargs):
        return SimpleNamespace(input_ids=torch.zeros(1, 77, dtype=torch.long))


def test_dataset_base_pixels_and_sample_index(samples):
    from middleware.src.models.data.lora_dataset import LoRADatasetV2

    (items, tmp_path) = samples
    dataset = LoRADatasetV2(
        samples=items, tokenizer_one=_StubTokenizer(), tokenizer_two=None,
        trigger_word="mychar", shuffle_tags=True, caption_dropout=0.0,
        augmentations=[],
    )
    base, crop_tl = dataset.base_pixels(0)
    assert base.shape == (3, 64, 64)
    assert 0.0 <= float(base.min()) <= float(base.max()) <= 1.0

    item = dataset[0]
    assert item["sample_index"] == 0
    # Without augmentations the step pixels are exactly base*2-1.
    assert torch.allclose(item["pixel_values"], base * 2.0 - 1.0)
    assert crop_tl == (0, 0)
