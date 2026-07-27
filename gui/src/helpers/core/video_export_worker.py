from typing import Optional, Tuple

from backend.src.core import ImageMerger
from PySide6.QtCore import QThread, Signal


class ScrollVideoExportWorker(QThread):
    """
    Runs `ImageMerger.export_scrolling_video` off the GUI thread (roadmap
    §4.2 — Export Stitched Panorama to Scrolling Video). Mirrors the
    MergeWorker signal pattern used elsewhere in the Merge tab.
    """

    sig_finished = Signal(str)  # output path
    error = Signal(str)

    def __init__(
        self,
        image_path: str,
        output_path: str,
        scroll_speed_px_per_frame: int = 10,
        fps: int = 30,
        resolution: Optional[Tuple[int, int]] = None,
        scroll_axis: Optional[str] = None,
        codec: str = "libx264",
    ):
        super().__init__()
        self.image_path = image_path
        self.output_path = output_path
        self.scroll_speed_px_per_frame = scroll_speed_px_per_frame
        self.fps = fps
        self.resolution = resolution
        self.scroll_axis = scroll_axis
        self.codec = codec

    def run(self):
        try:
            result_path = ImageMerger.export_scrolling_video(
                self.image_path,
                self.output_path,
                scroll_speed_px_per_frame=self.scroll_speed_px_per_frame,
                fps=self.fps,
                resolution=self.resolution,
                scroll_axis=self.scroll_axis,
                codec=self.codec,
            )
            self.sig_finished.emit(result_path)
        except Exception as e:
            self.error.emit(f"Scrolling video export failed: {e}")
