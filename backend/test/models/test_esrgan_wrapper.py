"""Tests for backend/src/models/wrappers/esrgan_wrapper.py — Content Gen §1.6."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
import torch

from backend.src.errors import ModelLoadError
from backend.src.models.wrappers.esrgan_wrapper import (
    ANIME_6B_MODEL,
    ANIME_6B_MODEL_FALLBACK,
    RRDB,
    ESRGANWrapper,
    ResidualDenseBlock,
    RRDBNet,
)


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """ESRGANWrapper._models is a class-level cache keyed on
    (model_name, num_block, device) -- clear it around every test so one
    test's cached model doesn't short-circuit another's load() call."""
    ESRGANWrapper._models.clear()
    yield
    ESRGANWrapper._models.clear()


# ── Architecture shape tests (random init, no network/weights needed) ──────


def test_residual_dense_block_preserves_spatial_shape():
    block = ResidualDenseBlock(num_feat=8, num_grow_ch=4)
    x = torch.randn(1, 8, 16, 16)
    out = block(x)
    assert out.shape == x.shape


def test_rrdb_preserves_spatial_shape():
    block = RRDB(num_feat=8, num_grow_ch=4)
    x = torch.randn(1, 8, 16, 16)
    out = block(x)
    assert out.shape == x.shape


@pytest.mark.parametrize("num_block", [1, 3, 6])
def test_rrdbnet_upscales_by_4x(num_block):
    net = RRDBNet(num_feat=8, num_block=num_block, num_grow_ch=4)
    net.eval()
    x = torch.randn(1, 3, 20, 24)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (1, 3, 80, 96)


def test_rrdbnet_matches_real_checkpoint_key_structure():
    """The real anime_6B checkpoint has exactly 6 RRDB blocks (body.0..body.5)
    and num_feat=64 -- verified by downloading and inspecting the actual
    state dict before writing this architecture (see module docstring).
    This test locks that structural assumption without needing the network:
    a num_block=6, num_feat=64 net's state_dict key set must be a strict
    match for what the real checkpoint provides."""
    net = RRDBNet(num_feat=64, num_block=6, num_grow_ch=32)
    keys = set(net.state_dict().keys())
    assert "conv_first.weight" in keys
    assert "body.5.rdb3.conv5.weight" in keys
    assert "body.6.rdb1.conv1.weight" not in keys  # exactly 6 blocks, 0-indexed
    assert "conv_up1.weight" in keys and "conv_up2.weight" in keys
    assert "conv_hr.weight" in keys and "conv_last.weight" in keys


# ── Wrapper load() fallback logic (mocked weight loading, no network) ──────


def _fake_state_dict(num_block=1, num_feat=8, num_grow_ch=4):
    return RRDBNet(num_feat=num_feat, num_block=num_block, num_grow_ch=num_grow_ch).state_dict()


def test_load_uses_primary_repo_when_available():
    wrapper = ESRGANWrapper(device="cpu", num_block=1)
    with patch.object(
        ESRGANWrapper, "_load_state_dict", return_value=_fake_state_dict()
    ) as mock_load, patch.object(RRDBNet, "__init__", RRDBNet.__init__):
        # Patch RRDBNet construction to match the fake state dict's small dims.
        with patch(
            "backend.src.models.wrappers.esrgan_wrapper.RRDBNet",
            lambda num_block: RRDBNet(num_feat=8, num_block=num_block, num_grow_ch=4),
        ):
            wrapper.load()
    mock_load.assert_called_once_with(ANIME_6B_MODEL)
    assert wrapper.loaded


def test_load_falls_back_to_secondary_repo_on_primary_failure():
    wrapper = ESRGANWrapper(device="cpu", num_block=1)
    calls = []

    def _side_effect(repo_id):
        calls.append(repo_id)
        if repo_id == ANIME_6B_MODEL:
            raise RuntimeError("primary repo unreachable")
        return _fake_state_dict()

    with patch.object(
        ESRGANWrapper, "_load_state_dict", side_effect=_side_effect
    ), patch(
        "backend.src.models.wrappers.esrgan_wrapper.RRDBNet",
        lambda num_block: RRDBNet(num_feat=8, num_block=num_block, num_grow_ch=4),
    ):
        wrapper.load()

    assert calls == [ANIME_6B_MODEL, ANIME_6B_MODEL_FALLBACK]
    assert wrapper.loaded


