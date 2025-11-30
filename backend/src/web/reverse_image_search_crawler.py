import os
import time

from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from src.web.crawler import WebCrawler 


class ReverseImageSearchCrawler(WebCrawler):
    """
    A specialized crawler that performs reverse image searches using Google Lens
    via Selenium, extracting similar images and filtering by resolution.
    """

    def __init__(self, headless=True, download_dir=None, screenshot_dir=None, browser="brave"):
        super().__init__(headless=headless, download_dir=download_dir, 
                         screenshot_dir=screenshot_dir, browser=browser)
        self.results: List[Dict[str, str]] = []

    def login(self, credentials):
        """Not required for public Google search."""
        pass

    def process_data(self):
        """Not used directly; we use perform_reverse_search."""
        pass

    def perform_reverse_search(self, image_path: str, min_width: int = 0, min_height: int = 0) -> List[Dict[str, str]]:
        """
        Main workflow:
        1. Navigate to Google Images.
        2. Upload the local image to Google Lens.
        3. Scrape results.
        4. Filter by resolution (if possible to determine from metadata).
        """
        self.results = []
        
        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            return []

        try:
            # 1. Navigate to Google Images
            self.navigate_to_url("https://images.google.com/")
            
            # Handle Consent Popup (European Union)
            try:
                # Common "Accept all" or "Reject all" buttons in multiple languages
                # Selector strategy: look for buttons with specific text or IDs
                consent_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept all') or contains(text(), 'Reject all')]")
                if consent_buttons:
                    consent_buttons[0].click()
                    time.sleep(1)
            except Exception:
                pass # Consent might not appear or is already handled

            # 2. Click "Search by image" (Camera Icon)
            # The aria-label is usually stable for Google Lens
            try:
                camera_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[aria-label='Search by image'], span[aria-label='Search by image']")
                ))
                camera_btn.click()
            except Exception as e:
                print(f"❌ Failed to find camera icon: {e}")
                return []
            
            # 3. Upload Image
            # Find the file input field (it might be hidden)
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file'][name='encoded_image']")
                file_input.send_keys(image_path)
            except Exception as e:
                print(f"❌ Failed to find file input for upload: {e}")
                return []

            # Wait for results to load
            print("⏳ Analyzing image...")
            time.sleep(5) # Give it time to process and redirect

            # 4. Click "Find image source" to get better visual matches if available
            try:
                find_source_btn = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Find image source')]")
                find_source_btn.click()
                time.sleep(3)
            except Exception:
                # If this specific button isn't there, we are likely already on the visual matches page
                pass

            # 5. Scrape Results
            # Google Lens results are dynamic. We look for the grid of images.
            # Common selectors for result items
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "div[data-ved] img")
            
            # We need to find the links associated with these thumbnails
            # This is heuristics-based as Google changes classes frequently.
            
            # Strategy: Look for anchor tags that likely contain the result link
            # We specifically want "Visual matches" section
            
            potential_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'http')]")
            
            print(f"🔍 Scanning {len(potential_links)} potential links...")

            found_urls = set()
            
            for link_elem in potential_links:
                href = link_elem.get_attribute('href')
                
                # Filter out google-specific links, keep external results
                if not href or "google.com" in href or "googleusercontent" in href:
                    continue
                
                if href in found_urls:
                    continue
                
                # Check for image extension in URL (simple heuristic)
                # Google Lens often links to PAGES, not direct images.
                # However, sometimes it links to the image resource.
                
                # To be more robust, we accept page links too, but mark them.
                is_direct_image = any(href.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp'])
                
                # Try to find resolution text if available in the parent container
                # Google often displays "1920 x 1080" near the result
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
                        # Simple parsing: "1920 x 1080"
                        # Sometimes text has extra chars
                        w_str = "".join(filter(str.isdigit, parts[0]))
                        h_str = "".join(filter(str.isdigit, parts[1].split()[0]))
                        width = int(w_str)
                        height = int(h_str)
                    except:
                        pass
                
                # Filter by Resolution
                if min_width > 0 and width < min_width:
                    continue
                if min_height > 0 and height < min_height:
                    continue
                
                found_urls.add(href)
                self.results.append({
                    "url": href,
                    "resolution": f"{width}x{height}" if width > 0 else "Unknown",
                    "title": link_elem.get_attribute("title") or "Result",
                    "is_direct": is_direct_image
                })

                if len(self.results) >= 20: # Limit results
                    break
            
            return self.results

        except Exception as e:
            print(f"❌ Error during reverse search: {e}")
            return []

    def close(self):
        super().close()