"""GIF upscale mode and advanced switches as settings (C1, #1159)."""

from __future__ import annotations

import pytest
from middleware.src.services.media.gif_upscale import job_settings as js
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.pipeline import _palette_mode
from middleware.src.settings.keys import definition_for


class Store:
    def __init__(self, **values: object) -> None:
        self.values = {f"gif_upscale.{key}": value for key, value in values.items()}

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)


def test_every_key_is_registered_with_the_documented_default() -> None:
    defaults = {
        js.MODE_KEY: "balanced",
        js.WORKERS_KEY: 1,
        js.VRAM_CAP_KEY: 0.0,
        js.DEVICES_KEY: [],
        js.PALETTE_MODE_KEY: "mediancut",
        js.DERING_STRENGTH_KEY: 1.0,
        js.NO_GPU_THRESHOLD_KEY: 120,
        js.NO_GPU_PROMPT_KEY: True,
    }
    for key, default in defaults.items():
        definition = definition_for(key)
        assert definition is not None, key
        assert definition.default == default


def test_defaults_fill_an_empty_request() -> None:
    out = js.with_job_settings({}, Store())
    assert out == {"quality": "balanced", "workers": 1, "palette_mode": "mediancut", "dering_strength": 1.0}


def test_settings_fill_the_keys_the_request_left_out() -> None:
    store = Store(mode="fast", workers=4, vram_cap_gb=6, devices=[1], palette_mode="libimagequant", dering_strength=0.5)
    out = js.with_job_settings({}, store)
    assert out["quality"] == "fast"
    assert out["workers"] == 4
    assert out["vram_cap_gb"] == 6.0
    assert out["allow_devices"] == [1]
    assert out["palette_mode"] == "libimagequant"
    assert out["dering_strength"] == 0.5


def test_a_request_key_always_wins() -> None:
    store = Store(mode="fast", workers=4, devices=[1])
    out = js.with_job_settings({"quality": "exact", "workers": 2, "allow_devices": [0]}, store)
    assert (out["quality"], out["workers"], out["allow_devices"]) == ("exact", 2, [0])


def test_the_input_is_not_mutated() -> None:
    params = {"algorithm": "lanczos"}
    js.with_job_settings(params, Store(workers=3))
    assert params == {"algorithm": "lanczos"}


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("mode", "turbo"),
        ("workers", 0),
        ("workers", "x"),
        ("vram_cap_gb", -1),
        ("palette_mode", "kmeans"),
        ("dering_strength", 2),
        ("devices", ["a"]),
    ],
)
def test_an_invalid_stored_value_falls_back_to_the_default(key: str, bad: object) -> None:
    out = js.with_job_settings({}, Store(**{key: bad}))
    assert out["quality"] == "balanced"
    assert out["workers"] == 1
    assert out["palette_mode"] == "mediancut"
    assert out["dering_strength"] == 1.0
    assert "allow_devices" not in out
    assert "vram_cap_gb" not in out


def test_a_failing_store_gives_defaults() -> None:
    class Broken:
        def get(self, key: str, default: object = None) -> object:
            raise OSError("disk")

    assert js.with_job_settings({}, Broken())["workers"] == 1


def test_no_gpu_window_settings() -> None:
    assert js.no_gpu_threshold_s(Store()) == 120
    assert js.no_gpu_prompt_enabled(Store()) is True
    assert js.no_gpu_threshold_s(Store(no_gpu_threshold_s=300)) == 300
    assert js.no_gpu_prompt_enabled(Store(no_gpu_prompt=False)) is False
    assert js.no_gpu_threshold_s(Store(no_gpu_threshold_s=0)) == 120


def test_palette_mode_in_the_pipeline() -> None:
    assert _palette_mode({}) == "mediancut"
    assert _palette_mode({"palette_mode": "LibImageQuant"}) == "libimagequant"
    with pytest.raises(AlgorithmError):
        _palette_mode({"palette_mode": "kmeans"})
