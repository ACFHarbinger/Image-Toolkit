"""Managed WebDriver service process lifecycle.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QProcess

from ....styles import set_button_role


class _WebDriverMixin:
    """Starts/stops the external WebDriver management script and streams its output."""

    def toggle_webdriver(self):
        if self.webdriver_process.state() == QProcess.ProcessState.NotRunning:
            if getattr(sys, "frozen", False):
                self.log_window.show()
                self.log_window.append_log(
                    "❌ Managed WebDriver launches "
                    "backend/scripts/manage_webdriver.py with a separate "
                    "Python — not available in the packaged build. Run from "
                    "a source checkout to use it."
                )
                return
            self.log_window.show()
            self.log_window.append_log(
                "🌐 Preparing Managed WebDriver (this may take a few seconds)..."
            )

            # Dynamic resolution of project root and script path
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
            )
            script_candidates = [
                os.path.join(project_root, "backend", "scripts", "manage_webdriver.py"),
                os.path.join(project_root, "scripts", "manage_webdriver.py"),
                os.path.abspath("backend/scripts/manage_webdriver.py"),
                os.path.abspath("scripts/manage_webdriver.py"),
            ]
            script_path = next(
                (p for p in script_candidates if os.path.exists(p)), script_candidates[0]
            )

            python_candidates = [
                os.path.join(project_root, ".venv", "bin", "python3"),
                os.path.abspath(".venv/bin/python3"),
            ]
            python_exe = next(
                (p for p in python_candidates if os.path.exists(p)), sys.executable
            )

            browser = "brave"
            if hasattr(self, "browser_combo") and self.browser_combo:
                browser = self.browser_combo.currentText()

            self.webdriver_process.start(python_exe, [script_path, "start", f"--browser={browser}"])
            if not self.webdriver_process.waitForStarted(10000):
                self.log_window.append_log(
                    "❌ Failed to start WebDriver manager script."
                )
                return
            self.webdriver_button.setText("🛑 Stop WebDriver Service")
            set_button_role(self.webdriver_button, "danger")
        else:
            self.log_window.append_log("🛑 Stopping WebDriver service...")
            self.webdriver_process.terminate()
            if not self.webdriver_process.waitForFinished(3000):
                self.webdriver_process.kill()

    def on_webdriver_stdout(self):
        data = self.webdriver_process.readAllStandardOutput().data().decode().strip() # pyrefly: ignore [missing-attribute]
        if data:
            self.log_window.append_log(f"DRIVER: {data}")

    def on_webdriver_stderr(self):
        data = self.webdriver_process.readAllStandardError().data().decode().strip() # pyrefly: ignore [missing-attribute]
        if data:
            self.log_window.append_log(f"DRIVER ERROR: {data}")

    def on_webdriver_finished(self):
        self.log_window.append_log("🌐 WebDriver service stopped.")
        self.webdriver_button.setText("🌐 Start WebDriver Service")
        set_button_role(self.webdriver_button, "success")


__all__ = ["_WebDriverMixin"]
