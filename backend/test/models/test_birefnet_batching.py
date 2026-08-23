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
