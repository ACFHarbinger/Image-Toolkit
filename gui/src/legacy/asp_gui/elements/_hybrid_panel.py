"""Hybrid Stitch sub-tab.

Hosts both directions of the frame handoff: Hybrid Stitch → Stitch
(``sequence_accepted``) and a finished ASP result → Hybrid Stitch (#1088).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from middleware.src.services.asp.handoff import (
    AspHybridHandoff,
    HandoffContractError,
    handoff_summary,
)
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from ._stitch_tab_protocol import _StitchTabHost

    # Type-checking-only base: gives mypy visibility into attributes set by
    # StitchTab.__init__ / sibling mixins (see _stitch_tab_protocol.py).
    # Zero runtime effect -- at runtime this mixin still only inherits object.
    class _Base(_StitchTabHost, QWidget): ...
else:
    _Base = object


class _HybridPanelMixin(_Base):
    def _build_hybrid_panel(self) -> QWidget:
        from asp_gui.tabs.stencil import HybridStitchPanel

        self._hybrid_panel = HybridStitchPanel(self)
        self._hybrid_panel.sequence_accepted.connect(self._on_hybrid_sequence_accepted)
        return self._hybrid_panel

    @Slot(list)
    def _on_hybrid_sequence_accepted(self, paths: list[str]):
        """Load the sequence from the Hybrid Stitch panel into the Stitch tab."""
        if not paths:
            return
        self._frame_paths = list(paths)
        self._frame_item_map.clear()
        self._frame_list.clear()
        for p in self._frame_paths:
            self._frame_list.addItem(self._make_frame_item(p))
        self._refresh_pair_combo()
        self._tab_widget.setCurrentIndex(0)
        QMessageBox.information(
            self,
            "Hybrid Stitch",
            f"Loaded {len(paths)} frame(s) into the Stitch tab.\n"
            "Switch to the Stitch tab to run the pipeline.",
        )

    def _clear_asp_hybrid_handoff(self) -> None:
        """Drop the previous ASP result so a new run cannot refine stale frames."""
        self._asp_hybrid_handoff = None
        button = getattr(self, "_btn_refine_hybrid", None)
        if button is not None:
            button.setEnabled(False)

    @Slot(object)
    def _on_asp_hybrid_handoff(self, payload: object) -> None:
        """Store a finished ASP result until the user sends it to Hybrid Stitch."""
        try:
            if not isinstance(payload, (AspHybridHandoff, Mapping)):
                raise HandoffContractError("hybrid handoff payload must be an object", field="payload")
            handoff = AspHybridHandoff.from_payload(payload)
        except HandoffContractError as exc:
            self._clear_asp_hybrid_handoff()
            self._log_append(f"[Stitch] Hybrid handoff unavailable: {exc}")
            return
        self._asp_hybrid_handoff = handoff
        self._btn_refine_hybrid.setEnabled(True)
        self._log_append(
            f"[Stitch] Hybrid Stitch handoff ready — {len(handoff.image_paths)} frames, "
            f"{len(handoff.pair_homographies)} seeded pair(s)."
        )

    def _handoff_asp_to_hybrid(self) -> None:
        """Load the last ASP result into Hybrid Stitch and switch to that tab."""
        handoff = getattr(self, "_asp_hybrid_handoff", None)
        if handoff is None:
            return
        self._hybrid_panel.apply_asp_handoff(handoff)
        index = self._tab_widget.indexOf(self.hybrid_stitch_panel)
        if index >= 0:
            self._tab_widget.setCurrentIndex(index)
        summary = handoff_summary(handoff)
        self._log_append("[Stitch] " + summary.replace("\n", " "))
        QMessageBox.information(self, "Hybrid Stitch", summary)


__all__ = ["_HybridPanelMixin"]
