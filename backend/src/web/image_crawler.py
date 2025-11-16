# image_crawler.py
import os
import time
import requests

from urllib.parse import urlparse, urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
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
        
        # --- FIX 1: Explicit JavaScript Wait Condition ---
        # We perform the wait here to ensure the gallery is ready
        self.on_status.emit("Waiting for gallery image articles to appear...")
        if not self.wait_for_image_element(By.CSS_SELECTOR, "article[id^='post_']", timeout=20):
            self.on_status.emit("Timed out waiting for image gallery to load. Exiting process_data.")
            return 0
        # --------------------------------------------------

        self.on_status.emit("Scanning for images...")
        
        try:
            # --- CRITICAL LOOP FIX: Slice the list ONCE and iterate directly ---
            images = self.driver.find_elements(By.TAG_NAME, "img")
            total_found = len(images)
            skip_total = self.skip_first + self.skip_last
            
            if skip_total >= total_found:
                self.on_status.emit(f"Not enough images to skip on page {self.current_page_index + 1}.")
                return 0
            
            # Slice the list correctly, resulting in the final list of elements to process
            start_index = self.skip_first
            end_index = total_found - self.skip_last
            images_to_process_final = images[start_index:end_index]
            total_to_process = len(images_to_process_final)
            
            self.on_status.emit(f"Found {total_found} images. Processing {total_to_process}...")
            
            download_count = 0
            original_tab = self.driver.current_window_handle

            # Iterate directly over the stable, sliced list
            for i, image_element in enumerate(images_to_process_final):
                if self.driver is None:
                    return download_count
                
                self.on_status.emit(f"Page {self.current_page_index + 1}: Processing image {i + 1}/{total_to_process}...")
                
                try:
                    # Pass the stable element directly to the sequence
                    downloaded = self.run_action_sequence(image_element, original_tab)
                    if downloaded:
                        download_count += 1
                        
                except Exception as e:
                    # Catch all exceptions during action sequence
                    print(f"Failed sequence for image {i+1}: {e}")
                    self.on_status.emit(f"Failed to process image {i+1} due to error, skipping. Check console.")
                
                finally:
                    self.cleanup_tabs(original_tab)
                    time.sleep(0.1)
            
            return download_count
            # --- END CRITICAL LOOP FIX ---

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
            self.driver.switch_to.window(original_tab)
        except Exception as e:
            print(f"Error cleaning up tabs: {e}")

    def run_action_sequence(self, element, original_tab) -> bool:
        """
        Runs the defined action list for a single target element.
        Returns True if a download was successful, False otherwise.
        """
        current_element = element
        
        for action in self.actions:
            if self.driver is None:
                return False
                
            action_type = action["type"]
            param = action["param"]
            
            self.on_status.emit(f"Action: {action_type}...")

            try:
                if action_type == "Find Parent Link (<a>)":
                    current_element = current_element.find_element(By.XPATH, "./ancestor::a")
                
                elif action_type == "Download Simple Thumbnail (Legacy)":
                    url = element.get_attribute("src") 
                    if not url:
                        print("Action 'Legacy Download': No src found on original element.")
                        return False
                    return self._download_image_from_url(url)
                
                elif action_type == "Wait for Gallery (Context Reset)":
                    self.on_status.emit("Awaiting gallery load after security challenge...")
                    # Give a longer timeout (30s) for manual interaction
                    if not self.wait_for_image_element(By.CSS_SELECTOR, "article[id^='post_']", timeout=30):
                         self.on_status.emit("Timed out waiting for image gallery to resume.")
                         return False 
                    self.on_status.emit("Gallery context confirmed.")

                elif action_type == "Extract High-Res Preview URL":
                    try:
                        picture_tag = current_element.find_element(By.XPATH, "./ancestor::picture")
                        source_tag = picture_tag.find_element(By.TAG_NAME, "source")
                        srcset = source_tag.get_attribute("srcset")
                        larger_url = srcset.split('2x')[0].split(',')[-1].strip()
                        self.on_status.emit(f"Extracted preview URL: {larger_url}")
                        return self._download_image_from_url(larger_url)
                    except NoSuchElementException:
                        url = current_element.get_attribute("src")
                        self.on_status.emit("Preview source failed, falling back to standard <img> src.")
                        return self._download_image_from_url(url)

                elif action_type == "Open Link in New Tab":
                    href = current_element.get_attribute("href")
                    if not href:
                        print("Action 'Open Link': No href found on current element.")
                        return False
                    self.driver.execute_script("window.open(arguments[0], '_blank');", href)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.wait_for_page_to_load(timeout=5)
                
                elif action_type == "Click Element by Text":
                    if not param:
                        print("Action 'Click Element': Missing text parameter.")
                        return False
                    el = self.driver.find_element(By.PARTIAL_LINK_TEXT, param) 
                    el.click()
                
                elif action_type == "Wait for Page Load":
                    self.wait_for_page_to_load(timeout=5)
                
                elif action_type == "Switch to Last Tab":
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                
                elif action_type == "Find First <img> on Page":
                    current_element = self.driver.find_element(By.TAG_NAME, "img")
                
                elif action_type == "Download Image from Element":
                    url = current_element.get_attribute("src")
                    if not url:
                        print("Action 'Download Image': No src found on current element.")
                        return False
                    return self._download_image_from_url(url)
                
                elif action_type == "Download Current URL as Image":
                    url = self.driver.current_url
                    if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                        print(f"Action 'Download URL': Current URL doesn't look like an image: {url}")
                        return False
                    return self._download_image_from_url(url)


            except NoSuchElementException:
                self.on_status.emit(f"Action '{action_type}' failed: Element not found.")
                return False
            except Exception as e:
                print(f"Action '{action_type}' failed: {e}")
                self.on_status.emit(f"Action '{action_type}' failed, stopping sequence for this image.")
                return False
        
        return False

    def _download_image_from_url(self, url):
        try:
            url = urljoin(self.driver.current_url, url)
            
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path).split('?')[0]
            if not filename or '.' not in filename:
                filename = f"image_{int(time.time() * 1000)}.jpg"

            save_path = os.path.join(self.download_dir, filename)
            save_path = self.get_unique_filename(save_path)

            response = requests.get(url, stream=True, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            })
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            self.on_image_saved.emit(save_path)
            return True

        except Exception as e:
            print(f"Failed {url}: {e}")
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
