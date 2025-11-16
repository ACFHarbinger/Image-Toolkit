import os
import abc
import time
import shutil
import atexit
import tempfile
import platform
import subprocess
try:
    import backend.src.utils.definitions as udef
except:
    import src.utils.definitions as udef

from .web_file_loader import WebFileLoader
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.core.os_manager import ChromeType
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService


class WebCrawler(abc.ABC):
    """
    Abstract Base Class for all web crawlers. 
    Handles driver setup, navigation, generic clicking, and debugging utilities.
    Requires subclasses to implement specific workflow methods.
    """
    def __init__(self, headless=False, download_dir=None, screenshot_dir=None, browser="brave"):
        """
        Initialize the Web crawler and setup the WebDriver.
        
        Args:
            browser (str): Browser to use - "brave", "firefox", "chrome", "edge", or "safari"
        """
        self.download_dir = download_dir or os.path.join(os.getcwd(), "downloads")
        self.screenshot_dir = screenshot_dir or os.path.join(os.getcwd(), "screenshots")
        self.browser = browser.lower()
        self.browser_methods = [self._setup_brave_driver, self._setup_firefox_driver, self._setup_chrome_driver, self._setup_edge_driver, self._setup_safari_driver]
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            os.makedirs(self.screenshot_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create required directories: {e}")
            raise
            
        self.driver = None # Will be set in setup_driver
        self.wait = None   # Will be set in setup_driver

        self.setup_driver(headless, self.download_dir)
        self.file_loader = WebFileLoader(self.driver, self.download_dir)
        print(f"✅ WebCrawler base initialized with {self.browser}.")
    
    # --- Abstract Methods (Must be implemented by all concrete subclasses) ---
    @abc.abstractmethod
    def login(self, credentials):
        """
        Abstract method for handling the specific bank login process.
        Subclasses must implement this.
        """
        pass

    @abc.abstractmethod
    def process_data(self):
        """
        Abstract method for the main data retrieval and processing workflow.
        Subclasses must implement this.
        """
        pass

    # --- Concrete Methods (Generic Utilities) ---
    def setup_driver(self, headless=False, download_dir=None):
        """Setup webdriver for the selected browser with appropriate options"""
        browser_methods = dict(zip(udef.WC_BROWSERS, self.browser_methods))
        if self.browser in browser_methods:
            try:
                browser_methods[self.browser](udef.CRAWLER_SETUP_WAIT_TIME, headless, download_dir)
                print(f"✅ Successfully initialized {self.browser} driver")
            except Exception as e:
                print(f"❌ Failed to initialize {self.browser} driver: {e}")
                self._fallback_to_available_browser(udef.CRAWLER_SETUP_WAIT_TIME, headless, download_dir)
        else:
            print(f"❌ Unsupported browser: {self.browser}. Falling back to available browser.")
            self._fallback_to_available_browser(udef.CRAWLER_SETUP_WAIT_TIME, headless, download_dir)

    def _fallback_to_available_browser(self, wait_time, headless, download_dir):
        """Try available browsers in order of preference"""
        for browser in ["brave"]:
            if browser == self.browser:
                continue  # Skip the one that already failed
                
            try:
                print(f"🔄 Attempting fallback to {browser}...")
                self.browser = browser
                browser_methods = {
                    "firefox": self._setup_firefox_driver,
                    "chrome": self._setup_chrome_driver,
                    "edge": self._setup_edge_driver,
                    "safari": self._setup_safari_driver
                }
                browser_methods[browser](wait_time, headless, download_dir)
                print(f"✅ Fallback successful: using {browser}")
                return
            except Exception as e:
                print(f"❌ Fallback to {browser} failed: {e}")
                continue
        
        raise ModuleNotFoundError("No available browser drivers found. Please install Chrome, Firefox, or Edge.")

    def _setup_firefox_driver(self, wait_time, headless=False, download_dir=None):
        profile_dir = tempfile.mkdtemp(prefix="firefox-profile-")
        print(f"🧹 Using clean Firefox profile: {profile_dir}")

        firefox_options = FirefoxOptions()
        if headless:
            print("⚙️ Setting Firefox to headless mode.")
            firefox_options.add_argument("--headless")
        
        # CRITICAL FOR HEADLESS
        firefox_options.add_argument("--disable-gpu")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--disable-extensions")
        firefox_options.add_argument("--window-size=1920,1080")
        firefox_options.add_argument(f"--profile={profile_dir}")
        firefox_options.add_argument("-no-remote")
        firefox_options.add_argument("--no-first-run")

        # Use firefox-esr
        firefox_options.binary_location = "/usr/bin/firefox-esr"
        print("ℹ️ Using specific binary: /usr/bin/firefox-esr")

        # Language
        firefox_options.set_preference("general.useragent.override",
            "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0")
        firefox_options.set_preference("intl.accept_languages", "pt-PT,pt,en")
        print("ℹ️ Setting language preferences: pt-PT, pt, en")

        # Download
        if download_dir:
            os.makedirs(download_dir, exist_ok=True)
            firefox_options.set_preference("browser.download.dir", download_dir)
            firefox_options.set_preference("browser.download.folderList", 2)
            firefox_options.set_preference("browser.download.useDownloadDir", True)
            firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk",
                "application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            firefox_options.set_preference("browser.download.manager.showWhenStarting", False)
            firefox_options.set_preference("pdfjs.disabled", True)
            print(f"📁 Setting download directory to: {download_dir}")

        try:
            print("⬇️ Installing geckodriver...")
            service = FirefoxService(
                executable_path=GeckoDriverManager().install(),
                log_path="/tmp/geckodriver.log"
            )
            print(f"🛠️ GeckoDriver ready: {service.path}")

            # SET ENV + XVFB
            env = os.environ.copy()
            env["MOZ_HEADLESS"] = "1"
            env["DISPLAY"] = ":99"
            print("🖥️ Starting X virtual framebuffer (Xvfb)...")

            # Start virtual display
            xvfb = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"])
            time.sleep(2)

            print("🚀 Starting Firefox...")
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            print("✅ Firefox driver started!")

            self.wait = WebDriverWait(self.driver, wait_time)
            self.driver.get("https://example.com")
            print(f"📄 Title: {self.driver.title}")
        except Exception as e:
            print(f"❌ Firefox browser failed: {e}")
            try:
                with open("/tmp/geckodriver.log") as f:
                    print("=== GECKODRIVER LOG ===")
                    print(f.read())
            except:
                pass
            raise OSError(f"Failed to initialize Gecko driver: {e}")
        finally:
            atexit.register(lambda: shutil.rmtree(profile_dir, ignore_errors=True))
            atexit.register(xvfb.terminate if 'xvfb' in locals() else lambda: None)
    
    def _find_firefox_executable(self):
        """Find Firefox browser executable path on different operating systems"""
        firefox_paths = []
        system = platform.system()
        if system == "Windows":
            try: # Try using 'where' command
                result = subprocess.run(['where', 'firefox'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0]  # Take first result
            except:
                pass

            firefox_paths = [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ]  
        elif system == "Darwin":  # macOS
            firefox_paths = [
                "/Applications/Firefox.app/Contents/MacOS/firefox",
                "/usr/local/bin/firefox",
            ]
        elif system == "Linux":
            try: # Try using 'which' command
                result = subprocess.run(['which', 'firefox'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass

            firefox_paths = [
                "/usr/bin/firefox",
                "/usr/local/bin/firefox",
                "/snap/bin/firefox",
                "/opt/firefox/firefox",
            ]

        # Check common paths
        for path in firefox_paths:
            if os.path.exists(path):
                return path
        
        return None  # Return None if not found

    def _print_firefox_troubleshooting(self):
        """Print helpful troubleshooting information for Firefox issues"""
        print("\n🔧 Firefox Troubleshooting:")
        print("1. Check if Firefox is installed: firefox --version")
        print("2. Try removing existing Firefox profiles:")
        print("   - Linux: rm -rf ~/.mozilla/firefox/*.default*")
        print("   - Windows: Delete %APPDATA%\\Mozilla\\Firefox\\Profiles\\")
        print("   - macOS: rm -rf ~/Library/Application Support/Firefox/Profiles/")
        print("3. Install geckodriver manually:")
        print("   - Download from: https://github.com/mozilla/geckodriver/releases")
        print("   - Add to PATH or place in /usr/local/bin/")
        print("4. Try: pip install webdriver-manager")

    def _setup_chrome_driver(self, wait_time, headless=False, download_dir=None):
        """Setup Chrome webdriver with appropriate options"""   
        print("⚙️ Setting up Chrome options...")
        chrome_options = ChromeOptions()
        if headless:
            print("⚙️ Setting Chrome to headless mode.")
            chrome_options.add_argument("--headless")
        
        # Important options for Portuguese banking sites
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Use Portuguese user agent to avoid geo-blocking
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Accept language preferences
        chrome_options.add_argument("--lang=pt-PT")
        chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'pt-PT,pt,en'})
        print("ℹ️ Setting language preferences: pt-PT, pt, en")
        
        # Disable notifications and popups
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")

        # Set download directory and preferences
        if download_dir is not None:
            download_prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "safebrowsing.disable_download_protection": True,
                "profile.default_content_settings.popups": 0,
                "plugins.always_open_pdf_externally": True,
                "download.extensions_to_open": "",
            }
            chrome_options.add_experimental_option("prefs", download_prefs)
            print(f"📁 Setting download directory to: {download_dir}")
        
        # Try with webdriver-manager first, then fallback to system driver
        try:
            print("📦 Installing/updating Chrome driver for Chrome via webdriver-manager...")
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ ChromeDriver initialized successfully with webdriver-manager")
        except Exception as e:
            print(f"⚠️ webdriver-manager failed ({e}). Falling back to system installed driver.")
            print("🔄 Trying system Chrome driver for Chrome...")
            try:
                # Fallback to system chromedriver
                self.driver = webdriver.Chrome(options=chrome_options)
                print("✅ Chrome initialized successfully with system driver")
            except Exception as e2:
                print(f"❌ Chrome browser failed: {e2}")
                raise OSError(f"Failed to initialize Chrome driver: {e2}")

        self.wait = WebDriverWait(self.driver, wait_time)

    def _setup_edge_driver(self, wait_time, headless=False, download_dir=None):
        """Setup Microsoft Edge webdriver with appropriate options"""
        print("⚙️ Setting up Edge options...")
        edge_options = EdgeOptions()
        if headless:
            print("⚙️ Setting Edge to headless mode.")
            edge_options.add_argument("--headless")
        
        # Important options for Portuguese banking sites
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        
        # Use Portuguese user agent to avoid geo-blocking
        edge_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
        
        # Accept language preferences
        edge_options.add_argument("--lang=pt-PT")
        edge_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'pt-PT,pt,en',
        })
        print("ℹ️ Setting language preferences: pt-PT, pt, en")
        
        # Disable notifications and popups
        edge_options.add_argument("--disable-notifications")
        edge_options.add_argument("--disable-popup-blocking")

        # Set download directory and preferences
        if download_dir is not None:
            download_prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "safebrowsing.disable_download_protection": True,
                "profile.default_content_settings.popups": 0,
                "plugins.always_open_pdf_externally": True,
            }
            edge_options.add_experimental_option("prefs", download_prefs)
            print(f"📁 Setting download directory to: {download_dir}")
        
        # Try with webdriver-manager first, then fallback to system driver
        try:
            print("📦 Attempting to use webdriver-manager for EdgeDriver...")
            service = EdgeService(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=edge_options)
            print("✅ EdgeDriver initialized successfully with webdriver-manager")
        except Exception as e:
            print(f"⚠️ webdriver-manager failed ({e}). Falling back to system installed driver.")
            print("🔄 Trying system Edge driver for Edge...")
            try:
                # Fallback to system edgedriver
                self.driver = webdriver.Edge(options=edge_options)
                print("✅ EdgeDriver initialized successfully with system driver")
            except Exception as e2:
                print(f"❌ Edge browser failed: {e2}")
                raise OSError(f"Failed to initialize Edge driver: {e2}")

        self.wait = WebDriverWait(self.driver, wait_time)

    def _setup_safari_driver(self, wait_time, headless=False, download_dir=None):
        """Setup Safari webdriver (Note: Safari doesn't support headless mode)"""
        if headless:
            print("⚠️  Safari does not support headless mode. Running in normal mode.")
        
        if platform.system() != "Darwin":
            print("❌ Safari driver setup failed: Not running on macOS.")
            raise OSError("Safari driver is only available on macOS")
        
        print("⚙️ Setting up Safari driver...")
        # Safari options are limited compared to other browsers
        try:
            self.driver = webdriver.Safari()
            print("✅ Safari driver initialized successfully.")
        except Exception as e:
            print(f"❌ Safari browser failed: {e}")
            raise
        
        # Configure download directory (limited control in Safari)
        if download_dir is not None:
            # Note: Safari has limited download configuration via Selenium
            print(f"ℹ️  Safari download directory cannot be configured via Selenium. Default download location will be used.")
        
        self.wait = WebDriverWait(self.driver, wait_time)

    def _setup_brave_driver(self, wait_time, headless=False, download_dir=None):
        """Setup Brave webdriver with appropriate options"""
        brave_options = ChromeOptions()
        if headless:
            brave_options.add_argument("--headless")
        
        # Important options for Portuguese banking sites
        brave_options.add_argument("--no-sandbox")
        brave_options.add_argument("--disable-dev-shm-usage")
        brave_options.add_argument("--disable-gpu")
        brave_options.add_argument("--window-size=1920,1080")

        # Critical arguments for DevToolsActivePort issue (uncomment if Brave was installed via APT|SNAP)
        #brave_options.add_argument("--remote-debugging-port=9222")
        #brave_options.add_argument("--remote-debugging-address=0.0.0.0")
        #brave_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Use Portuguese user agent to avoid geo-blocking
        brave_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Accept language preferences
        brave_options.add_argument("--lang=pt-PT")
        brave_options.add_experimental_option('prefs', {'intl.accept_languages': 'pt-PT,pt,en'})
        
        # Disable notifications and popups
        brave_options.add_argument("--disable-notifications")
        brave_options.add_argument("--disable-popup-blocking")

        # Set download directory and preferences
        if download_dir is not None:
            download_prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "safebrowsing.disable_download_protection": True,
                "profile.default_content_settings.popups": 0,
                "plugins.always_open_pdf_externally": True,
                "download.extensions_to_open": "",
            }
            brave_options.add_experimental_option("prefs", download_prefs)
        
        # Find Brave browser executable path
        brave_path = self._find_brave_executable()
        if brave_path:
            brave_options.binary_location = brave_path
            print(f"🔍 Found Brave browser at: {brave_path}")
        else:
            print("⚠️  Brave browser not found in common locations. Trying Chrome driver with Brave detection...")
        
        # Try with webdriver-manager first
        try:
            print("📦 Installing/updating Chrome driver for Brave via webdriver-manager...")     
            service = ChromeService(ChromeDriverManager(chrome_type=ChromeType.BRAVE).install())
            self.driver = webdriver.Chrome(service=service, options=brave_options)
            print("✅ Brave driver initialized successfully with webdriver-manager")
        except Exception as e:
            print(f"⚠️ webdriver-manager approach failed: {e}")
            print("🔄 Trying system Chrome driver for Brave...")
            try:
                # Fallback to system chromedriver
                self.driver = webdriver.Chrome(options=brave_options)
                print("✅ Brave browser initialized successfully with system driver")
            except Exception as e2:
                print(f"❌ Brave browser failed: {e2}")
                self._print_brave_troubleshooting()
                raise OSError(f"Failed to initialize Chrome driver: {e2}")
        
        self.wait = WebDriverWait(self.driver, wait_time)

    def _find_brave_executable(self):
        """Find Brave browser executable path on different operating systems"""
        brave_paths = []
        system = platform.system()
        if system == "Windows":
            try: # Try using 'where' command
                result = subprocess.run(['where', 'brave-browser'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0]  # Take first result
            except:
                pass

            brave_paths = [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Users\{}\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe".format(os.getenv('USERNAME')),
            ]
        elif system == "Darwin":  # macOS
            brave_paths = [
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "/Applications/Brave Browser Nightly.app/Contents/MacOS/Brave Browser",
            ]
        elif system == "Linux":
            try: # Try using 'which' command
                result = subprocess.run(['which', 'brave-browser'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass

            brave_paths = [
                "/etc/alternatives/brave-browser",
                "/opt/brave.com/brave/brave-browser"
                "/usr/bin/brave-browser",
                "/usr/bin/brave-browser-stable",
                "/usr/bin/brave",
                "/snap/bin/brave",
                "/opt/brave.com/brave/brave-browser",
            ]
        
        for path in brave_paths:
            if os.path.exists(path):
                return path 
        return None

    def _print_brave_troubleshooting(self):
        """Print helpful troubleshooting information for Brave issues"""
        print("\n🔧 Brave Browser Troubleshooting:")
        print("1. Make sure Brave browser is installed")
        print("2. Brave uses ChromeDriver, so ChromeDriver must be installed")
        print("3. Installation methods:")
        print("   - Windows: Download from https://brave.com/download/")
        print("   - macOS: brew install --cask brave-browser")
        print("   - Linux: sudo apt install brave-browser")
        print("4. Or download ChromeDriver manually from: https://chromedriver.chromium.org/")
        print("5. Try: pip install webdriver-manager")

    def get_browser_info(self):
        """Get information about the current browser and driver"""
        if not self.driver:
            return "No browser initialized"
        
        try:
            capabilities = self.driver.capabilities
            browser_name = capabilities.get('browserName', 'Unknown')
            browser_version = capabilities.get('browserVersion', 'Unknown')
            driver_version = capabilities.get('chrome', {}).get('chromedriverVersion', 
                              capabilities.get('moz:geckodriverVersion', 
                              capabilities.get('ms:edgeChromium', {}).get('msedgedriverVersion', 'Unknown')))
            
            return f"Browser: {browser_name} {browser_version}, Driver: {driver_version}"
        except Exception as e:
            return f"Browser info unavailable: {e}"

    def navigate_to_url(self, url, take_screenshot=False):
        """Navigates to the given URL and waits for the page body to be present."""
        try:
            print(f"🌐 Navigating to: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("✅ Webpage loaded successfully")
            
            # Take a screenshot for debugging
            if take_screenshot: 
                # Create a simple, safe filename for the screenshot
                filename = url.split('//')[-1].split('/')[0].replace('.', '_')
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"{filename}.png"))
                print(f"📸 Screenshot saved: {filename}.png")
            return True
        except TimeoutException:
            print("❌ Timeout loading webpage")
            return False
        except Exception as e:
            print(f"❌ Error loading webpage: {str(e)}")
            return False
    
    def wait_for_page_to_load(self, timeout=3, selectors=[], screenshot_name=None):
        """
        Wait for the page to load by checking the readyState and/or specific selectors.
        """
        try:
            print("⏳ Waiting for page to load...")
            for selector in selectors:
                try:
                    element = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print(f"✅ Found element indicating page load: {selector}")
                    break
                except TimeoutException:
                    print(f"⚠️  Element not found (may not be critical): {selector}")
                    continue
            else:
                try:
                    WebDriverWait(self.driver, timeout).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    print("✅ Page has loaded")
                except TimeoutException:
                    print("❌ Timeout waiting for page to load")
                    return False
            
            if screenshot_name: 
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"{screenshot_name}.png"))
                
            return True
        except Exception as e:
            print(f"❌ Error waiting for page to load: {str(e)}")
            return False

    def find_and_click_button(self, button_selectors, in_page_wait=0, screenshot_name=None):
        """Find and click a button using multiple selectors and robust click methods."""
        try:
            print("🔍 Looking for selected button...")
            button = None
            for selector in button_selectors:
                try:
                    print(f"   Trying selector: {selector}")
                    button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"✅ Found button with selector: {selector}")
                    break
                except TimeoutException:
                    print(f"   ❌ Selector {selector} not found or not clickable")
                    continue
                
            if not button:
                print("❌ Could not find the button with any selector")
                self.debug_available_buttons()
                return False
            
            self.debug_element_info(button)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(1)
            if screenshot_name: 
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"before_{screenshot_name}.png"))
            
            print("🖱️  Clicking button...")
            if self.try_click_methods(button):
                print("✅ Button clicked successfully")
            
            if in_page_wait > 0:
                print(f"⏳ Waiting for in-page change for {in_page_wait} seconds...")
                time.sleep(in_page_wait)
            else:
                self.wait_for_page_to_load()
            
            current_url = self.driver.current_url
            print(f"📍 Current URL after click: {current_url}")
            if screenshot_name:
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"after_{screenshot_name}.png"))
            return True        
        except TimeoutException:
            print("❌ Timeout waiting for button")
            self.debug_available_buttons()
            return False
        except Exception as e:
            print(f"❌ Error clicking button: {str(e)}")
            return False

    def click_link(self, link_selectors, in_page_wait=0, screenshot_name=None):
        """Click the specified link to open dropdown or navigate."""
        try:
            print("🔍 Looking for specified link...")
            link = None
            for selector in link_selectors:
                try:
                    print(f"   Trying selector: {selector}")
                    link = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"✅ Found link with selector: {selector}")
                    break
                except TimeoutException:
                    print(f"   ❌ Selector {selector} not found or not clickable")
                    continue
            
            if not link:
                print("❌ Could not find link with any selector")
                # self.debug_available_links() # Assuming this is a generic debug helper
                return False
            
            # ... (rest of the click_link logic remains the same) ...
            link_details = {
                'text': link.text,
                'classes': link.get_attribute('class'),
                'href': link.get_attribute('href')
            }
            print(f"📋 Link details:")
            for key, val in link_details.items():
                print(f"   {key.capitalize()}: '{val}'")
            
            if 'open' in link_details['classes']:
                print("ℹ️  Dropdown is already open")
                return True
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
            time.sleep(1)
            
            if screenshot_name:
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"before_{screenshot_name}.png"))
            
            print("🖱️  Clicking link...")
            link.click()
            
            if in_page_wait > 0:
                print("⏳ Waiting for in-page changes...")
                time.sleep(in_page_wait)
            else:
                self.wait_for_page_to_load()
            
            if screenshot_name:
                self.driver.save_screenshot(os.path.join(self.screenshot_dir, f"after_{screenshot_name}.png"))
                
            return True
        except TimeoutException:
            print("❌ Timeout waiting for link")
            return False
        except Exception as e:
            print(f"❌ Error clicking link: {str(e)}")
            return False

    def get_page_title_and_url(self, timeout=2):
        """Get current page information."""
        title = self.driver.title
        url = self.driver.current_url
        print(f"📄 Page Title: {title}")
        print(f"🔗 Current URL: {url}")
        time.sleep(timeout)
        return title, url
    
    def download_file(self, download_dict, file_type="xls"):
        """Attempt to download the file using various methods via WebFileLoader."""
        if file_type.lower() == "xls":
            file = self.file_loader.download_xls_file(download_dict)
        elif file_type.lower() == "pdf":
             file = self.file_loader.download_pdf_file(download_dict)
        else:
            print(f"❌ Unsupported file type: {file_type}")
            return None
        return file

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            print("🔒 Browser closed")
            return True
        return False

    def try_click_methods(self, element):
        """Try different methods to click the element (Direct, JS, ActionChains)."""
        methods = [
            ("JavaScript click", lambda: self.driver.execute_script("arguments[0].click();", element)),
            ("ActionChain click", lambda: ActionChains(self.driver).move_to_element(element).click().perform()),
            ("Direct click", lambda: element.click())
        ]
        for method_name, click_func in methods:
            try:
                print(f"   Trying {method_name}...")
                click_func()
                time.sleep(1)
                print(f"   ✅ {method_name} successful")
                return True
            except Exception as e:
                print(f"   ❌ {method_name} failed: {str(e)}")
                continue
        return False

    def debug_available_buttons(self):
        """Debug function to see what buttons are available on the page."""
        try:
            print("\n🔍 DEBUG: Looking for available buttons on page...")
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            print(f"Found {len(inputs)} input elements:")
            for i, input_elem in enumerate(inputs[:10]):
                try:
                    input_type = input_elem.get_attribute('type')
                    input_name = input_elem.get_attribute('name')
                    input_id = input_elem.get_attribute('id')
                    input_class = input_elem.get_attribute('class')
                    input_value = input_elem.get_attribute('value')
                    print(f"  {i+1}. Type:{input_type}, Name:{input_name}, ID:{input_id}")
                    print(f"      Class:{input_class}, Value:{input_value}")
                except:
                    continue
            
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            print(f"\nFound {len(buttons)} button elements:")
            for i, button in enumerate(buttons[:5]):
                try:
                    button_text = button.text
                    button_class = button.get_attribute('class')
                    button_onclick = button.get_attribute('onclick')
                    print(f"  {i+1}. Text:{button_text}, Class:{button_class}")
                    print(f"      OnClick:{button_onclick}")
                except:
                    continue
        except Exception as e:
            print(f"❌ Error in debug function: {str(e)}")

    def debug_input_fields(self):
        """Debug function to see what input fields are available on the page."""
        try:
            print("\n🔍 DEBUG: Looking for available input fields on page...")
            input_fields = self.driver.find_elements(By.TAG_NAME, "input")
            text_fields = [f for f in input_fields if f.get_attribute('type') in ['text', 'password', 'tel', 'email']]
            print(f"Found {len(text_fields)} text-like input elements:")
            for i, field in enumerate(text_fields[:10]): # Limit to first 10
                try:
                    field_type = field.get_attribute('type')
                    field_name = field.get_attribute('name')
                    field_id = field.get_attribute('id')
                    field_placeholder = field.get_attribute('placeholder')
                    print(f"  {i+1}. Type:{field_type}, Name:{field_name}, ID:{field_id}, Placeholder:'{field_placeholder}'")
                except:
                    continue
        except Exception as e:
            print(f"❌ Error in debug input fields function: {str(e)}")

    def debug_element_info(self, element):
        """Debug information about the element."""
        try:
            print(f"📋 Element details:")
            print(f"   Tag: {element.tag_name}")
            print(f"   Text: {element.text.strip()}")
            print(f"   Href: {element.get_attribute('href')}")
            print(f"   OnClick: {element.get_attribute('onclick')}")
            print(f"   Class: {element.get_attribute('class')}")
            print(f"   Style: {element.get_attribute('style')}")
            print(f"   Displayed: {element.is_displayed()}")
            print(f"   Enabled: {element.is_enabled()}")
        except Exception as e:
            print(f"   ❌ Could not get element info: {str(e)}")

    def enter_password_virtual_keyboard(self, password):
        """
        Generic method to enter a password using a virtual/onscreen keyboard based on common patterns.
        """
        wait = WebDriverWait(self.driver, 10)
        print("⌨️  Attempting to enter password via virtual keyboard...")
        for digit in password:
            try:
                # Wait for the button to be clickable using a generic selector pattern
                digit_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, 
                        f"//div[contains(@class, 'VirtualKbd_Button') and contains(@onclick, 'btClick(this, {digit})')]"))
                )
                
                digit_button.click()
                time.sleep(0.3)
            except Exception as e:
                print(f"❌ Error clicking digit {digit}: {e}")
                return False
        
        # Click Enter button (assuming a common ID for submission)
        try:
            enter_button = wait.until(
                EC.element_to_be_clickable((By.ID, "loginForm:submit"))
            )
            enter_button.click()
            print("✅ Clicked Enter button")
            return True
        except Exception as e:
            print(f"❌ Error clicking Enter button: {e}")
            return False
