"""Cross-panel edge annotations, the defect-tagging dialog, and the annotation
list.

An Edge connects a point in one panel's image to a point in another (e.g. "this
seam in ASP corresponds to this clean region in ground truth"). Two panels each
own their own ``QGraphicsScene``, so an edge line can't be a ``QGraphicsItem``
in either — it's painted on a transparent overlay stacked over the whole panel
grid, and ``sync_geometry()`` must be called by the container on resize.

The annotation list stores its indices in ``Qt.UserRole`` data rather than
re-parsing its own display strings to recover them, which is what the old
``_remove_selected`` did (``text[1:].split("]", 1)`` — one label containing a
``]`` away from breaking).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants.schema import (
    COMPARATOR_TITLES,
    DEFECT_TITLES,
    DEFECTS,
    SEVERITY_LABELS,
)
from ..constants.user_interface import COL_EDGE
from ..other.schema import Edge, EdgePoint
from .image_panel import ImagePanel


class DefectDialog(QDialog):
    """Captures a drawn region's defect class, severity and description.

    Replaces the old flow's bare ``QInputDialog.getText``, which could only
    collect a free-text label — so nothing a user drew was ever machine-
    classifiable, and §0.2's metric-calibration item had no structured
    failure-mode data to correlate against.
    """

    def __init__(self, image_title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag defect region")
        self.setMinimumWidth(400)
        form = QFormLayout()
        form.addRow(QLabel(f"Region drawn on <b>{image_title}</b>"))

        self.defect_combo = QComboBox()
        for key, title, hint in DEFECTS:
            self.defect_combo.addItem(f"{title} — {hint}", key)
        form.addRow("Defect class", self.defect_combo)

        self.severity_combo = QComboBox()
        for value, label in sorted(SEVERITY_LABELS.items()):
            self.severity_combo.addItem(f"{value} — {label}", value)
        self.severity_combo.setCurrentIndex(1)
        form.addRow("Severity", self.severity_combo)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("optional — what exactly is wrong here")
        form.addRow("Note", self.label_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.label_edit.setFocus()

    def result_values(self) -> Tuple[str, int, str]:
        return (
            self.defect_combo.currentData(),
            int(self.severity_combo.currentData()),
            self.label_edit.text().strip(),
        )


class EdgeOverlay(QWidget):
    """Transparent overlay painting edge lines across panel boundaries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._panels: Dict[str, ImagePanel] = {}
        self._edges: List[Edge] = []

    def register_panel(self, key: str, panel: ImagePanel) -> None:
        self._panels[key] = panel

    def register_panels(self, panels: Dict[str, ImagePanel]) -> None:
        self._panels.update(panels)

    def sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
            self.raise_()

    def set_edges(self, edges: List[Edge]) -> None:
        self._edges = list(edges)
        self.update()

    def _to_overlay_point(self, ep: EdgePoint) -> Optional[QPoint]:
        panel = self._panels.get(ep.image)
        container = self.parentWidget()
        if panel is None or container is None or not panel.isVisible():
            return None
        view_pt = panel.scene_point_to_view(ep.x, ep.y)
        if view_pt is None:
            return None
        return panel.mapTo(container, view_pt.toPoint())

    def paintEvent(self, event) -> None:  # noqa: D102 - Qt override
        if not self._edges:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COL_EDGE), 2, Qt.PenStyle.DashLine))
        painter.setFont(QFont("Sans", 9))
        for edge in self._edges:
            pa, pb = self._to_overlay_point(edge.a), self._to_overlay_point(edge.b)
            if pa is None or pb is None:
                continue
            painter.drawLine(pa, pb)
            painter.drawEllipse(pa, 4, 4)
            painter.drawEllipse(pb, 4, 4)
            if edge.label:
                mid = QPoint((pa.x() + pb.x()) // 2, (pa.y() + pb.y()) // 2)
                painter.drawText(mid, edge.label)
        painter.end()


class EdgeBuilder:
    """Holds the first endpoint of an in-progress edge across two
    ``pointPicked`` signals from (possibly) two different panels."""

    def __init__(self):
        self._first: Optional[EdgePoint] = None

    def pending(self) -> Optional[EdgePoint]:
        return self._first

    def reset(self) -> None:
        self._first = None

    def add_point(self, image_key: str, x: float, y: float) -> Optional[Tuple[EdgePoint, EdgePoint]]:
        """Returns the endpoint pair once two points exist, else ``None``.

        Deliberately does *not* prompt for a label itself — the old version
        raised a modal dialog from inside this call, which put a Qt dependency
        in the middle of the state machine and made it untestable.
        """
        if self._first is None:
            self._first = EdgePoint(image=image_key, x=x, y=y)
            return None
        first, second = self._first, EdgePoint(image=image_key, x=x, y=y)
        self._first = None
        return first, second


class AnnotationListWidget(QWidget):
    """The current test's regions and links, with per-row removal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(False)
        layout.addWidget(self.list_widget)
        row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(self.remove_btn)
        row.addStretch(1)
        layout.addLayout(row)
        self._on_remove: Optional[Callable[[str, int], None]] = None

    def set_remove_callback(self, callback: Callable[[str, int], None]) -> None:
        self._on_remove = callback

    def refresh(self, bboxes: List, edges: List) -> None:
        self.list_widget.clear()
        for i, b in enumerate(bboxes):
            title = COMPARATOR_TITLES.get(b.image, b.image)
            defect = DEFECT_TITLES.get(b.defect, b.defect) or "untagged"
            severity = f" · {SEVERITY_LABELS.get(b.severity, '')}" if b.severity else ""
            detail = f" — {b.label}" if b.label else ""
            item = QListWidgetItem(f"▢ {title}: {defect}{severity}{detail}")
            item.setData(Qt.ItemDataRole.UserRole, ("bbox", i))
            item.setToolTip(f"x={b.x:.3f} y={b.y:.3f} w={b.w:.3f} h={b.h:.3f}")
            self.list_widget.addItem(item)
        for i, e in enumerate(edges):
            a_title = COMPARATOR_TITLES.get(e.a.image, e.a.image)
            b_title = COMPARATOR_TITLES.get(e.b.image, e.b.image)
            item = QListWidgetItem(f"↔ {a_title} ⟷ {b_title} — {e.label or '(no description)'}")
            item.setData(Qt.ItemDataRole.UserRole, ("edge", i))
            self.list_widget.addItem(item)
        if not bboxes and not edges:
            placeholder = QListWidgetItem("No regions or links yet.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)
        self.remove_btn.setEnabled(bool(bboxes or edges))

    def _remove_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None or self._on_remove is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, index = payload
        self._on_remove(kind, index)
