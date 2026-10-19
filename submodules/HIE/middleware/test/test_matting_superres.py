"""Unit tests for MattingAdapter and SuperResolutionAdapter model contracts."""

import pytest
from models import (
    MattingAdapter,
    MattingModel,
    ModelUnavailable,
    SuperResolutionAdapter,
    SuperResModel,
)


def test_matting_adapter_unavailable():
    adapter = MattingAdapter()
    assert not adapter.is_available()
    with pytest.raises(ModelUnavailable):
        adapter.propose("canvas_01.png")


def test_matting_adapter_available_propose():
    adapter = MattingModel(
        backend="torch",
        weights_uri="https://example.com/birefnet.pth",
    )
    assert adapter.is_available()
    proposal = adapter.propose(
        "canvas_01.png",
        fg_points=[(100, 100)],
        box=(50, 50, 200, 200),
        feather_radius=3,
    )
    assert proposal.operation == "matting"
    assert proposal.confidence == 0.95
    assert proposal.payload["fg_points"] == [(100, 100)]
    assert proposal.payload["box"] == (50, 50, 200, 200)
    assert proposal.payload["feather_radius"] == 3


def test_superres_adapter_scale_validation():
    with pytest.raises(ValueError, match="super-resolution scale must be between 2 and 8"):
        SuperResolutionAdapter(scale=1)

    with pytest.raises(ValueError, match="super-resolution scale must be between 2 and 8"):
        SuperResolutionAdapter(scale=16)


def test_superres_adapter_available_propose():
    adapter = SuperResModel(
        backend="torch",
        weights_uri="https://example.com/esrgan.pth",
        scale=4,
        tile_size=512,
    )
    assert adapter.is_available()
    proposal = adapter.propose("input_01.png", scale=8, tile_size=256)

    assert proposal.operation == "upscale"
    assert proposal.payload["scale"] == 8
    assert proposal.payload["tile_size"] == 256
    assert proposal.payload["model_variant"] == "RealESRGAN_x4plus"
