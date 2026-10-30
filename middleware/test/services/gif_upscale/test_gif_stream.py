"""Long GIFs are written one frame at a time and still round-trip."""

from __future__ import annotations

import numpy as np
from middleware.src.services.media.gif_upscale.encode import IndexedGifWriter, _shared_palette, index_frame
from middleware.src.services.media.gif_upscale.pipeline import _needs_stream
from PIL import Image


def test_indexed_writer_keeps_duration_and_colors(tmp_path) -> None:
    red = np.zeros((4, 6, 4), dtype=np.uint8)
    red[..., 0] = 255
    red[..., 3] = 255
    blue = red.copy()
    blue[..., 0] = 0
    blue[..., 2] = 255
    palette = _shared_palette([red, blue], 256, "mediancut")
    path = tmp_path / "stream.gif"
    writer = IndexedGifWriter(str(path), 6, 4, palette, loop=2, transparent=False)
    writer.add_frame(index_frame(red, palette, transparent=False), 40)
    writer.add_frame(index_frame(blue, palette, transparent=False), 80)
    writer.close()
    with Image.open(path) as gif:
        assert gif.n_frames == 2
        assert gif.size == (6, 4)
        assert gif.info.get("loop") == 2
        gif.seek(0)
        assert gif.info.get("duration") == 40
        assert gif.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
        gif.seek(1)
        assert gif.info.get("duration") == 80
        assert gif.convert("RGB").getpixel((0, 0)) == (0, 0, 255)


def test_many_frames_need_the_stream_path(tmp_path) -> None:
    path = tmp_path / "long.gif"
    frame = Image.new("RGB", (64, 64), (1, 2, 3))
    frames = [frame.copy() for _ in range(80)]
    for index, image in enumerate(frames):
        image.putpixel((0, 0), (index, 0, 0))
    frames[0].save(path, format="GIF", save_all=True, append_images=frames[1:], duration=40, loop=0, optimize=False)
    assert _needs_stream(str(path), {"mode": "factor", "factor": 8}) is True
    assert _needs_stream(str(path), {"mode": "factor", "factor": 1}) is False


def test_detailed_indexed_round_trip(tmp_path):
    from PIL import Image
    from middleware.src.services.media.gif_upscale.encode import IndexedGifWriter

    for size in (32, 128, 256):
        pixels = np.random.default_rng(size).integers(0, 256, (size, size), dtype=np.uint8)
        palette = np.repeat(np.arange(256)[:, None], 3, axis=1)
        path = tmp_path / f"detailed-{size}.gif"
        writer = IndexedGifWriter(str(path), size, size, palette, 0, transparent=False)
        writer.add_frame(pixels, 100)
        writer.close()
        with Image.open(path) as image:
            np.testing.assert_array_equal(np.asarray(image), pixels)
