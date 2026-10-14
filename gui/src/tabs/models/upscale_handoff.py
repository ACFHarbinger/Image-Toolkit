"""Upscale handoff: Send-to-Upscale job shared by Generate/Review (#749).

Wires the existing (previously unwired) ``ESRGANWrapper``
(``backend/src/models/wrappers/esrgan_wrapper.py``) into the DL workspace:
every surface resolves its output to image bytes or a local file, runs one
admission-guarded job off the GUI thread, and lands the result back where
the source was shown.

Job shape mirrors ``LoRAGenerateTab.run_generation``: ``try_admit`` under
one owner, work, ``gpu_lease.release`` in ``finally``. The lease is shared
with training and generation, so an upscale never runs concurrently with
them — it waits its turn via the refusal message instead.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import threading
from pathlib import Path

from backend.src.comfy_matrix import gpu_lease, try_admit
from backend.src.core.gpu_vram_estimate import estimate_job_gb, image_size
from PySide6.QtCore import QObject, Signal

UPSCALE_OWNER = "upscale"
UPSCALE_SUFFIX = "_upscaled_4x"


def upscaled_output_path(source_path: str) -> str:
    """Sibling output path for *source_path*; never equal to the source."""
    base, ext = os.path.splitext(source_path)
    candidate = f"{base}{UPSCALE_SUFFIX}{ext or '.png'}"
    index = 2
    while os.path.exists(candidate):
        candidate = f"{base}{UPSCALE_SUFFIX}_{index}{ext or '.png'}"
        index += 1
    return candidate


def latest_output_paths(output_filename: str, batch_size: int) -> list[str]:
    """Existing files from the last generation run.

    Batch runs save ``{stem}_{i}{ext}`` (1-based); a single run saves
    *output_filename* itself (see ``LoRATuner.generate_anime_image``).
    Missing files are skipped, never invented.
    """
    base, ext = os.path.splitext(output_filename)
    candidates = (
        [f"{base}_{i + 1}{ext}" for i in range(batch_size)]
        if batch_size > 1
        else [output_filename]
    )
    return [path for path in candidates if os.path.isfile(path)]


def decode_image_bytes(data: bytes):
    """Decode raw image bytes to a BGR uint8 array; None when undecodable.

    Decoded with Qt rather than OpenCV: ``gui/test/conftest.py`` replaces
    ``cv2`` with a stub, and Qt is already a hard GUI dependency.
    """
    import numpy as np
    from PySide6.QtGui import QImage

    if not isinstance(data, (bytes, bytearray)) or not data:
        return None
    image = QImage()
    if not image.loadFromData(bytes(data)):
        return None
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    height, width = rgb.height(), rgb.width()
    if height <= 0 or width <= 0:
        return None
    arr = (
        np.frombuffer(rgb.constBits(), dtype=np.uint8)
        .reshape(height, rgb.bytesPerLine())[:, :width * 3]
        .reshape(height, width, 3)
        .copy()
    )
    return arr[:, :, ::-1]


def run_upscale_file(input_path: str, output_path: str) -> str:
    """Upscale one local file under GPU admission; return *output_path*.

    Blocking — call off the GUI thread (see :class:`UpscaleRunner`).
    Raises ``RuntimeError`` when the lease is held, ``FileNotFoundError``
    for a missing source. The wrapper import stays lazy so constructing
    tabs never pays for torch.
    """
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ValueError("Upscale output must not replace its source.")
    size = image_size(input_path)
    refusal = try_admit(
        UPSCALE_OWNER,
        estimated_gb=estimate_job_gb(
            UPSCALE_OWNER,
            width=None if size is None else size[0],
            height=None if size is None else size[1],
        ),
    )
    if refusal:
        raise RuntimeError(refusal)
    try:
        from backend.src.models.wrappers.esrgan_wrapper import ESRGANWrapper

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        # Exclusive reservation prevents overwriting an earlier result or a symlink.
        with open(output_path, "xb"):
            pass
        try:
            wrapper = ESRGANWrapper()
            try:
                wrapper.upscale_path(input_path, output_path)
            finally:
                unload = getattr(wrapper, "unload", None)
                if callable(unload):
                    unload()
            if os.path.getsize(output_path) == 0:
                raise OSError("Upscaler did not write an output image.")
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(output_path)
            raise
    finally:
        gpu_lease.release(UPSCALE_OWNER)
    return output_path


class UpscaleRunner(QObject):
    """One upscale job on a daemon thread with GUI-safe completion signals."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._closed = threading.Event()
        self.destroyed.connect(lambda *_args, closed=self._closed: closed.set())

    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, input_paths) -> threading.Thread | None:
        """Start a batch; each image obtains GPU admission before processing."""
        input_paths = [input_paths] if isinstance(input_paths, str) else list(input_paths)
        if self.busy():
            self.error.emit("An upscale job is already running.")
            return None
        thread = threading.Thread(
            target=self._run, args=(input_paths,), daemon=True
        )
        self._thread = thread
        thread.start()
        return thread

    def start_remote(self, fetcher, filename: str, subfolder: str, kind: str, directory: str):
        if self.busy():
            return None

        def resolve():
            from PySide6.QtGui import QImage

            data = fetcher(filename, subfolder, kind)
            image = QImage.fromData(data)
            if image.isNull():
                raise ValueError("Could not decode the original output.")
            os.makedirs(directory, exist_ok=True)
            fd, path = tempfile.mkstemp(prefix="comfy-", suffix=".png", dir=directory)
            os.close(fd)
            if not image.save(path, "PNG"):
                os.unlink(path)
                raise OSError("Could not save output snapshot.")
            return [path]

        self._thread = threading.Thread(target=self._run, args=(resolve,), daemon=True)
        self._thread.start()
        return self._thread

    def _run(self, input_paths) -> None:
        """Synchronous worker body; tests call this directly, no thread."""
        try:
            paths = input_paths() if callable(input_paths) else input_paths
            outputs = []
            for path in paths:
                if self._closed.is_set():
                    return
                outputs.append(run_upscale_file(path, upscaled_output_path(path)))
        except Exception as exc:
            if not self._closed.is_set():
                with contextlib.suppress(RuntimeError):
                    self.error.emit(str(exc))
        else:
            if not self._closed.is_set():
                with contextlib.suppress(RuntimeError):
                    self.finished.emit(outputs)
