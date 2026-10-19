"""Page scraping, image fetch/download, and Selenium action-sequence execution for ImageCrawler."""

import base64
import contextlib
import os
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup


class _ScrapingMixin:
    """Scraping/download methods for ``ImageCrawler``."""

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
