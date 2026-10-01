import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
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
        # === Events (issue #529: plain Observables, not Qt signals) ===
        self.on_status: Observable[str] = Observable()
        self.on_image_saved: Observable[str] = Observable()
        self.on_finished: Observable[str] = Observable()

    def stop(self):
        self._is_running = False
        self.on_status.publish("Cancellation pending...")

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

        if driver and login_url and (login_user or login_pass):
            self._perform_login(driver, login_url, login_user, login_pass)
            self._sync_cookies_to_session(driver, session)
        elif not driver and login_url and (login_user or login_pass):
            self._perform_http_login(
                session, login_url, login_user, login_pass, session_headers
            )

        try:
            for page_idx, target_url in enumerate(target_urls):
                if not self._is_running:
                    self.on_status.publish("🛑 Crawl cancelled by user.")
                    break

                self.on_status.publish(
                    f"🌐 Page {page_idx + 1}/{len(target_urls)}: Navigating to {target_url}"
                )

                extracted_urls = []

                if driver:
                    try:
                        driver.get(target_url)
                        time.sleep(1.5)
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
                for u in extracted_urls:
                    if u not in global_seen:
                        global_seen.add(u)
                        unique_urls.append(u)

                is_manual_selection = "Manual Selection" in selection_mode

                urls_to_download = list(unique_urls)
                if not is_manual_selection:
                    if skip_first > 0:
                        urls_to_download = urls_to_download[skip_first:]
                    if skip_last > 0 and len(urls_to_download) > skip_last:
                        urls_to_download = urls_to_download[:-skip_last]

                self.on_status.publish(
                    f"📷 Found {len(urls_to_download)} downloadable image(s) on page {page_idx + 1}."
                )

                # Download images
                host = urllib.parse.urlparse(target_url).netloc
                download_headers = dict(session_headers)
                download_headers["Referer"] = f"https://{host}/"

                for img_idx, img_url in enumerate(urls_to_download, start=1):
                    if not self._is_running:
                        break

                    saved_path = self._download_single_image(
                        session, img_url, download_dir, download_headers
                    )
                    if saved_path:
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
                    driver.quit()

        message = f"Crawl finished. Downloaded **{downloaded_count}** image(s)!"
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

    def _try_init_driver(self):  # noqa: C901
        """Try connecting to Remote Selenium WebDriver or local browser driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions

            browser_name = self.config.get("browser") or self.config.get("gen_browser") or "brave"
            browser_name = str(browser_name).lower().strip()
            headless = self.config.get("headless", False)

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
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            if headless:
                options.add_argument("--headless=new")

            browser_bin = self._find_browser_binary(browser_name)
            if browser_bin:
                options.binary_location = browser_bin

            # 1. Instant check for an active remote debugging session on port 9222
            if self._is_port_open("127.0.0.1", 9222):
                try:
                    dbg_options = ChromeOptions()
                    dbg_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    driver = webdriver.Chrome(options=dbg_options)
                    self.on_status.publish(f"🌐 Connected to active {browser_name.title()} debugging session (port 9222).")
                    return driver
                except Exception:
                    pass

            # 2. Instant check for Managed Remote WebDriver on port 9515
            if self._is_port_open("127.0.0.1", 9515):
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
                user_dir = os.path.expanduser("~/.image-toolkit/browser_profile")
            with contextlib.suppress(Exception):
                os.makedirs(user_dir, exist_ok=True)

            # 3. For Brave specifically on Linux/Mac, launch remote-debugging subprocess if direct ChromeDriver session traps
            if browser_name == "brave" and browser_bin:
                try:
                    cmd = [
                        browser_bin,
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

                    dbg_options = ChromeOptions()
                    dbg_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    driver = webdriver.Chrome(options=dbg_options)
                    self.on_status.publish(
                        f"🌐 Initialized local {browser_name.title()} browser session."
                    )
                    return driver
                except Exception as ex:
                    self.on_status.publish(f"⚠️ Brave subprocess launch warning: {ex}")

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
            driver.get(login_url)
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
                        src = (
                            img.get_attribute("src")
                            or img.get_attribute("data-src")
                            or img.get_attribute("data-original")
                            or img.get_attribute("data-lazy-src")
                            or img.get_attribute("data-high-res")
                            or img.get_attribute("data-large-src")
                            or img.get_attribute("data-full-url")
                            or img.get_attribute("data-thumb")
                        )
                        if not src:
                            srcset = img.get_attribute("srcset")
                            if srcset:
                                parts = [
                                    p.strip().split()[0]
                                    for p in srcset.split(",")
                                    if p.strip()
                                ]
                                if parts:
                                    src = parts[-1]
                        if src and not src.startswith("data:"):
                            full_url = urllib.parse.urljoin(base_url, src)
                            cleaned = self._clean_image_url(full_url)
                            if cleaned:
                                extracted.append(cleaned)
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
                        if tag == "img":
                            src = (
                                el.get_attribute("src")
                                or el.get_attribute("data-src")
                                or el.get_attribute("data-original")
                                or el.get_attribute("data-lazy-src")
                            )
                        elif tag == "a":
                            src = el.get_attribute("href")
                        else:
                            nested = el.find_elements(By.TAG_NAME, "img")
                            if nested:
                                src = (
                                    nested[0].get_attribute("src")
                                    or nested[0].get_attribute("data-src")
                                    or nested[0].get_attribute("data-original")
                                )
                            else:
                                src = el.get_attribute("src") or el.get_attribute("href")

                        if src and not src.startswith("data:"):
                            full_url = urllib.parse.urljoin(base_url, src)
                            cleaned = self._clean_image_url(full_url)
                            if cleaned:
                                extracted.append(cleaned)
                    except Exception:
                        continue

            elif atype == "Find <img> Number X on Page" and param:
                with contextlib.suppress(Exception):
                    idx = int(param) - 1
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    if 0 <= idx < len(imgs):
                        img = imgs[idx]
                        src = (
                            img.get_attribute("src")
                            or img.get_attribute("data-src")
                            or img.get_attribute("data-original")
                        )
                        if src and not src.startswith("data:"):
                            full_url = urllib.parse.urljoin(base_url, src)
                            cleaned = self._clean_image_url(full_url)
                            if cleaned:
                                extracted.append(cleaned)

            elif atype == "Download Image from Element":
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    try:
                        src = img.get_attribute("src") or img.get_attribute("data-src")
                        if src and not src.startswith("data:"):
                            full_url = urllib.parse.urljoin(base_url, src)
                            cleaned = self._clean_image_url(full_url)
                            if cleaned:
                                extracted.append(cleaned)
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
                    src = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-original")
                        or img.get_attribute("data-lazy-src")
                    )
                    if src and not src.startswith("data:"):
                        full_url = urllib.parse.urljoin(base_url, src)
                        cleaned = self._clean_image_url(full_url)
                        if cleaned:
                            extracted.append(cleaned)
                except Exception:
                    continue

        return extracted

    def _process_requests_page(self, session, page_url, headers) -> list[str]:
        """Fetch and parse images via HTTP request fallback."""
        extracted = []
        try:
            resp = session.get(page_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            for img in soup.find_all("img"):
                src = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-original")
                    or img.get("data-lazy-src")
                )
                if src and not src.startswith("data:"):
                    full_url = urllib.parse.urljoin(page_url, src)
                    cleaned = self._clean_image_url(full_url)
                    if cleaned:
                        extracted.append(cleaned)

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
        self, session, img_url, download_dir, headers
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

            resp = session.get(img_url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return None

            c_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" in c_type or "text/plain" in c_type or "application/xhtml" in c_type:
                return None

            content = resp.content
            if len(content) < 100:
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
