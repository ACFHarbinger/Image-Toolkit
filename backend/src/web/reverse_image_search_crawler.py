import os
import time

from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException
from src.web.crawler import WebCrawler


class ReverseImageSearchCrawler(WebCrawler):
    """
    A specialized crawler that performs reverse image searches using Google Lens
    via Selenium. It includes logic to detect if the user closes the browser manually.
    """

    def __init__(
        self, headless=True, download_dir=None, screenshot_dir=None, browser="brave"
    ):
        super().__init__(
            headless=headless,
            download_dir=download_dir,
            screenshot_dir=screenshot_dir,
            browser=browser,
        )
        self.results: List[Dict[str, str]] = []

    def _is_browser_open(self) -> bool:
        """Checks if the browser window is still open."""
        try:
            # If window_handles is empty or raises an error, the browser is closed
            if not self.driver.window_handles:
                return False
            return True
        except Exception:
            return False

    def _wait_and_check_browser(self, seconds: int) -> bool:
        """
        Waits for a specified duration, checking every second if the browser is still open.
        Returns False if the browser was closed, True if the wait completed successfully.
        """
        for _ in range(int(seconds)):
            if not self._is_browser_open():
                print("⚠️ Browser closed by user. Stopping search.")
                return False
            time.sleep(1)
        return True

    def login(self, credentials):
        """Not required for public Google search."""
        pass

    def process_data(self):
        """Not used directly; we use perform_reverse_search."""
        pass

    def perform_reverse_search(
        self,
        image_path: str,
        min_width: int = 0,
        min_height: int = 0,
        search_mode: str = "All",
    ) -> List[Dict[str, str]]:
        self.results = []

        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            return []

        try:
            # 1. Navigate
            self.navigate_to_url("https://images.google.com/?hl=en")

            # Consent (EU)
            try:
                if not self._is_browser_open():
                    return []
                consent_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//button[contains(text(), 'Accept all') or contains(text(), 'Reject all')]",
                )
                if not consent_buttons:
                    consent_buttons = self.driver.find_elements(
                        By.XPATH, "//div[text()='Reject all']//ancestor::button"
                    )
                if consent_buttons:
                    consent_buttons[0].click()
                    if not self._wait_and_check_browser(1):
                        return []
            except Exception:
                pass

            # 2. Click Camera Icon
            try:
                if not self._is_browser_open():
                    return []
                selectors = [
                    (By.CSS_SELECTOR, "svg.Gdd5U"),
                    (By.XPATH, "//*[name()='svg' and @viewBox='0 -960 960 960']"),
                    (By.CSS_SELECTOR, "div[aria-label='Search by image']"),
                    (By.CSS_SELECTOR, "span[aria-label='Search by image']"),
                    (By.CSS_SELECTOR, "div.nDCdf"),
                    (
                        By.XPATH,
                        "//div[@role='button'][descendant::img[contains(@src, 'google_lens') or contains(@src, 'camera')]]",
                    ),
                ]

                camera_btn = None
                for by_method, selector in selectors:
                    try:
                        camera_btn = self.wait.until(
                            EC.element_to_be_clickable((by_method, selector))
                        )
                        if camera_btn:
                            camera_btn.click()
                            break
                    except Exception:
                        continue

                if not camera_btn:
                    # Fallback click parent
                    svg_element = self.driver.find_element(By.CSS_SELECTOR, "svg.Gdd5U")
                    svg_element.find_element(By.XPATH, "./..").click()

            except Exception as e:
                print(f"❌ Failed to find camera icon: {e}")
                return []

            # 3. Upload Image
            try:
                time.sleep(1.5)  # Wait for animation
                file_input = self.driver.find_element(
                    By.CSS_SELECTOR, "input[type='file'][name='encoded_image']"
                )
                file_input.send_keys(image_path)
            except Exception as e:
                if not self._is_browser_open():
                    return []
                print(f"❌ Failed to find file input: {e}")
                return []

            # --- CAPTCHA / RESULTS WAIT BLOCK (MODIFIED) ---

            # Wait 10s for the initial redirect to complete
            print("⏳ Analyzing image. Waiting 10s for page redirect...")
            if not self._wait_and_check_browser(10):
                return []

            # Use WebDriverWait (up to 50s) to wait for the results element to appear.
            # This allows the script to proceed immediately after the CAPTCHA is solved.
            print(
                "⚠️ CAPTCHA CHECK: Waiting up to 50 seconds for results/CAPTCHA solution."
            )
            try:
                # We wait for div[data-ved] img, which is present once the results page loads.
                WebDriverWait(self.driver, 50).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-ved] img")
                    )
                )
                print("✅ Results detected. Continuing search.")
            except TimeoutException:
                # If the wait times out, assume the user failed to solve the CAPTCHA or closed the window.
                if not self._is_browser_open():
                    return []
                print(
                    "⚠️ Timed out waiting for results. Proceeding anyway, but search may fail."
                )

            # --- END CAPTCHA WAIT BLOCK ---

            if not self._is_browser_open():
                return []

            # 4. HANDLE SEARCH MODE NAVIGATION
            SEARCH_WAIT_TIME = 10

            # --- Common selector for both modes ---
            span_base_selector = (
                "//span[@class='R1QWuf' and contains(text(), '{mode}')]"
            )

            if search_mode == "Visual matches":
                print("🔎 Switching to 'Visual matches'...")
                try:
                    # Look for the 'Find image source' button first (the standard way)
                    find_source_btn = WebDriverWait(
                        self.driver, SEARCH_WAIT_TIME
                    ).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//a[contains(text(), 'Find image source')]")
                        )
                    )
                    find_source_btn.click()
                    if not self._wait_and_check_browser(2):
                        return []
                except Exception:
                    # Fallback to direct span click if 'Find image source' is skipped/already done
                    try:
                        visual_span_xpath = span_base_selector.format(
                            mode="Visual matches"
                        )
                        visual_span = WebDriverWait(
                            self.driver, SEARCH_WAIT_TIME
                        ).until(
                            EC.element_to_be_clickable((By.XPATH, visual_span_xpath))
                        )
                        visual_span.click()
                        if not self._wait_and_check_browser(3):
                            return []
                    except Exception as e:
                        print(f"Could not click 'Visual matches' span: {e}")

            elif search_mode == "Exact matches":
                print("🔎 Switching to 'Exact matches'...")

                # 4a. Navigate to the source tab if necessary (via 'Find image source')
                try:
                    find_source_btn = WebDriverWait(
                        self.driver, SEARCH_WAIT_TIME
                    ).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//a[contains(text(), 'Find image source')]")
                        )
                    )
                    find_source_btn.click()
                    if not self._wait_and_check_browser(2):
                        return []
                except Exception:
                    pass

                # 4b. Now look for the "Exact matches" span and click it
                try:
                    # Target the specific span element you provided
                    exact_span_xpath = span_base_selector.format(mode="Exact matches")

                    exact_span = WebDriverWait(self.driver, SEARCH_WAIT_TIME).until(
                        EC.element_to_be_clickable((By.XPATH, exact_span_xpath))
                    )
                    exact_span.click()
                    if not self._wait_and_check_browser(3):
                        return []
                except Exception as e:
                    print(f"Could not find or click 'Exact matches' span: {e}")

            if not self._is_browser_open():
                return []

            # 5. Scrape Results
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "div[data-ved] img")
            potential_links = self.driver.find_elements(
                By.XPATH, "//a[contains(@href, 'http')]"
            )

            print(f"🔍 Scanning {len(potential_links)} potential links...")

            found_urls = set()

            for link_elem in potential_links:
                # Basic check inside loop in case browser closes mid-scrape
                try:
                    href = link_elem.get_attribute("href")
                except WebDriverException:
                    return []

                if not href or "google.com" in href or "googleusercontent" in href:
                    continue

                if href in found_urls:
                    continue

                is_direct_image = any(
                    href.lower().endswith(ext)
                    for ext in [".jpg", ".jpeg", ".png", ".webp"]
                )

                resolution_text = ""
                try:
                    parent = link_elem.find_element(By.XPATH, "./..")
                    resolution_text = parent.text
                except:
                    pass

                width, height = 0, 0
                if " x " in resolution_text:
                    try:
                        parts = resolution_text.split(" x ")
                        w_str = "".join(filter(str.isdigit, parts[0]))
                        h_str = "".join(filter(str.isdigit, parts[1].split()[0]))
                        width = int(w_str)
                        height = int(h_str)
                    except:
                        pass

                if min_width > 0 and width < min_width:
                    continue
                if min_height > 0 and height < min_height:
                    continue

                found_urls.add(href)
                self.results.append(
                    {
                        "url": href,
                        "resolution": f"{width}x{height}" if width > 0 else "Unknown",
                        "title": link_elem.get_attribute("title") or "Result",
                        "is_direct": is_direct_image,
                    }
                )

                if len(self.results) >= 20:
                    break

            return self.results

        except Exception as e:
            # Suppress errors if they are caused by closing the browser
            if (
                "chrome not reachable" in str(e)
                or "no such window" in str(e)
                or not self._is_browser_open()
            ):
                print("Browser closed.")
                return []
            print(f"❌ Error during reverse search: {e}")
            return []

    def close(self):
        super().close()
