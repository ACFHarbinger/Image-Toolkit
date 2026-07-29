"""Managed WebDriver service process lifecycle.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QProcess


class _WebDriverMixin:
    """Starts/stops the external WebDriver management script and streams its output."""

    def toggle_webdriver(self):
        if self.webdriver_process.state() == QProcess.ProcessState.NotRunning:
            self.log_window.show()
            self.log_window.append_log(
                "🌐 Preparing Managed WebDriver (this may take a few seconds)..."
            )

            # Use the virtual environment python to run the management script
            # Assumes the app is launched from project root where .venv exists
            python_exe = os.path.abspath(".venv/bin/python3")
            script_path = os.path.abspath("scripts/manage_webdriver.py")

            if not os.path.exists(python_exe):
                # Fallback to system python if venv not found (though AGENTS.md says it should be there)
                python_exe = "python3"

            self.webdriver_process.start(python_exe, [script_path, "start"])
            if not self.webdriver_process.waitForStarted(10000):
                self.log_window.append_log(
                    "❌ Failed to start WebDriver manager script."
                )
                return
            self.webdriver_button.setText("🛑 Stop WebDriver Service")
            self.webdriver_button.setStyleSheet(self._get_cancel_btn_style())
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
        self.webdriver_button.setStyleSheet(self._get_webdriver_btn_style())


__all__ = ["_WebDriverMixin"]
