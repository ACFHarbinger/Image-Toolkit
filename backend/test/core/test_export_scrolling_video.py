"""
Tests for ImageMerger.export_scrolling_video (roadmap §4.2 — Export
Stitched Panorama to Scrolling Video, Option B: FFmpeg pipe).

Runs the real `ffmpeg` binary against small synthetic PNGs (no mocking of
subprocess) so the test is a genuine end-to-end check of the pipe/encode
path; it's still fast (sub-second clips) and does not touch the GUI, so it
is safe to run directly with pytest (not part of the full-suite freeze
concerns tracked in project memory).
"""

import os
import shutil
import subprocess
import unittest

import numpy as np
from PIL import Image

from backend.src.core.image_merger import ImageMerger

_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_HAS_FFPROBE = shutil.which("ffprobe") is not None


def _ffprobe_json(path: str) -> dict:
    import json

    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(proc.stdout)


@unittest.skipUnless(_HAS_FFMPEG, "ffmpeg not available on PATH")
class TestExportScrollingVideo(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_tmp_scroll_video"
        )
        os.makedirs(self.tmp_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_image(self, path: str, w: int, h: int) -> None:
        arr = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
        Image.fromarray(arr).save(path)

    def test_vertical_scroll_produces_expected_frame_count(self):
        img_path = os.path.join(self.tmp_dir, "tall.png")
        # 1080 wide x 8000 tall -> vertical auto-detected scroll axis.
        self._make_image(img_path, 1080, 8000)
        out_path = os.path.join(self.tmp_dir, "tall_scroll.mp4")

        result = ImageMerger.export_scrolling_video(
            img_path, out_path, scroll_speed_px_per_frame=200, fps=30
        )

        self.assertEqual(result, out_path)
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 0)

        if _HAS_FFPROBE:
            info = _ffprobe_json(out_path)
            stream = info["streams"][0]
            self.assertEqual(stream["codec_name"], "h264")
            self.assertEqual(stream["pix_fmt"], "yuv420p")
            self.assertEqual(stream["width"], 1080)
            # viewport height derived as ~16:9 of width, clamped even
            self.assertLessEqual(stream["height"], 8000)
            self.assertGreater(int(stream["nb_frames"]), 1)

    def test_horizontal_scroll_auto_detected_for_wide_image(self):
        img_path = os.path.join(self.tmp_dir, "wide.png")
        self._make_image(img_path, 6000, 1080)
        out_path = os.path.join(self.tmp_dir, "wide_scroll.mp4")

        ImageMerger.export_scrolling_video(
            img_path, out_path, scroll_speed_px_per_frame=150, fps=25
        )

        self.assertTrue(os.path.exists(out_path))
        if _HAS_FFPROBE:
            info = _ffprobe_json(out_path)
            stream = info["streams"][0]
            self.assertEqual(stream["height"], 1080)

    def test_nothing_to_scroll_produces_static_clip(self):
        """
        Panorama smaller than one viewport's worth of scroll: documented
        behaviour is a short static clip (not an exception).
        """
        img_path = os.path.join(self.tmp_dir, "small.png")
        self._make_image(img_path, 300, 400)
        out_path = os.path.join(self.tmp_dir, "small_static.mp4")

        result = ImageMerger.export_scrolling_video(
            img_path, out_path, scroll_speed_px_per_frame=10, fps=24
        )

        self.assertEqual(result, out_path)
        self.assertTrue(os.path.exists(out_path))
        if _HAS_FFPROBE:
            info = _ffprobe_json(out_path)
            duration = float(info["format"]["duration"])
            self.assertGreater(duration, 0.5)  # roughly 1 second, not empty

    def test_explicit_resolution_and_scroll_axis_respected(self):
        img_path = os.path.join(self.tmp_dir, "custom.png")
        self._make_image(img_path, 2000, 3000)
        out_path = os.path.join(self.tmp_dir, "custom_scroll.mp4")

        ImageMerger.export_scrolling_video(
            img_path,
            out_path,
            scroll_speed_px_per_frame=50,
            fps=20,
            resolution=(640, 480),
            scroll_axis="horizontal",
        )

        self.assertTrue(os.path.exists(out_path))
        if _HAS_FFPROBE:
            info = _ffprobe_json(out_path)
            stream = info["streams"][0]
            self.assertEqual(stream["width"], 640)
            self.assertEqual(stream["height"], 480)

    def test_rejects_missing_ffmpeg(self):
        img_path = os.path.join(self.tmp_dir, "tall2.png")
        self._make_image(img_path, 100, 200)
        out_path = os.path.join(self.tmp_dir, "unreachable.mp4")

        import unittest.mock as mock

        # §5.17: export_scrolling_video moved to image_merger/_gif_video.py,
        # which does its own `import shutil` -- patch that submodule, not
        # the pre-split top-level image_merger path.
        with mock.patch(
            "backend.src.core.image_merger._gif_video.shutil.which",
            return_value=None,
        ), self.assertRaises(RuntimeError):
            ImageMerger.export_scrolling_video(img_path, out_path)


if __name__ == "__main__":
    unittest.main()
