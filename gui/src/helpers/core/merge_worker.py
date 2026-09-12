import os
from typing import Any, Dict, List, Union

from backend.src.constants import SUPPORTED_IMG_FORMATS
from backend.src.core import FSETool, ImageMerger
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.core.config_types import MergeConfig


class MergeWorker(BaseQThreadWorker):
    progress = Signal(int, int)  # (current, total)
    finished = Signal(object)  # output path, None on failure/cancel

    def __init__(self, config: Union[MergeConfig, Dict[str, Any]]):
        super().__init__()
        self.config = config

    def _execute(self) -> object:
        output_path = self.config["output_path"]
        direction = self.config["direction"]

        # ── Canvas composite mode ───────────────────────────────────────────
        if direction == "canvas":
            return self._run_canvas_composite(output_path)

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
                    image_files.extend(FSETool.get_files_by_extension(path, fmt, recursive=False))

        image_files = list(dict.fromkeys(input_paths))
        if not image_files:
            raise RuntimeError("No images found to merge.")

        if len(image_files) < 2:
            raise RuntimeError("Need at least 2 images to merge.")

        if self._cancelled:
            return None

        self.progress.emit(0, len(image_files))

        # "panorama" mode carries an engine choice (opencv/hugin/overmix/
        # asp); every other direction ignores engine/engine_kwargs.
        ImageMerger.merge_images(
            image_paths=image_files,
            output_path=output_path,
            direction=direction,
            grid_size=grid_size,
            align_mode=align_mode,
            spacing=spacing,
            engine=self.config.get("engine") or "opencv",
            engine_kwargs=self.config.get("engine_kwargs"),
        )

        self.progress.emit(len(image_files), len(image_files))
        return output_path

    def _run_canvas_composite(self, output_path: str) -> object:
        """PIL-based free-placement composite from canvas layout."""
        layout: List[Dict[str, Any]] | object | Any = self.config.get("canvas_layout", [])
        assert hasattr(layout, "__len__")
        if len(layout) < 2:  # pyrefly: ignore [bad-argument-type]
            raise RuntimeError("Need at least 2 images on the canvas.")

        from PIL import Image as PILImage

        canvas_w: int = self.config.get("canvas_width", 1920)  # pyrefly: ignore [bad-assignment]
        canvas_h: int = self.config.get("canvas_height", 1080)  # pyrefly: ignore [bad-assignment]
        bg: str = self.config.get("canvas_background", "transparent")  # pyrefly: ignore [bad-assignment]
        if bg == "white":
            result = PILImage.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
        elif bg == "black":
            result = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
        else:
            result = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        total = len(layout)  # pyrefly: ignore [bad-argument-type]
        for i, item in enumerate(layout):  # pyrefly: ignore [bad-argument-type]
            if self._cancelled:
                return None

            self.progress.emit(i, total)

            img = PILImage.open(item["path"]).convert("RGBA")
            w = max(1, item["w"])
            h = max(1, item["h"])
            img = img.resize((w, h), PILImage.Resampling.LANCZOS)
            result.paste(img, (item["x"], item["y"]), img)

        self.progress.emit(total, total)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        result.save(output_path, "PNG")
        return output_path
