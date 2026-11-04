"""No-GPU warning for a long GIF resample (C3, #1161, D15, D17, D18, D20).

Shown when this job will run on CPU, the pre-flight estimate is above
``gif_upscale.no_gpu_threshold_s``, and ``gif_upscale.no_gpu_prompt`` is on.
CUDA being present is not enough to hide the window: the default ``lanczos``
algorithm never takes the GPU path, so a CUDA machine still offers the
window for that job. ``lanczos3-dering`` with the temporal encoder skips the
window only when a free allowed card is projected. That projection honors
the allow-list, current holders, and a pinned device. Admission is
provisional and is not a lease.

Only the first GIF is timed. A later GIF in the same batch can be slower
and is not estimated.

Enter accepts the spin-box count and stores it as ``gif_upscale.workers``.
Shift+Enter continues and leaves that default alone. Closing cancels.
"Do not ask again" is written only after Enter or Shift+Enter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from middleware.src.services.media.gif_upscale.estimate import (
    estimate_gif_job,
    usable_gif_gpu,
    workers_batch_warning,
)
from middleware.src.services.media.gif_upscale.job_settings import (
    NO_GPU_PROMPT_KEY,
    WORKERS_KEY,
    no_gpu_prompt_enabled,
    no_gpu_threshold_s,
    with_job_settings,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from gui.src.helpers.core.sampler_worker import compute_resample_dims

_MAX_WORKERS = 64
_GPU_ALGORITHM = "lanczos3-dering"
_GPU_ENCODER = "temporal"
_PROVISIONAL = "Admission is provisional and is not a lease."


@dataclass(frozen=True)
class NoGpuChoice:
    """What the window returned. ``cancel`` means the job must not start."""

    action: str
    workers: int | None = None
    remember: bool = False


def should_prompt_no_gpu(
    *,
    usable_gpu: bool,
    estimate_s: float,
    threshold_s: float,
    prompt_enabled: bool,
) -> bool:
    """The window's gate. A short job, a usable GPU, or the off flag skips it."""
    if usable_gpu or not prompt_enabled:
        return False
    return float(estimate_s) > float(threshold_s)


