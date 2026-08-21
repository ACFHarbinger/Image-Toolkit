"""Tab-config collect/get_default_config/set_config for ImageCrawlTab.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Collects/restores the full ImageCrawlTab UI state as a config dict."""

    def collect(self) -> dict:
        """Collects current configuration for saving."""

        # Actions List Reconstruction
        actions = []
        for i in range(self.action_list_widget.count()):
            txt = self.action_list_widget.item(i).text()
            atype = txt.split(" | Param: ")[0]
            param = txt.split(" | Param: ")[1] if " | Param: " in txt else None
            actions.append({"type": atype, "param": param})

        return {
            "crawler_type_index": self.crawler_type_combo.currentIndex(),
            # Common
            "download_dir": self.download_dir_path.text(),
            "screenshot_dir": self.screenshot_dir_path.text(),
            # General Settings
            "gen_login_url": self.gen_login_url.text(),
            "gen_username": self.gen_username.text(),
            "gen_password": self.gen_password.text(),  # Be careful saving passwords
            "gen_target_url": self.url_input.text(),
            "gen_replace_str": self.replace_str_input.text(),
            "gen_replacements": self.replacements_input.text(),
            "gen_browser": self.browser_combo.currentText(),
            "gen_headless": self.headless_checkbox.isChecked(),
            "gen_skip_first": self.skip_first_input.text(),
            "gen_skip_last": self.skip_last_input.text(),
            "gen_actions": actions,
            # Board Settings
            "board_url": self.board_url.text(),
            "board_resource": self.board_resource.text(),
            "board_tags": self.board_tags.text(),
            "board_limit": self.board_limit.text(),
            "board_max_pages": self.board_max_pages.text(),
            "board_extra_params": self.board_extra_params.text(),
            "board_username": self.board_username.text(),
            "board_apikey": self.board_apikey.text(),
        }

    def get_default_config(self) -> dict:
        """Returns defaults for resetting."""
        return {
            "crawler_type_index": 0,
            "download_dir": LOCAL_SOURCE_PATH,
            "screenshot_dir": "",
            # General
            "gen_login_url": "",
            "gen_username": "",
            "gen_password": "",
            "gen_target_url": "",
            "gen_replace_str": "",
            "gen_replacements": "",
            "gen_browser": "brave",
            "gen_headless": True,
            "gen_skip_first": "0",
            "gen_skip_last": "0",
            "gen_actions": [],
            # Board
            "board_url": "https://danbooru.donmai.us",
            "board_resource": "posts",
            "board_tags": "",
            "board_limit": "20",
            "board_max_pages": "5",
            "board_extra_params": "",
            "board_username": "",
            "board_apikey": "",
        }

    def set_config(self, config: dict):
        """Restores UI state from config."""
        try:
            # Crawler Type
            idx = config.get("crawler_type_index", 0)
            self.crawler_type_combo.setCurrentIndex(idx)
            self.on_crawler_type_changed(idx)

            # Paths
            self.download_dir_path.setText(config.get("download_dir", ""))
            self.screenshot_dir_path.setText(config.get("screenshot_dir", ""))
            if self.screenshot_dir_path.text():
                self.screenshot_field.set_open(True)

            # General Page
            self.gen_login_url.setText(config.get("gen_login_url", ""))
            self.gen_username.setText(config.get("gen_username", ""))
            self.gen_password.setText(config.get("gen_password", ""))
            self.url_input.setText(config.get("gen_target_url", ""))
            self.replace_str_input.setText(config.get("gen_replace_str", ""))
            self.replacements_input.setText(config.get("gen_replacements", ""))
            self.browser_combo.setCurrentText(config.get("gen_browser", "brave"))
            self.headless_checkbox.setChecked(config.get("gen_headless", True))
            self.skip_first_input.setText(config.get("gen_skip_first", "0"))
            self.skip_last_input.setText(config.get("gen_skip_last", "0"))

            # Restore Actions List
            self.action_list_widget.clear()
            saved_actions = config.get("gen_actions", [])
            for act in saved_actions:
                atype = act.get("type", "")
                param = act.get("param")
                display = atype
                if param:
                    display += f" | Param: {param}"
                self.action_list_widget.addItem(display)

            # Board Page
            self.board_url.setText(config.get("board_url", ""))
            self.board_resource.setText(config.get("board_resource", ""))
            self.board_tags.setText(config.get("board_tags", ""))
            self.board_limit.setText(config.get("board_limit", "20"))
            self.board_max_pages.setText(config.get("board_max_pages", "5"))
            self.board_extra_params.setText(config.get("board_extra_params", ""))
            self.board_username.setText(config.get("board_username", ""))
            self.board_apikey.setText(config.get("board_apikey", ""))

            print("ImageCrawlTab configuration loaded.")

        except Exception as e:
            print(f"Error applying ImageCrawlTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
