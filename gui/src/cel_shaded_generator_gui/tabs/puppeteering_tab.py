"""Manga Puppeteering tab (roadmap §3.3/§6.2, issue #194).

Exercises the ARAP mesh-deformation backend end-to-end through a rigging
UI: load a static panel image, paint a binary mask over the region to
puppeteer (reusing the same freehand-paint interaction as
``MangaCanvasEditor``'s scribble layer, via ``MeshOverlayEditor``), generate
a triangle mesh over that mask (``logic/src/rigging/arap.py``'s
``generate_mesh()``), then drag any mesh vertex to pose it -- every drag
re-solves ``arap_deform()`` in real time (synchronously on the GUI thread;
see ``MeshOverlayEditor``'s own module docstring for why an async QThread
dispatch would actually hurt drag responsiveness here, unlike every other
cel_shaded_generator solver in this codebase).

This is explicitly a test/exercise harness for the already-built ARAP
solver (same posture as the Manga Animation Tab, issue #196), not a
production rigging tool -- no skeleton/bone hierarchy UI, no keyframe
timeline, no image warping (the mesh wireframe overlays the static image;
actually deforming the *pixels* per triangle is a separate, real follow-up,
not attempted here).

New feature, not code motion.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..elements import MeshOverlayEditor
from ..platform import DIALOG_OPTS, IMAGE_FILE_DIALOG_FILTER, load_qimage


class MangaPuppeteeringTab(QWidget):
    """Load an image, paint a mask, generate an ARAP mesh, and drag vertices
    to pose it in real time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        btn_load = QPushButton("Load Image…")
        btn_load.clicked.connect(self._browse_image)
        toolbar.addWidget(btn_load)

        self.chk_paint_mask = QCheckBox("Paint Mask")
        self.chk_paint_mask.setToolTip(
            "Paint the region to mesh. Uncheck to switch to dragging mesh vertices."
        )
        self.chk_paint_mask.toggled.connect(self._on_paint_mode_toggled)
        toolbar.addWidget(self.chk_paint_mask)

        toolbar.addWidget(QLabel("Mask Pen Width:"))
        self.pen_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.pen_width_slider.setRange(4, 100)
        self.pen_width_slider.setValue(24)
        self.pen_width_slider.setFixedWidth(120)
        self.pen_width_slider.valueChanged.connect(self._on_pen_width_changed)
        toolbar.addWidget(self.pen_width_slider)

        btn_clear_mask = QPushButton("Clear Mask")
        btn_clear_mask.clicked.connect(self._on_clear_mask)
        toolbar.addWidget(btn_clear_mask)

        toolbar.addWidget(QLabel("Grid Step:"))
        self.grid_step_spin = QSpinBox()
        self.grid_step_spin.setRange(4, 64)
        self.grid_step_spin.setValue(16)
        self.grid_step_spin.setToolTip(
            "Mesh vertex spacing in pixels "
            "(rigging.arap.generate_mesh). "
            "Smaller = finer mesh, more triangles to solve for."
        )
        toolbar.addWidget(self.grid_step_spin)

        self.btn_generate_mesh = QPushButton("▶ Generate Mesh")
        self.btn_generate_mesh.clicked.connect(self._on_generate_mesh)
        toolbar.addWidget(self.btn_generate_mesh)

        self.btn_reset_pose = QPushButton("↺ Reset Pose")
        self.btn_reset_pose.clicked.connect(self._on_reset_pose)
        toolbar.addWidget(self.btn_reset_pose)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.editor = MeshOverlayEditor()
        self.editor.mesh_generated.connect(self._on_mesh_generated)
        self.editor.pose_changed.connect(self._on_pose_changed)
        layout.addWidget(self.editor, 1)

        self.status_label = QLabel(
            "Load an image, paint a mask over the region to puppeteer, then Generate Mesh."
        )
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Panel Image", "", IMAGE_FILE_DIALOG_FILTER, options=DIALOG_OPTS
        )
        if not path:
            return
        image = load_qimage(path)
        if image.isNull():
            QMessageBox.warning(self, "Manga Puppeteering", f"Could not load image:\n{path}")
            return
        self.editor.set_image(image)
        self.status_label.setText(f"Loaded '{path}'. Paint a mask over the region to puppeteer.")

    def _on_paint_mode_toggled(self, checked: bool) -> None:
        self.editor.set_paint_mode(checked)

    def _on_pen_width_changed(self, value: int) -> None:
        self.editor.set_pen_width(value)

    def _on_clear_mask(self) -> None:
        self.editor.clear_mask()

    def _on_generate_mesh(self) -> None:
        if not self.editor.has_image():
            QMessageBox.information(self, "Manga Puppeteering", "Load an image first.")
            return
        if not self.editor.has_mask():
            QMessageBox.information(
                self, "Manga Puppeteering", "Paint a mask over the region to puppeteer first."
            )
            return
        try:
            self.editor.generate_mesh(grid_step=self.grid_step_spin.value())
        except ValueError as e:
            QMessageBox.warning(self, "Manga Puppeteering", str(e))
            return
        # Switch out of paint mode automatically -- once a mesh exists, the
        # natural next action is dragging vertices, not continuing to paint.
        self.chk_paint_mask.setChecked(False)

    def _on_mesh_generated(self) -> None:
        vertices = self.editor.get_rest_vertices()
        triangles = self.editor.get_triangles()
        if vertices is None or triangles is None:
            return
        n_vertices = vertices.shape[0]
        n_triangles = triangles.shape[0]
        self.status_label.setText(
            f"Mesh generated: {n_vertices} vertices, {n_triangles} triangles. "
            "Drag a vertex to pose it."
        )

    def _on_reset_pose(self) -> None:
        self.editor.reset_pose()

    def _on_pose_changed(self) -> None:
        n_anchors = len(self.editor.get_anchors())
        self.status_label.setText(f"Posing… {n_anchors} vertex/vertices pinned.")


__all__ = ["MangaPuppeteeringTab"]
