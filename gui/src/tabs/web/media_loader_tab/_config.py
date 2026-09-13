"""Tab-config persistence for ``MediaLoaderTab``.

Saves/restores source selection, output settings, Reddit and nhentai form state.
"""

from __future__ import annotations

from typing import Any, Dict

from ._tab_bound import TabBoundController


class MediaLoaderConfigController(TabBoundController):
    """collect/set_config/get_default_config for MediaLoaderTab."""

    def collect(self) -> dict[str, Any]:
        return {
            "source_index": self.source_combo.currentIndex(),
            "download_dir": self.download_dir_path.text().strip() or None,
            "on_exists": self.on_exists_combo.currentData(),
            "reddit": {
                "mode": self.reddit_mode_combo.currentIndex(),
                "source": self.reddit_source_input.text().strip(),
                "sort": self.reddit_sort_combo.currentIndex(),
                "limit": self.reddit_limit_spin.value(),
                "images": self.reddit_download_images_chk.isChecked(),
                "videos": self.reddit_download_videos_chk.isChecked(),
            },
            "nhentai_gallery": self.nhentai_gallery_input.text().strip(),
        }

    def get_default_config(self) -> dict[str, Any]:
        return {
            "source_index": 0,
            "download_dir": None,
            "on_exists": "overwrite",
            "reddit": {
                "mode": 0,
                "source": "",
                "sort": 0,
                "limit": 50,
                "images": True,
                "videos": True,
            },
            "nhentai_gallery": "",
        }

    def set_config(self, config: Dict[str, Any]) -> None:
        if "source_index" in config:
            self.source_combo.setCurrentIndex(config["source_index"])

        if "download_dir" in config and config["download_dir"]:
            self.download_dir_path.setText(config["download_dir"])

        if "on_exists" in config:
            idx = self.on_exists_combo.findData(config["on_exists"])
            if idx >= 0:
                self.on_exists_combo.setCurrentIndex(idx)

        if "reddit" in config:
            reddit = config["reddit"]
            if "mode" in reddit:
                self.reddit_mode_combo.setCurrentIndex(reddit["mode"])
            if "source" in reddit:
                self.reddit_source_input.setText(reddit["source"])
            if "sort" in reddit:
                self.reddit_sort_combo.setCurrentIndex(reddit["sort"])
            if "limit" in reddit:
                self.reddit_limit_spin.setValue(reddit["limit"])
            if "images" in reddit:
                self.reddit_download_images_chk.setChecked(reddit["images"])
            if "videos" in reddit:
                self.reddit_download_videos_chk.setChecked(reddit["videos"])

        if "nhentai_gallery" in config:
            self.nhentai_gallery_input.setText(config["nhentai_gallery"])


__all__ = ["MediaLoaderConfigController"]
