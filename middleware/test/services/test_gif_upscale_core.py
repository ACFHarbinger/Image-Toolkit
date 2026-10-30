"""Registry, GIF frame IO, palette encoder, tiling, and the weights policy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmSpec
from middleware.src.services.media.gif_upscale.io import composite_disposal, decode_gif, iter_gif_frames
from middleware.src.services.media.gif_upscale.licenses import LICENSES, shipping_allowed
from middleware.src.services.media.gif_upscale.policy import (
    WEIGHTS_POLICY_KEY,
    WeightUnavailable,
    ensure_weight,
    sha256_file,
    weights_policy,
)
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms, register_algorithm
from middleware.src.services.media.gif_upscale.tiling import process_tiled
from middleware.src.services.media.subtabs import resample
from middleware.src.settings.adapters import MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService
from PIL import Image


def _animated(path, size=(8, 4), frames=2) -> None:
    images = []
    for index in range(frames):
        color = (255, 0, 0) if index % 2 == 0 else (0, 0, 255)
        images.append(Image.new("RGB", size, color))
    images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=[40, 80][:frames] if frames > 1 else 40,
        loop=2,
        disposal=2,
    )
    for image in images:
        image.close()


def test_sampler_gif_keeps_frames_duration_and_loop(tmp_path) -> None:
    source = tmp_path / "clip.GIF"
    output = tmp_path / "up.gif"
    _animated(source)
    result = resample(
        {
            "input_path": str(source),
            "output_path": str(output),
            "mode": "factor",
            "factor": 2,
            "algorithm": "nearest",
        }
    )
    assert result["success"] is True
    assert (result["width"], result["height"]) == (16, 8)
    with Image.open(output) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames == 2
        assert gif.size == (16, 8)
        assert gif.info.get("loop") == 2
        gif.seek(0)
        assert gif.info.get("duration") == 40
        assert gif.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
        gif.seek(1)
        assert gif.info.get("duration") == 80
        assert gif.convert("RGB").getpixel((0, 0)) == (0, 0, 255)


def test_transparent_and_odd_single_frame_round_trip(tmp_path) -> None:
    source = tmp_path / "odd.gif"
    output = tmp_path / "odd-out.gif"
    image = Image.new("RGBA", (7, 5), (255, 0, 0, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(source, format="GIF", save_all=True, loop=0, duration=20)
    image.close()
    result = resample({"input_path": str(source), "output_path": str(output), "factor": 1, "algorithm": "nearest"})
    assert result["success"] is True
    with Image.open(output) as gif:
        assert gif.size == (7, 5)
        assert gif.n_frames == 1
        rgba = gif.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((1, 1))[:3] == (255, 0, 0)
        assert rgba.getpixel((1, 1))[3] == 255


def test_shared_palette_does_not_shimmer_identical_frames(tmp_path) -> None:
    source = tmp_path / "grad.gif"
    output = tmp_path / "grad-out.gif"
    gradient = Image.new("RGB", (64, 8))
    for x in range(64):
        for y in range(8):
            gradient.putpixel((x, y), (x * 4, 0, 255 - x * 4))
    shifted = gradient.copy()
    shifted.putpixel((63, 7), (0, 0, 0))
    gradient.save(source, format="GIF", save_all=True, append_images=[shifted], duration=[50, 50], loop=0, optimize=False)
    gradient.close()
    shifted.close()
    assert resample({"input_path": str(source), "output_path": str(output), "factor": 1, "algorithm": "nearest"})["success"]
    clip = decode_gif(str(output))
    assert len(clip.frames) == 2
    # The shared palette keeps the untouched columns stable across frames.
    assert np.array_equal(clip.frames[0][:, :60], clip.frames[1][:, :60])
    source_rgb = np.asarray(Image.open(source).convert("RGB"), dtype=np.int16)
    written_rgb = clip.frames[0][:, :, :3].astype(np.int16)
    assert np.abs(source_rgb - written_rgb).mean() < 20
    assert output.stat().st_size < 64 * 8 * 4 * 2


def test_iterator_does_not_require_the_caller_to_keep_every_frame(tmp_path) -> None:
    source = tmp_path / "many.gif"
    frame = Image.new("RGB", (2, 2), (10, 20, 30))
    frames = []
    for index in range(30):
        image = frame.copy()
        image.putpixel((0, 0), (index, 20, 30))
        frames.append(image)
    frames[0].save(source, format="GIF", save_all=True, append_images=frames[1:], duration=40, loop=1, optimize=False)
    seen = 0
    last = None
    for rgba, duration, loop in iter_gif_frames(str(source)):
        seen += 1
        last = rgba
        assert duration == 40
        assert loop == 1
        del rgba
    assert seen == 30
    assert last is not None and last.shape == (2, 2, 4)


def test_partial_frame_disposal_restores_the_rectangle() -> None:
    canvas = np.zeros((3, 3, 4), dtype=np.uint8)
    canvas[:, :] = (255, 0, 0, 255)
    frame = np.zeros((1, 1, 4), dtype=np.uint8)
    frame[0, 0] = (0, 0, 255, 255)
    displayed, nxt = composite_disposal(canvas, frame, (1, 1), 2)
    assert tuple(displayed[1, 1]) == (0, 0, 255, 255)
    assert tuple(displayed[0, 0]) == (255, 0, 0, 255)
    assert tuple(nxt[1, 1]) == (0, 0, 0, 0)
    assert tuple(nxt[0, 0]) == (255, 0, 0, 255)


def test_tiled_identity_matches_and_oom_shrinks_the_tile() -> None:
    frame = np.arange(48, dtype=np.float32).reshape(6, 8, 1)
    frame = np.repeat(frame, 4, axis=2)

    def identity(tile: np.ndarray) -> np.ndarray:
        return tile

    assert np.allclose(process_tiled(frame, identity, tile=4, overlap=2), frame)
    seen: list[int] = []

    def boom(tile: np.ndarray) -> np.ndarray:
        seen.append(tile.shape[1])
        if tile.shape[1] > 3:
            raise MemoryError("too wide")
        return tile

    result = process_tiled(frame, boom, tile=8, overlap=0, min_tile=2)
    assert np.allclose(result, frame)
    assert max(seen) > 3
    assert min(seen) <= 3


def test_trailing_tile_narrower_than_the_overlap_still_blends() -> None:
    frame = np.ones((250, 250, 4), dtype=np.float32)
    assert np.allclose(process_tiled(frame, lambda tile: tile), frame)


def test_still_integer_nearest_is_not_replaced_by_lanczos(tmp_path) -> None:
    source = tmp_path / "blocks.png"
    output = tmp_path / "blocks-out.png"
    image = Image.new("RGB", (2, 2), (255, 0, 0))
    image.putpixel((1, 0), (0, 0, 255))
    image.putpixel((1, 1), (0, 0, 255))
    image.save(source)
    image.close()
    result = resample(
        {"input_path": str(source), "output_path": str(output), "factor": 2, "algorithm": "integer-nearest"}
    )
    assert result["success"] is True
    assert (result["width"], result["height"]) == (4, 4)
    with Image.open(output) as written:
        assert written.getpixel((0, 0))[:3] == (255, 0, 0)
        assert written.getpixel((1, 0))[:3] == (255, 0, 0)
        assert written.getpixel((2, 0))[:3] == (0, 0, 255)
        assert written.getpixel((3, 0))[:3] == (0, 0, 255)


def test_unknown_algorithm_on_a_still_is_an_error(tmp_path) -> None:
    source = tmp_path / "still.png"
    output = tmp_path / "still-out.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(source)
    result = resample(
        {"input_path": str(source), "output_path": str(output), "factor": 2, "algorithm": "anime4k-nope"}
    )
    assert result["success"] is False
    assert "Unknown resample algorithm" in result["message"]
    assert not output.exists()


def test_gifski_keeps_a_shared_delay_and_falls_back_when_delays_differ(tmp_path, monkeypatch) -> None:
    from middleware.src.services.media.gif_upscale.encode import encode_gif

    frames = [np.zeros((2, 2, 4), dtype=np.float32), np.ones((2, 2, 4), dtype=np.float32)]
    calls: list[list[str]] = []

    def _run(args, check, capture_output):
        del check, capture_output
        calls.append(list(args))
        Path(args[args.index("-o") + 1]).write_bytes(b"GIF89a")
        return None

    monkeypatch.setattr("middleware.src.services.media.gif_upscale.encode.shutil.which", lambda _name: "/usr/bin/gifski")
    monkeypatch.setattr("middleware.src.services.media.gif_upscale.encode.subprocess.run", _run)
    uniform = tmp_path / "uniform.gif"
    assert encode_gif(str(uniform), frames, [40, 40], 0, encoder="gifski") == "gifski"
    assert "--fps" in calls[0]
    assert calls[0][calls[0].index("--fps") + 1] == "25.0"

    varied = tmp_path / "varied.gif"
    assert encode_gif(str(varied), frames, [40, 80], 0, encoder="gifski") == "temporal"
    assert len(calls) == 1
    assert varied.stat().st_size > 6


def test_unknown_algorithm_is_an_error_and_does_not_write(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    output = tmp_path / "out.gif"
    _animated(source)
    result = resample(
        {"input_path": str(source), "output_path": str(output), "factor": 2, "algorithm": "not-a-scaler"}
    )
    assert result["success"] is False
    assert "Unknown resample algorithm" in result["message"]
    assert not output.exists()


def test_unavailable_backend_reports_its_reason(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    output = tmp_path / "out.gif"
    _animated(source)

    def refuse(frames, scale, opts):
        del frames, scale, opts
        raise AssertionError("unavailable backend ran")

    register_algorithm(
        AlgorithmSpec(
            id="test-missing-weights",
            family="test",
            content="realistic",
            kind="neural",
            supports_scale=frozenset({2.0}),
            supports_downscale=False,
            needs_gpu=True,
            vram_mb_estimate=100,
            license="MIT",
            weights_sha256=None,
            available=lambda: (False, "weights missing for test-missing-weights"),
        ),
        refuse,
    )
    result = resample(
        {"input_path": str(source), "output_path": str(output), "factor": 2, "algorithm": "test-missing-weights"}
    )
    assert result["success"] is False
    assert result["message"] == "weights missing for test-missing-weights"
    assert not output.exists()
    listed = {row["id"]: row for row in list_algorithms()}
    assert listed["lanczos"]["available"] is True
    assert listed["test-missing-weights"]["reason"] == "weights missing for test-missing-weights"


def test_fixed_scale_backend_refuses_a_different_size(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    output = tmp_path / "out.gif"
    _animated(source)
    register_algorithm(
        AlgorithmSpec(
            id="test-x4-only",
            family="test",
            content="realistic",
            kind="neural",
            supports_scale=frozenset({4.0}),
            supports_downscale=False,
            needs_gpu=False,
            vram_mb_estimate=0,
            license="MIT",
            weights_sha256=None,
            available=lambda: (True, ""),
        ),
        lambda frames, scale, opts: frames,
    )
    result = resample({"input_path": str(source), "output_path": str(output), "factor": 2, "algorithm": "test-x4-only"})
    assert result["success"] is False
    assert "supports scales" in result["message"]
    assert not output.exists()


def test_weights_policy_and_offline_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", raising=False)
    service = SettingsService({SettingScope.DEVICE: MemoryStore(), SettingScope.ACCOUNT: MemoryStore()})
    assert weights_policy(service) == "on_demand"
    service.set(WEIGHTS_POLICY_KEY, "offline")
    assert weights_policy(service) == "offline"
    with pytest.raises(ValueError):
        service.set(WEIGHTS_POLICY_KEY, "sometimes")

    payload = tmp_path / "blob.bin"
    payload.write_bytes(b"weights")
    digest = sha256_file(payload)
    calls: list[str] = []

    def fetch(url: str, destination) -> None:
        calls.append(url)
        destination.write_bytes(b"nope")

    with pytest.raises(WeightUnavailable):
        ensure_weight("model.pth", digest, "https://example.invalid/model.pth", "offline", cache=tmp_path / "cache", fetch=fetch)
    assert calls == []

    def good_fetch(url: str, destination) -> None:
        calls.append(url)
        destination.write_bytes(b"weights")

    cached = ensure_weight(
        "model.pth", digest, "https://example.invalid/model.pth", "on_demand", cache=tmp_path / "cache", fetch=good_fetch
    )
    assert cached.read_bytes() == b"weights"
    assert calls == ["https://example.invalid/model.pth"]
    ensure_weight("model.pth", digest, "https://example.invalid/model.pth", "offline", cache=tmp_path / "cache", fetch=fetch)
    assert calls == ["https://example.invalid/model.pth"]


def test_license_record_does_not_block_private_use_backends() -> None:
    apisr = LICENSES["apisr"]
    gifski = LICENSES["gifski"]
    assert apisr.redistribution == "private-use"
    assert "academic" in apisr.note
    assert gifski.spdx == "AGPL-3.0-only"
    assert shipping_allowed(apisr) is True
    assert shipping_allowed(gifski) is True
    assert get_algorithm("lanczos").spec.license == "MIT"
