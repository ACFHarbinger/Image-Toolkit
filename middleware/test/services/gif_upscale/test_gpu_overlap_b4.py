"""Task B4 (#1157): bounded overlap queue. The fake session has no CUDA device."""

from __future__ import annotations

import inspect

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import ResampleCancelled
from middleware.src.services.media.gif_upscale.gpu_overlap import run_device_pipeline


class _FakeSession:
    """Records scale-then-index order. ``open`` counts started-but-not-finished batches."""

    def __init__(self) -> None:
        self.open = 0
        self.max_open = 0
        self.events: list[tuple[str, int]] = []

    def scale_batch_uint8(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        self.open += 1
        self.max_open = max(self.max_open, self.open)
        token = int(frames[0][0, 0, 0])
        self.events.append(("scale", token))
        return [np.array(frame, copy=True) for frame in frames]

    def index_batch_uint8(self, frames_u8: list[np.ndarray]) -> np.ndarray:
        token = int(frames_u8[0][0, 0, 0])
        self.events.append(("index", token))
        count = len(frames_u8)
        indices = np.zeros((count, 4, 4), dtype=np.uint8)
        indices[..., 0] = token
        self.open -= 1
        return indices


def _frames(token: int, count: int = 2) -> list[np.ndarray]:
    frames = []
    for index in range(count):
        frame = np.zeros((3, 5, 4), dtype=np.uint8)
        frame[..., 0] = token
        frame[..., 1] = index
        frames.append(frame)
    return frames


def test_queue_depth_limits_inflight_and_preserves_batch_ids() -> None:
    signature = inspect.signature(run_device_pipeline)
    assert list(signature.parameters) == ["session", "batches", "queue_depth", "cancel"]
    assert signature.parameters["queue_depth"].default == 2
    assert signature.parameters["queue_depth"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["cancel"].kind is inspect.Parameter.KEYWORD_ONLY

    fake = _FakeSession()
    # Unsorted on purpose: completion order must not be re-sorted.
    ids = ["a", "c", "b", "e", "d"]
    batches = [(batch_id, _frames(token)) for token, batch_id in enumerate(ids, start=1)]
    results = run_device_pipeline(fake, batches, queue_depth=2)

    assert [batch_id for batch_id, _indices in results] == ids
    assert fake.max_open <= 2
    assert [kind for kind, _token in fake.events] == ["scale", "index"] * 5
    assert [token for _kind, token in fake.events] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    for token, (_batch_id, indices) in enumerate(results, start=1):
        assert indices.dtype == np.uint8
        assert indices.shape == (2, 4, 4)
        assert int(indices[0, 0, 0]) == token
    assert fake.open == 0


def test_cancel_on_batch_2_stops_further_launches() -> None:
    fake = _FakeSession()
    batches = [(batch_id, _frames(batch_id)) for batch_id in (0, 1, 2, 3, 4)]
    calls = {"n": 0}

    def cancel() -> None:
        # Invoked once before each launch. Batch 2 is the third launch.
        if calls["n"] == 2:
            raise ResampleCancelled("batch 2")
        calls["n"] += 1

    with pytest.raises(ResampleCancelled, match="batch 2"):
        run_device_pipeline(fake, batches, queue_depth=2, cancel=cancel)

    assert calls["n"] == 2
    assert fake.max_open <= 2
    assert fake.events == [("scale", 0), ("index", 0), ("scale", 1), ("index", 1)]
    assert fake.open == 0
