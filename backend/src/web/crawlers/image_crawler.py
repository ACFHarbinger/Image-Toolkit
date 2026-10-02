import base64
import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from backend.src.events import Observable


class ImageCrawler:
    """
    Advanced Python Image Crawler supporting Action Sequences, URL replacements,
    and Selenium / requests fallback parsing for general web scraping.
    """

    def __init__(self, config: dict):
        self.config = config
        self._is_running = True
        self._access_blocked = False
        self._login_blocked = False
        self.completion_message = ""
        self._attached_browser = False
        self._driver_error = ""
        # === Events (issue #529: plain Observables, not Qt signals) ===
        self.on_status: Observable[str] = Observable()
        self.on_image_saved: Observable[str] = Observable()
        self.on_finished: Observable[str] = Observable()
        # Fired when a human-verification challenge is detected; the GUI
        # must call resume() after the user dismisses the prompt.
        self.on_verification_required: Observable[str] = Observable()
        # Set by resume() so _wait_for_browser_access() can unblock.
        self._resume_event: threading.Event = threading.Event()

    def stop(self):
        self._is_running = False
        self._resume_event.set()  # unblock any waiting verification poll
        self.on_status.publish("Cancellation pending...")

    def resume(self) -> None:
        """Unblock a crawl that is paused at a verification prompt."""
        self._resume_event.set()

    def on_status_emitted(self, msg: str):
        self.on_status.publish(msg)

    def on_error_emitted(self, msg: str):
        self.on_status.publish(f"ERROR: {msg}")

    def run(self) -> int:  # noqa: C901
        download_dir = self.config.get("download_dir", "downloads")
        os.makedirs(download_dir, exist_ok=True)

        selection_mode = self.config.get("selection_mode", "Download All (Default)")
        self.on_status.publish(f"🌐 Crawl starting with selection mode: {selection_mode}")

        base_url = self.config.get("url", "").strip()
        if not base_url:
            self.on_status.publish("❌ Error: No target URL specified.")
            return 0

        replace_str = self.config.get("replace_str")
        replacements = self.config.get("replacements")

        target_urls = [base_url]
        if replace_str and replacements:
            if isinstance(replacements, str):
                replacements = [r.strip() for r in replacements.split(",") if r.strip()]

            clean_replace_str = replace_str.strip()
            for r in replacements:
                clean_r = r.strip()
                if clean_replace_str.startswith("?") and not clean_r.startswith("?") and not clean_r.startswith("&"):
                    if "page=" in clean_replace_str and "page=" not in clean_r:
                        clean_r = f"?page={clean_r}"
                    else:
                        clean_r = f"?{clean_r}"
                elif clean_replace_str.startswith("page=") and not clean_r.startswith("page="):
                    clean_r = f"page={clean_r}"

                new_url = base_url.replace(clean_replace_str, clean_r)
                if new_url not in target_urls:
                    target_urls.append(new_url)

        self.on_status.publish(f"🌐 Target pages queued ({len(target_urls)}): {', '.join(target_urls)}")

        skip_first = int(self.config.get("skip_first", 0) or 0)
        skip_last = int(self.config.get("skip_last", 0) or 0)

        actions = self.config.get("actions", [])
        driver = self._try_init_driver()
        if self.config.get("attach_existing") and driver is None:
            self.completion_message = f"Crawl stopped: {self._driver_error}" if self._driver_error else (
                "Crawl stopped: no existing browser session is available on localhost:9223. "
                "Open the browser with remote debugging, log in, and retry."
            )
            self.on_status.publish(self.completion_message)
            self.on_finished.publish(self.completion_message)
            return 0

        downloaded_count = 0
        global_seen = set()
        session = requests.Session()
        session_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # Check login configuration
        login_cfg = self.config.get("login_config") or {}
        login_url = (
            login_cfg.get("url")
            or self.config.get("gen_login_url")
            or self.config.get("login_url")
        )
        login_user = (
            login_cfg.get("username")
            or self.config.get("gen_username")
            or self.config.get("username")
        )
        login_pass = (
            login_cfg.get("password")
            or self.config.get("gen_password")
            or self.config.get("password")
        )

        try:
            if driver and self.config.get("attach_existing"):
                self.on_status.publish("Using the existing browser login; automatic login skipped.")
                self._sync_cookies_to_session(driver, session)
            elif driver and login_url and (login_user or login_pass):
                self._perform_login(driver, login_url, login_user, login_pass)
                self._sync_cookies_to_session(driver, session)
            elif not driver and login_url and (login_user or login_pass):
                self._perform_http_login(
                    session, login_url, login_user, login_pass, session_headers
                )

            for page_idx, target_url in enumerate(target_urls):
                if self._access_blocked:
                    break
                if not self._is_running:
                    self.on_status.publish("🛑 Crawl cancelled by user.")
                    break

                self.on_status.publish(
                    f"🌐 Page {page_idx + 1}/{len(target_urls)}: Navigating to {target_url}"
                )

                extracted_urls = []

                if driver:
                    try:
                        if not self._navigate_browser(driver, target_url):
                            break
                        self._scroll_page_to_trigger_lazy_load(driver)
                        self._sync_cookies_to_session(driver, session)

                        parsed_urls = self._process_selenium_actions(
                            driver, actions, target_url
                        )
                        if parsed_urls:
                            extracted_urls.extend(parsed_urls)
                        else:
                            self.on_status.publish("ℹ️ Selenium extracted 0 images. Using HTTP fallback parser...")
                            extracted_urls.extend(
                                self._process_requests_page(session, target_url, session_headers)
                            )
                    except Exception as e:
                        self.on_status.publish(
                            f"⚠️ Selenium navigation error: {e}. Falling back to HTTP parser..."
                        )
                        extracted_urls.extend(
                            self._process_requests_page(session, target_url, session_headers)
                        )
                else:
                    extracted_urls.extend(
                        self._process_requests_page(session, target_url, session_headers)
                    )

                # Deduplicate against global_seen set across all pages
                unique_urls = []
                page_seen = set()
                for u in extracted_urls:
                    if u not in global_seen and u not in page_seen:
                        page_seen.add(u)
                        unique_urls.append(u)

                is_manual_selection = "Manual Selection" in selection_mode

                urls_to_download = list(unique_urls)
                if not is_manual_selection:
                    if skip_first > 0:
                        urls_to_download = urls_to_download[skip_first:]
                    if skip_last > 0 and len(urls_to_download) > skip_last:
                        urls_to_download = urls_to_download[:-skip_last]

                self.on_status.publish(
                    f"🔎 Page {page_idx + 1}: extracted {len(extracted_urls)} URL(s), "
                    f"{len(unique_urls)} new unique image(s); "
                    f"skip first={skip_first}, skip last={skip_last} "
                    f"({'ignored for manual selection' if is_manual_selection else 'applied'})."
                )
                self.on_status.publish(
                    f"📷 Found {len(urls_to_download)} downloadable image(s) on page {page_idx + 1}."
                )

                # Download images
                download_headers = dict(session_headers)
                download_headers["Referer"] = target_url
                if driver:
                    with contextlib.suppress(Exception):
                        download_headers["User-Agent"] = driver.execute_script("return navigator.userAgent;")
                    self._sync_cookies_to_session(driver, session)

                for img_idx, img_url in enumerate(urls_to_download, start=1):
                    if not self._is_running:
                        break

                    saved_path = self._download_single_image(
                        session, img_url, download_dir, download_headers, driver=driver
                    )
                    if saved_path:
                        global_seen.add(img_url)
                        downloaded_count += 1
                        pos_on_page = img_idx
                        meta = {
                            "path": saved_path,
                            "page_url": target_url,
                            "page_num": page_idx + 1,
                            "index_on_page": pos_on_page,
                            "total_on_page": len(urls_to_download),
                            "global_id": downloaded_count,
                            "img_url": img_url,
                            "skip_first": skip_first,
                            "skip_last": skip_last,
                        }
                        self.on_image_saved.publish(json.dumps(meta))
                        self.on_status.publish(
                            f"✅ Saved [{downloaded_count}] (Page {page_idx + 1} #{pos_on_page}): {os.path.basename(saved_path)}"
                        )

                    time.sleep(0.1)

        finally:
            if driver:
                with contextlib.suppress(Exception):
                    if self._attached_browser:
                        # DELETE /session can close a browser the user opened themselves.
                        driver.service.stop()
                    else:
                        driver.quit()

        message = f"Crawl finished. Downloaded **{downloaded_count}** image(s)!"
        if self._access_blocked:
            message = (
                f"Crawl stopped: login is required in the connected browser. "
                f"Downloaded **{downloaded_count}** image(s). "
                "Log in in that window, confirm the album gallery is visible, and retry."
            ) if self._login_blocked else (
                f"Crawl stopped: website security verification did not complete. "
                f"Downloaded **{downloaded_count}** image(s). "
                "Selenium sessions may be rejected even after checking the verification box."
            )
        self.completion_message = message
        self.on_status.publish(message)
        self.on_finished.publish(message)
        return downloaded_count

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
                if not self._is_port_open("127.0.0.1", 9223):
                    return None
                driver = self._connect_debug_browser(9223)
                self._attached_browser = True
                self.on_status.publish("Connected to the existing browser session on localhost:9223.")
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

    def _perform_login(  # noqa: C901
        self, driver, login_url: str, username: str | None, password: str | None
    ) -> bool:
        """Attempt automated login via Selenium."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self.on_status.publish(f"🔑 Navigating to login page: {login_url}")
        try:
            if not self._navigate_browser(driver, login_url):
                return False
            time.sleep(2.0)

            # Check if user is already authenticated
            page_src = driver.page_source.lower()
            if "logout" in page_src or "sign out" in page_src or "/user/index" in page_src:
                self.on_status.publish("ℹ️ Already authenticated session detected.")
                return True

            # Find user/email input
            user_el = None
            for sel in [
                "input[name='email']",
                "input[type='email']",
                "input[id='email']",
                "input[name='username']",
                "input[id='username']",
                "input[name='user']",
                "input[type='text']",
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        user_el = el
                        break
                if user_el:
                    break

            if user_el and username:
                user_el.clear()
                user_el.send_keys(username)

            # Find password input
            pass_el = None
            for sel in [
                "input[name='password']",
                "input[type='password']",
                "input[id='password']",
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        pass_el = el
                        break
                if pass_el:
                    break

            if pass_el and password:
                pass_el.clear()
                pass_el.send_keys(password)

            # Check Remember Me if present
            with contextlib.suppress(Exception):
                remember_boxes = driver.find_elements(
                    By.CSS_SELECTOR,
                    "input[name='remember'], input[id='remember'], input[type='checkbox']",
                )
                for box in remember_boxes:
                    if not box.is_selected():
                        box.click()

            # Detect Captcha / Cloudflare Turnstile
            captcha_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".g-recaptcha, .cf-turnstile, div[class*='recaptcha'], div[class*='turnstile'], iframe[src*='turnstile'], iframe[src*='recaptcha']",
            )
            if captcha_elements:
                self.on_status.publish(
                    "⚠️ Captcha/Turnstile detected on login page. If login does not complete automatically, "
                    "launch your browser with --remote-debugging-port=9222 and log in manually first."
                )

            # Submit form
            submitted = False
            for btn_sel in [
                "button[type='submit']",
                "input[type='submit']",
                "form button",
                ".btn-primary",
            ]:
                btns = driver.find_elements(By.CSS_SELECTOR, btn_sel)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        submitted = True
                        break
                if submitted:
                    break

            if not submitted and pass_el:
                pass_el.send_keys(Keys.RETURN)

            time.sleep(3.0)
            self.on_status.publish(
                f"🔑 Login form submitted. Current page: {driver.current_url}"
            )
            return True
        except Exception as e:
            self.on_status.publish(f"⚠️ Automated login encounter: {e}")
            return False

    def _perform_http_login(
        self,
        session: requests.Session,
        login_url: str,
        username: str | None,
        password: str | None,
        headers: dict,
    ) -> bool:
        """Best-effort HTTP form POST login fallback when WebDriver is unavailable."""
        try:
            resp = session.get(login_url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form")
            if not form:
                return False

            payload = {}
            for inp in form.find_all("input"):
                name = inp.get("name")
                val = inp.get("value", "")
                if name:
                    payload[name] = val

            for k in payload:
                lk = k.lower()
                if ("user" in lk or "email" in lk) and username:
                    payload[k] = username
                elif "pass" in lk and password:
                    payload[k] = password

            action = form.get("action")
            post_url = urllib.parse.urljoin(login_url, action) if action else login_url
            post_resp = session.post(post_url, data=payload, headers=headers, timeout=10)
            self.on_status.publish(
                f"🔑 HTTP login POST sent to {post_url} (Status: {post_resp.status_code})"
            )
            return post_resp.status_code in (200, 302)
        except Exception as e:
            self.on_status.publish(f"⚠️ HTTP login fallback failed: {e}")
            return False

    def _sync_cookies_to_session(self, driver, session: requests.Session) -> None:
        """Transfer browser cookies into requests session for authenticated media downloads."""
        try:
            cookies = driver.get_cookies()
            for c in cookies:
                session.cookies.set(
                    c["name"],
                    c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )
            if cookies:
                self.on_status.publish(
                    f"🍪 Synchronized {len(cookies)} browser cookie(s) to HTTP session."
                )
        except Exception as e:
            self.on_status.publish(f"⚠️ Cookie synchronization warning: {e}")

    def _navigate_browser(self, driver, url: str) -> bool:
        from selenium.common.exceptions import TimeoutException

        driver.set_page_load_timeout(30)
        try:
            driver.get(url)
        except TimeoutException:
            if not self._browser_has_challenge(driver):
                raise
            # Challenge resources can keep navigation pending before polling starts.
            self.on_status.publish("⚠️ Navigation is waiting on website security verification.")
        return self._wait_for_browser_access(driver)

    def _browser_has_challenge(self, driver) -> bool:
        from selenium.webdriver.common.by import By

        title = (driver.title or "").lower()
        if any(marker in title for marker in ("just a moment", "attention required")):
            return True
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            return False
        return any(marker in body for marker in (
            "performing security verification",
            "this page is displayed while the website verifies you are not a bot",
            "verifying you are human",
        ))

    def _wait_for_browser_access(self, driver) -> bool:
        """Allow verification to finish without treating a challenge as a gallery.

        When a Cloudflare/captcha challenge is detected the crawler pauses and
        fires ``on_verification_required``.  The GUI layer must show a dialog
        and call :meth:`resume` after the user has solved the check — that sets
        ``_resume_event`` which unblocks this loop.
        """
        from selenium.webdriver.common.by import By

        headless = self.config.get("headless")
        notified = False
        login_pending = False
        album_url = None
        restored_album = False
        while self._is_running:
            challenge = self._browser_has_challenge(driver)
            if not challenge and not login_pending:
                body = driver.find_element(By.TAG_NAME, "body").text
                if self._has_album_login_gate(body):
                    login_pending = True
                    album_url = driver.current_url
                    self.on_status.publish(
                        "🔑 This browser is not logged in: the site is showing only an album preview. "
                        "Log in in the connected browser window within two minutes. "
                        "Your normal Brave window uses a different profile."
                    )
            if not challenge and not login_pending:
                return True
            if login_pending and not challenge and driver.find_elements(By.CSS_SELECTOR, ".photos-list img"):
                if driver.current_url != album_url and not restored_album:
                    restored_album = True
                    driver.get(album_url)
                    continue
                return True
            if challenge and not notified:
                if headless:
                    # Headless sessions can never solve a visual challenge.
                    self.on_status.publish(
                        "⚠️ Browser verification required but running headless — disable Headless and retry."
                    )
                    self._access_blocked = True
                    return False
                # Non-headless: pause and ask the user to solve it, then press OK.
                msg = (
                    "⏸️ Human verification required. Complete the check in the browser window, "
                    "then press OK in the dialog to resume the crawl."
                )
                self.on_status.publish(msg)
                self._resume_event.clear()
                self.on_verification_required.publish(msg)
                # Block the crawler thread until resume() is called (or stop()).
                while self._is_running and not self._resume_event.is_set():
                    self._resume_event.wait(timeout=0.5)
                if not self._is_running:
                    return False
                self._resume_event.clear()
                notified = True  # suppress further pause prompts for same page
            time.sleep(0.5)
        return False

    @staticmethod
    def _has_album_login_gate(text: str) -> bool:
        return isinstance(text, str) and "you need to log in to view more content of this album" in " ".join(text.lower().split())

    def _image_element_url(self, get_attribute, base_url: str) -> str | None:
        # A nonempty placeholder src must not mask the actual lazy/full-size URL.
        for attr in (
            "data-high-res", "data-large-src", "data-full-url", "data-original",
            "data-src", "data-lazy-src", "data-srcset", "srcset", "src", "data-thumb",
        ):
            value = get_attribute(attr)
            if not isinstance(value, str) or not value.strip():
                continue
            candidates = [value.strip()]
            if attr.endswith("srcset"):
                entries = [part.split() for part in value.split(",") if part.strip()]

                def size(entry):
                    try:
                        return float(entry[1].rstrip("wx")) if len(entry) > 1 else 1
                    except ValueError:
                        return 0

                candidates = [entry[0] for entry in sorted(entries, key=size, reverse=True)]
            for candidate in candidates:
                url = self._clean_image_url(urllib.parse.urljoin(base_url, candidate))
                if url:
                    return url
        return None

    def _fetch_browser_image(self, driver, url: str) -> bytes:
        """Retry using the browser session; normal browser CORS rules still apply."""
        try:
            result = driver.execute_async_script("""
                const url = arguments[0], done = arguments[arguments.length - 1];
                const controller = new AbortController();
                const timer = setTimeout(() => controller.abort(), 15000);
                fetch(url, {credentials: 'include', signal: controller.signal})
                    .then(response => {
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        return response.blob();
                    })
                    .then(blob => new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = () => reject(new Error('Image read failed'));
                        reader.readAsDataURL(blob);
                    }))
                    .then(data => { clearTimeout(timer); done({data}); })
                    .catch(error => { clearTimeout(timer); done({error: String(error)}); });
            """, url)
            if result.get("data"):
                return base64.b64decode(result["data"], validate=True)
            self.on_status.publish(f"⚠️ Browser image request failed: {result.get('error')}: {url}")
        except Exception as exc:
            self.on_status.publish(f"⚠️ Browser image request failed: {exc}")
        return b""

    def _scroll_page_to_trigger_lazy_load(self, driver) -> None:
        """Gradually scroll through the page to trigger IntersectionObserver and lazy-loaded images."""
        with contextlib.suppress(Exception):
            total_height = (
                driver.execute_script(
                    "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
                )
                or 1000
            )
            step = 600
            for y in range(0, int(total_height), step):
                driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(0.1)
            driver.execute_script(f"window.scrollTo(0, {total_height});")
            time.sleep(0.4)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.2)

    def _process_selenium_actions(self, driver, actions, base_url) -> list[str]:  # noqa: C901
        """Execute configured actions on Selenium driver."""
        from selenium.webdriver.common.by import By

        extracted = []
        for act in actions:
            atype = act.get("type", "")
            param = act.get("param")

            if atype == "Wait for Gallery (Context Reset)":
                self._scroll_page_to_trigger_lazy_load(driver)
                time.sleep(1)

            elif atype == "Wait X Seconds" and param:
                with contextlib.suppress(Exception):
                    time.sleep(float(param))

            elif atype == "Wait for Page Load":
                with contextlib.suppress(Exception):
                    delay = float(param) if param else 2.0
                    time.sleep(delay)

            elif atype in (
                "Extract High-Res Preview URL",
                "Download Simple Thumbnail (Legacy)",
            ):
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    try:
                        url = self._image_element_url(img.get_attribute, base_url)
                        if url:
                            extracted.append(url)
                    except Exception:
                        continue

            elif atype == "Find Parent Link (<a>)":
                links = driver.find_elements(By.XPATH, "//a[img]")
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        if href and not href.startswith("javascript:"):
                            cleaned = self._clean_image_url(href)
                            if cleaned:
                                extracted.append(cleaned)
                    except Exception:
                        continue

            elif atype == "Find Element by CSS Selector" and param:
                elements = driver.find_elements(By.CSS_SELECTOR, str(param))
                for el in elements:
                    try:
                        tag = el.tag_name.lower()
                        if tag == "a":
                            src = el.get_attribute("href")
                            url = self._clean_image_url(urllib.parse.urljoin(base_url, src)) if src else None
                            if url:
                                extracted.append(url)
                        else:
                            images = [el] if tag == "img" else el.find_elements(By.TAG_NAME, "img")
                            for img in images:
                                url = self._image_element_url(img.get_attribute, base_url)
                                if url:
                                    extracted.append(url)
                            if not images:
                                src = el.get_attribute("src") or el.get_attribute("href")
                                url = self._clean_image_url(urllib.parse.urljoin(base_url, src)) if src else None
                                if url:
                                    extracted.append(url)
                    except Exception:
                        continue

            elif atype == "Find <img> Number X on Page" and param:
                with contextlib.suppress(Exception):
                    idx = int(param) - 1
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    if 0 <= idx < len(imgs):
                        img = imgs[idx]
                        url = self._image_element_url(img.get_attribute, base_url)
                        if url:
                            extracted.append(url)

            elif atype == "Download Image from Element":
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    try:
                        url = self._image_element_url(img.get_attribute, base_url)
                        if url:
                            extracted.append(url)
                    except Exception:
                        continue

            elif atype == "Download Current URL as Image":
                curr = driver.current_url
                cleaned = self._clean_image_url(curr)
                if cleaned:
                    extracted.append(cleaned)

            elif atype == "Click Element by Text" and param:
                with contextlib.suppress(Exception):
                    txt = str(param).strip()
                    for by_type, query in [
                        (By.LINK_TEXT, txt),
                        (By.PARTIAL_LINK_TEXT, txt),
                        (By.XPATH, f"//*[contains(text(), '{txt}')]"),
                    ]:
                        elems = driver.find_elements(by_type, query)
                        clicked = False
                        for el in elems:
                            if el.is_displayed():
                                el.click()
                                clicked = True
                                time.sleep(1.5)
                                break
                        if clicked:
                            break

            elif atype == "Open Link in New Tab" and param:
                with contextlib.suppress(Exception):
                    driver.execute_script(f"window.open('{param}', '_blank');")
                    time.sleep(1.0)

            elif atype == "Switch to Last Tab":
                with contextlib.suppress(Exception):
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.switch_to.window(handles[-1])
                        time.sleep(0.5)

            elif atype == "Close Current Tab":
                with contextlib.suppress(Exception):
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(0.5)

            elif atype == "Scan Page for Text and Skip if Found" and param:
                if str(param) in driver.page_source:
                    self.on_status.publish(
                        f"⏩ Page skipped due to match for text: {param}"
                    )
                    return []

        if not extracted:
            # Default extraction if actions list did not collect URLs
            imgs = driver.find_elements(By.TAG_NAME, "img")
            for img in imgs:
                try:
                    url = self._image_element_url(img.get_attribute, base_url)
                    if url:
                        extracted.append(url)
                except Exception:
                    continue

        return extracted

    def _process_requests_page(self, session, page_url, headers) -> list[str]:
        """Fetch and parse images via HTTP request fallback."""
        extracted = []
        try:
            resp = session.get(page_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.on_status.publish(
                    f"⚠️ Page request returned HTTP {resp.status_code}: {page_url}. "
                    "If browser verification or login is required, use a visible browser session."
                )
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            if self._has_album_login_gate(soup.get_text(" ", strip=True)):
                self._access_blocked = True
                self._login_blocked = True
                self.on_status.publish("🔑 HTTP page contains a login gate, not the album gallery; stopping.")
                return []
            for img in soup.find_all("img"):
                url = self._image_element_url(img.get, resp.url or page_url)
                if url:
                    extracted.append(url)

            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if href and href.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp", ".gif")
                ):
                    full_url = urllib.parse.urljoin(page_url, href)
                    cleaned = self._clean_image_url(full_url)
                    if cleaned:
                        extracted.append(cleaned)

        except Exception as e:
            self.on_status.publish(f"⚠️ HTTP request error for {page_url}: {e}")

        return extracted

    def _clean_image_url(self, url: str) -> str | None:
        """Filter out non-image files and strip proxy wrappers."""
        if not url or url.startswith("data:") or ".svg" in url.lower():
            return None

        # Strip Jetpack/WordPress image proxies (i0.wp.com, i1.wp.com, etc.)
        url = re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", url)

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        path = parsed.path.lower()

        # Reject HTML webpage links
        if any(path.endswith(ext) for ext in (".html", ".htm", ".php", ".asp", ".aspx")):
            return None

        if any(
            path.endswith(ext)
            for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
        ):
            return url

        # If query parameters contain image formats
        if any(ext in parsed.query.lower() for ext in ("jpeg", "jpg", "png", "webp")):
            return url

        return None

    def _download_single_image(
        self, session, img_url, download_dir, headers, driver=None
    ) -> str | None:
        """Download single image file and write to target directory."""
        try:
            parsed = urllib.parse.urlparse(img_url)
            fname = os.path.basename(parsed.path)
            fname = urllib.parse.unquote(fname).split("?")[0].split("#")[0]
            if (
                not fname
                or len(fname) < 4
                or not any(
                    fname.lower().endswith(ext)
                    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
                )
            ):
                ext = ".jpg"
                for e in (".png", ".webp", ".gif", ".bmp", ".jpeg", ".jpg"):
                    if e in img_url.lower():
                        ext = e
                        break
                fname = f"img_{int(time.time() * 1000)}_{abs(hash(img_url)) % 10000}{ext}"

            out_path = os.path.abspath(os.path.join(download_dir, fname))

            # Skip if already exists and valid
            if os.path.exists(out_path) and os.path.getsize(out_path) > 3000:
                return out_path

            content = b""
            try:
                resp = session.get(img_url, headers=headers, timeout=20)
                c_type = resp.headers.get("Content-Type", "").lower()
                if resp.status_code == 200 and not any(
                    kind in c_type for kind in ("text/", "application/xhtml")
                ):
                    content = resp.content
                else:
                    self.on_status.publish(
                        f"⚠️ Image request rejected: HTTP {resp.status_code}, {c_type}: {img_url}"
                    )
            except requests.RequestException as exc:
                self.on_status.publish(f"⚠️ Image HTTP request failed: {exc}")

            if not content and driver is not None:
                content = self._fetch_browser_image(driver, img_url)
            if len(content) < 100:
                self.on_status.publish(f"⚠️ No image data received: {img_url}")
                return None

            # Verify image magic bytes
            is_valid_image = (
                content.startswith(b"\xff\xd8\xff")  # JPEG
                or content.startswith(b"\x89PNG")     # PNG
                or content.startswith(b"GIF8")        # GIF
                or (content.startswith(b"RIFF") and b"WEBP" in content[:16])  # WEBP
                or content.startswith(b"BM")          # BMP
            )
            if not is_valid_image:
                self.on_status.publish(f"⚠️ Response is not a supported image: {img_url}")
                return None

            # Correct extension if mismatch
            if content.startswith(b"\xff\xd8\xff") and not out_path.lower().endswith((".jpg", ".jpeg")):
                out_path = os.path.splitext(out_path)[0] + ".jpg"
            elif content.startswith(b"\x89PNG") and not out_path.lower().endswith(".png"):
                out_path = os.path.splitext(out_path)[0] + ".png"
            elif b"WEBP" in content[:16] and not out_path.lower().endswith(".webp"):
                out_path = os.path.splitext(out_path)[0] + ".webp"

            with open(out_path, "wb") as f:
                f.write(content)
            return out_path

        except Exception as e:
            self.on_status.publish(f"⚠️ Download failed for {img_url}: {e}")

        return None
