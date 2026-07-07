import numpy as np
import pytest


@pytest.fixture
def image_dir(tmp_path):
    """Small synthetic corpus: a base image, an exact copy, a resized copy,
    a brightness-shifted copy, and two unrelated images."""
    import cv2

    rng = np.random.default_rng(42)
    base = rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)
    # Structured content so perceptual hashes are meaningful
    cv2.circle(base, (64, 64), 40, (255, 255, 255), -1)
    cv2.rectangle(base, (10, 10), (50, 50), (0, 0, 255), -1)

    unrelated1 = np.zeros((128, 128, 3), dtype=np.uint8)
    cv2.line(unrelated1, (0, 0), (127, 127), (0, 255, 0), 5)
    unrelated2 = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)

    d = tmp_path / "imgs"
    d.mkdir()
    cv2.imwrite(str(d / "base.png"), base)
    cv2.imwrite(str(d / "copy_exact.png"), base)
    cv2.imwrite(str(d / "copy_resized.png"), cv2.resize(base, (96, 96)))
    bright = cv2.convertScaleAbs(base, alpha=1.05, beta=8)
    cv2.imwrite(str(d / "copy_bright.jpg"), bright)
    cv2.imwrite(str(d / "unrelated1.png"), unrelated1)
    cv2.imwrite(str(d / "unrelated2.png"), unrelated2)
    return d
