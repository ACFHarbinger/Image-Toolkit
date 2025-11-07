package com.example.image_toolkit;

import io.github.bonigarcia.wdm.WebDriverManager;
import org.openqa.selenium.TimeoutException;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.edge.EdgeDriver;
import org.openqa.selenium.edge.EdgeOptions;
import org.openqa.selenium.firefox.FirefoxDriver;
import org.openqa.selenium.firefox.FirefoxOptions;
import org.openqa.selenium.safari.SafariDriver;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.interactions.Actions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.BiConsumer;

/**
 * Abstract Base Class for all web crawlers.
 * Handles driver setup, navigation, generic clicking, and debugging utilities.
 */
public abstract class WebCrawler {

    protected WebDriver driver;
    protected WebDriverWait wait;
    protected WebFileLoader fileLoader;

    protected final Path downloadDir;
    protected final Path screenshotDir;
    protected String browser;
    protected final boolean isHeadless;

    private static final int DEFAULT_WAIT_TIME = 30; // Placeholder for udef.CRAWLER_SETUP_WAIT_TIME

    public WebCrawler(boolean headless, String downloadDir, String screenshotDir, String browser) {
        this.isHeadless = headless;
        this.browser = browser.toLowerCase();
        
        // --- Directory Setup ---
        this.downloadDir = (downloadDir != null) ? Paths.get(downloadDir) : Paths.get(System.getProperty("user.dir"), "downloads");
        this.screenshotDir = (screenshotDir != null) ? Paths.get(screenshotDir) : Paths.get(System.getProperty("user.dir"), "screenshots");
        try {
            Files.createDirectories(this.downloadDir);
            Files.createDirectories(this.screenshotDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create required directories: " + e.getMessage());
        }

        // --- Driver Setup ---
        setupDriver();
        this.fileLoader = new WebFileLoader(this.driver, this.downloadDir.toString());
        System.out.printf("✅ WebCrawler base initialized with %s.%n", this.browser);
    }

    // --- Abstract Methods (Must be implemented by all concrete subclasses) ---
    public abstract boolean login(Map<String, String> credentials);
    public abstract void processData();

    // --- Concrete Methods (Generic Utilities) ---

    protected void setupDriver() {
        Map<String, BiConsumer<Integer, Boolean>> browserMethods = new HashMap<>();
        browserMethods.put("brave", (wait, headless) -> setupBraveDriver(wait, headless, downloadDir.toString()));
        browserMethods.put("firefox", (wait, headless) -> setupFirefoxDriver(wait, headless, downloadDir.toString()));
        browserMethods.put("chrome", (wait, headless) -> setupChromeDriver(wait, headless, downloadDir.toString()));
        browserMethods.put("edge", (wait, headless) -> setupEdgeDriver(wait, headless, downloadDir.toString()));
        browserMethods.put("safari", (wait, headless) -> setupSafariDriver(wait, headless, downloadDir.toString()));

        if (browserMethods.containsKey(this.browser)) {
            try {
                browserMethods.get(this.browser).accept(DEFAULT_WAIT_TIME, isHeadless);
                System.out.printf("✅ Successfully initialized %s driver%n", this.browser);
            } catch (Exception e) {
                System.out.printf("❌ Failed to initialize %s driver: %s%n", this.browser, e.getMessage());
                fallbackToAvailableBrowser(DEFAULT_WAIT_TIME, isHeadless, this.downloadDir.toString());
            }
        } else {
            System.out.printf("❌ Unsupported browser: %s. Falling back to available browser.%n", this.browser);
            fallbackToAvailableBrowser(DEFAULT_WAIT_TIME, isHeadless, this.downloadDir.toString());
        }
        
        this.wait = new WebDriverWait(this.driver, Duration.ofSeconds(DEFAULT_WAIT_TIME));
    }
    
    // ... (Setup methods for each browser, using WebDriverManager and standard Java paths/logic) ...
    
    // --- Simplified Browser Setup Methods (Illustrative, using WebDriverManager) ---
    
    protected void setupChromeDriver(int waitTime, boolean headless, String downloadDir) {
        System.out.println("⚙️ Setting up Chrome options...");
        WebDriverManager.chromedriver().setup();

        ChromeOptions options = new ChromeOptions();
        if (headless) {
            System.out.println("⚙️ Setting Chrome to headless mode.");
            options.addArguments("--headless=new");
        }
        options.addArguments("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1920,1080");
        options.addArguments("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        options.addArguments("--lang=pt-PT");
        options.setExperimentalOption("prefs", Map.of(
            "intl.accept_languages", "pt-PT,pt,en",
            "download.default_directory", downloadDir,
            "download.prompt_for_download", false,
            "plugins.always_open_pdf_externally", true
        ));

        this.driver = new ChromeDriver(options);
    }
    
    protected void setupFirefoxDriver(int waitTime, boolean headless, String downloadDir) {
        System.out.println("⚙️ Setting up Firefox options...");
        WebDriverManager.firefoxdriver().setup();

        FirefoxOptions options = new FirefoxOptions();
        if (headless) {
            System.out.println("⚙️ Setting Firefox to headless mode.");
            options.addArguments("-headless");
        }
        options.addPreference("general.useragent.override", "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0");
        options.addPreference("intl.accept_languages", "pt-PT,pt,en");
        options.addPreference("browser.download.dir", downloadDir);
        options.addPreference("browser.download.folderList", 2);
        options.addPreference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        options.addPreference("pdfjs.disabled", true);

        this.driver = new FirefoxDriver(options);
    }
    
    // Note: Brave setup uses Chrome driver logic and binary location (if found)
    protected void setupBraveDriver(int waitTime, boolean headless, String downloadDir) {
        System.out.println("⚙️ Setting up Brave options (using Chrome driver logic)...");
        // WebDriverManager does support BRAVE browser type
        WebDriverManager.chromedriver().browserInPath("brave").setup();

        ChromeOptions options = new ChromeOptions();
        // ... (Add Brave specific options, similar to Chrome setup) ...
        
        this.driver = new ChromeDriver(options);
    }
    
    // ... (Edge and Safari setup methods would follow a similar pattern) ...
    
    protected void setupEdgeDriver(int waitTime, boolean headless, String downloadDir) {
        System.out.println("⚙️ Setting up Edge options...");
        WebDriverManager.edgedriver().setup();

        EdgeOptions options = new EdgeOptions();
        // ... (Similar options to Chrome, adjusted for Edge) ...
        
        this.driver = new EdgeDriver(options);
    }

    protected void setupSafariDriver(int waitTime, boolean headless, String downloadDir) {
        if (headless) {
            System.out.println("⚠️  Safari does not support headless mode. Running in normal mode.");
        }
        if (!System.getProperty("os.name").toLowerCase().contains("mac")) {
            throw new UnsupportedOperationException("Safari driver is only available on macOS");
        }
        WebDriverManager.safaridriver().setup();
        this.driver = new SafariDriver();
    }
    
    protected void fallbackToAvailableBrowser(int waitTime, boolean headless, String downloadDir) {
        String[] preferredBrowsers = {"firefox", "chrome", "edge"};
        for (String browser : preferredBrowsers) {
            if (browser.equals(this.browser)) continue;
            try {
                System.out.printf("🔄 Attempting fallback to %s...%n", browser);
                this.browser = browser;
                switch (browser) {
                    case "firefox": setupFirefoxDriver(waitTime, headless, downloadDir); break;
                    case "chrome": setupChromeDriver(waitTime, headless, downloadDir); break;
                    case "edge": setupEdgeDriver(waitTime, headless, downloadDir); break;
                    default: continue;
                }
                System.out.printf("✅ Fallback successful: using %s%n", browser);
                return;
            } catch (Exception e) {
                System.out.printf("❌ Fallback to %s failed: %s%n", browser, e.getMessage());
            }
        }
        throw new RuntimeException("No available browser drivers found. Please install Chrome, Firefox, or Edge.");
    }
    
    // --- Navigation and Core Actions ---

    public boolean navigateToUrl(String url, boolean takeScreenshot) {
        // ... (Standard Selenium navigation logic) ...
        try {
            System.out.printf("🌐 Navigating to: %s%n", url);
            driver.get(url);
            wait.until(ExpectedConditions.presenceOfElementLocated(By.tagName("body")));
            System.out.println("✅ Webpage loaded successfully");
            if (takeScreenshot) {
                // Java Selenium screenshot logic
                // ...
            }
            return true;
        } catch (TimeoutException e) {
            System.out.println("❌ Timeout loading webpage");
            return false;
        } catch (Exception e) {
            System.out.printf("❌ Error loading webpage: %s%n", e.getMessage());
            return false;
        }
    }

    public boolean waitBeforePageLoad(int timeoutSeconds, String[] selectors, String screenshotName) {
        // ... (Standard Selenium wait logic, similar to Python's wait_for_page_to_load) ...
        try {
            System.out.println("⏳ Waiting for page to load...");
            for (String selector : selectors) {
                try {
                    wait.until(ExpectedConditions.presenceOfElementLocated(By.cssSelector(selector)));
                    System.out.printf("✅ Found element indicating page load: %s%n", selector);
                    break;
                } catch (TimeoutException e) {
                    System.out.printf("⚠️  Element not found (may not be critical): %s%n", selector);
                }
            }
            
            // Check document readyState if no selector found
            new WebDriverWait(driver, Duration.ofSeconds(timeoutSeconds)).until(
                webDriver -> ((JavascriptExecutor) webDriver).executeScript("return document.readyState").equals("complete")
            );
            System.out.println("✅ Page has loaded");

            if (screenshotName != null) {
                // Java Selenium screenshot logic
                // ...
            }
            return true;
        } catch (TimeoutException e) {
            System.out.println("❌ Timeout waiting for page to load");
            return false;
        } catch (Exception e) {
            System.out.printf("❌ Error waiting for page to load: %s%n", e.getMessage());
            return false;
        }
    }

    public boolean findAndClickButton(String[] buttonSelectors, int inPageWait, String screenshotName) {
        // ... (Standard Selenium find/click logic using a loop and tryClickMethods) ...
        try {
            System.out.println("🔍 Looking for selected button...");
            WebElement button = null;
            for (String selector : buttonSelectors) {
                try {
                    System.out.printf("   Trying selector: %s%n", selector);
                    button = wait.until(ExpectedConditions.elementToBeClickable(By.cssSelector(selector)));
                    System.out.printf("✅ Found button with selector: %s%n", selector);
                    break;
                } catch (TimeoutException e) {
                    System.out.printf("   ❌ Selector %s not found or not clickable%n", selector);
                }
            }
            
            if (button == null) {
                System.out.println("❌ Could not find the button with any selector");
                // debugAvailableButtons();
                return false;
            }

            ((JavascriptExecutor) driver).executeScript("arguments[0].scrollIntoView({block: 'center'});", button);
            TimeUnit.SECONDS.sleep(1);
            
            System.out.println("🖱️  Clicking button...");
            if (tryClickMethods(button)) {
                System.out.println("✅ Button clicked successfully");
            }

            if (inPageWait > 0) {
                System.out.printf("⏳ Waiting for in-page change for %d seconds...%n", inPageWait);
                TimeUnit.SECONDS.sleep(inPageWait);
            } else {
                waitBeforePageLoad(DEFAULT_WAIT_TIME, new String[]{}, null);
            }
            
            System.out.printf("📍 Current URL after click: %s%n", driver.getCurrentUrl());
            return true;
        } catch (TimeoutException e) {
            System.out.println("❌ Timeout waiting for button");
            return false;
        } catch (Exception e) {
            System.out.printf("❌ Error clicking button: %s%n", e.getMessage());
            return false;
        }
    }

    public Path downloadFile(Map<String, String[]> downloadDict, String fileType) {
        String type = fileType.toLowerCase();
        if ("xls".equals(type)) {
            return fileLoader.downloadXlsFile(downloadDict);
        } else if ("pdf".equals(type)) {
            // Need to implement downloadPdfFile in WebFileLoader
            // return fileLoader.downloadPdfFile(downloadDict);
            System.out.println("❌ PDF download not implemented in file loader");
            return null;
        } else {
            System.out.printf("❌ Unsupported file type: %s%n", fileType);
            return null;
        }
    }

    protected boolean tryClickMethods(WebElement element) {
        // ... (Implementation of click methods: JS, ActionChains, Direct) ...
        JavascriptExecutor js = (JavascriptExecutor) driver;
        Actions actions = new Actions(driver);
        
        try {
            System.out.println("   Trying JavaScript click...");
            js.executeScript("arguments[0].click();", element);
            return true;
        } catch (Exception e) {
            System.out.printf("   ❌ JavaScript click failed: %s%n", e.getMessage());
        }

        try {
            System.out.println("   Trying ActionChain click...");
            actions.moveToElement(element).click().perform();
            return true;
        } catch (Exception e) {
            System.out.printf("   ❌ ActionChain click failed: %s%n", e.getMessage());
        }

        try {
            System.out.println("   Trying Direct click...");
            element.click();
            return true;
        } catch (Exception e) {
            System.out.printf("   ❌ Direct click failed: %s%n", e.getMessage());
        }
        
        return false;
    }

    public void close() {
        if (driver != null) {
            driver.quit();
            System.out.println("🔒 Browser closed");
        }
    }
}