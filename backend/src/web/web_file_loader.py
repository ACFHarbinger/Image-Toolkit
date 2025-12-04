import os
import time

from selenium.webdriver.common.by import By


class WebFileLoader:
    def __init__(self, driver, download_dir=None):
        self.driver = driver
        self.download_dir = download_dir
        self.download_methods = {
            "javascript": self._download_via_javascript,
            "element_click": self._download_via_element_click,
            "function_call": self._download_via_function_call,
        }
        self.initial_files = set(os.listdir(self.download_dir))

    def _download_via_javascript(self, selectors):
        """Execute JavaScript function directly"""
        try:
            for selector in selectors:
                try:
                    self.driver.execute_script(selector)
                    time.sleep(3)
                    return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"   JavaScript execution failed: {e}")
            return False

    def _download_via_element_click(self, selectors):
        """Find and click the download element"""
        try:
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    self.driver.execute_script("arguments[0].click();", element)
                    time.sleep(3)
                    return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"   Element click failed: {e}")
            return False

    def _download_via_function_call(self, selectors):
        """Try alternative function calls"""
        try:
            for call in selectors:
                try:
                    self.driver.execute_script(call)
                    time.sleep(2)
                    # If no error, assume it worked
                    return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"   Function calls failed: {e}")
            return False

    def wait_for_download_to_complete(self, timeout=30):
        """
        Wait for download to complete and return file path
        """
        last_size = -1
        stable_count = 0
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_files = set(os.listdir(self.download_dir))
            new_files = current_files - self.initial_files

            # Look for files
            file_ls = []
            for file in new_files:
                file_path = os.path.join(self.download_dir, file)
                file_ls.append(file_path)

            if file_ls:
                # Check if file size is stable (download complete)
                current_size = sum(os.path.getsize(f) for f in file_ls)
                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= 2:  # Size stable for 2 seconds
                        for file in new_files:
                            self.initial_files.add(file)
                        print(f"✅ Download complete: {len(file_ls)} file(s)")
                        return file_ls[0]  # Return first file
                else:
                    stable_count = 0
                    last_size = current_size
            time.sleep(1)

        # Return any found files even if timeout (might be partial download)
        current_files = set(os.listdir(self.download_dir))
        new_files = current_files - self.initial_files
        if new_files:
            file_path = os.path.join(self.download_dir, new_files[0])
            print(f"⚠️  Download may be incomplete: {file_path}")
            return file_path
        return None

    def download_xls_file(self, download_dict):
        """
        Comprehensive XLS file download with multiple approaches
        """
        print("💾 Starting XLS file download process...")
        for method_name, selectors in download_dict.items():
            method_func = self.download_methods.get(method_name, None)
            assert method_func is not None, "Unknown download method: {}".format(
                method_name
            )

            print(f"\n🔄 Trying method: {method_func.__name__}")
            result = method_func(selectors)
            if result:
                print(f"✅ {method_func.__name__} succeeded")

                # Verify download
                downloaded_file = self.wait_for_download_to_complete()
                if downloaded_file:
                    return downloaded_file
                else:
                    print("⚠️  Approach worked but no file detected")
            else:
                print(f"❌ {method_func.__name__} failed")

        print("💥 All download methods failed")
        return None
