"""``ClusterListModel`` -- the cluster ("stack"/"album") list backing the QML gallery.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change,
to keep the file under the codebase's 500-code-line convention (§5.17).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractListModel, QByteArray, Qt


class ClusterListModel(QAbstractListModel):
    """Cluster ("stack"/"album") list for the QML gallery."""

    ClusterIdRole = Qt.ItemDataRole.UserRole + 1
    PathsRole = Qt.ItemDataRole.UserRole + 2
    SizeRole = Qt.ItemDataRole.UserRole + 3
    ConfidenceRole = Qt.ItemDataRole.UserRole + 4
    TierRole = Qt.ItemDataRole.UserRole + 5
    KeeperRole = Qt.ItemDataRole.UserRole + 6
    ReferencePathsRole = Qt.ItemDataRole.UserRole + 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clusters: List[dict] = []

    def roleNames(self):
        return {
            self.ClusterIdRole: QByteArray(b"clusterId"),
            self.PathsRole: QByteArray(b"paths"),
            self.SizeRole: QByteArray(b"clusterSize"),
            self.ConfidenceRole: QByteArray(b"confidence"),
            self.TierRole: QByteArray(b"tier"),
            self.KeeperRole: QByteArray(b"keeperPath"),
            self.ReferencePathsRole: QByteArray(b"referencePaths"),
        }

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._clusters)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._clusters)):
            return None
        c = self._clusters[index.row()]
        if role == self.ClusterIdRole:
            return c["id"]
        if role == self.PathsRole:
            return c["paths"]
        if role == self.SizeRole:
            return c["size"]
        if role == self.ConfidenceRole:
            return c["confidence"]
        if role == self.TierRole:
            return c["tier"]
        if role == self.KeeperRole:
            return c.get("keeper", "")
        if role == self.ReferencePathsRole:
            return c.get("reference_paths", [])
        return None

    def set_clusters(self, clusters: List[dict]):
        self.beginResetModel()
        self._clusters = clusters
        self.endResetModel()

    def set_keeper(self, cluster_id: str, keeper: str):
        for row, c in enumerate(self._clusters):
            if c["id"] == cluster_id:
                c["keeper"] = keeper
                idx = self.index(row)
                self.dataChanged.emit(idx, idx, [self.KeeperRole])
                return

    def clusters(self) -> List[dict]:
        return self._clusters

    def get(self, cluster_id: str) -> Optional[dict]:
        for c in self._clusters:
            if c["id"] == cluster_id:
                return c
        return None


__all__ = ["ClusterListModel"]
