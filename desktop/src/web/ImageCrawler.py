import os
import time
import requests

from urllib.parse import urlparse, urljoin
from selenium.webdriver.common.by import By
from PySide6.QtCore import QObject, Signal
from .Crawler import WebCrawler


class QtABCMeta(type(QObject), type(WebCrawler)):
    """Combines Qt's QObject metaclass with ABC's metaclass."""
    pass


class ImageCrawler(WebCrawler, QObject, metaclass=QtABCMeta):
    """Downloads all images from a webpage with live Qt signals."""
    
    # === SIGNALS ===
    on_progress = Signal(int, int)      # (current, total)
    on_status = Signal(str)            # status message
    on_image_saved = Signal(str)       # saved file path

    def __init__(self, url, skip_first=0, skip_last=9, headless=False, download_dir=None, screenshot_dir=None, browser="brave"):
        QObject.__init__(self)         # ← Initialize QObject
        WebCrawler.__init__(self, headless, download_dir, screenshot_dir, browser)
        self.target_url = url
        self.skip_first = skip_first
        self.skip_last = skip_last
        print(f"ImageCrawler ready: {url}")

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

    def process_data(self): # 4 12
        self.on_status.emit("Loading page...")
        if not self.navigate_to_url(self.target_url, take_screenshot=False):
            self.on_status.emit("Failed to load page.")
            return

        self.wait_for_page_to_load(timeout=10)
        self.on_status.emit("Scanning for images...")

        try:
            images = self.driver.find_elements(By.TAG_NAME, "img")
            total_found = len(images)
            skip_total = self.skip_first + self.skip_last
            if skip_total >= total_found:
                self.on_status.emit("Not enough images to skip.")
                return

            images_to_process = images[self.skip_first:-self.skip_last]  # ← SKIP LAST 5
            total = len(images_to_process)

            self.on_progress.emit(0, total)
            self.on_status.emit(f"Found {total_found} images. Skipping {skip_total}. Downloading {total}...")

            urls = {
                urljoin(self.driver.current_url, img.get_attribute("src"))
                for img in images_to_process
                if img.get_attribute("src") and not img.get_attribute("src").startswith("data:")
            }

            self.on_status.emit(f"Downloading {len(urls)} unique images...")

            for i, url in enumerate(urls):
                if self._download_image_from_url(url):
                    self.on_progress.emit(i + 1, len(urls))
                time.sleep(0.1)

            self.on_status.emit(f"Downloaded {len(urls)} images! Skipped {skip_total}.")

        except Exception as e:
            self.on_status.emit(f"Error: {e}")

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
        try:
            self.login()
            self.process_data()
        finally:
            self.close()
        return 0
