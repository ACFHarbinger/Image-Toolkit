import os

from PIL import Image as PILImage
from typing import Dict, List, Union, Any
from PySide6.QtCore import QObject, Signal
from backend.src.core import FSETool, ImageMerger
from backend.src.constants import SUPPORTED_IMG_FORMATS
from gui.src.helpers.core.config_types import MergeConfig


class MergeWorker(QObject):
    progress = Signal(int, int)  # (current, total)
    finished = Signal(str)  # output path
    error = Signal(str)
    cancelled = Signal()

    def __init__(self, config: Union[MergeConfig, Dict[str, Any]]):
        super().__init__()
        self.config = config
        self._should_stop = False

    def cancel(self) -> None:
        """Signal the worker to stop before the next checkpoint."""
        self._should_stop = True

    def run(self):
        try:
            output_path = self.config["output_path"]
            direction = self.config["direction"]

            # ── Canvas composite mode ───────────────────────────────────────────
            if direction == "canvas":
                self._run_canvas_composite(output_path)
                return

            # ── Traditional / AI stitch modes ──────────────────────────────────
            input_paths = self.config["input_path"]
            spacing = self.config["spacing"]
            align_mode = self.config["align_mode"]
            grid_size = self.config["grid_size"]
            formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS

            image_files: List[str] = []
            for path in input_paths:
                if os.path.isfile(path):
                    if any(path.lower().endswith(f".{fmt}") for fmt in formats):
                        image_files.append(path)
                elif os.path.isdir(path):
                    for fmt in formats:
                        image_files.extend(
                            FSETool.get_files_by_extension(path, fmt, recursive=False)
                        )

            image_files = list(dict.fromkeys(input_paths))
            if not image_files:
                self.error.emit("No images found to merge.")
                return

            if len(image_files) < 2:
                self.error.emit("Need at least 2 images to merge.")
                return

            if self._should_stop:
                self.cancelled.emit()
                return

            self.progress.emit(0, len(image_files))

            perfect_stitch_mode = self.config.get("perfect_stitch_mode", False)
            edge_crop_px = self.config.get("edge_crop_px", 0)
            pyramid_levels = self.config.get("pyramid_levels", 4)

            if perfect_stitch_mode:
                ImageMerger.perfect_stitch(
                    image_paths=image_files,
                    output_path=output_path,
                    edge_crop=edge_crop_px,
                    pyramid_levels=pyramid_levels,
                    use_siamese=self.config.get("use_siamese", True),
                    use_apap=self.config.get("use_apap", True),
                    use_lsd=self.config.get("use_lsd", True),
                    use_gan=self.config.get("use_gan", True),
                    use_birefnet=self.config.get("use_birefnet", True),
                    use_basic=self.config.get("use_basic", True),
                    use_loftr=self.config.get("use_loftr", True),
                    use_ecc=self.config.get("use_ecc", True),
                    renderer=self.config.get("renderer", "blend"),
                    composite_fg=self.config.get("composite_fg", True),
                    motion_model=self.config.get("motion_model", "translation"),
                    mfsr_mode=self.config.get("mfsr_mode", False),
                    mfsr_n_dct_iter=self.config.get("mfsr_n_dct_iter", 20),
                    mfsr_use_prior=self.config.get("mfsr_use_prior", True),
                    mfsr_use_diffusion=self.config.get("mfsr_use_diffusion", False),
                )
            else:
                ImageMerger.merge_images(
                    image_paths=image_files,
                    output_path=output_path,
                    direction=direction,
                    grid_size=grid_size,
                    align_mode=align_mode,
                    spacing=spacing,
                )

            self.progress.emit(len(image_files), len(image_files))
            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(f"Merge failed: {str(e)}")

    def _run_canvas_composite(self, output_path: str) -> None:
        """PIL-based free-placement composite from canvas layout."""
        try:
            layout: List[Dict[str, Any]] | object | Any = self.config.get("canvas_layout", [])
            assert hasattr(layout, '__len__')
            if len(layout) < 2: # pyrefly: ignore [bad-argument-type]
                self.error.emit("Need at least 2 images on the canvas.")
                return

            canvas_w: int = self.config.get("canvas_width", 1920) # pyrefly: ignore [bad-assignment]
            canvas_h: int = self.config.get("canvas_height", 1080) # pyrefly: ignore [bad-assignment]
            bg: str = self.config.get("canvas_background", "transparent") # pyrefly: ignore [bad-assignment]
            if bg == "white":
                result = PILImage.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
            elif bg == "black":
                result = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
            else:
                result = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

            total = len(layout) # pyrefly: ignore [bad-argument-type]
            for i, item in enumerate(layout): # pyrefly: ignore [bad-argument-type]
                if self._should_stop:
                    self.cancelled.emit()
                    return

                self.progress.emit(i, total)

                img = PILImage.open(item["path"]).convert("RGBA")
                w = max(1, item["w"])
                h = max(1, item["h"])
                img = img.resize((w, h), PILImage.Resampling.LANCZOS)
                result.paste(img, (item["x"], item["y"]), img)

            self.progress.emit(total, total)

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            result.save(output_path, "PNG")
            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(f"Canvas merge failed: {str(e)}")
