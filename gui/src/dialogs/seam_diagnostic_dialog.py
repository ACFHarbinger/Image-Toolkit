"""§2.4A/C — Seam Registration Inspector dialog (S95–S96).

Surfaces per-seam diagnostic data from HITL checkpoint 4.6:
- post_warp_diff coloured green/amber/red (using the same thresholds as §2.4B overlay)
- single-pose escalation badge
- ±50px seam zone crop thumbnail (§2.4C, S96)
- "Force single-pose" / "Force blend" checkboxes per seam (mutually exclusive)
- "Accept" / "Cancel" buttons; "Accept" returns the user's per-seam overrides
"""

from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.src.constants import SEAM_OVERLAY_AMBER_THRESH, SEAM_OVERLAY_RED_THRESH


class _SeamCard(QFrame):
    """Compact per-seam diagnostic card.

    Displays seam index, boundary y-position, post_warp_diff (coloured),
    single-pose status, optional ±50px crop thumbnail (§2.4C), and two
    mutually-exclusive override checkboxes.
    """

    def __init__(
        self,
        k: int,
        boundary_y: float,
        post_diff: float,
        is_single_pose: bool,
        crop: Optional[np.ndarray] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._k = k
        self._post_diff = post_diff
        self._is_single_pose = is_single_pose

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        has_crop = crop is not None and crop.size > 0
        self.setMinimumHeight(56 + (70 if has_crop else 0))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(12)
        outer.addLayout(row)

        # ── Seam identity ──────────────────────────────────────────────────
        id_lbl = QLabel(f"S{k}")
        id_lbl.setFixedWidth(28)
        id_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        id_lbl.setStyleSheet("font-weight:bold; font-size:12px;")
        row.addWidget(id_lbl)

        # Boundary position
        pos_lbl = QLabel(f"y={int(boundary_y)}px")
        pos_lbl.setFixedWidth(64)
        row.addWidget(pos_lbl)

        # post_warp_diff with colour coding
        if is_single_pose or post_diff >= SEAM_OVERLAY_RED_THRESH:
            diff_colour = "#cc2200"
        elif post_diff >= SEAM_OVERLAY_AMBER_THRESH:
            diff_colour = "#cc7700"
        else:
            diff_colour = "#007700"

        diff_text = f"diff={post_diff:.1f}" if post_diff < 90.0 else "diff=forced"
        diff_lbl = QLabel(diff_text)
        diff_lbl.setStyleSheet(
            f"color:{diff_colour}; font-weight:bold; min-width:80px;"
        )
        row.addWidget(diff_lbl)

        # Single-pose badge
        sp_lbl = QLabel("SP" if is_single_pose else "—")
        sp_lbl.setFixedWidth(28)
        sp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_single_pose:
            sp_lbl.setStyleSheet(
                "background:#cc2200; color:white; border-radius:3px; font-size:10px;"
            )
        row.addWidget(sp_lbl)

        row.addStretch(1)

        # Override checkboxes (mutually exclusive)
        self._cb_sp = QCheckBox("Force SP")
        self._cb_sp.setToolTip("Force this seam to use the dominant single-pose frame (no blend)")
        self._cb_blend = QCheckBox("Force blend")
        self._cb_blend.setToolTip("Force this seam to use DSFN blend even if post_warp_diff is high")
        self._cb_sp.toggled.connect(self._on_sp_toggled)
        self._cb_blend.toggled.connect(self._on_blend_toggled)
        row.addWidget(self._cb_sp)
        row.addWidget(self._cb_blend)

        # ── §2.4C: seam zone crop thumbnail ───────────────────────────────
        if has_crop:
            pix = self._make_crop_pixmap(crop, max_width=300, max_height=64)
            crop_lbl = QLabel()
            crop_lbl.setPixmap(pix)
            crop_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            crop_lbl.setContentsMargins(8, 0, 8, 4)
            outer.addWidget(crop_lbl)

    # ── §2.4C helper ────────────────────────────────────────────────────────

    @staticmethod
    def _make_crop_pixmap(
        arr: np.ndarray, max_width: int = 300, max_height: int = 64
    ) -> QPixmap:
        """Scale a BGR crop array to fit within (max_width, max_height) and return QPixmap."""
        h, w = arr.shape[:2]
        scale = min(max_width / max(w, 1), max_height / max(h, 1), 1.0)
        if scale < 1.0:
            arr = cv2.resize(
                arr, (max(1, int(w * scale)), max(1, int(h * scale))), cv2.INTER_AREA
            )
            h, w = arr.shape[:2]
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimg)

    # ── mutual exclusion ────────────────────────────────────────────────────

    def _on_sp_toggled(self, checked: bool) -> None:
        if checked:
            self._cb_blend.blockSignals(True)
            self._cb_blend.setChecked(False)
            self._cb_blend.blockSignals(False)

    def _on_blend_toggled(self, checked: bool) -> None:
        if checked:
            self._cb_sp.blockSignals(True)
            self._cb_sp.setChecked(False)
            self._cb_sp.blockSignals(False)

    # ── accessors ───────────────────────────────────────────────────────────

    @property
    def seam_index(self) -> int:
        return self._k

    def force_single_pose(self) -> bool:
        return self._cb_sp.isChecked()

    def force_blend(self) -> bool:
        return self._cb_blend.isChecked()

    def has_override(self) -> bool:
        return self._cb_sp.isChecked() or self._cb_blend.isChecked()


