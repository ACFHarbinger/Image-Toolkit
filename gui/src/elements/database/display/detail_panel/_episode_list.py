"""Episode/chapter/part list rendering and add/edit/remove.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Any, Dict

from gui.src.elements.database.dialog.episode_dialog import _EpisodeDialog
from gui.src.helpers.image import apply_thumbnail_to_label
from gui.src.tabs.core.elements.common.listings_common import open_file_location, open_web_link
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class _EpisodeListMixin:
    """Renders the episode/chapter/part rows and their add/edit/remove actions."""

    def _refresh_episode_list(self):
        while self.ep_list_layout.count():
            item = self.ep_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()  # pyrefly: ignore [missing-attribute]

        sorted_eps = sorted(self._episode_data, key=lambda x: x.get("number", 0))

        for ep in sorted_eps:
            row = QFrame()
            row.setStyleSheet("QFrame{background:#23272a; border-radius:4px; padding:2px;}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            num = ep.get("number", 0)
            title = ep.get("title", "")
            rating = ep.get("rating", 0)
            img_path = ep.get("image_path", "")

            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            apply_thumbnail_to_label(
                t_lbl,
                img_path,
                50,
                40,
                worker_size=80,
                placeholder_text="No Img",
                placeholder_style=("background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"),
            )
            rl.addWidget(t_lbl)
            info = QLabel(f"<b>#{num}</b> {title}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

            local_file = ep.get("local_file", "")
            web_link = ep.get("web_link", "")

            if local_file:
                file_btn = QPushButton("📁")
                file_btn.setFixedSize(24, 24)
                file_btn.setToolTip(f"Open: {local_file}")
                file_btn.setStyleSheet(
                    "background-color:#16a085; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                file_btn.clicked.connect(lambda _, path=local_file: open_file_location(path))
                rl.addWidget(file_btn)

            if web_link:
                link_btn = QPushButton("🌐")
                link_btn.setFixedSize(24, 24)
                link_btn.setToolTip(f"Open Link: {web_link}")
                link_btn.setStyleSheet(
                    "background-color:#2980b9; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                link_btn.clicked.connect(lambda _, url=web_link: open_web_link(url))
                rl.addWidget(link_btn)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit episode")
            edit_btn.clicked.connect(lambda _, e=ep: self._edit_episode(e))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove episode record")
            del_btn.clicked.connect(lambda _, eid=ep["id"]: self._remove_episode(eid))
            rl.addWidget(del_btn)

            self.ep_list_layout.addWidget(row)

    def _add_episode(self):
        dlg = _EpisodeDialog(parent=self)
        if dlg.exec():
            new_ep = dlg.get_data()
            self._episode_data.append(new_ep)
            self._refresh_episode_list()

    def _edit_episode(self, ep_data: Dict[str, Any]):
        dlg = _EpisodeDialog(ep_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, e in enumerate(self._episode_data):
                if e["id"] == updated["id"]:
                    self._episode_data[i] = updated
                    break
            self._refresh_episode_list()

    def _remove_episode(self, ep_id: str):
        self._episode_data = [e for e in self._episode_data if e["id"] != ep_id]
        self._refresh_episode_list()


__all__ = ["_EpisodeListMixin"]
