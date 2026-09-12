"""``SamplerSubTab`` -- composed from controllers (#544)."""

from __future__ import annotations

import contextlib
from typing import Any

from PySide6.QtCore import QPoint, Slot

from ....classes import AbstractClassTwoGalleries
from ._config import SamplerConfigController, _ConfigMixin
from ._directory_browse import SamplerDirectoryController, _DirectoryBrowseMixin
from ._gallery_cards import SamplerGalleryCardsController, _GalleryCardsMixin
from ._lifecycle import SamplerLifecycleController, _LifecycleMixin
from ._preview_context import SamplerPreviewController, _PreviewContextMixin
from ._resample_worker import SamplerWorkerController, _ResampleWorkerMixin
from ._scale_mode import SamplerScaleModeController, _ScaleModeMixin
from ._ui_builder import SamplerUIBuilder, _UIBuilderMixin


class SamplerSubTab(AbstractClassTwoGalleries):
    """Upsample / downsample images, GIFs, and videos."""

    def __init__(self):
        super().__init__()
        self.worker = None

        # Composed controllers
        self.ui_builder = SamplerUIBuilder(self)
        self.scale_mode_controller = SamplerScaleModeController(self)
        self.directory_controller = SamplerDirectoryController(self)
        self.gallery_cards_controller = SamplerGalleryCardsController(self)
        self.preview_controller = SamplerPreviewController(self)
        self.worker_controller = SamplerWorkerController(self)
        self.config_controller = SamplerConfigController(self)
        self.lifecycle_controller = SamplerLifecycleController(self)

        self._build_ui()

    # --- Direct Qt / Gallery lifecycle overrides ---
    def cancel_loading(self):
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        if hasattr(self, "worker") and self.worker:
            with contextlib.suppress(Exception):
                self.worker.cancel()

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        self.cancel_loading()
        super().closeEvent(event)

    # --- Facade delegation ---
    # UI Builder
    def _build_ui(self) -> None:
        self.ui_builder.build_ui()

    # Scale mode
    @Slot(bool)
    def _on_scale_mode_changed(self, factor_selected: bool) -> None:
        self.scale_mode_controller._on_scale_mode_changed(factor_selected)

    # Directory browse
    @Slot()
    def _browse_input(self) -> None:
        self.directory_controller._browse_input()

    @Slot()
    def _browse_output(self) -> None:
        self.directory_controller._browse_output()

    def _collect_paths(self) -> list:
        return self.directory_controller._collect_paths()

    def _scan_and_load(self) -> None:
        self.directory_controller._scan_and_load()

    # Gallery cards
    def on_selection_changed(self) -> None:
        self.gallery_cards_controller.on_selection_changed()

    def _sync_selection_from_dual(self) -> None:
        self.gallery_cards_controller._sync_selection_from_dual()

    def refresh_found_gallery(self) -> None:
        self.gallery_cards_controller.refresh_found_gallery()

    def refresh_selected_panel(self) -> None:
        self.gallery_cards_controller.refresh_selected_panel()

    def toggle_selection(self, path: str) -> None:
        self.gallery_cards_controller.toggle_selection(path)

    def clear_galleries(self, clear_data: bool = True) -> None:
        self.gallery_cards_controller.clear_galleries(clear_data)

    # Preview context
    @Slot(str)
    def _preview_image(self, path: str) -> None:
        self.preview_controller._preview_image(path)

    @Slot(QPoint, str)
    def _context_menu(self, pos: QPoint, path: str) -> None:
        self.preview_controller._context_menu(pos, path)

    # Resample worker
    def _collect_config(self, use_selection: bool) -> dict:
        return self.worker_controller._collect_config(use_selection)

    @Slot(bool)
    def _start_worker(self, use_selection: bool) -> None:
        self.worker_controller._start_worker(use_selection)

    @Slot(int, int)
    def _on_progress(self, completed: int, total: int) -> None:
        self.worker_controller._on_progress(completed, total)

    @Slot(int, str)
    def _on_done(self, count: int, msg: str) -> None:
        self.worker_controller._on_done(count, msg)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self.worker_controller._on_error(msg)

    # Config
    def get_default_config(self) -> dict[str, Any]:
        return self.config_controller.get_default_config()

    def set_config(self, config: dict[str, Any]) -> None:
        self.config_controller.set_config(config)


__all__ = [
    "SamplerSubTab",
    "_ConfigMixin",
    "_DirectoryBrowseMixin",
    "_GalleryCardsMixin",
    "_LifecycleMixin",
    "_PreviewContextMixin",
    "_ResampleWorkerMixin",
    "_ScaleModeMixin",
    "_UIBuilderMixin",
]
