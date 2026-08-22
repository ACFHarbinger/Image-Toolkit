"""Selection handling + the bottom "Selected Images" gallery for ``ScanMetadataTab``.

The selected gallery now lives inside the ``VirtualDualGallery`` (GUI/UX §2.1
Option A): the dual maintains the selected-set insertion order, which replaces
the old drag-reorderable grid. ``selected_image_paths`` stays the tab's
source of truth for upsert/delete flows; ``_selected_order`` preserves the
manual/insertion order the dual provides.
"""

from __future__ import annotations

from ....utils.sort_utils import natural_sort_key


class _SelectionGalleryMixin:
    """Toggle/marquee selection and sync the dual gallery's selected panel."""

    def on_selection_changed(self) -> None:
        """Required by AbstractClassTwoGalleries base class."""
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def toggle_selection(self, path):
        if not path:
            self.update_button_states(connected=(self.db_tab_ref.db is not None))
            return
        # The dual toggles the path in its selection set and emits
        # selection_changed, which syncs selected_image_paths back via
        # _sync_selection_from_dual.
        self.dual.toggle_selection(path)

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        # Marquee/drag selection is handled natively by the QListView
        # selection model; the dual's selection_changed already synced it.
        self._sync_selection_from_dual()

    def _sync_selection_from_dual(self):
        """Mirror the dual's selected paths into ``selected_image_paths`` and
        reconcile ``_selected_order`` (self-healing like the old grid)."""
        self.selected_image_paths = set(self.dual.selected_paths())
        ordered = self._selected_order
        kept = [p for p in ordered if p in self.selected_image_paths]
        missing = sorted(
            self.selected_image_paths - set(kept), key=natural_sort_key
        )
        self._selected_order = kept + missing
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def _push_selection_to_dual(self):
        """Apply ``selected_image_paths``/``_selected_order`` to the dual."""
        ordered = self._selected_order
        kept = [p for p in ordered if p in self.selected_image_paths]
        missing = sorted(
            self.selected_image_paths - set(kept), key=natural_sort_key
        )
        self._selected_order = kept + missing
        self.dual.set_selected_paths(self._selected_order)

    def populate_selected_images_gallery(self):
        """Rebuild the dual's selected panel from the reconciled order."""
        self._push_selection_to_dual()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def reorder_selected(self, dragged_path: str, target_path: str) -> None:
        """Drag-and-drop callback (kept for API compatibility): reorders
        ``_selected_order`` and pushes it back to the dual."""
        from ....classes.mixins import compute_reordered

        self._selected_order = compute_reordered(
            self._selected_order, dragged_path, target_path
        )
        self._push_selection_to_dual()


__all__ = ["_SelectionGalleryMixin"]
