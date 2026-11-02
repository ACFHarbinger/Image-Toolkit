"""No-GPU warning for a long GIF resample (C3, #1161, D15, D17, D18, D20).

Shown only when no usable GPU is found, the pre-flight estimate is above
``gif_upscale.no_gpu_threshold_s``, and ``gif_upscale.no_gpu_prompt`` is on.
Enter accepts the spin-box count and stores it as ``gif_upscale.workers``.
Shift+Enter continues and leaves that default alone. Closing cancels.
"Do not ask again" is written only after Enter or Shift+Enter.
"""

from __future__ import annotations

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

_MAX_WORKERS = 64


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
            f"No usable GPU was found. {name} is estimated at {total:.0f}s and will be slow."
        )
        self._warning.setWordWrap(True)
        self._path = QLabel(path)
        self._path.setWordWrap(True)
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


def estimate_params(config: dict[str, Any]) -> dict[str, Any]:
    """The resample request the Sampler would send, without a progress callback."""
    mode = str(config.get("scale_mode") or "factor")
    params: dict[str, Any] = {"algorithm": str(config.get("algorithm") or "lanczos")}
    if mode == "dimensions":
        params["mode"] = "dimensions"
        params["width"] = int(config.get("target_width") or 0)
        params["height"] = int(config.get("target_height") or 0)
    else:
        params["mode"] = "factor"
        params["factor"] = float(config.get("scale_factor") or 1)
    return params


def _first_gif(files: list[str]) -> str | None:
    for path in files:
        if str(path).lower().endswith(".gif"):
            return str(path)
    return None


def confirm_slow_gif(
    config: dict[str, Any],
    parent=None,
    *,
    probe: Callable[[], tuple[bool, str]] | None = None,
    settings: Any | None = None,
    estimate_fn: Callable[..., Any] | None = None,
) -> bool:
    """True to start the job. False when the user closes the window or the estimate fails.

    The default GPU probe may initialize CUDA. Tests pass ``probe`` and
    ``settings``. Only the first GIF is timed.
    """
    gif = _first_gif(list(config.get("files_to_process") or []))
    if gif is None:
        return True
    if settings is None:
        from middleware.src.settings.service import SettingsService

        settings = SettingsService()
    if not no_gpu_prompt_enabled(settings):
        return True
    usable, _label = usable_gif_gpu(probe)
    if usable:
        return True
    run = estimate_fn or estimate_gif_job
    try:
        estimate = run(
            gif,
            estimate_params(config),
            use_multicore=bool(config.get("use_multicore")),
            device_probe=probe if probe is not None else (lambda: (False, "cpu")),
            settings_service=settings,
        )
    except Exception as exc:
        QMessageBox.critical(parent, "GIF estimate failed", str(exc))
        return False
    if not should_prompt_no_gpu(
        usable_gpu=False,
        estimate_s=float(estimate.total_s),
        threshold_s=float(no_gpu_threshold_s(settings)),
        prompt_enabled=True,
    ):
        return True
    dialog = NoGpuWindow(
        estimate,
        use_multicore=bool(config.get("use_multicore")),
        source_name=gif,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    apply_no_gpu_choice(config, dialog.choice, settings)
    return True
