"""Browser binary discovery, debug-port attach, and WebDriver init for ImageCrawler."""

import contextlib
import os
import re
import shutil
import socket
import subprocess
import time

import requests


class _BrowserSetupMixin:
    """Browser discovery/init methods for ``ImageCrawler``."""

    def _find_browser_binary(self, browser_name: str) -> str | None:  # noqa: C901
        """Find binary executable path for specified browser."""
        b_name = (browser_name or "").lower().strip()
        if b_name == "brave":
            for cmd in ("brave-browser", "brave", "brave-browser-stable"):
                p = shutil.which(cmd)
                if p and os.path.exists(p):
                    return p
            for p in (
                "/usr/bin/brave-browser",
                "/usr/bin/brave",
                "/snap/bin/brave",
                "/opt/brave.com/brave/brave-browser",
                "/opt/brave.com/brave/brave",
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            ):
                if os.path.exists(p):
                    return p
        elif b_name in ("edge", "msedge"):
            for cmd in ("msedge", "microsoft-edge", "microsoft-edge-stable"):
                p = shutil.which(cmd)
                if p and os.path.exists(p):
                    return p
            for p in (
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ):
                if os.path.exists(p):
                    return p
        elif b_name in ("chrome", "chromium"):
            for cmd in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
                p = shutil.which(cmd)
                if p and os.path.exists(p):
                    return p
            for p in (
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ):
                if os.path.exists(p):
                    return p
        return None

    def _is_port_open(self, host: str, port: int, timeout: float = 0.2) -> bool:
        """Quick check if a TCP port is open to avoid long Selenium connection timeouts."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _find_brave_launch_command(self, binary: str | None) -> list[str]:
        if binary:
            return [binary]
        flatpak = shutil.which("flatpak")
        if flatpak:
            try:
                result = subprocess.run(
                    [flatpak, "info", "com.brave.Browser"],
                    capture_output=True, timeout=5, check=False,
                )
                if result.returncode == 0:
                    return [flatpak, "run", "com.brave.Browser"]
            except (OSError, subprocess.TimeoutExpired):
                pass
        return []

    def _connect_debug_browser(self, port: int):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.selenium_manager import SeleniumManager

        # Flatpak's Chromium version cannot be inferred from host Chrome binaries.
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(f"http://127.0.0.1:{port}/json/version", timeout=5)
            response.raise_for_status()
            browser = response.json().get("Browser", "")
        version = re.search(r"(?:Chrome|Chromium|HeadlessChrome)/(\d+)\.", browser)
        if not version:
            raise ValueError(f"Debugging endpoint returned an unsupported browser: {browser!r}")
        major = version.group(1)
        self.on_status.publish(f"Detected {browser}; resolving ChromeDriver {major}.")
        paths = SeleniumManager().binary_paths([
            "--browser", "chrome", "--browser-version", major,
            "--skip-driver-in-path", "--skip-browser-in-path",
            "--avoid-browser-download", "--avoid-stats", "--timeout", "30",
        ])
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        return webdriver.Chrome(service=Service(executable_path=paths["driver_path"]), options=options)

    def _try_init_driver(self):  # noqa: C901
        """Try connecting to Remote Selenium WebDriver or local browser driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions

            browser_name = self.config.get("browser") or self.config.get("gen_browser") or "brave"
            browser_name = str(browser_name).lower().strip()
            headless = self.config.get("headless", False)

            if self.config.get("attach_existing"):
                if browser_name == "firefox":
                    raise ValueError("Existing-session mode requires Brave, Chrome, or Edge.")
                _attach_port = self.config.get("debug_port", 9223)
                if not self._is_port_open("127.0.0.1", _attach_port):
                    return None
                driver = self._connect_debug_browser(_attach_port)
                self._attached_browser = True
                self.on_status.publish(f"Connected to the existing browser session on localhost:{_attach_port}.")
                return driver

            # Firefox support
            if browser_name == "firefox":
                ff_options = FirefoxOptions()
                if headless:
                    ff_options.add_argument("-headless")
                driver = webdriver.Firefox(options=ff_options)
                self.on_status.publish("🌐 Initialized local Firefox session.")
                return driver

            # Chromium-based options (Brave, Chrome, Edge)
            options = ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            if headless:
                options.add_argument("--headless=new")

            browser_bin = self._find_browser_binary(browser_name)
            if browser_bin:
                options.binary_location = browser_bin
            brave_command = self._find_brave_launch_command(browser_bin) if browser_name == "brave" else []
            is_flatpak = len(brave_command) > 1

            # 1. Instant check for an active remote debugging session on port 9222
            if self._is_port_open("127.0.0.1", 9222):
                try:
                    driver = self._connect_debug_browser(9222)
                    self.on_status.publish(f"🌐 Connected to active {browser_name.title()} debugging session (port 9222).")
                    return driver
                except Exception:
                    pass

            # 2. Instant check for Managed Remote WebDriver on port 9515
            if not is_flatpak and self._is_port_open("127.0.0.1", 9515):
                try:
                    driver = webdriver.Remote(
                        command_executor="http://localhost:9515", options=options
                    )
                    self.on_status.publish(f"🌐 Connected to Managed WebDriver service on port 9515 ({browser_name.title()}).")
                    return driver
                except Exception:
                    pass

            # Support persistent profile directory so logins/cookies persist across runs
            user_dir = self.config.get("user_data_dir")
            if not user_dir:
                user_dir = os.path.expanduser(
                    "~/.var/app/com.brave.Browser/config/image-toolkit-crawler"
                    if is_flatpak else "~/.image-toolkit/browser_profile"
                )
            with contextlib.suppress(Exception):
                os.makedirs(user_dir, exist_ok=True)

            # 3. For Brave specifically on Linux/Mac, launch remote-debugging subprocess if direct ChromeDriver session traps
            if browser_name == "brave" and brave_command:
                try:
                    cmd = [
                        *brave_command,
                        "--remote-debugging-port=9222",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        f"--user-data-dir={user_dir}",
                    ]
                    if headless:
                        cmd.append("--headless=new")

                    self._brave_proc = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    time.sleep(1.5)

                    driver = self._connect_debug_browser(9222)
                    self.on_status.publish(
                        f"🌐 Initialized local {browser_name.title()} browser session."
                    )
                    return driver
                except Exception as ex:
                    self.on_status.publish(f"⚠️ Brave subprocess launch warning: {ex}")
                    if is_flatpak:
                        raise RuntimeError("Could not connect to Flatpak Brave") from ex

            # 4. Fallback to direct Chrome/Chromium launch with persistent profile
            try:
                options_with_profile = ChromeOptions()
                for arg in options.arguments:
                    options_with_profile.add_argument(arg)
                if options.binary_location:
                    options_with_profile.binary_location = options.binary_location
                options_with_profile.add_argument(f"--user-data-dir={user_dir}")
                driver = webdriver.Chrome(options=options_with_profile)
                self.on_status.publish(
                    f"🌐 Initialized local {browser_name.title()} session with persistent profile."
                )
                return driver
            except Exception:
                driver = webdriver.Chrome(options=options)
                self.on_status.publish(f"🌐 Initialized local {browser_name.title()} session.")
                return driver

        except Exception as e:
            if self.config.get("attach_existing"):
                self._driver_error = f"Could not connect to the existing browser: {getattr(e, 'msg', str(e))}"
                self.on_status.publish(f"⚠️ {self._driver_error}")
                return None
            self.on_status.publish(
                f"ℹ️ WebDriver not connected ({e}). Using high-performance HTTP crawler."
            )
            return None