def test_load_raises_model_load_error_when_both_repos_fail():
    wrapper = ESRGANWrapper(device="cpu", num_block=1)
    with patch.object(
        ESRGANWrapper, "_load_state_dict", side_effect=RuntimeError("network down")
    ):
        with pytest.raises(ModelLoadError):
            wrapper.load()
    assert not wrapper.loaded


def test_load_is_cached_per_key():
    """Second load() with the same (model_name, num_block, device) key must
    reuse the class-level cache, not re-download/re-construct."""
    wrapper1 = ESRGANWrapper(device="cpu", num_block=1)
    with patch.object(
        ESRGANWrapper, "_load_state_dict", return_value=_fake_state_dict()
    ) as mock_load, patch(
        "backend.src.models.wrappers.esrgan_wrapper.RRDBNet",
        lambda num_block: RRDBNet(num_feat=8, num_block=num_block, num_grow_ch=4),
    ):
        wrapper1.load()
        wrapper2 = ESRGANWrapper(device="cpu", num_block=1)
        wrapper2.load()
    assert mock_load.call_count == 1
    assert wrapper1._model is wrapper2._model


# ── Tiling correctness (small random-init model, no network) ───────────────


@pytest.fixture()
def tiny_wrapper():
    """A fast, randomly-initialized wrapper for shape/tiling tests --
    real weight download is verified manually (documented in the module
    docstring / PR description), not required for these structural tests."""
    wrapper = ESRGANWrapper(device="cpu", num_block=1, tile_size=64, tile_pad=8)
    wrapper._model = RRDBNet(num_feat=8, num_block=1, num_grow_ch=4).eval()
    return wrapper


def test_upscale_shape_non_tiled_path(tiny_wrapper):
    img = (np.random.rand(40, 50, 3) * 255).astype(np.uint8)
    out = tiny_wrapper.upscale(img)
    assert out.shape == (160, 200, 3)
    assert out.dtype == np.uint8


def test_upscale_shape_tiled_path_exact_multiple(tiny_wrapper):
    # 128x128 = exactly 2x2 tiles at tile_size=64, no remainder tile.
    img = (np.random.rand(128, 128, 3) * 255).astype(np.uint8)
    out = tiny_wrapper.upscale(img)
    assert out.shape == (512, 512, 3)


def test_upscale_shape_tiled_path_with_remainder_tile(tiny_wrapper):
    # 130x150: neither dimension divides evenly by tile_size=64, exercising
    # the smaller final tile in each row/column.
    img = (np.random.rand(130, 150, 3) * 255).astype(np.uint8)
    out = tiny_wrapper.upscale(img)
    assert out.shape == (520, 600, 3)


def test_upscale_path_reads_and_writes_file(tiny_wrapper, tmp_path):
    import cv2

    in_path = tmp_path / "in.png"
    out_path = tmp_path / "out.png"
    img = (np.random.rand(32, 40, 3) * 255).astype(np.uint8)
    cv2.imwrite(str(in_path), img)

    tiny_wrapper.upscale_path(str(in_path), str(out_path))

    result = cv2.imread(str(out_path))
    assert result is not None
    assert result.shape == (128, 160, 3)


def test_upscale_path_missing_input_raises(tiny_wrapper, tmp_path):
    with pytest.raises(FileNotFoundError):
        tiny_wrapper.upscale_path(str(tmp_path / "nope.png"), str(tmp_path / "out.png"))


def test_unload_clears_model(tiny_wrapper):
    assert tiny_wrapper.loaded
    tiny_wrapper.unload()
    assert not tiny_wrapper.loaded
