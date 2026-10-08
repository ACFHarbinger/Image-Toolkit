"""Browser-launch controller for ``ImageCrawlTab``.

Starts a browser with ``--remote-debugging-port`` so the crawler can attach
to it via ``attach_existing`` mode, without the user having to open a
terminal.  Mirrors the ``ImageCrawlWebDriverController`` QProcess pattern.
"""

from __future__ import annotations

import shutil
import subprocess

from PySide6.QtCore import QProcess, Slot
from PySide6.QtWidgets import QMessageBox

from ....styles import set_button_role
from ._tab_bound import TabBoundController

# Flatpak application IDs for each browser choice
_FLATPAK_IDS: dict[str, str] = {
    "brave": "com.brave.Browser",
    "chrome": "com.google.Chrome",
    "firefox": "org.mozilla.firefox",
    "edge": "com.microsoft.Edge",
}

# Default isolated profile directory per browser (created inside the user's
# home so the crawl session is fully separate from the everyday profile).
_DEFAULT_PROFILE_SUFFIX: dict[str, str] = {
    "brave": ".var/app/com.brave.Browser/config/image-toolkit-manual",
    "chrome": ".var/app/com.google.Chrome/config/image-toolkit-manual",
    "firefox": "",  # Firefox uses --profile, not --user-data-dir
    "edge": ".var/app/com.microsoft.Edge/config/image-toolkit-manual",
}


class ImageCrawlBrowserLauncher(TabBoundController):
    """Starts/stops a remote-debug browser session from the crawler UI."""

    def _get_debug_port(self) -> int:
        try:
            return int(self.debug_port_input.value())
        except Exception:
            return 9223

    def _get_browser(self) -> str:
        if hasattr(self, "browser_combo") and self.browser_combo:
            return self.browser_combo.currentText().lower().strip()
        return "brave"

    def _get_start_url(self) -> str:
        if hasattr(self, "url_input") and self.url_input:
            return self.url_input.text().strip()
        return ""

    # ── Build command ────────────────────────────────────────────────────────

    def _build_launch_command(self) -> list[str] | None:
        """Return the argv list to launch the browser, or None on failure."""
        import os

        browser = self._get_browser()
        port = self._get_debug_port()
        start_url = self._get_start_url()

        # 1. Try native binary
        binary = self._find_native_binary(browser)
        if binary:
            cmd = self._chromium_argv(binary, browser, port, start_url)
            return cmd

        # 2. Flatpak fallback
        flatpak = shutil.which("flatpak")
        if flatpak:
            app_id = _FLATPAK_IDS.get(browser)
            if app_id:
                try:
                    result = subprocess.run(
                        [flatpak, "info", app_id],
                        capture_output=True, timeout=5, check=False,
                    )
                    if result.returncode == 0:
                        suffix = _DEFAULT_PROFILE_SUFFIX.get(browser, "")
                        profile_dir = os.path.join(os.path.expanduser("~"), suffix) if suffix else None
                        cmd = [flatpak, "run", app_id]
                        if browser == "firefox":
                            if profile_dir:
                                cmd += ["--profile", profile_dir]
                            cmd += [f"--remote-debugging-port={port}"]
                        else:
                            cmd += [f"--remote-debugging-port={port}"]
                            if profile_dir:
                                cmd += [f"--user-data-dir={profile_dir}"]
                            cmd += ["--no-first-run", "--no-default-browser-check"]
                        if start_url:
                            cmd.append(start_url)
                        return cmd
                except (OSError, subprocess.TimeoutExpired):
                    pass

        return None

    @staticmethod
    def _find_native_binary(browser: str) -> str | None:
        candidates: dict[str, list[str]] = {
            "brave": ["brave-browser", "brave", "brave-browser-stable"],
            "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
            "edge": ["msedge", "microsoft-edge", "microsoft-edge-stable"],
            "firefox": ["firefox", "firefox-esr"],
        }
        for cmd in candidates.get(browser, []):
            p = shutil.which(cmd)
            if p:
                return p
        return None

    @staticmethod
    def _chromium_argv(binary: str, browser: str, port: int, start_url: str) -> list[str]:
        import os
        import tempfile

        profile_dir = os.path.join(
            tempfile.gettempdir(), f"image-toolkit-crawl-{browser}"
        )
        cmd = [
            binary,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if start_url:
            cmd.append(start_url)
        return cmd

    # ── Toggle ───────────────────────────────────────────────────────────────

    @Slot()
    def toggle_browser_launch(self) -> None:
        if self.browser_process.state() == QProcess.ProcessState.NotRunning:
            self._do_launch()
        else:
            self._do_stop()

    def _do_launch(self) -> None:
        cmd = self._build_launch_command()
        if not cmd:
            browser = self._get_browser()
            QMessageBox.warning(
                self.tab,
                "Browser Not Found",
                f"Could not locate {browser!r} as a native binary or Flatpak application.\n"
                "Install it and try again, or launch the browser manually.",
            )
            return

        port = self._get_debug_port()
        self.log_window.show()
        self.log_window.append_log(
            f"🚀 Launching {self._get_browser()} on debug port {port}…\n"
            f"   {' '.join(cmd)}"
        )

        self.browser_process.setProgram(cmd[0])
        self.browser_process.setArguments(cmd[1:])
        self.browser_process.start()

        if not self.browser_process.waitForStarted(8000):
            self.log_window.append_log("❌ Browser failed to start.")
            return

        self.launch_browser_button.setText("🛑 Close Browser")
        set_button_role(self.launch_browser_button, "danger")

        # Auto-tick "attach existing" so crawl will connect to it.
        if hasattr(self, "attach_existing_checkbox"):
            self.attach_existing_checkbox.setChecked(True)

        self.log_window.append_log(
            f"✅ Browser started. Log in, navigate to your target page, then click "
            f"\"Run Crawler\" with \"Use existing browser session\" checked."
        )

    def _do_stop(self) -> None:
        self.log_window.append_log("🛑 Closing browser…")
        self.browser_process.terminate()
        if not self.browser_process.waitForFinished(4000):
            self.browser_process.kill()

    # ── QProcess callbacks ────────────────────────────────────────────────────

    def on_browser_process_stdout(self) -> None:
        data = self.browser_process.readAllStandardOutput().data().decode(errors="replace").strip()  # pyrefly: ignore [missing-attribute]
        if data:
            self.log_window.append_log(f"BROWSER: {data}")

    def on_browser_process_stderr(self) -> None:
        data = self.browser_process.readAllStandardError().data().decode(errors="replace").strip()  # pyrefly: ignore [missing-attribute]
        if data:
            # Chromium writes many non-fatal diagnostics to stderr — only log
            # lines that look like genuine errors.
            lower = data.lower()
            if any(w in lower for w in ("error", "fatal", "crash", "fail")):
                self.log_window.append_log(f"BROWSER ERR: {data}")

    def on_browser_process_finished(self) -> None:
        self.log_window.append_log("🌐 Browser closed.")
        self.launch_browser_button.setText("🚀 Launch Browser")
        set_button_role(self.launch_browser_button, "primary")


__all__ = ["ImageCrawlBrowserLauncher"]
