import os
import time
import requests

from urllib.parse import urlparse, urljoin
from selenium.webdriver.common.by import By
from PySide6.QtCore import QObject, Signal
from .crawler import WebCrawler


class QtABCMeta(type(QObject), type(WebCrawler)):
    """Combines Qt's QObject metaclass with ABC's metaclass."""
    pass


class ImageCrawler(WebCrawler, QObject, metaclass=QtABCMeta):
    """Downloads all images from one or more webpages with live Qt signals."""
    
    # === SIGNALS ===
    # on_progress = Signal(int, int) # Removed, using indeterminate progress bar
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
        self.skip_first = config.get("skip_first", 0)
        self.skip_last = config.get("skip_last", 9)
        
        # --- NEW: Replacement logic ---
        self.replace_str = config.get("replace_str")
        self.replacements = config.get("replacements")
        
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

    def process_data(self, url: str) -> int:
        """
        Processes a single URL, finds images, and downloads them.
        Returns the count of successfully downloaded images.
        """
        self.on_status.emit(f"Loading page {self.current_page_index + 1}/{self.total_pages}: {url}")
        if not self.navigate_to_url(url, take_screenshot=False):
            self.on_status.emit(f"Failed to load page: {url}")
            return 0

        self.wait_for_page_to_load(timeout=10)
        self.on_status.emit("Scanning for images...")

        try:
            images = self.driver.find_elements(By.TAG_NAME, "img")
            total_found = len(images)
            skip_total = self.skip_first + self.skip_last
            if skip_total >= total_found:
                self.on_status.emit(f"Not enough images to skip on page {self.current_page_index + 1}.")
                return 0

            images_to_process = images[self.skip_first:-self.skip_last]
            total_to_download = len(images_to_process)

            self.on_status.emit(f"Found {total_found} images. Skipping {skip_total}. Downloading {total_to_download}...")

            urls = {
                urljoin(self.driver.current_url, img.get_attribute("src"))
                for img in images_to_process
                if img.get_attribute("src") and not img.get_attribute("src").startswith("data:")
            }
            
            unique_total = len(urls)
            self.on_status.emit(f"Downloading {unique_total} unique images from page {self.current_page_index + 1}...")
            
            download_count = 0
            for i, img_url in enumerate(urls):
                if self.driver is None: # Check if cancelled
                    return download_count
                    
                self.on_status.emit(f"Page {self.current_page_index + 1}/{self.total_pages}: Downloading image {i + 1}/{unique_total}...")
                if self._download_image_from_url(img_url):
                    download_count += 1
                time.sleep(0.1) # Be nice to the server

            return download_count

        except Exception as e:
            self.on_status.emit(f"Error on page {url}: {e}")
            return 0

    def _download_image_from_url(self, url):
        try:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path).split('?')[0]
            if not filename or '.' not in filename:
                filename = f"image_{int(time.time() * 1000)}.jpg"

            save_path = os.path.join(self.download_dir, filename)
            save_path = self.get_unique_filename(save_path)  # ← NEVER OVERWRITE

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
        """
        Main worker execution loop.
        Generates all URLs and processes them sequentially.
        """
        total_downloaded = 0
        try:
            self.login()
            
            for i, url in enumerate(self.urls_to_scrape):
                self.current_page_index = i
                
                # Process the page and get the count of downloaded images
                count = self.process_data(url)
                total_downloaded += count
                
                # If driver is gone, it means 'close()' was called (likely by cancel_crawl)
                if self.driver is None:
                    break
            
            if self.driver is not None: # If not cancelled
                self.on_status.emit(f"Crawl complete. Downloaded {total_downloaded} total images.")
        
        except Exception as e:
            # Emit error if something outside process_data fails
            self.on_status.emit(f"An unexpected error occurred: {e}")
        
        finally:
            self.close()
            
        return total_downloaded # Return total count
