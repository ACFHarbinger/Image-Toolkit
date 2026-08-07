"""Separate offline Krita Docker for deterministic line-art segmentation."""

from __future__ import annotations

from krita import DockWidget, Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from .segmentation_masks import (
    GAP_CLOSED_PREFIX,
    LINE_ART_GROUP_NAME,
    REGION_GROUP_NAME,
    REGION_PREFIX,
    close_line_gaps_bytes,
    filter_small_regions,
    region_adjacency_bytes,
    segment_regions_bytes,
)
from .value_masks import find_named_node


class SegmentationDocker(DockWidget):
    """Close line-art gaps and segment enclosed regions into editable layers."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Line Art Segmentation")
        container = QWidget(self)
        layout = QVBoxLayout(container)
        self._status = QLabel(
            "Select a line-art layer (opaque ink, transparent elsewhere).", container
        )
        self._status.setWordWrap(True)
        actions = (
            ("Close Line Art Gaps", self._close_gaps),
            ("Segment Regions into Layers", self._segment_regions),
            ("Report Region Adjacency", self._report_adjacency),
        )
        for label, callback in actions:
            button = QPushButton(label, container)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addWidget(self._status)
        self.setWidget(container)

    def _close_gaps(self):
        document = Krita.instance().activeDocument()
        node = document.activeNode() if document is not None else None
        if document is None or node is None:
            self._status.setText("Open a document and select a line-art layer first.")
            return
        max_gap_px, accepted = QInputDialog.getInt(
            self, "Close Line Art Gaps", "Maximum gap width (pixels):", 1, 0, 20, 1
        )
        if not accepted:
            return
        width, height = document.width(), document.height()
        ink = self._ink_mask(node, width, height)
        if ink is None:
            return
        closed = close_line_gaps_bytes(ink, width, height, max_gap_px)
        root = document.rootNode()
        group = find_named_node(root, LINE_ART_GROUP_NAME)
        if group is None:
            group = document.createNode(LINE_ART_GROUP_NAME, "grouplayer")
            if group is None or not root.addChildNode(group, None):
                self._status.setText("Krita could not create the Line Art group.")
                return
        name = f"{GAP_CLOSED_PREFIX} (radius {max_gap_px})"
        layer = document.createNode(name, "paintlayer")
        if layer is None or not group.addChildNode(layer, None):
            self._status.setText("Krita could not create the gap-closed preview layer.")
            return
        pixels = bytearray(width * height * 4)
        for index, value in enumerate(closed):
            offset = index * 4
            pixels[offset : offset + 4] = bytes((0, 0, 0, 255 if value else 0))
        if not layer.setPixelData(QByteArray(bytes(pixels)), 0, 0, width, height):
            layer.remove()
            self._status.setText("Krita could not write the gap-closed preview safely.")
            return
        document.refreshProjection()
        self._status.setText(
            f"Created '{name}'; source line art is unchanged. Delete the layer if unwanted."
        )

    def _segment_regions(self):
        document = Krita.instance().activeDocument()
        node = document.activeNode() if document is not None else None
        if document is None or node is None:
            self._status.setText("Open a document and select a (gap-closed) line-art layer.")
            return
        width, height = document.width(), document.height()
        ink = self._ink_mask(node, width, height)
        if ink is None:
            return
        labels = segment_regions_bytes(ink, width, height)
        min_area, accepted = QInputDialog.getInt(
            self, "Segment Regions", "Minimum region area (pixels):", 4, 0, 1_000_000, 1
        )
        if not accepted:
            return
        before = len({value for value in labels if value})
        labels = filter_small_regions(labels, min_area)
        region_ids = sorted({value for value in labels if value})
        discarded = before - len(region_ids)
        if not region_ids:
            self._status.setText("No enclosed regions found; close gaps first if needed.")
            return
        root = document.rootNode()
        group = find_named_node(root, REGION_GROUP_NAME)
        if group is None:
            group = document.createNode(REGION_GROUP_NAME, "grouplayer")
            if group is None or not root.addChildNode(group, None):
                self._status.setText("Krita could not create the Regions group.")
                return
        for region_id in region_ids:
            layer = document.createNode(f"{REGION_PREFIX}{region_id}", "paintlayer")
            if layer is None or not group.addChildNode(layer, None):
                self._status.setText("Krita could not create a region layer.")
                return
            pixels = bytearray(width * height * 4)
            for index, value in enumerate(labels):
                if value == region_id:
                    offset = index * 4
                    pixels[offset : offset + 4] = bytes((255, 255, 255, 255))
            if not layer.setPixelData(QByteArray(bytes(pixels)), 0, 0, width, height):
                layer.remove()
                self._status.setText("Krita could not write a region layer safely.")
                return
        document.refreshProjection()
        discarded_note = (
            f" ({discarded} speck(s) below the minimum area were discarded.)" if discarded else ""
        )
        self._status.setText(
            f"Created {len(region_ids)} region layer(s) under '{REGION_GROUP_NAME}'."
            f"{discarded_note} Rename each to a meaningful region id before assigning "
            "correspondence."
        )

    def _report_adjacency(self):
        document = Krita.instance().activeDocument()
        if document is None:
            self._status.setText("Open a document with segmented region layers first.")
            return
        group = find_named_node(document.rootNode(), REGION_GROUP_NAME)
        if group is None:
            self._status.setText(f"No '{REGION_GROUP_NAME}' group found; segment regions first.")
            return
        width, height = document.width(), document.height()
        labels = [0] * (width * height)
        names = {}
        for region_id, node in enumerate(group.childNodes(), start=1):
            if not node.name().startswith(REGION_PREFIX):
                continue
            names[region_id] = node.name()[len(REGION_PREFIX) :]
            raw = bytes(node.pixelData(0, 0, width, height))
            if len(raw) != width * height * 4:
                self._status.setText("Krita returned an unexpected region-layer buffer.")
                return
            for index in range(width * height):
                if raw[index * 4 + 3] > 0:
                    labels[index] = region_id
        pairs = region_adjacency_bytes(labels, width, height)
        if not pairs:
            self._status.setText("No adjacent region pairs found.")
            return
        described = ", ".join(f"{names.get(a, a)}—{names.get(b, b)}" for a, b in sorted(pairs))
        self._status.setText(f"{len(pairs)} adjacent region pair(s): {described}")

    def _ink_mask(self, node, width, height):
        raw = bytes(node.pixelData(0, 0, width, height))
        if len(raw) != width * height * 4:
            self._status.setText("Krita returned an unexpected line-art buffer.")
            return None
        return bytes(1 if raw[index * 4 + 3] > 0 else 0 for index in range(width * height))

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this docker does not inspect the canvas."""
