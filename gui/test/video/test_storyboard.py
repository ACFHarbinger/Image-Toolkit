import json
import os
import time

import pytest
from gui.src.helpers.video.storyboard import (
    StoryboardBuilder,
    StoryboardMeta,
    storyboard_is_complete,
    storyboard_meta_path_for,
)

pytestmark = pytest.mark.gui

HEVC_SAMPLE = (
    "/home/pkhunter/Downloads/data/Videos/"
    "Midareuchi - 02 [1080p-HEVC][hstream.moe][v2].mkv"
)


def _make_meta(**overrides):
    defaults = dict(
        interval_ms=100,
        tile_width=128,
        tile_height=72,
        cols=5,
        tiles_per_page=20,
        count=45,
        duration_ms=4_500,
        pages=["page_0000.jpg", "page_0001.jpg", "page_0002.jpg"],
    )
    defaults.update(overrides)
    return StoryboardMeta(**defaults)


class TestStoryboardMeta:
    def test_tile_location_for_first_tile(self):
        meta = _make_meta()
        assert meta.tile_location_for(0) == (0, 0, 0, 128, 72)

    def test_tile_location_for_wraps_to_next_row_within_a_page(self):
        meta = _make_meta()
        # idx = 5 -> within page 0 (tiles_per_page=20): row 1, col 0
        assert meta.tile_location_for(500) == (0, 0, 72, 128, 72)
        # idx = 7 -> page 0, row 1, col 2
        assert meta.tile_location_for(700) == (0, 256, 72, 128, 72)

    def test_tile_location_for_crosses_into_next_page(self):
        meta = _make_meta()
        # idx = 20 -> exactly the first tile of page 1
        assert meta.tile_location_for(2_000) == (1, 0, 0, 128, 72)
        # idx = 25 -> page 1, idx_in_page=5 -> row 1, col 0
        assert meta.tile_location_for(2_500) == (1, 0, 72, 128, 72)

    def test_tile_location_for_clamps_past_the_last_tile(self):
        meta = _make_meta()
        last_idx = meta.count - 1  # 44
        expected_page = last_idx // meta.tiles_per_page
        idx_in_page = last_idx % meta.tiles_per_page
        expected_col = idx_in_page % meta.cols
        expected_row = idx_in_page // meta.cols
        assert meta.tile_location_for(999_999) == (
            expected_page,
            expected_col * 128,
            expected_row * 72,
            128,
            72,
        )

    def test_tile_location_for_clamps_negative(self):
        meta = _make_meta()
        assert meta.tile_location_for(-500) == (0, 0, 0, 128, 72)

    def test_round_trips_through_json(self, tmp_path):
        meta = _make_meta()
        path = tmp_path / "meta.json"
        path.write_text(meta.to_json())
        loaded = StoryboardMeta.load(path)
        assert loaded == meta


