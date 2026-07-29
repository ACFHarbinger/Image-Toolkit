"""Encrypted session-recovery save/restore of active tab and configurations.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import inspect
import json
import os

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import QTimer


class _SessionRecoveryMixin:
    """Restores/persists the active tab and per-tab configs across launches."""

    def _restore_session_recovery(self) -> None:  # noqa: C901
        """Restores the previously opened tab and configurations on startup."""
        if not self.vault_manager or not self.cached_creds:
            return

        prefs = self.cached_creds.get("preferences", {})
        recovery_level = prefs.get("session_recovery_level", "None")
        if recovery_level == "Currrent Tab":
            recovery_level = "Current Tab"

        username = getattr(self.vault_manager, "account_name", None)
        recovery_data = {}
        # Guest vaults have no SecureJsonVault / secret_key — skip encrypted recovery entirely.
        _is_guest = getattr(self.vault_manager, "is_guest", False)
        if username and not _is_guest:
            for recovery_dir in (os.path.expanduser("~/.image-toolkit/recovery"),):
                enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                if os.path.exists(enc_file_path):
                    try:
                        SecureJsonVault = self.vault_manager.SecureJsonVault
                        secret_key = self.vault_manager.secret_key
                        temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                        java_string = temp_file_vault.loadData()
                        decrypted_json = str(java_string)
                        recovery_data = json.loads(decrypted_json)
                        break
                    except Exception as e:
                        print(f"Warning: Failed to decrypt recovery file {enc_file_path}: {e}")

        if not recovery_data:
            # Fallback to cached_creds if no file was decrypted (backward compatibility)
            recovery_data = self.cached_creds.get("session_recovery_data") or {}

        active_category = recovery_data.get("active_category")
        active_tab_name = recovery_data.get("active_tab")
        tab_configs = recovery_data.get("tab_configs", {})

        # Restore last browsed directories based on restore_last_dir preference and recovery level
        restore_last_dir = prefs.get("restore_last_dir", True)
        if restore_last_dir:
            default_dir = LOCAL_SOURCE_PATH

            # Determine target active tab instance
            target_active_tab = None
            if recovery_level != "None" and active_category and active_tab_name:
                target_active_tab = self.all_tabs.get(active_category, {}).get(active_tab_name)
            if not target_active_tab:
                curr_cat = self.command_combo.currentText()
                curr_tab_name = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.currentIndex() >= 0 else None
                if curr_cat and curr_tab_name:
                    target_active_tab = self.all_tabs.get(curr_cat, {}).get(curr_tab_name)

            if recovery_level == "None":
                # Reset all tabs
                for cat_tabs in self.all_tabs.values():
                    for tab in cat_tabs.values():
                        for obj in (tab, getattr(tab, "format_tab", None)):
                            if obj is not None:
                                if hasattr(obj, "last_browsed_scan_dir"):
                                    obj.last_browsed_scan_dir = default_dir  # pyrefly: ignore [missing-attribute]
                                if hasattr(obj, "last_browsed_dir"):
                                    obj.last_browsed_dir = default_dir  # pyrefly: ignore [missing-attribute]
            elif recovery_level == "Current Tab":
                # Reset all tabs except the active tab
                for cat_tabs in self.all_tabs.values():
                    for tab in cat_tabs.values():
                        if tab is target_active_tab:
                            continue
                        for obj in (tab, getattr(tab, "format_tab", None)):
                            if obj is not None:
                                if hasattr(obj, "last_browsed_scan_dir"):
                                    obj.last_browsed_scan_dir = default_dir  # pyrefly: ignore [missing-attribute]
                                if hasattr(obj, "last_browsed_dir"):
                                    obj.last_browsed_dir = default_dir  # pyrefly: ignore [missing-attribute]
            elif recovery_level == "All Tabs":
                # All directories remain restored
                pass

        if recovery_level == "None":
            return

        active_category = recovery_data.get("active_category")
        active_tab_name = recovery_data.get("active_tab")
        tab_configs = recovery_data.get("tab_configs", {})

        # Transfer user to the previously opened tab FIRST, so that on_command_changed
        # fires and re-wraps all tab widgets BEFORE set_config is called.
        # If set_config ran first, the subsequent on_command_changed (triggered below)
        # would re-parent tab widgets via takeWidget/setWidget and could reset
        # visibility state that set_config just established.
        if active_category and active_category in self.all_tabs:
            self.command_combo.setCurrentText(active_category)
            if active_tab_name:
                for index in range(self.tabs.count()):
                    if self.tabs.tabText(index) == active_tab_name:
                        self.tabs.setCurrentIndex(index)
                        break

        # Defer config restoration by 150ms to ensure the UI layout has fully settled and shown
        def do_restore():
            # Apply active profile configurations first so that they are loaded when layouts have settled
            self._apply_active_tab_configs()

            # Apply config information depending on the level of recovery configured
            if recovery_level == "All Tabs":
                for _category, tabs_in_category in self.all_tabs.items():
                    for tab_instance in tabs_in_category.values():
                        tab_class_name = type(tab_instance).__name__
                        if (
                            tab_class_name in tab_configs
                            and hasattr(tab_instance, "set_config")
                            and callable(tab_instance.set_config)
                        ):
                            try:
                                sanitized_cfg = self._sanitize_config_if_needed(tab_configs[tab_class_name])
                                if tab_class_name == "ExtractorTab":
                                    avc = sanitized_cfg.get("active_videos_config", {})
                                    print(
                                        f"[RECOVERY] Restoring {tab_class_name}: active_videos_config has {len(avc)} entries, video_path='{sanitized_cfg.get('video_path', '')}'"
                                    )
                                sig = inspect.signature(tab_instance.set_config)
                                if "quiet" in sig.parameters:
                                    tab_instance.set_config(sanitized_cfg, quiet=True)  # pyrefly: ignore [unexpected-keyword]
                                else:
                                    tab_instance.set_config(sanitized_cfg)
                            except Exception as e:
                                print(
                                    f"Warning: Failed to restore config to {tab_class_name} during session recovery: {e}"
                                )
            elif recovery_level == "Current Tab":
                if active_category and active_tab_name:
                    tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
                    if tab_instance:
                        tab_class_name = type(tab_instance).__name__
                        if (
                            tab_class_name in tab_configs
                            and hasattr(tab_instance, "set_config")
                            and callable(tab_instance.set_config)
                        ):
                            try:
                                sanitized_cfg = self._sanitize_config_if_needed(tab_configs[tab_class_name])
                                if tab_class_name == "ExtractorTab":
                                    avc = sanitized_cfg.get("active_videos_config", {})
                                    print(
                                        f"[RECOVERY] Restoring {tab_class_name}: active_videos_config has {len(avc)} entries, video_path='{sanitized_cfg.get('video_path', '')}'"
                                    )
                                sig = inspect.signature(tab_instance.set_config)
                                if "quiet" in sig.parameters:
                                    tab_instance.set_config(sanitized_cfg, quiet=True)  # pyrefly: ignore [unexpected-keyword]
                                else:
                                    tab_instance.set_config(sanitized_cfg)
                            except Exception as e:
                                print(
                                    f"Warning: Failed to restore config to active tab {tab_class_name} during session recovery: {e}"
                                )
            else:
                print(f"[RECOVERY] recovery_level='{recovery_level}' — no set_config called")

        if "PYTEST_CURRENT_TEST" in os.environ:
            do_restore()
        else:
            QTimer.singleShot(150, do_restore)

    def _save_session_recovery(self) -> None:  # noqa: C901
        """Saves current active tab and tab configurations for session recovery."""
        if not self.vault_manager or getattr(self.vault_manager, "is_guest", False) is True:
            return

        try:
            # Load current credentials/preferences from the vault
            creds = self.vault_manager.load_account_credentials()
            if not creds:
                return

            prefs = creds.get("preferences", {})
            recovery_level = prefs.get("session_recovery_level", "None")
            if recovery_level == "Currrent Tab":
                recovery_level = "Current Tab"

            username = getattr(self.vault_manager, "account_name", None)
            if not username:
                return

            recovery_data = {}
            if recovery_level != "None":
                active_category = self.command_combo.currentText()
                active_tab_index = self.tabs.currentIndex()
                active_tab_name = self.tabs.tabText(active_tab_index) if active_tab_index >= 0 else None

                tab_configs = {}
                if recovery_level == "All Tabs":
                    for _category, tabs_in_category in self.all_tabs.items():
                        for tab_instance in tabs_in_category.values():
                            if hasattr(tab_instance, "collect") and callable(tab_instance.collect):
                                try:
                                    tab_configs[type(tab_instance).__name__] = tab_instance.collect()
                                except Exception as e:
                                    print(f"Warning: Failed to collect config from {type(tab_instance).__name__}: {e}")
                elif recovery_level == "Current Tab" and active_category and active_tab_name:
                    tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
                    if tab_instance and hasattr(tab_instance, "collect") and callable(tab_instance.collect):
                        try:
                            cfg = tab_instance.collect()
                            tab_class_name = type(tab_instance).__name__
                            if tab_class_name == "ExtractorTab":
                                avc = cfg.get("active_videos_config", {})  # pyrefly: ignore [missing-attribute]
                                print(
                                    f"[SAVE] {tab_class_name}.collect(): active_videos_config has {len(avc)} entries, video_path='{cfg.get('video_path', '')}'" # pyrefly: ignore [missing-attribute]
                                )
                            tab_configs[tab_class_name] = cfg
                        except Exception as e:
                            print(
                                f"Warning: Failed to collect config from active tab {type(tab_instance).__name__}: {e}"
                            )

                recovery_data = {
                    "active_category": active_category,
                    "active_tab": active_tab_name,
                    "tab_configs": tab_configs,
                }

                # Save session recovery data to the encrypted file
                for recovery_dir in (os.path.expanduser("~/.image-toolkit/recovery"),):
                    try:
                        os.makedirs(recovery_dir, exist_ok=True)
                        enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                        SecureJsonVault = self.vault_manager.SecureJsonVault
                        secret_key = self.vault_manager.secret_key
                        temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                        temp_file_vault.saveData(json.dumps(recovery_data))
                        break
                    except Exception as e:
                        print(f"Warning: Failed to save recovery data to {recovery_dir}: {e}")

                # Keep vault backup in sync
                creds["session_recovery_data"] = recovery_data
            else:
                creds["session_recovery_data"] = {}
                # Delete recovery file if recovery level is set to None
                for recovery_dir in (os.path.expanduser("~/.image-toolkit/recovery"),):
                    enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                    if os.path.exists(enc_file_path):
                        try:
                            os.remove(enc_file_path)
                        except Exception as e:
                            print(f"Warning: Failed to remove recovery file: {e}")

            self.vault_manager.save_data(json.dumps(creds))
        except Exception as e:
            print(f"Warning: Failed to save session recovery data: {e}")


__all__ = ["_SessionRecoveryMixin"]
