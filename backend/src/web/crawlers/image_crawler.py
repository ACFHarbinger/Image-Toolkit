"""Image crawler orchestrator: config/lifecycle + the main run() loop.

Browser setup, login, and scraping/download logic live in
``image_crawler_parts/`` as mixins -- see that package's modules for the
per-concern methods ``run()`` calls on ``self``.
"""

import contextlib
import json
import os
import threading
import time

import requests

from backend.src.events import Observable

from .image_crawler_parts._browser_setup import _BrowserSetupMixin
from .image_crawler_parts._login import _LoginMixin
from .image_crawler_parts._scraping import _ScrapingMixin


class ImageCrawler(_BrowserSetupMixin, _LoginMixin, _ScrapingMixin):
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
                f"Crawl stopped: no existing browser session is available on localhost:{self.config.get('debug_port', 9223)}. "
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

