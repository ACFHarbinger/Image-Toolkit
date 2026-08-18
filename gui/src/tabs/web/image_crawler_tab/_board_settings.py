"""Crawler-type switching and per-board auth label/placeholder updates.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations


class _BoardSettingsMixin:
    """Switches settings-stack pages and updates board-specific auth labels."""

    def update_board_auth_labels(self, index: int):
        """Dynamically updates labels/placeholders based on selected board type."""
        # Ensure elements exist before trying to update them
        if not hasattr(self, "board_username_label"):
            return

        if index == 1:  # Danbooru
            self.board_username_label.setText("Username:")
            self.board_username.setPlaceholderText("Danbooru Username")
            self.board_apikey_label.setText("API Key:")
            self.board_url.setText("https://danbooru.donmai.us")
            self.board_resource.setText("posts")
            self.board_limit.setText("20")
            link = '<a href="https://danbooru.donmai.us/wiki_pages/help:api">Danbooru API Documentation</a>'
            self.api_doc_link.setText(link)

        elif index == 2:  # Gelbooru
            self.board_username_label.setText("User ID:")
            self.board_username.setPlaceholderText("Gelbooru User ID")
            self.board_apikey_label.setText("API Key:")
            self.board_url.setText("https://gelbooru.com")
            self.board_resource.setText("post")
            self.board_limit.setText("100")
            link = '<a href="https://gelbooru.com/index.php?page=wiki&s=view&id=18780">Gelbooru API Documentation</a>'
            self.api_doc_link.setText(link)

        elif index == 3:  # Sankaku Complex
            self.board_username_label.setText("Username/Email:")
            self.board_username.setPlaceholderText("Sankaku Username or Email")
            self.board_apikey_label.setText("Password:")
            self.board_url.setText("https://capi-v2.sankakucomplex.com")
            self.board_resource.setText("posts")
            self.board_limit.setText("40")
            link = '<a href="https://sankaku.app/">Sankaku Complex API Info</a>'
            self.api_doc_link.setText(link)

    def on_crawler_type_changed(self, index):
        # Map combo box index to stack index
        # Combo: 0=General, 1=Danbooru, 2=Gelbooru, 3=Sankaku
        # Stack: 0=General Page, 1=Board Page (Shared)

        # If index is 0, show page 0. If index is >= 1, show page 1.
        stack_index = 0 if index == 0 else 1
        self.settings_stack.setCurrentIndex(stack_index)

        if index >= 1:
            self.update_board_auth_labels(index)


__all__ = ["_BoardSettingsMixin"]
