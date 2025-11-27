import os
import time
import requests
import json

from urllib.parse import urljoin, urlparse
from PySide6.QtCore import QObject, Signal


class ImageBoardCrawler(QObject):
    """
    Abstract Base Class for Image Board Crawlers.
    Provides common signals, initialization, and helper methods.
    """
    
    # === SIGNALS ===
    on_status = Signal(str)            # status message
    on_image_saved = Signal(str)       # saved file path

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        
        self.download_dir = config.get("download_dir", "downloads")
        self.tags = config.get("tags", "")
        self.limit = config.get("limit", 20)
        self.max_pages = config.get("max_pages", 5)
        self.base_url = config.get("url") # Subclasses might override default if missing
        
        # Authentication (Common keys, specific mapping in subclasses if needed)
        self.login_config = config.get("login_config", {})
        self.username = self.login_config.get("username")
        self.api_key = self.login_config.get("password") 
        
        # State
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ImageToolkitCrawler/1.0 (Generic User)'
        })
        
        # Rate Limiting
        self.request_count = 0
        self.REQUEST_LIMIT = 5
        self.SLEEP_TIME = 1.0

    def get_unique_filename(self, filepath):
        """Returns a unique filename like: cat.jpg -> cat (1).jpg"""
        base, ext = os.path.splitext(filepath)
        counter = 1
        new_path = filepath
        while os.path.exists(new_path):
            new_path = f"{base} ({counter}){ext}"
            counter += 1
        return new_path

    def run(self):
        """Main execution loop (Template Method)."""
        total_downloaded = 0
        
        try:
            board_name = self.__class__.__name__.replace("Crawler", "")
            self.on_status.emit(f"Starting {board_name} Crawl on: {self.base_url}")
            
            os.makedirs(self.download_dir, exist_ok=True)

            for page in range(1, self.max_pages + 1):
                self.on_status.emit(f"Fetching page {page}...")
                
                posts = self.fetch_posts(page)
                
                if not posts:
                    self.on_status.emit("No posts found or end of results.")
                    break
                
                download_count = self.process_posts(posts)
                total_downloaded += download_count
                
                time.sleep(0.5) 

            self.on_status.emit(f"Crawl complete. Downloaded {total_downloaded} images.")
            
        except Exception as e:
            self.on_status.emit(f"Critical Error: {str(e)}")
            
        return total_downloaded

    def check_rate_limit(self):
        """Checks and applies rate limiting."""
        self.request_count += 1
        if self.request_count % self.REQUEST_LIMIT == 0:
            self.on_status.emit(f"Rate limiting active: Waiting {self.SLEEP_TIME}s...")
            time.sleep(self.SLEEP_TIME)

    def fetch_posts(self, page):
        """
        Abstract method to fetch posts. Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement fetch_posts")

    def process_posts(self, posts):
        """
        Iterates through posts and downloads images. 
        Most logic is common, but URL extraction might differ slightly.
        """
        count = 0
        
        if not isinstance(posts, list):
            # Try to handle single dict response if API behaves oddly
            if isinstance(posts, dict):
                posts = [posts]
            else:
                self.on_status.emit(f"Unexpected API response format: {type(posts)}")
                return 0

        for post in posts:
            file_url = self.extract_file_url(post)
            
            if not file_url:
                continue
                
            if urlparse(file_url).scheme not in ['http', 'https']:
                 file_url = urljoin(self.base_url, file_url)
            
            ext = os.path.splitext(urlparse(file_url).path)[1]
            if not ext: ext = ".jpg"
                
            filename = f"{post.get('id', 'unknown')}_{post.get('md5', int(time.time()))}{ext}"
            save_path = os.path.join(self.download_dir, filename)
            
            if os.path.exists(save_path):
                self.on_status.emit(f"Skipping existing file: {filename}")
                continue
            
            if self.download_image(file_url, save_path):
                count += 1
                self.save_metadata(save_path, post)
                time.sleep(0.5) 
                
        return count

    def extract_file_url(self, post):
        """Hook for subclasses to extract URL from post object."""
        return post.get("file_url")

    def download_image(self, url, save_path):
        """Downloads the file from the URL."""
        try:
            self.on_status.emit(f"Downloading: {os.path.basename(save_path)}")
            self.check_rate_limit() # Apply rate limit to downloads too? Optional.
            
            response = self.session.get(url, stream=True, timeout=20)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            
            self.on_image_saved.emit(save_path)
            return True
            
        except Exception as e:
            self.on_status.emit(f"Download failed for {url}: {e}")
            return False

    def save_metadata(self, image_path, post_data):
        json_path = os.path.splitext(image_path)[0] + ".json"
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(post_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save metadata: {e}")