class NoGpuWindow(QDialog):
    """Warn that the GIF will be slow and ask for a CPU worker count."""

    def __init__(self, estimate: Any, *, use_multicore: bool, source_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("No GPU for this GIF")
        self.choice = NoGpuChoice("cancel")
        self._use_multicore = bool(use_multicore)
        total = float(getattr(estimate, "total_s", 0.0))
        path = str(getattr(estimate, "path", "") or "cpu")
        name = source_name or "the first GIF"

        self._warning = QLabel(
            f"This job will run on CPU. {name} is estimated at {total:.0f}s and will be slow. "
            "Only the first GIF is timed; a later GIF can be slower."
        )
        self._warning.setWordWrap(True)
        self._path = QLabel(path)
        self._path.setWordWrap(True)
        self._admission = QLabel(_PROVISIONAL)
        self._admission.setWordWrap(True)
        self._spin = QSpinBox()
        self._spin.setRange(1, _MAX_WORKERS)
        self._spin.setValue(1)
        self._spin.setPrefix("CPU workers: ")
        self._d10 = QLabel("")
        self._d10.setWordWrap(True)
        self._remember = QCheckBox("Do not ask again")
        self._workers_btn = QPushButton("Use this many workers (Enter)")
        self._continue_btn = QPushButton("Continue without more workers (Shift+Enter)")
        self._workers_btn.clicked.connect(self.accept_workers)
        self._continue_btn.clicked.connect(self.continue_without_workers)
        self._spin.valueChanged.connect(self._refresh_warning)
        self._bind_keys()

        row = QHBoxLayout()
        row.addWidget(self._spin)
        buttons = QHBoxLayout()
        buttons.addWidget(self._workers_btn)
        buttons.addWidget(self._continue_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(self._warning)
        layout.addWidget(self._path)
        layout.addWidget(self._admission)
        layout.addLayout(row)
        layout.addWidget(self._d10)
        layout.addWidget(self._remember)
        layout.addLayout(buttons)
        self._refresh_warning()

    def _bind_keys(self) -> None:
        context = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for sequence, slot in (
            (QKeySequence(Qt.Key.Key_Return), self.accept_workers),
            (QKeySequence(Qt.Key.Key_Enter), self.accept_workers),
            (QKeySequence("Shift+Return"), self.continue_without_workers),
            (QKeySequence("Shift+Enter"), self.continue_without_workers),
        ):
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(context)
            shortcut.activated.connect(slot)

    def _refresh_warning(self) -> None:
        text = workers_batch_warning(int(self._spin.value()), self._use_multicore)
        self._d10.setText(text or "")

    def accept_workers(self) -> None:
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.continue_without_workers()
            return
        self.choice = NoGpuChoice("workers", int(self._spin.value()), self._remember.isChecked())
        self.accept()

    def continue_without_workers(self) -> None:
        self.choice = NoGpuChoice("continue", None, self._remember.isChecked())
        self.accept()

    def reject(self) -> None:  # noqa: D102
        self.choice = NoGpuChoice("cancel")
        super().reject()


def apply_no_gpu_choice(config: dict[str, Any], choice: NoGpuChoice, service: Any) -> None:
    """Store an accepted choice. Cancel writes nothing. Continue does not change workers."""
    if choice.action == "cancel":
        return
    if choice.remember:
        service.set(NO_GPU_PROMPT_KEY, False)
    if choice.action == "workers" and choice.workers is not None:
        service.set(WORKERS_KEY, int(choice.workers))
        config["workers"] = int(choice.workers)


def estimate_params(config: dict[str, Any], source_size: tuple[int, int] | None = None) -> dict[str, Any]:
    """The resample request the Sampler worker would send, without a progress callback.

    When the source size is known, width and height are the fitted pixels from
    ``compute_resample_dims`` (the same function the worker uses), including a
    width-only or height-only request. Without a size, a dimensions request
    keeps the raw spin values so a missing test path is not opened.
    """
    params: dict[str, Any] = {"algorithm": str(config.get("algorithm") or "lanczos")}
    if source_size is not None:
        width, height = compute_resample_dims(config, int(source_size[0]), int(source_size[1]))
        params["mode"] = "dimensions"
        params["width"] = int(width)
        params["height"] = int(height)
    else:
        mode = str(config.get("scale_mode") or "factor")
        if mode == "dimensions":
            params["mode"] = "dimensions"
            params["width"] = int(config.get("target_width") or 0)
            params["height"] = int(config.get("target_height") or 0)
        else:
            params["mode"] = "factor"
            params["factor"] = float(config.get("scale_factor") or 1)
    for key in ("device", "allow_devices", "gpu_arbiter", "encoder"):
        if key not in config:
            continue
        value = config.get(key)
        if value in (None, ""):
            continue
        params[key] = value
    return params


def _source_size(path: str) -> tuple[int, int] | None:
    """Pixel size of a real file. A missing path stays None so tests do not open it."""
    if not os.path.isfile(path):
        return None
    from PIL import Image

    with Image.open(path) as image:
        return int(image.size[0]), int(image.size[1])


def _job_uses_gpu(request: dict[str, Any], probe: Callable[[], tuple[bool, str]] | None) -> bool:
    """Whether this job would take the production GPU path.

    That path is ``lanczos3-dering`` plus the temporal encoder, and a card
    ``usable_gif_gpu`` still projects as free. The result is provisional and
    is not a lease. Default ``lanczos`` returns False without asking CUDA,
    so the no-GPU window can still open on a machine that has a card.
    """
    algorithm = str(request.get("algorithm") or "lanczos").strip().lower()
    encoder = str(request.get("encoder") or _GPU_ENCODER).strip().lower()
    if algorithm != _GPU_ALGORITHM or encoder != _GPU_ENCODER:
        return False
    usable, _label = usable_gif_gpu(probe, params=request)
    return bool(usable)


def _first_gif(files: list[str]) -> str | None:
    for path in files:
        if str(path).lower().endswith(".gif"):
            return str(path)
    return None


@dataclass(frozen=True)
class SlowGifPlan:
    """Widget-free preflight result. ``prompt`` still needs a dialog on the GUI thread."""

    action: str
    message: str = ""
    estimate: Any = None
    source_name: str = ""
    settings: Any = None


def plan_slow_gif(
    config: dict[str, Any],
    *,
    probe: Callable[[], tuple[bool, str]] | None = None,
    settings: Any | None = None,
    estimate_fn: Callable[..., Any] | None = None,
) -> SlowGifPlan:
    """Decide whether to start, fail, or prompt. Does not create widgets.

    Safe to call off the GUI thread. The default probe may initialize CUDA
    and is only reached for a job that would actually take the GPU path.
    ``settings`` left as None is opened here. Only the first GIF is timed;
    a later GIF can be slower.
    """
    if settings is None:
        from middleware.src.settings.service import SettingsService

        settings = SettingsService()
    gif = _first_gif(list(config.get("files_to_process") or []))
    if gif is None or not no_gpu_prompt_enabled(settings):
        return SlowGifPlan("start", settings=settings)
    request = with_job_settings(estimate_params(config, _source_size(gif)), settings)
    if _job_uses_gpu(request, probe):
        return SlowGifPlan("start", settings=settings)
    run = estimate_fn or estimate_gif_job
    try:
        estimate = run(
            gif,
            request,
            use_multicore=bool(config.get("use_multicore")),
            device_probe=probe,
            settings_service=settings,
        )
    except Exception as exc:
        return SlowGifPlan("fail", message=str(exc), settings=settings)
    if not should_prompt_no_gpu(
        usable_gpu=False,
        estimate_s=float(estimate.total_s),
        threshold_s=float(no_gpu_threshold_s(settings)),
        prompt_enabled=True,
    ):
        return SlowGifPlan("start", settings=settings)
    return SlowGifPlan("prompt", estimate=estimate, source_name=gif, settings=settings)


def confirm_slow_gif(
    config: dict[str, Any],
    parent=None,
    *,
    probe: Callable[[], tuple[bool, str]] | None = None,
    settings: Any | None = None,
    estimate_fn: Callable[..., Any] | None = None,
) -> bool:
    """True to start the job. False when the user closes the window or the estimate fails.

    The dialog runs on the caller thread. The Sampler controller does not use
    this; it runs ``plan_slow_gif`` on a worker and shows the dialog from a
    queued signal. Only the first GIF is timed.
    """
    if settings is None:
        from middleware.src.settings.service import SettingsService

        settings = SettingsService()
    decision = plan_slow_gif(config, probe=probe, settings=settings, estimate_fn=estimate_fn)
    if decision.action == "start":
        return True
    if decision.action == "fail":
        QMessageBox.critical(parent, "GIF estimate failed", decision.message)
        return False
    dialog = NoGpuWindow(
        decision.estimate,
        use_multicore=bool(config.get("use_multicore")),
        source_name=decision.source_name,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    apply_no_gpu_choice(config, dialog.choice, settings)
    return True
