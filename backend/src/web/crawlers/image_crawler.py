import contextlib
import json
import os
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from PySide6.QtCore import QObject, Signal


class ImageCrawler(QObject):
    """
    Advanced Python Image Crawler supporting Action Sequences, URL replacements,
    and Selenium / requests fallback parsing for general web scraping.
    """

    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def on_status_emitted(self, msg: str):
        self.on_status.emit(msg)

    def on_error_emitted(self, msg: str):
        self.on_status.emit(f"ERROR: {msg}")

    def run(self) -> int:  # noqa: C901
        download_dir = self.config.get("download_dir", "downloads")
        os.makedirs(download_dir, exist_ok=True)

        selection_mode = self.config.get("selection_mode", "Download All (Default)")
        self.on_status.emit(f"🌐 Crawl starting with selection mode: {selection_mode}")

        base_url = self.config.get("url", "").strip()
        if not base_url:
            self.on_status.emit("❌ Error: No target URL specified.")
            return 0

        replace_str = self.config.get("replace_str")
        replacements = self.config.get("replacements")

        target_urls = [base_url]
        if replace_str and replacements:
            if isinstance(replacements, str):
                replacements = [r.strip() for r in replacements.split(",") if r.strip()]
            for r in replacements:
                new_url = base_url.replace(replace_str, r)
                if new_url not in target_urls:
                    target_urls.append(new_url)

        self.on_status.emit(f"🌐 Target pages queued: {len(target_urls)}")

        skip_first = int(self.config.get("skip_first", 0) or 0)
        skip_last = int(self.config.get("skip_last", 0) or 0)

        actions = self.config.get("actions", [])
        driver = self._try_init_driver()

        downloaded_count = 0
        session = requests.Session()
        session_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            for page_idx, target_url in enumerate(target_urls):
                if not self._is_running:
                    self.on_status.emit("🛑 Crawl cancelled by user.")
                    break

                self.on_status.emit(
                    f"🌐 Page {page_idx + 1}/{len(target_urls)}: Navigating to {target_url}"
                )

                extracted_urls = []

                if driver:
                    try:
                        driver.get(target_url)
                        time.sleep(2)
                        parsed_urls = self._process_selenium_actions(
                            driver, actions, target_url
                        )
                        extracted_urls.extend(parsed_urls)
                    except Exception as e:
                        self.on_status.emit(
                            f"⚠️ Selenium navigation error: {e}. Falling back to HTTP parser..."
                        )
                        extracted_urls.extend(
                            self._process_requests_page(session, target_url, session_headers)
                        )
                else:
                    extracted_urls.extend(
                        self._process_requests_page(session, target_url, session_headers)
                    )

                # Deduplicate while preserving order
                seen = set()
                unique_urls = []
                for u in extracted_urls:
                    if u not in seen:
                        seen.add(u)
                        unique_urls.append(u)

                # Slice skip_first and skip_last
                if skip_first > 0:
                    unique_urls = unique_urls[skip_first:]
                if skip_last > 0 and len(unique_urls) > skip_last:
                    unique_urls = unique_urls[:-skip_last]

                self.on_status.emit(
                    f"📷 Found {len(unique_urls)} downloadable image(s) on page {page_idx + 1}."
                )

                # Download images
                host = urllib.parse.urlparse(target_url).netloc
                download_headers = dict(session_headers)
                download_headers["Referer"] = f"https://{host}/"

                for img_idx, img_url in enumerate(unique_urls, start=1):
                    if not self._is_running:
                        break

                    saved_path = self._download_single_image(
                        session, img_url, download_dir, download_headers
                    )
                    if saved_path:
                        downloaded_count += 1
                        pos_on_page = (skip_first if skip_first > 0 else 0) + img_idx
                        meta = {
                            "path": saved_path,
                            "page_url": target_url,
                            "page_num": page_idx + 1,
                            "index_on_page": pos_on_page,
                            "global_id": downloaded_count,
                            "img_url": img_url,
                        }
                        self.on_image_saved.emit(json.dumps(meta))
                        self.on_status.emit(
                            f"✅ Saved [{downloaded_count}] (Page {page_idx + 1} #{pos_on_page}): {os.path.basename(saved_path)}"
                        )

                    time.sleep(0.1)

        finally:
            if driver:
                with contextlib.suppress(Exception):
                    driver.quit()

        message = f"Crawl finished. Downloaded **{downloaded_count}** image(s)!"
        self.on_status.emit(message)
        self.on_finished.emit(message)
        return downloaded_count

    def _try_init_driver(self):
        """Try connecting to Remote Selenium WebDriver or local Chrome driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            if self.config.get("headless", False):
                options.add_argument("--headless=new")

            # Try Remote WebDriver at port 9515 first (managed by manage_webdriver.py)
            try:
                driver = webdriver.Remote(
                    command_executor="http://localhost:9515", options=options
                )
                self.on_status.emit("🌐 Connected to Managed WebDriver service (port 9515).")
                return driver
            except Exception:
                pass

            # Fallback to direct Chrome launch
            driver = webdriver.Chrome(options=options)
            self.on_status.emit("🌐 Initialized local ChromeDriver session.")
            return driver

        except Exception as e:
            self.on_status.emit(
                f"ℹ️ WebDriver not connected ({e}). Using high-performance HTTP crawler."
            )
            return None

    def _process_selenium_actions(self, driver, actions, base_url) -> list[str]:
        """Execute configured actions on Selenium driver."""
        from selenium.webdriver.common.by import By

        extracted = []
        for act in actions:
            atype = act.get("type", "")
            param = act.get("param")

            if atype == "Wait for Gallery (Context Reset)":
                driver.execute_script("window.scrollBy(0, 1500);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, 0);")
            elif atype == "Wait X Seconds" and param:
                time.sleep(float(param))
            elif atype == "Extract High-Res Preview URL":
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

        if not extracted:
            # Default extraction if actions list did not collect URLs
            imgs = driver.find_elements(By.TAG_NAME, "img")
            for img in imgs:
                try:
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
            self.on_status.emit(f"⚠️ HTTP request error for {page_url}: {e}")

        return extracted

    def _clean_image_url(self, url: str) -> str | None:
        """Filter out non-image files and strip proxy wrappers."""
        if not url or url.startswith("data:") or ".svg" in url.lower():
            return None

        # Strip Jetpack/WordPress image proxies (i0.wp.com, i1.wp.com, etc.)
        url = re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", url)

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()

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

            # Skip if already exists
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                return out_path

            resp = session.get(img_url, headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 3000:
                with open(out_path, "wb") as f:
                    f.write(resp.content)
                return out_path

        except Exception as e:
            self.on_status.emit(f"⚠️ Download failed for {img_url}: {e}")

        return None