class SeamDiagnosticDialog(QDialog):
    """§2.4A — Per-seam diagnostic panel with per-seam overrides.

    Shows a scrollable list of :class:`_SeamCard` widgets (one per seam boundary,
    sorted worst-first by post_warp_diff) alongside a small canvas preview.
    The user can set "Force single-pose" or "Force blend" on any seam; on Accept
    these are returned via :meth:`get_overrides`.
    """

    def __init__(
        self,
        data: dict,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Parameters
        ----------
        data:
            Dict from HITL checkpoint 4.6 with keys:
            ``canvas_preview`` (np.ndarray BGR), ``boundaries`` (list[float]),
            ``seam_post_diffs`` (dict[int, float]),
            ``seam_single_pose_keys`` (list[int]),
            ``canvas_h`` (int), ``canvas_w`` (int).
        """
        super().__init__(parent)
        self.setWindowTitle("Seam Registration Inspector — §2.4A")
        self.setMinimumSize(700, 450)
        self.setSizeGripEnabled(True)

        boundaries: List[float] = data.get("boundaries", [])
        seam_post_diffs: dict = data.get("seam_post_diffs", {})
        sp_keys: List[int] = data.get("seam_single_pose_keys", [])
        canvas_preview: Optional[np.ndarray] = data.get("canvas_preview")
        seam_crops: dict = data.get("seam_crops", {})

        # ── Root layout ────────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Canvas preview (left) ──────────────────────────────────────────
        if canvas_preview is not None and canvas_preview.size > 0:
            _pix = self._np_to_pixmap(canvas_preview, max_width=260)
            _prev_lbl = QLabel()
            _prev_lbl.setPixmap(_pix)
            _prev_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
            _prev_lbl.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
            )
            root.addWidget(_prev_lbl)

        # ── Right panel: seam cards + buttons ─────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(6)
        root.addLayout(right)

        # Header
        header_lbl = QLabel(
            f"<b>{len(boundaries)} seam(s)</b> — sorted by alignment score (worst first)"
        )
        right.addWidget(header_lbl)

        # Scroll area with seam cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        card_layout = QVBoxLayout(inner)
        card_layout.setSpacing(4)
        card_layout.setContentsMargins(4, 4, 4, 4)

        # Build cards, sort worst-first by post_diff
        seam_info: List[tuple] = []
        for k, by in enumerate(boundaries):
            diff = float(seam_post_diffs.get(k, 0.0))
            is_sp = k in sp_keys
            seam_info.append((k, by, diff, is_sp))
        seam_info.sort(key=lambda t: (t[3], t[2]), reverse=True)  # SP first, then high diff

        self._cards: List[_SeamCard] = []
        for k, by, diff, is_sp in seam_info:
            card = _SeamCard(k, by, diff, is_sp, crop=seam_crops.get(k))
            card_layout.addWidget(card)
            self._cards.append(card)

        card_layout.addStretch(1)
        scroll.setWidget(inner)
        right.addWidget(scroll, 1)

        # Legend
        legend = QLabel(
            "<small>"
            "<span style='color:#007700'>■</span> good (diff&lt;10)  "
            "<span style='color:#cc7700'>■</span> moderate (10–22)  "
            "<span style='color:#cc2200'>■</span> poor / single-pose  "
            "SP = already in single-pose fallback"
            "</small>"
        )
        legend.setWordWrap(True)
        right.addWidget(legend)

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Accept && Continue")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        right.addWidget(btn_box)

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _np_to_pixmap(arr: np.ndarray, max_width: int = 260) -> QPixmap:
        """Convert a BGR numpy array to a QPixmap scaled to *max_width*."""
        h, w = arr.shape[:2]
        if w > max_width:
            scale = max_width / w
            arr = cv2.resize(arr, (max_width, max(1, int(h * scale))), cv2.INTER_AREA)
            h, w = arr.shape[:2]
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimg)

    # ── public API ───────────────────────────────────────────────────────────

    def get_overrides(self) -> Dict[int, dict]:
        """Return per-seam override dict (only non-default seams included)."""
        result: Dict[int, dict] = {}
        for card in self._cards:
            if card.has_override():
                result[card.seam_index] = {
                    "force_single_pose": card.force_single_pose(),
                    "force_blend": card.force_blend(),
                }
        return result
