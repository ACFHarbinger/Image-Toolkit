from types import SimpleNamespace

import pytest

from backend.src.models.data.lora_dataset import _clip_max_length


@pytest.mark.parametrize("raw, expected", [(77, 77), (32, 32), (10**30, 77), (None, 77), (float("inf"), 77), (-1, 77)])
def test_clip_limit_handles_unbounded_and_invalid_metadata(raw, expected):
    assert _clip_max_length(SimpleNamespace(model_max_length=raw)) == expected
