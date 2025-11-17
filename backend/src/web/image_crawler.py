# image_crawler.py
import os
import time
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
    on_status = Signal(str)            # status message
    on_image_saved = Signal(str)       # saved file path

    def __init__(self, config: dict):
        QObject.__init__(self)
        WebCrawler.__init__(
            self, 
            headless=config.get("headless", False), 
            download_dir=config.get("download_dir"), 
            screenshot_dir=config.get("screenshot_dir"), 
            browser=config.get("browser", "brave")
        )
        
        self.target_url = config.get("url")
        # NOTE: Skip default changed to 0 for safer list slicing if user sends empty config
        self.skip_first = config.get("skip_first", 0)
        self.skip_last = config.get("skip_last", 0)
        
        # --- Replacement logic ---
        self.replace_str = config.get("replace_str")
        self.replacements = config.get("replacements")
        
        # --- Action Sequence ---
        self.actions = config.get("actions", [])
        if not self.actions:
            # Default action: Simple Download (Legacy)
            self.actions = [{"type": "Download Simple Thumbnail (Legacy)", "param": None}] 
        # --- END Action Sequence ---
        
        self.urls_to_scrape = [self.target_url]
        if self.replace_str and self.replacements:
            for rep in self.replacements:
                new_url = self.target_url.replace(self.replace_str, rep)
                self.urls_to_scrape.append(new_url)
        
        self.total_pages = len(self.urls_to_scrape)
        self.current_page_index = 0
        
        print(f"ImageCrawler ready: {self.total_pages} pages to scrape.")

    def login(self, credentials=None):
        self.on_status.emit("No login needed.")
        return True
    
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
        self.on_status.emit(f"Loading page {self.current_page_index + 1}/{self.total_pages}: {url}")
        if not self.navigate_to_url(url, take_screenshot=False):
            self.on_status.emit(f"Failed to load page: {url}")
            return 0

        self.wait_for_page_to_load(timeout=10)
        
        self.on_status.emit("Waiting for image elements to appear...")
        # Target a common gallery image element or link
        if not self.wait_for_image_element(By.TAG_NAME, "img", timeout=20):
            self.on_status.emit("Timed out waiting for image gallery to load. Exiting process_data.")
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
                 self.on_status.emit(f"Found {total_found} images, but 0 left to process after skipping.")
                 return 0
                 
            self.on_status.emit(f"Found {total_found} images. Processing {total_to_process}...")
            
            download_count = 0
            original_tab = self.driver.current_window_handle

            # Iterate over the valid indices
            for i, global_index in enumerate(indices_to_process):
                if self.driver is None:
                    return download_count
                
                self.on_status.emit(f"Page {self.current_page_index + 1}: Processing image {i + 1}/{total_to_process} (Index: {global_index})...")
                
                try:
                    # RE-LOCATE THE ELEMENT JUST BEFORE USE
                    # Find ALL <img> tags again and select the one at global_index
                    images_on_page = self.driver.find_elements(By.TAG_NAME, "img")
                    
                    if global_index >= len(images_on_page):
                        self.on_status.emit(f"Index {global_index} out of range after re-locating. Stopping.")
                        break

                    image_element = images_on_page[global_index]
                    
                    # Pass the FRESH element reference to the sequence
                    downloaded = self.run_action_sequence(image_element, original_tab)
                    
                    if downloaded:
                        download_count += 1
                        
                except Exception as e:
                    # Catch all exceptions during image processing cycle
                    print(f"Failed image cycle for image {i+1}: {e}")
                    self.on_status.emit(f"Failed to process image {i+1} due to error, skipping. Check console.")
                
                finally:
                    # Cleanup tabs to return to the original gallery page
                    self.cleanup_tabs(original_tab)
                    time.sleep(0.1)
            
            return download_count
            # --- CRITICAL FIX END ---

        except Exception as e:
            self.on_status.emit(f"Error on page {url}: {e}")
            return 0

    def cleanup_tabs(self, original_tab):
        """Closes all extra tabs and returns to the original_tab."""
        try:
            if self.driver is None:
                return
            handles = self.driver.window_handles
            if len(handles) > 1:
                for handle in handles:
                    if handle != original_tab:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
            # Ensure we are back on the original tab before returning from the function
            self.driver.switch_to.window(original_tab)
        except Exception as e:
            print(f"Error cleaning up tabs: {e}")

    def run_action_sequence(self, element, original_tab) -> bool:
        """
        Runs the defined action list for a single target element.
        Returns True if a download was successful, False otherwise.
        """
        current_element = element
        downloaded = False
        
        for action in self.actions:
            if self.driver is None:
                return downloaded
                
            action_type = action["type"]
            param = action["param"]
            
            self.on_status.emit(f"Action: {action_type}...")

            try:
                if action_type == "Find Parent Link (<a>)":
                    current_element = current_element.find_element(By.XPATH, "./ancestor::a")
                
                elif action_type == "Download Simple Thumbnail (Legacy)":
                    url = element.get_attribute("src") 
                    if not url:
                        self.on_status.emit("Download failed: No src found on original element.")
                        return downloaded 
                    downloaded = self._download_image_from_url(url)
                    return downloaded
                
                elif action_type == "Wait for Gallery (Context Reset)":
                    if not self.wait_for_image_element(By.TAG_NAME, "img", timeout=30):
                         self.on_status.emit("Wait failed: Timed out waiting for gallery to resume.")
                         return downloaded 
                    self.on_status.emit("Gallery context confirmed.")
                
                # --- Actions that modify browser state ---
                elif action_type == "Open Link in New Tab":
                    href = current_element.get_attribute("href")
                    if not href:
                        raise NoSuchElementException("Action 'Open Link': No href found on current element.")
                    self.driver.execute_script("window.open(arguments[0], '_blank');", href)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.wait_for_page_to_load(timeout=5)
                
                elif action_type == "Extract High-Res Preview URL":
                    current_element.click()
                    self.wait_for_page_to_load(timeout=5)
                    self.on_status.emit("Clicked element and navigating to new page...")
                    
                elif action_type == "Click Element by Text":
                    if not param:
                        raise ValueError("Action 'Click Element': Missing text parameter.")
                    el = self.driver.find_element(By.PARTIAL_LINK_TEXT, param) 
                    el.click()
                
                elif action_type == "Wait for Page Load":
                    self.wait_for_page_to_load(timeout=5)
                
                # --- NEW ACTION IMPLEMENTATION ---
                elif action_type == "Wait X Seconds":
                    if not isinstance(param, (int, float)) or param < 0:
                        raise ValueError(f"Action 'Wait X Seconds': Invalid parameter: {param}")
                    self.on_status.emit(f"Waiting for {param} seconds...")
                    time.sleep(param)
                # --- END NEW ACTION IMPLEMENTATION ---

                elif action_type == "Switch to Last Tab":
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                
                # --- Actions that find elements ---
                elif action_type == "Find <img> Number X on Page":
                    if not isinstance(param, int) or param < 1:
                        raise ValueError(f"Action 'Find <img> Number X': Invalid parameter: {param}")
                        
                    xpath_query = f"//img[{param}]"
                    current_element = self.driver.find_element(By.XPATH, xpath_query)

                elif action_type == "Find Element by CSS Selector":
                    if not param:
                        raise ValueError("Action 'Find Element by CSS Selector': Missing selector parameter.")
                    current_element = self.driver.find_element(By.CSS_SELECTOR, param)
                
                # --- Download Actions ---
                elif action_type == "Download Image from Element":
                    url = current_element.get_attribute("src") or current_element.get_attribute("href")
                    if not url:
                        self.on_status.emit("Download failed: No src/href found on current element.")
                        return downloaded 
                    downloaded = self._download_image_from_url(url)
                    return downloaded
                
                elif action_type == "Download Current URL as Image":
                    url = self.driver.current_url
                    if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                        self.on_status.emit(f"Download failed: Current URL doesn't look like an image: {url}")
                        return downloaded 
                    downloaded = self._download_image_from_url(url)
                    return downloaded

                # If execution reaches here without an explicit return, it means the action succeeded.
                
            except (NoSuchElementException, StaleElementReferenceException) as e:
                # Non-critical failure: Log and continue to the next action
                self.on_status.emit(f"Action '{action_type}' failed (Element not found/stale). Skipping to next action.")
                print(f"Non-critical Failure in sequence: {action_type} - {e}")
                continue
                
            except (TimeoutException, ValueError, Exception) as e:
                # Critical failure: Log and stop the sequence for this image
                self.on_status.emit(f"Action '{action_type}' failed critically. Stopping sequence for this image.")
                print(f"Critical Failure in sequence: {action_type} - {e}")
                return downloaded
        
        return downloaded

    def _download_image_from_url(self, url):
        try:
            # 1. Resolve URL relative to the current page
            url = urljoin(self.driver.current_url, url)
            
            # 2. Extract clean filename
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path).split('?')[0]
            if not filename or '.' not in filename or len(filename) < 5: # Basic check for valid filename
                filename = f"image_{int(time.time() * 1000)}.jpg"

            save_path = os.path.join(self.download_dir, filename)
            save_path = self.get_unique_filename(save_path)

            # 3. Download using requests
            response = requests.get(url, stream=True, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            self.on_image_saved.emit(save_path)
            return True

        except requests.exceptions.HTTPError as he:
            self.on_status.emit(f"Download failed: HTTP Error {he.response.status_code}")
            print(f"Failed to download {url}: HTTP Error {he.response.status_code}")
            return False
        except Exception as e:
            self.on_status.emit(f"Download failed: {e}")
            print(f"Failed to download {url}: {e}")
            return False

    def run(self):
        total_downloaded = 0
        try:
            self.login()
            
            for i, url in enumerate(self.urls_to_scrape):
                self.current_page_index = i
                
                count = self.process_data(url)
                total_downloaded += count
                
                if self.driver is None:
                    break
            
            if self.driver is not None:
                self.on_status.emit(f"Crawl complete. Downloaded {total_downloaded} total images.")
        
        except Exception as e:
            self.on_status.emit(f"An unexpected error occurred: {e}")
        
        finally:
            self.close()
            
        return total_downloaded
