"""ffmpeg-based timelapse preview generation for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING, List, Optional, Tuple, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from ._traversal import _build_traversal

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _PreviewMixin:
    """Generate + open a temporary concatenated preview video of the graph traversal."""

    _preview_tmp_dir: "Optional[str]"

    @Slot()
    def _preview_timelapse(self: "MonitorDisplaySubTabHostProtocol"):
        graph = self._current_graph()
        if graph is None:
            return
        seq = _build_traversal(graph)
        if not seq:
            QMessageBox.information(cast(QWidget, self), "Empty Sequence",
                                    "Add nodes and edges to build a sequence before previewing.")
            return
        if not shutil.which("ffmpeg"):
            QMessageBox.warning(cast(QWidget, self), "ffmpeg Not Found",
                                "ffmpeg must be installed to generate a preview video.\n"
                                "Install it via your package manager (e.g. sudo apt install ffmpeg).")
            return

        # Clean up previous temp dir
        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)

        tmp = tempfile.mkdtemp(prefix="wallpaper_preview_")
        self._preview_tmp_dir = tmp

        self._btn_preview.setText("Generating…")
        self._btn_preview.setEnabled(False)
        QTimer.singleShot(0, lambda: self._generate_preview(seq, tmp))

    def _generate_preview(self: "MonitorDisplaySubTabHostProtocol", seq: List[Tuple[str, float]], tmp: str):
        try:
            concat_list = os.path.join(tmp, "concat.txt")
            segment_paths = []
            resolution = "1280:720"
            vf_pad = (
                f"scale={resolution}:force_original_aspect_ratio=decrease,"
                f"pad={resolution}:(ow-iw)/2:(oh-ih)/2:black"
            )

            for i, (fp, dur) in enumerate(seq):
                seg = os.path.join(tmp, f"seg{i:04d}.mp4")
                ext = os.path.splitext(fp)[1].lower()
                if ext in SUPPORTED_VIDEO_FORMATS:
                    cmd = ["ffmpeg", "-y", "-i", fp,
                           "-t", str(dur),
                           "-vf", vf_pad,
                           "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-an", seg]
                else:
                    cmd = ["ffmpeg", "-y",
                           "-loop", "1", "-i", fp,
                           "-t", str(dur),
                           "-vf", vf_pad,
                           "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-an", seg]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(
                        f"ffmpeg failed on segment {i}:\n"
                        + result.stderr.decode(errors="replace")[-500:]
                    )
                segment_paths.append(seg)

            with open(concat_list, "w") as f:
                for sp in segment_paths:
                    f.write(f"file '{sp}'\n")

            out_path = os.path.join(tmp, "preview.mp4")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", concat_list, "-c", "copy", out_path]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(
                    "ffmpeg concat failed:\n"
                    + result.stderr.decode(errors="replace")[-500:]
                )

            self._open_file(out_path)
        except Exception as e:
            QMessageBox.critical(cast(QWidget, self), "Preview Error", f"Failed to generate preview:\n{e}")
        finally:
            self._btn_preview.setText("▶ Preview Timelapse")
            self._btn_preview.setEnabled(True)

    def _open_file(self: "MonitorDisplaySubTabHostProtocol", path: str):
        sys_name = platform.system()
        try:
            if sys_name == "Windows":
                start_fn = getattr(os, "startfile", None)
                if start_fn:
                    start_fn(path)
            elif sys_name == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            QMessageBox.warning(cast(QWidget, self), "Open Error", f"Could not open preview:\n{path}\n{e}")


__all__ = ["_PreviewMixin"]
