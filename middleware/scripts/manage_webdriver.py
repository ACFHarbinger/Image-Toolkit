import os
import subprocess
import sys

from webdriver_manager.chrome import ChromeDriverManager


def install_driver():
    """Download and install the correct chromedriver for the system."""
    print("🌐 Downloading/Updating WebDriver...")
    try:
        # This will download the driver if it's missing or outdated
        path = ChromeDriverManager().install()
        print(f"✅ Driver ready at: {path}")
        return path
    except Exception as e:
        print(f"❌ Failed to install driver: {e}")
        # Try to find an existing one as fallback?
        # No, better to fail and inform the user.
        sys.exit(1)

def start_driver(port=9515, browser="brave"):
    """Start the chromedriver server on the specified port for the given browser."""
    driver_path = install_driver()

    # Ensure the driver is executable
    if not os.access(driver_path, os.X_OK):
        print(f"🛠️ Setting executable permissions on {driver_path}...")
        os.chmod(driver_path, 0o755)

    print(f"🌐 Starting Managed WebDriver service for {browser.title()} on port {port}...")
    try:
        # Execute the driver binary
        # Use --port flag as required by standard chromedriver
        subprocess.run([driver_path, f"--port={port}"])
    except KeyboardInterrupt:
        print("\n🛑 WebDriver stopped.")
    except Exception as e:
        print(f"❌ Failed to start driver: {e}")
        sys.exit(1)

if __name__ == "__main__":
    browser_arg = "brave"
    for arg in sys.argv:
        if arg.startswith("--browser="):
            browser_arg = arg.split("=", 1)[1].strip()

    if len(sys.argv) > 1 and sys.argv[1] == "start":
        start_driver(browser=browser_arg)
    else:
        # Default to just installing/updating
        install_driver()
