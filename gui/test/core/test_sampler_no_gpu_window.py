"""C3 (#1161): the Sampler no-GPU window. Offscreen. No CUDA and no home settings.

The device probe and the settings store are injected. Closing cancels.
Enter stores the spin-box count as the workers default. Shift+Enter continues
and leaves that default alone. "Do not ask again" is written only on those
two accepts.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from middleware.src.settings.adapters import MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService
from PySide6.QtCore import Qt, QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from gui.src.helpers.core.sampler_worker import SamplerWorker
from gui.src.tabs.core.sampler_subtab import no_gpu_window as no_gpu_mod
from gui.src.tabs.core.sampler_subtab._resample_worker import SamplerWorkerController
from gui.src.tabs.core.sampler_subtab.no_gpu_window import (
    NoGpuChoice,
    NoGpuWindow,
    apply_no_gpu_choice,
    confirm_slow_gif,
    should_prompt_no_gpu,
)


def _settings(**values: object) -> SettingsService:
    store = MemoryStore()
    for key, value in values.items():
        store.set(key, value)
    return SettingsService(stores={SettingScope.DEVICE: store})


def _estimate(total: float = 180.0):
    return SimpleNamespace(
        total_s=total,
        path="timed cpu lanczos on 4 of 20 frames; job would use cpu; workers=1; batch multi-core off",
    )


def test_prompt_gate_needs_no_gpu_a_long_estimate_and_the_flag() -> None:
    assert should_prompt_no_gpu(usable_gpu=False, estimate_s=121, threshold_s=120, prompt_enabled=True)
    assert not should_prompt_no_gpu(usable_gpu=True, estimate_s=500, threshold_s=120, prompt_enabled=True)
    assert not should_prompt_no_gpu(usable_gpu=False, estimate_s=120, threshold_s=120, prompt_enabled=True)
    assert not should_prompt_no_gpu(usable_gpu=False, estimate_s=500, threshold_s=120, prompt_enabled=False)


def test_enter_accepts_the_count_and_shift_enter_does_not() -> None:
    app = QApplication.instance()
    assert app is not None
    window = NoGpuWindow(_estimate(), use_multicore=True, source_name="clip.gif")
    window.show()
    app.processEvents()
    window._spin.setValue(4)
    window._remember.setChecked(True)
    assert "D10" in window._d10.text()
    assert "8 processes" in window._d10.text()
    QTest.keyClick(window._spin, Qt.Key.Key_Return)
    assert window.choice == NoGpuChoice("workers", 4, True)
    assert window.result() == QDialog.DialogCode.Accepted

    other = NoGpuWindow(_estimate(), use_multicore=False, source_name="clip.gif")
    other.show()
    app.processEvents()
    other._spin.setValue(6)
    QTest.keyClick(other._spin, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert other.choice == NoGpuChoice("continue", None, False)
    assert other.result() == QDialog.DialogCode.Accepted
    assert "timed cpu lanczos" in other._path.text()
    assert "Shift+Enter" in other._continue_btn.text()


def test_closing_cancels_and_writes_nothing() -> None:
    service = _settings()
    window = NoGpuWindow(_estimate(), use_multicore=False)
    window.show()
    window._spin.setValue(5)
    window._remember.setChecked(True)
    window.close()
    assert window.choice.action == "cancel"
    assert window.result() == QDialog.DialogCode.Rejected
    config: dict = {}
    apply_no_gpu_choice(config, window.choice, service)
    assert config == {}
    assert service.get("gif_upscale.workers", 1) == 1
    assert service.get("gif_upscale.no_gpu_prompt", True) is True


def test_accepted_count_becomes_the_workers_default_and_continue_does_not() -> None:
    service = _settings()
    config: dict = {}
    apply_no_gpu_choice(config, NoGpuChoice("workers", 3, True), service)
    assert config["workers"] == 3
    assert service.get("gif_upscale.workers") == 3
    assert service.get("gif_upscale.no_gpu_prompt") is False

    other = _settings()
    plain: dict = {}
    apply_no_gpu_choice(plain, NoGpuChoice("continue", None, True), other)
    assert "workers" not in plain
    assert other.get("gif_upscale.workers", 1) == 1
    assert other.get("gif_upscale.no_gpu_prompt") is False


def test_confirm_skips_a_usable_gpu_a_short_job_and_a_disabled_prompt() -> None:
    config = {"files_to_process": ["clip.gif", "other.png"], "scale_mode": "factor", "scale_factor": 2}

    def boom(*_args, **_kwargs):
        raise AssertionError("estimate should not run")

    # A real GPU job is lanczos3-dering plus the temporal encoder. Default lanczos estimates.
    assert confirm_slow_gif(
        {**config, "algorithm": "lanczos3-dering"},
        probe=lambda: (True, "cuda:0"),
        settings=_settings(),
        estimate_fn=boom,
    )
    assert confirm_slow_gif({"files_to_process": ["still.png"]}, settings=_settings(), estimate_fn=boom)
    assert confirm_slow_gif(
        config,
        probe=lambda: (False, "cpu"),
        settings=_settings(**{"gif_upscale.no_gpu_prompt": False}),
        estimate_fn=boom,
    )
    assert confirm_slow_gif(
        config,
        probe=lambda: (False, "cpu"),
        settings=_settings(),
        estimate_fn=lambda *_args, **_kwargs: _estimate(30),
    )
    assert "workers" not in config


def test_confirm_cancel_does_not_start_and_accept_sets_workers(monkeypatch) -> None:
    config = {"files_to_process": ["/tmp/clip.gif"], "scale_mode": "factor", "scale_factor": 2, "use_multicore": True}
    service = _settings(**{"gif_upscale.no_gpu_threshold_s": 120})

    class Closed:
        choice = NoGpuChoice("cancel")

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "gui.src.tabs.core.sampler_subtab.no_gpu_window.NoGpuWindow",
        lambda *args, **kwargs: Closed(),
    )
    assert confirm_slow_gif(
        config,
        probe=lambda: (False, "cpu"),
        settings=service,
        estimate_fn=lambda *_args, **_kwargs: _estimate(200),
    ) is False
    assert "workers" not in config

    class Accepted:
        choice = NoGpuChoice("workers", 2, False)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "gui.src.tabs.core.sampler_subtab.no_gpu_window.NoGpuWindow",
        lambda *args, **kwargs: Accepted(),
    )
    assert confirm_slow_gif(
        config,
        probe=lambda: (False, "cpu"),
        settings=service,
        estimate_fn=lambda *_args, **_kwargs: _estimate(200),
    )
    assert config["workers"] == 2
    assert service.get("gif_upscale.workers") == 2


def test_start_worker_returns_when_the_window_cancels(monkeypatch) -> None:
    """Cancel arrives on the queued plan. The call itself does not start a worker."""
    seen: dict = {}

    class Shown:
        choice = NoGpuChoice("cancel")

        def exec(self):
            seen["dialog"] = True
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(no_gpu_mod, "estimate_gif_job", lambda *_args, **_kwargs: _estimate(200))
    monkeypatch.setattr(no_gpu_mod, "NoGpuWindow", lambda *args, **kwargs: Shown())
    tab = SimpleNamespace(
        worker=None,
        btn_all=MagicMock(),
        btn_selected=MagicMock(),
        status_label=MagicMock(),
        progress_bar=MagicMock(),
    )
    controller = SamplerWorkerController(tab)
    monkeypatch.setattr(
        SamplerWorkerController,
        "_collect_config",
        lambda self, _use: {"files_to_process": ["clip.gif"], "scale_mode": "factor", "scale_factor": 2},
    )
    controller._start_worker(False)
    assert tab.worker is None
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and "dialog" not in seen:
        QApplication.processEvents()
        time.sleep(0.01)
    assert seen.get("dialog") is True
    assert tab.worker is None


def test_registry_params_pass_an_accepted_worker_count() -> None:
    worker = SamplerWorker({"algorithm": "lanczos", "scale_mode": "factor", "scale_factor": 2, "workers": 4})
    params = worker._registry_params(8, 8)
    assert params["workers"] == 4
    assert params["width"] == 16
    plain = SamplerWorker({"algorithm": "lanczos", "scale_mode": "factor", "scale_factor": 2})
    assert "workers" not in plain._registry_params(8, 8)


def test_only_the_first_gif_is_named_as_a_limit() -> None:
    text = no_gpu_mod.__doc__ or ""
    assert "first GIF" in text
    assert "later" in text.lower()


def test_default_lanczos_on_cuda_still_offers_the_window(monkeypatch) -> None:
    """lanczos never takes the GPU path, so a CUDA machine still gets the window."""
    opened: list[str] = []

    class Shown:
        choice = NoGpuChoice("continue", None, False)

        def exec(self):
            opened.append("dialog")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(no_gpu_mod, "NoGpuWindow", lambda *args, **kwargs: Shown())
    config = {"files_to_process": ["clip.gif"], "scale_mode": "factor", "scale_factor": 2}
    assert confirm_slow_gif(
        config,
        probe=lambda: (True, "cuda:0"),
        settings=_settings(**{"gif_upscale.no_gpu_threshold_s": 120}),
        estimate_fn=lambda *_args, **_kwargs: _estimate(200),
    )
    assert opened == ["dialog"]


def test_disallowed_card_does_not_count_as_a_usable_gpu(monkeypatch) -> None:
    opened: list[str] = []

    class Shown:
        choice = NoGpuChoice("continue", None, False)

        def exec(self):
            opened.append("dialog")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(no_gpu_mod, "NoGpuWindow", lambda *args, **kwargs: Shown())
    config = {
        "files_to_process": ["clip.gif"],
        "scale_mode": "factor",
        "scale_factor": 2,
        "algorithm": "lanczos3-dering",
        "allow_devices": [1],
    }
    assert confirm_slow_gif(
        config,
        probe=lambda: (True, "cuda:0"),
        settings=_settings(**{"gif_upscale.no_gpu_threshold_s": 120}),
        estimate_fn=lambda *_args, **_kwargs: _estimate(200),
    )
    assert opened == ["dialog"]


def test_estimate_dimensions_match_the_worker(tmp_path) -> None:
    from PIL import Image

    path = tmp_path / "clip.gif"
    Image.new("RGB", (16, 8), (20, 30, 40)).save(path, format="GIF")
    seen: dict = {}

    def estimate_fn(_gif, params, **_kwargs):
        seen["params"] = dict(params)
        return _estimate(30)

    width_only = {
        "files_to_process": [str(path)],
        "scale_mode": "dimensions",
        "target_width": 32,
        "target_height": None,
        "preserve_aspect_ratio": True,
        "algorithm": "lanczos",
    }
    confirm_slow_gif(
        width_only,
        probe=lambda: (False, "cpu"),
        settings=_settings(),
        estimate_fn=estimate_fn,
    )
    assert (seen["params"]["width"], seen["params"]["height"]) == SamplerWorker(width_only)._compute_dims(16, 8)

    height_only = dict(width_only)
    height_only["target_width"] = None
    height_only["target_height"] = 24
    confirm_slow_gif(
        height_only,
        probe=lambda: (False, "cpu"),
        settings=_settings(),
        estimate_fn=estimate_fn,
    )
    assert (seen["params"]["width"], seen["params"]["height"]) == SamplerWorker(height_only)._compute_dims(16, 8)

    fitted = dict(width_only)
    fitted["target_width"] = 40
    fitted["target_height"] = 10
    confirm_slow_gif(
        fitted,
        probe=lambda: (False, "cpu"),
        settings=_settings(),
        estimate_fn=estimate_fn,
    )
    assert (seen["params"]["width"], seen["params"]["height"]) == SamplerWorker(fitted)._compute_dims(16, 8)


def test_start_worker_estimates_off_the_gui_thread(monkeypatch) -> None:
    gui = QThread.currentThread()
    seen: dict = {}

    def estimate_fn(*_args, **_kwargs):
        seen["estimate"] = QThread.currentThread()
        return _estimate(200)

    class Shown:
        choice = NoGpuChoice("cancel")

        def exec(self):
            seen["dialog"] = QThread.currentThread()
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(no_gpu_mod, "estimate_gif_job", estimate_fn)
    monkeypatch.setattr(no_gpu_mod, "usable_gif_gpu", lambda *_args, **_kwargs: (False, "cpu"))
    monkeypatch.setattr(no_gpu_mod, "NoGpuWindow", lambda *args, **kwargs: Shown())
    tab = SimpleNamespace(
        worker=None,
        btn_all=MagicMock(),
        btn_selected=MagicMock(),
        status_label=MagicMock(),
        progress_bar=MagicMock(),
    )
    controller = SamplerWorkerController(tab)
    monkeypatch.setattr(
        SamplerWorkerController,
        "_collect_config",
        lambda self, _use: {"files_to_process": ["clip.gif"], "scale_mode": "factor", "scale_factor": 2},
    )
    controller._start_worker(False)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and "dialog" not in seen:
        QApplication.processEvents()
        time.sleep(0.01)
    assert seen.get("estimate") is not None
    assert seen["estimate"] is not gui
    assert seen.get("dialog") is gui
    assert tab.worker is None
