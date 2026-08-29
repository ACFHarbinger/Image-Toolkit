"""Regression coverage for BiRefNet's bounded batch preprocessing."""

from __future__ import annotations

import numpy as np
import torch

from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper


class _Model:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def __call__(self, batch: torch.Tensor) -> list[torch.Tensor]:
        self.batch_sizes.append(len(batch))
        return [torch.zeros((len(batch), 1, 2, 2), device=batch.device)]


def test_mask_batch_processes_all_chunks_without_index_drift(monkeypatch):
    wrapper = BiRefNetWrapper(device="cpu", inference_size=(4, 4))
    model = _Model()
    monkeypatch.setattr(wrapper, "_ensure_loaded", lambda: model)
    monkeypatch.setattr(wrapper, "_compute_batch_size", lambda: 2)
    images = [np.full((6, 5, 3), value, dtype=np.uint8) for value in range(5)]

    masks = wrapper.get_mask_batch(images, dilate_px=0, erode_px=0)

    assert model.batch_sizes == [2, 2, 1]
    assert [mask.shape for mask in masks] == [(6, 5)] * len(images)


class _OOMOnceModel:
    """Raises a CUDA-style OOM for any batch larger than 1, succeeds at 1."""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def __call__(self, batch: torch.Tensor) -> list[torch.Tensor]:
        self.batch_sizes.append(len(batch))
        if len(batch) > 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 3.75 GiB")
        return [torch.zeros((len(batch), 1, 2, 2), device=batch.device)]


def test_mask_batch_shrinks_chunk_on_oom_instead_of_aborting(monkeypatch):
    wrapper = BiRefNetWrapper(device="cpu", inference_size=(4, 4))
    model = _OOMOnceModel()
    monkeypatch.setattr(wrapper, "_ensure_loaded", lambda: model)
    monkeypatch.setattr(wrapper, "_compute_batch_size", lambda: 4)
    # Force the CUDA-only OOM handling path even though the fake model runs on CPU.
    monkeypatch.setattr(
        "backend.src.models.wrappers.birefnet_wrapper.torch.cuda.empty_cache",
        lambda: None,
    )
    monkeypatch.setattr(
        "backend.src.models.wrappers.birefnet_wrapper.torch.cuda.is_available",
        lambda: True,
    )
    wrapper.device = "cuda"  # gate on_cuda without a real device

    images = [np.full((6, 5, 3), value, dtype=np.uint8) for value in range(5)]
    masks = wrapper.get_mask_batch(images, dilate_px=0, erode_px=0)

    # 4 (OOM) → 2 (OOM) → 1, then every remaining frame runs solo and succeeds.
    assert model.batch_sizes[:2] == [4, 2]
    assert model.batch_sizes[2:] == [1, 1, 1, 1, 1]
    assert [mask.shape for mask in masks] == [(6, 5)] * 5


def test_compute_batch_size_caps_lower_on_small_cards(monkeypatch):
    wrapper = BiRefNetWrapper(device="cuda", inference_size=(1024, 1024))
    bref = "backend.src.models.wrappers.birefnet_wrapper.torch.cuda"
    monkeypatch.setattr(f"{bref}.is_available", lambda: True)
    # 11 GiB free / 12 GiB total → plenty of "usable" but small-card hard cap = 2.
    monkeypatch.setattr(
        f"{bref}.mem_get_info", lambda: (11 * 1024 ** 3, 12 * 1024 ** 3)
    )
    assert wrapper._compute_batch_size() == 2
    # 30 GiB / 48 GiB desktop card → larger hard cap = 3.
    monkeypatch.setattr(
        f"{bref}.mem_get_info", lambda: (30 * 1024 ** 3, 48 * 1024 ** 3)
    )
    assert wrapper._compute_batch_size() == 3
