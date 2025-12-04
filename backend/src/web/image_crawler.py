import os
import time
import json
import requests

from urllib.parse import urlparse, urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from PySide6.QtCore import QObject, Signal
from .crawler import WebCrawler


class QtABCMeta(type(QObject), type(WebCrawler)):
    """Combines Qt's QObject metaclass with ABC's metaclass."""

    pass


class ImageCrawler(WebCrawler, QObject, metaclass=QtABCMeta):
    """Downloads all images from one or more webpages with live Qt signals."""

    # === SIGNALS ===
    on_status = Signal(str)  # status message
    on_image_saved = Signal(str)  # saved file path

    def __init__(self, config: dict):
        QObject.__init__(self)
        WebCrawler.__init__(
            self,
            headless=config.get("headless", False),
            download_dir=config.get("download_dir"),
            screenshot_dir=config.get("screenshot_dir"),
            browser=config.get("browser", "brave"),
        )

        self.target_url = config.get("url")
        self.skip_first = config.get("skip_first", 0)
        self.skip_last = config.get("skip_last", 0)

        # --- NEW: Login Configuration ---
        self.login_config = config.get("login_config", {})
        # --- END NEW ---

        # --- Replacement logic ---
        self.replace_str = config.get("replace_str")
        self.replacements = config.get("replacements")

        # --- Action Sequence ---
        self.actions = config.get("actions", [])
        if not self.actions:
            self.actions = [
                {"type": "Download Simple Thumbnail (Legacy)", "param": None}
            ]

        self.urls_to_scrape = [self.target_url]
        if self.replace_str and self.replacements:
            for rep in self.replacements:
                new_url = self.target_url.replace(self.replace_str, rep)
                self.urls_to_scrape.append(new_url)

        self.total_pages = len(self.urls_to_scrape)
        self.current_page_index = 0

        # --- Tracks the last selector used for Find/Scrape, to allow refreshing ---
        self._last_selector = None
        # --- END NEW ---

        print(f"ImageCrawler ready: {self.total_pages} pages to scrape.")

    def login(self):
        """
        Performs a pre-crawl login sequence if credentials and URL are provided.
        """
        login_url = self.login_config.get("url")
        username = self.login_config.get("username")
        password = self.login_config.get("password")

        if not (login_url and username and password):
            self.on_status.emit(
                "No login configuration provided. Skipping authentication."
            )
            return True

        self.on_status.emit(f"Starting login sequence to: {login_url}")

        # 1. Navigate to the login page
        if not self.navigate_to_url(login_url, take_screenshot=False):
            self.on_status.emit("Failed to load login page.")
            return False

        self.wait_for_page_to_load(timeout=10)

        try:
            # 2. Locate and fill the username/password fields

            # --- Attempt to find and fill Username/Email field ---
            user_field = None
            try:
                # Common selectors for username/email fields
                user_field = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "input[name*='user'], input[name*='email'], input[id*='user'], input[id*='email'], input[id*='login']",
                )
            except NoSuchElementException:
                self.on_status.emit(
                    "Warning: Could not locate standard username/email field."
                )

            if user_field:
                user_field.send_keys(username)
                self.on_status.emit("Entered username.")

            # --- Attempt to find and fill Password field ---
            pass_field = None
            try:
                # Common selectors for password fields
                pass_field = self.driver.find_element(
                    By.CSS_SELECTOR, "input[name*='pass'], input[id*='pass']"
                )
            except NoSuchElementException:
                self.on_status.emit(
                    "Warning: Could not locate standard password field."
                )

            if pass_field:
                pass_field.send_keys(password)
                self.on_status.emit("Entered password.")

            # 3. Locate and click the submit button
            # --- MODIFIED LOCATOR: Targets button/input with value/text 'Log in' ---
            submit_button_xpath = "//input[@type='submit' and @value='Log in'] | //button[text()='Log in'] | //button[contains(text(), 'Log in')]"

            submit_button = self.driver.find_element(By.XPATH, submit_button_xpath)

            self.on_status.emit("Found and clicking the specific 'Log in' button...")
            submit_button.click()

            # Short wait to ensure the POST request is initiated
            time.sleep(1)
            # --------------------------------------------------------------------------

            self.on_status.emit("Submitted login form. Waiting for redirect...")

            # 4. Wait for redirection to complete
            self.wait_for_page_to_load(timeout=15)

            # 5. Simple verification: Did we stay on the login page?
            if login_url in self.driver.current_url:
                self.on_status.emit("Login failed: Still on the login page.")
                return False

            self.on_status.emit("**Login Successful!**")
            return True

        except TimeoutException:
            self.on_status.emit("Login timed out during submission/redirect.")
            return False
        except Exception as e:
            self.on_status.emit(f"Login failed unexpectedly: {e}")
            return False

    def get_unique_filename(self, filepath):
        """Returns a unique filename like: cat.jpg → cat (1).jpg"""
        base, ext = os.path.splitext(filepath)
        counter = 1
        new_path = filepath
        while os.path.exists(new_path):
            new_path = f"{base} ({counter}){ext}"
            counter += 1
        return new_path

    def wait_for_image_element(self, by, value, timeout=20):
        """Waits until at least one element matching the criteria is present."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException as e:
            # Handle selenium timeout exceptions separately
            print(f"Wait for image element timed out: {e}")
            return False
        except Exception as e:
            print(f"Wait for image element failed: {e}")
            return False

    def process_data(self, url: str) -> int:
        """
        Processes a single URL, finds images, and runs the action
        sequence for each one.
        Returns the count of successfully downloaded images.
        """
        self.on_status.emit(
            f"Loading page {self.current_page_index + 1}/{self.total_pages}: {url}"
        )
        if not self.navigate_to_url(url, take_screenshot=False):
            self.on_status.emit(f"Failed to load page: {url}")
            return 0

        self.wait_for_page_to_load(timeout=10)

        self.on_status.emit("Waiting for image elements to appear...")
        # Target a common gallery image element or link
        if not self.wait_for_image_element(By.TAG_NAME, "img", timeout=20):
            self.on_status.emit(
                "Timed out waiting for image gallery to load. Exiting process_data."
            )
            return 0

        self.on_status.emit("Scanning for images...")

        try:
            # Re-locate ALL image elements to get the latest count
            images = self.driver.find_elements(By.TAG_NAME, "img")
            total_found = len(images)

            start_index = self.skip_first
            end_index = total_found - self.skip_last

            # --- CRITICAL FIX START: Iterate over the indices, not the elements ---

            # The indices we actually need to process
            indices_to_process = range(start_index, end_index)
            total_to_process = len(indices_to_process)

            if total_to_process <= 0:
                self.on_status.emit(
                    f"Found {total_found} images, but 0 left to process after skipping."
                )
                return 0

            self.on_status.emit(
                f"Found {total_found} images. Processing {total_to_process}..."
            )

            download_count = 0
            original_tab = self.driver.current_window_handle

            # Iterate over the valid indices
            for i, global_index in enumerate(indices_to_process):
                if self.driver is None:
                    return download_count

                self.on_status.emit(
                    f"Page {self.current_page_index + 1}: Processing image {i + 1}/{total_to_process} (Index: {global_index})..."
                )

                try:
                    # RE-LOCATE THE ELEMENT JUST BEFORE USE
                    # Find ALL <img> tags again and select the one at global_index
                    images_on_page = self.driver.find_elements(By.TAG_NAME, "img")

                    if global_index >= len(images_on_page):
                        self.on_status.emit(
                            f"Index {global_index} out of range after re-locating. Stopping."
                        )
                        break

                    image_element = images_on_page[global_index]

                    # Pass the FRESH element reference to the sequence
                    downloaded = self.run_action_sequence(image_element, original_tab)

                    if downloaded:
                        download_count += 1

                except Exception as e:
                    # Catch all exceptions during image processing cycle
                    print(f"Failed image cycle for image {i+1}: {e}")
                    self.on_status.emit(
                        f"Failed to process image {i+1} due to error, skipping. Check console."
                    )

                finally:
                    # --- MODIFIED: Rely on user-defined actions for explicit tab closure ---
                    # We only ensure we switch back if we are not on the original tab
                    if (
                        self.driver
                        and self.driver.current_window_handle != original_tab
                    ):
                        self.driver.switch_to.window(original_tab)
                    # --- END MODIFIED ---
                    time.sleep(0.1)

            return download_count
            # --- CRITICAL FIX END ---

        except Exception as e:
            self.on_status.emit(f"Error on page {url}: {e}")
            return 0

    def cleanup_tabs(self, original_tab):
        """
        MODIFIED: No longer closes extra tabs automatically.
        Only ensures we return to the original_tab if needed.
        """
        try:
            if self.driver is None:
                return

            # Just ensure we are back on the original tab if multiple are open
            if (
                len(self.driver.window_handles) > 1
                and self.driver.current_window_handle != original_tab
            ):
                self.driver.switch_to.window(original_tab)
                self.on_status.emit("Returned to original gallery tab.")

        except Exception as e:
            print(f"Error managing tabs: {e}")

    def _save_scraped_data_to_json(self, base_filename, scraped_data: dict) -> bool:
        """Saves scraped metadata to a JSON file."""
        if not scraped_data:
            return False

        # Create a .json file with the same name as the base_filename (image.jpg -> image.json)
        # This guarantees the JSON name matches the final, unique image name.
        json_path = os.path.splitext(base_filename)[0] + ".json"

        # --- Logic for handling metadata-only scrape (when base_filename is already a timestamped .json) ---
        if not os.path.exists(json_path) and "metadata_" in os.path.basename(json_path):
            # This means an image was NOT downloaded, and the base_filename is temporary/timestamped
            json_path = self.get_unique_filename(json_path)
            scraped_data["source_url"] = self.driver.current_url

        # If the file exists, it means we are updating existing metadata (usually after a download)
        elif os.path.exists(json_path):
            # Load existing data, update with new data, and save
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_data.update(scraped_data)
                scraped_data = existing_data
            except Exception as e:
                self.on_status.emit(
                    f"Warning: Failed to load existing metadata, overwriting: {e}"
                )

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            # LOG MODIFICATION: Confirm the saved file name
            self.on_status.emit(
                f"Saved metadata to match: {os.path.basename(json_path)}"
            )
            return True
        except Exception as e:
            self.on_status.emit(f"Failed to save metadata: {e}")
            print(f"Failed to save metadata for {json_path}: {e}")
            return False

    def run_action_sequence(self, element, original_tab) -> bool:
        """
        Runs the defined action list for a single target element.
        Returns True if a download was successful, False otherwise.
        """
        current_element = element
        downloaded = False
        scraped_data = {}  # <-- Initialized once per image sequence

        for action in self.actions:
            if self.driver is None:
                return downloaded

            action_type = action["type"]
            param = action["param"]

            self.on_status.emit(f"Action: {action_type}...")

            try:
                if action_type == "Find Parent Link (<a>)":
                    current_element = current_element.find_element(
                        By.XPATH, "./ancestor::a"
                    )

                elif action_type == "Download Simple Thumbnail (Legacy)":
                    url = element.get_attribute("src")
                    if not url:
                        self.on_status.emit(
                            "Download failed: No src found on original element."
                        )
                    else:
                        downloaded = self._download_image_from_url(
                            url, scraped_data
                        )  # <-- PASS DATA

                elif action_type == "Wait for Gallery (Context Reset)":
                    if not self.wait_for_image_element(By.TAG_NAME, "img", timeout=30):
                        self.on_status.emit(
                            "Wait failed: Timed out waiting for gallery to resume."
                        )
                        return downloaded
                    self.on_status.emit("Gallery context confirmed.")

                # --- Actions that modify browser state ---
                elif action_type == "Open Link in New Tab":
                    href = current_element.get_attribute("href")
                    if not href:
                        raise NoSuchElementException(
                            "Action 'Open Link': No href found on current element."
                        )
                    self.driver.execute_script(
                        "window.open(arguments[0], '_blank');", href
                    )
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.wait_for_page_to_load(timeout=5)

                # --- MODIFIED ACTION: Close Current Tab (Now Saves JSON) ---
                elif action_type == "Close Current Tab":
                    # Check if we are closing the original tab
                    if self.driver.current_window_handle == original_tab:
                        self.on_status.emit(
                            "Warning: Cannot close the original gallery tab."
                        )
                        continue

                    # 1. Save JSON data before closing if data was scraped
                    if scraped_data:
                        # Use a timestamp-based filename since no image was downloaded yet
                        base_filename = os.path.join(
                            self.download_dir,
                            f"metadata_{int(time.time() * 1000)}.json",
                        )
                        self._save_scraped_data_to_json(base_filename, scraped_data)

                    # 2. Close the tab and switch back
                    self.driver.close()
                    self.driver.switch_to.window(original_tab)
                    self.on_status.emit(
                        "Closed current tab and switched back to the gallery."
                    )
                # --- END MODIFIED ACTION ---

                elif action_type == "Extract High-Res Preview URL":
                    current_element.click()
                    self.wait_for_page_to_load(timeout=5)
                    self.on_status.emit("Clicked element and navigating to new page...")

                elif action_type == "Click Element by Text":
                    if not param:
                        raise ValueError(
                            "Action 'Click Element': Missing text parameter."
                        )
                    el = self.driver.find_element(By.PARTIAL_LINK_TEXT, param)
                    el.click()

                elif action_type == "Wait for Page Load":
                    self.wait_for_page_to_load(timeout=5)

                elif action_type == "Wait X Seconds":
                    if not isinstance(param, (int, float)) or param < 0:
                        raise ValueError(
                            f"Action 'Wait X Seconds': Invalid parameter: {param}"
                        )
                    self.on_status.emit(f"Waiting for {param} seconds...")
                    time.sleep(param)

                elif action_type == "Switch to Last Tab":
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                # --- NEW ACTION: Refresh Current Element ---
                elif action_type == "Refresh Current Element":
                    if not self._last_selector:
                        self.on_status.emit(
                            "Warning: Cannot refresh element; no selector stored from prior action."
                        )
                        continue

                    # Re-locate the element using the stored selector
                    current_element = self.driver.find_element(
                        By.CSS_SELECTOR, self._last_selector
                    )
                    self.on_status.emit(
                        "Refreshed element context to prevent staleness."
                    )
                # --- END NEW ACTION ---

                # --- NEW ACTION: Scan Page for Text & Skip ---
                elif action_type == "Scan Page for Text and Skip if Found":
                    if not param:
                        raise ValueError(
                            "Action 'Scan Page for Text': Missing text parameter."
                        )

                    keyword = param.lower()
                    page_text = self.driver.find_element(
                        By.TAG_NAME, "body"
                    ).text.lower()

                    if keyword in page_text:
                        self.on_status.emit(
                            f"Found keyword '{param}'. Skipping this image and closing tab..."
                        )

                        # Clean up tab if needed
                        if self.driver.current_window_handle != original_tab:
                            self.driver.close()
                            self.driver.switch_to.window(original_tab)
                            self.on_status.emit("Closed tab and returned to gallery.")

                        return (
                            downloaded  # Stop sequence, return current status (False)
                        )
                    else:
                        self.on_status.emit(
                            f"Keyword '{param}' not found. Continuing..."
                        )
                # --- END NEW ACTION ---

                # --- Actions that find elements ---
                elif action_type == "Find <img> Number X on Page":
                    if not isinstance(param, int) or param < 1:
                        raise ValueError(
                            f"Action 'Find <img> Number X': Invalid parameter: {param}"
                        )

                    xpath_query = f"//img[{param}]"
                    current_element = self.driver.find_element(By.XPATH, xpath_query)

                elif action_type == "Find Element by CSS Selector":
                    if not param:
                        raise ValueError(
                            "Action 'Find Element by CSS Selector': Missing selector parameter."
                        )
                    # Store the selector before finding the element
                    self._last_selector = param
                    current_element = self.driver.find_element(By.CSS_SELECTOR, param)

                elif action_type == "Scrape Text (Saves to JSON)":
                    if not param or ":" not in param:
                        raise ValueError(
                            "Action 'Scrape Text': Parameter must be in 'key_name:css_selector' format."
                        )

                    try:
                        json_key, selector_raw = param.split(":", 1)
                        json_key = json_key.strip()
                        selector_raw = selector_raw.strip()

                        if not json_key or not selector_raw:
                            raise ValueError("Invalid format.")

                    except ValueError:
                        raise ValueError(
                            f"Action 'Scrape Text': Invalid parameter format: '{param}'. Must be 'key_name:css_selector'."
                        )

                    # --- LOGIC: Use find_elements if the selector is complex (contains spaces or brackets) ---

                    if (
                        " " in selector_raw
                        or ">" in selector_raw
                        or "[" in selector_raw
                    ):
                        # Case 2: Multi-element scrape (e.g., '.tag-list li a[href*="post"]')

                        # Find all matching elements in the document
                        child_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, selector_raw
                        )

                        # Extract text from all children and store as a LIST of strings
                        extracted_list = [
                            el.text.strip() for el in child_elements if el.text.strip()
                        ]

                        # The element to chain to is the body, but for visual context, we use the first matching element if available
                        element_to_chain = (
                            child_elements[0]
                            if child_elements
                            else self.driver.find_element(By.TAG_NAME, "body")
                        )

                        extracted_text_display = f"[{len(extracted_list)} items]"

                    else:
                        # Case 1: Single element scrape (Original behavior for simple ID/Class names)
                        element_to_chain = self.driver.find_element(
                            By.CSS_SELECTOR, selector_raw
                        )
                        extracted_text = element_to_chain.text.strip()
                        extracted_list = extracted_text  # Still treat as a single item for storage if not complex
                        extracted_text_display = (
                            extracted_text[:100] if extracted_text else "<Empty Result>"
                        )

                    # --- END LOGIC ---

                    # 3. Store in the dictionary (Stores LIST of strings for complex selectors)
                    scraped_data[json_key] = extracted_list

                    # 4. Emit to log
                    if extracted_list:
                        self.on_status.emit(
                            f"SCRAPED: {json_key} = {extracted_text_display}"
                        )
                    else:
                        self.on_status.emit(f"SCRAPED: {json_key} = <Empty Result>")

                    current_element = (
                        element_to_chain  # Use the consistently defined variable
                    )

                # --- Download Actions (No longer return, allowing sequence continuation) ---
                elif action_type == "Download Image from Element":
                    url = current_element.get_attribute(
                        "src"
                    ) or current_element.get_attribute("href")
                    if not url:
                        self.on_status.emit(
                            "Download failed: No src/href found on current element."
                        )
                    else:
                        downloaded = self._download_image_from_url(url, scraped_data)

                elif action_type == "Download Current URL as Image":
                    url = self.driver.current_url
                    if not any(
                        url.lower().endswith(ext)
                        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]
                    ):
                        self.on_status.emit(
                            f"Download failed: Current URL doesn't look like an image: {url}"
                        )
                    else:
                        downloaded = self._download_image_from_url(url, scraped_data)

                elif action_type == "Extract Element Text by CSS Selector":
                    if not param:
                        raise ValueError(
                            "Action 'Extract Element Text by CSS Selector': Missing selector parameter."
                        )

                    text_element = self.driver.find_element(By.CSS_SELECTOR, param)
                    extracted_text = text_element.text.strip()

                    if extracted_text:
                        self.on_status.emit(f"SCRAPED TEXT: {extracted_text}")
                    else:
                        self.on_status.emit(f"SCRAPED TEXT: <Empty Result>")

                    current_element = text_element

            except (NoSuchElementException, StaleElementReferenceException) as e:
                # Non-critical failure: Log and continue to the next action
                self.on_status.emit(
                    f"Action '{action_type}' failed (Element not found/stale). Skipping to next action."
                )
                print(f"Non-critical Failure in sequence: {action_type} - {e}")
                continue

            except (TimeoutException, ValueError, Exception) as e:
                # Critical failure: Log and stop the sequence for this image
                self.on_status.emit(
                    f"Action '{action_type}' failed critically. Stopping sequence for this image."
                )
                print(f"Critical Failure in sequence: {action_type} - {e}")
                return downloaded

        return downloaded

    def run(self):
        total_downloaded = 0
        try:
            # --- MODIFIED: Login attempt occurs before the crawl loop starts ---
            if not self.login():
                self.on_status.emit("Pre-crawl login failed. Stopping crawl.")
                return
            # --- END MODIFIED ---

            for i, url in enumerate(self.urls_to_scrape):
                self.current_page_index = i

                count = self.process_data(url)
                total_downloaded += count

                if self.driver is None:
                    break

            if self.driver is not None:
                self.on_status.emit(
                    f"Crawl complete. Downloaded {total_downloaded} total images."
                )

        except Exception as e:
            self.on_status.emit(f"An unexpected error occurred: {e}")

        finally:
            self.close()

        return total_downloaded

    def _download_image_from_url(
        self, url, scraped_data: dict
    ):  # <-- ACCEPTS scraped_data
        try:
            # 1. Resolve URL relative to the current page
            url = urljoin(self.driver.current_url, url)

            # 2. Extract clean filename
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path).split("?")[0]
            if (
                not filename or "." not in filename or len(filename) < 5
            ):  # Basic check for valid filename
                filename = f"image_{int(time.time() * 1000)}.jpg"

            save_path = os.path.join(self.download_dir, filename)
            save_path = self.get_unique_filename(save_path)

            # LOGGING: Confirm the final unique filename
            self.on_status.emit(f"Downloading as: {os.path.basename(save_path)}")

            # 3. Download using requests
            response = requests.get(
                url,
                stream=True,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            self.on_image_saved.emit(save_path)

            # --- MODIFIED: Call helper function to save metadata ---
            if scraped_data:
                # Add image filename to the metadata for reference
                scraped_data["image_filename"] = os.path.basename(save_path)
                # Pass the final image path to ensure JSON name matches
                self._save_scraped_data_to_json(save_path, scraped_data)
            # --- END MODIFIED ---

            return True

        except requests.exceptions.HTTPError as he:
            self.on_status.emit(
                f"Download failed: HTTP Error {he.response.status_code}"
            )
            print(f"Failed to download {url}: HTTP Error {he.response.status_code}")
            return False
        except Exception as e:
            self.on_status.emit(f"Download failed: {e}")
            print(f"Failed to download {url}: {e}")
            return False