class TestStoryboardCache:
    def test_storyboard_is_complete_false_when_missing(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        assert storyboard_is_complete(str(video)) is False

    def test_storyboard_is_complete_false_for_zero_count(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        meta_path = storyboard_meta_path_for(str(video))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({"count": 0, "pages": []}))
        assert storyboard_is_complete(str(video)) is False

    def test_storyboard_is_complete_false_when_a_page_file_is_missing(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        meta_path = storyboard_meta_path_for(str(video))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps({"count": 42, "pages": ["page_0000.jpg"]})
        )
        # page_0000.jpg deliberately not created
        assert storyboard_is_complete(str(video)) is False

    def test_storyboard_is_complete_true_for_valid_cache(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        meta_path = storyboard_meta_path_for(str(video))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        (meta_path.parent / "page_0000.jpg").write_bytes(b"not a real jpeg")
        meta_path.write_text(json.dumps({"count": 42, "pages": ["page_0000.jpg"]}))
        assert storyboard_is_complete(str(video)) is True


class TestStoryboardBuilderCancellation:
    def test_cancel_before_start_prevents_any_work(self, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        builder = StoryboardBuilder(str(video), 60_000)
        builder.cancel()
        # run() checks self._cancelled first thing and returns immediately;
        # calling it directly (not via .start()) keeps this test synchronous.
        builder.run()
        assert not builder.meta_path.exists()

    def test_zero_duration_fails_cleanly(self, q_app, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        builder = StoryboardBuilder(str(video), 0)

        failures = []
        builder.failed.connect(failures.append)
        builder.run()

        assert len(failures) == 1


class TestStoryboardPagination:
    """Dense (100ms) sampling on a long video decodes to well over Qt's
    ~256MB QImageIOHandler allocation limit as a single sprite sheet
    (confirmed empirically -- QPixmap silently returns a null pixmap past
    that, no exception raised). _composite() must split tiles across
    multiple page images, each kept safely under that ceiling."""

    def test_composite_splits_into_multiple_pages_for_many_tiles(self, tmp_path):
        from gui.src.helpers.video.storyboard import _MAX_PAGE_RAW_MB, TILE_WIDTH
        from PIL import Image

        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        builder = StoryboardBuilder(str(video), 60_000)

        # Fabricate enough tiny source tiles that they must span >1 page at
        # the real TILE_WIDTH (mirrors what a long, densely-sampled video
        # would actually produce, without paying real ffmpeg decode cost).
        raw_bytes_per_tile = TILE_WIDTH * int(TILE_WIDTH * 9 / 16) * 3
        tiles_per_page_expected = max(1, (_MAX_PAGE_RAW_MB * 1_000_000) // raw_bytes_per_tile)
        tile_count = int(tiles_per_page_expected * 2.5)

        src_dir = tmp_path / "src_tiles"
        src_dir.mkdir()
        tile_paths = []
        for i in range(tile_count):
            p = src_dir / f"tile_{i:06d}.jpg"
            Image.new("RGB", (TILE_WIDTH, int(TILE_WIDTH * 9 / 16)), (i % 255, 0, 0)).save(p)
            tile_paths.append(p)

        builder._composite(tile_paths, interval_ms=100)

        meta = StoryboardMeta.load(builder.meta_path)
        assert meta.count == tile_count
        assert len(meta.pages) >= 2, "expected tiles to span multiple pages"
        for page_name in meta.pages:
            page_path = builder.cache_dir / page_name
            assert page_path.exists()
            with Image.open(page_path) as page_img:
                w, h = page_img.size
                raw_mb = (w * h * 3) / 1_000_000
                assert raw_mb <= _MAX_PAGE_RAW_MB * 1.05, (
                    f"page {page_name} raw decoded size {raw_mb:.1f}MB exceeds budget"
                )

    def test_composited_pages_load_as_valid_non_null_pixmaps(self, q_app, tmp_path):
        """The actual bug this pagination fixes: a too-large single sprite
        sheet loads as QPixmap.isNull() == True with no exception at all --
        so this must be verified via a real QPixmap load, not just PIL."""
        from gui.src.helpers.video.storyboard import _MAX_PAGE_RAW_MB, TILE_WIDTH
        from PIL import Image
        from PySide6.QtGui import QPixmap

        video = tmp_path / "episode.mkv"
        video.write_text("dummy")
        builder = StoryboardBuilder(str(video), 60_000)

        raw_bytes_per_tile = TILE_WIDTH * int(TILE_WIDTH * 9 / 16) * 3
        tiles_per_page_expected = max(1, (_MAX_PAGE_RAW_MB * 1_000_000) // raw_bytes_per_tile)
        tile_count = int(tiles_per_page_expected * 1.5)

        src_dir = tmp_path / "src_tiles"
        src_dir.mkdir()
        tile_paths = []
        for i in range(tile_count):
            p = src_dir / f"tile_{i:06d}.jpg"
            Image.new("RGB", (TILE_WIDTH, int(TILE_WIDTH * 9 / 16)), (i % 255, 100, 0)).save(p)
            tile_paths.append(p)

        builder._composite(tile_paths, interval_ms=100)
        meta = StoryboardMeta.load(builder.meta_path)

        for page_name in meta.pages:
            pixmap = QPixmap(str(builder.cache_dir / page_name))
            assert not pixmap.isNull(), f"{page_name} failed to load as QPixmap"


@pytest.mark.skipif(
    not os.path.exists(HEVC_SAMPLE), reason="HEVC sample file not present on disk"
)
def test_storyboard_builder_produces_a_real_sprite_sheet(q_app):
    from pathlib import Path

    import numpy as np
    from gui.src.helpers.video.storyboard import probe_duration_ms
    from PIL import Image
    from PySide6.QtGui import QPixmap

    duration_ms = probe_duration_ms(HEVC_SAMPLE)
    assert duration_ms > 0

    builder = StoryboardBuilder(HEVC_SAMPLE, duration_ms)
    result = {}
    builder.finished_ok.connect(lambda meta_path: result.update(meta=meta_path))
    builder.failed.connect(lambda msg: result.update(error=msg))

    builder.start()
    deadline = time.time() + 120
    while time.time() < deadline and not result:
        q_app.processEvents()
        time.sleep(0.05)
    builder.wait(2000)

    assert "error" not in result, result.get("error")
    assert "meta" in result

    meta = StoryboardMeta.load(Path(result["meta"]))
    assert meta.count > 0
    assert meta.duration_ms == duration_ms
    # Dense sampling requirement: at least one tile per 100ms of runtime.
    # ffmpeg's fps filter naturally yields one fewer frame than the
    # theoretical maximum at the very last partial interval (there's no
    # full 100ms of source left to sample), so allow a 1-tile boundary
    # slack rather than requiring an exact >=.
    assert meta.interval_ms <= 100
    assert meta.count >= (duration_ms // 100) - 1

    page_dir = Path(result["meta"]).parent
    page_index, x, y, w, h = meta.tile_location_for(30_000)
    page_path = page_dir / meta.pages[page_index]

    # Every page must actually load as a real (non-null) QPixmap -- this is
    # the exact failure mode a too-large single sprite sheet hit silently.
    for page_name in meta.pages:
        pixmap = QPixmap(str(page_dir / page_name))
        assert not pixmap.isNull(), f"{page_name} failed to load as QPixmap"

    with Image.open(page_path) as sheet:
        tile = sheet.crop((x, y, x + w, y + h))
        arr = np.array(tile)
    assert arr.std() > 5
