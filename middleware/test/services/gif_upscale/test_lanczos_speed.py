"""One Lanczos3-dering frame, not a corpus run."""

from __future__ import annotations

import time

import numpy as np
from middleware.src.services.media.gif_upscale.registry import get_algorithm


def test_lanczos3_dering_one_frame_finishes_under_eight_seconds() -> None:
    frame = np.zeros((270, 480, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    frame[:, 240:, :3] = 1.0
    started = time.perf_counter()
    out = get_algorithm("lanczos3-dering").upscale([frame], 2.0, {"size": (960, 540)})[0]
    elapsed = time.perf_counter() - started
    print(f"lanczos3-dering 480x270->960x540 {elapsed:.6f}s")
    assert elapsed < 8.0, f"lanczos3-dering took {elapsed:.3f}s"
    assert out.shape == (540, 960, 4)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
    edge = out[out.shape[0] // 2, :, 0]
    assert float(edge.min()) < 0.05
    assert float(edge.max()) > 0.95
    assert np.any((edge > 0.05) & (edge < 0.95))
