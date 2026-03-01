"""
Thumbnail generation performance benchmarks.

Measures the speed of native Rust image scaling and FFmpeg video thumbnailing.
"""

import sys
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from PIL import Image
import numpy as np

# Add parent to path (backend) and root (Image-Toolkit)
backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))
from benchmark.utils import BenchmarkRunner, measure_memory

# Native image loading (Rust Base)
try:
    import base

    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False

# Video Thumbnailer
try:
    from gui.src.helpers.video.video_scan_worker import VideoThumbnailer

    HAS_VIDEO_THUMBNAILER = True
except ImportError:
    HAS_VIDEO_THUMBNAILER = False


runner = BenchmarkRunner("Thumbnail Generation")


def create_test_image(size=(1920, 1080)):
    """Create a high-res test RGB image."""
    img = Image.fromarray(np.random.randint(0, 255, (*size, 3), dtype=np.uint8))
    return img


def create_test_video(path: str, duration: int = 5):
    """Create a test MP4 video using FFmpeg synthetics."""
    if not shutil.which("ffmpeg"):
        return False

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=1920x1080:rate=30",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


@runner.benchmark("image_thumbnail_single_native", iterations=10, warmup=2)
@measure_memory
def bench_image_single():
    """Benchmark generating a single 180px thumbnail using Native Rust."""
    if not HAS_NATIVE_IMAGING:
        print("Skipping Native Imaging benchmark")
        return None

    # Create test image
    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = create_test_image()
        img.save(tmp.name, quality=90)
        tmp_path = tmp.name

    # Benchmark load_image_batch on a 1 item list
    results = base.load_image_batch([tmp_path], 180)

    # Cleanup
    Path(tmp_path).unlink()

    return len(results) if results else 0


@runner.benchmark("image_thumbnail_batch_10_native", iterations=5, warmup=1)
@measure_memory
def bench_image_batch_10():
    """Benchmark generating 10 180px thumbnails using Native Rust batch process."""
    if not HAS_NATIVE_IMAGING:
        return None

    # Create 10 test images
    tmp_paths = []
    for _ in range(10):
        with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img = create_test_image()
            img.save(tmp.name, quality=90)
            tmp_paths.append(tmp.name)

    # Benchmark parallel batch processing
    results = base.load_image_batch(tmp_paths, 180)

    # Cleanup
    for path in tmp_paths:
        Path(path).unlink()

    return len(results) if results else 0


@runner.benchmark("video_thumbnail_single_180px", iterations=5, warmup=1)
@measure_memory
def bench_video_single():
    """Benchmark generating a single video thumbnail using VideoThumbnailer."""
    if not HAS_VIDEO_THUMBNAILER:
        print("Skipping Video Thumbnailer benchmark (Gui not found)")
        return None

    thumbnailer = VideoThumbnailer()

    # Create test video
    with NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    if not create_test_video(tmp_path, duration=6):
        print("Skipping video benchmark (Failed to create test video)")
        Path(tmp_path).unlink()
        return None

    # Benchmark
    image = thumbnailer.generate(tmp_path, size=180, crop_square=True)

    # Cleanup
    Path(tmp_path).unlink()

    if image:
        # Check size to prove it worked
        return f"{image.width()}x{image.height()}"
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Thumbnail generation benchmarks")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument(
        "--baseline", type=Path, help="Baseline file for regression check"
    )
    args = parser.parse_args()

    # Create fake PyQt context for QImage internals inside generate()
    if HAS_VIDEO_THUMBNAILER:
        from PySide6.QtWidgets import QApplication

        if not QApplication.instance():
            _app = QApplication(sys.argv)

    runner.run()
    runner.print_results()

    if args.save:
        output_path = runner.save_json()
        print(f"Results saved to {output_path}")

    if args.baseline:
        passed = runner.check_regression(args.baseline)
        sys.exit(0 if passed else 1)
