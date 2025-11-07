package com.example.image_toolkit;

import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * Handles file downloading using various Selenium/JavaScript methods
 * and waits for the download to complete.
 */
public class WebFileLoader {
    private final WebDriver driver;
    private final Path downloadDir;
    private final Set<String> initialFiles;
    private final Map<String, DownloadMethod> downloadMethods;

    @FunctionalInterface
    private interface DownloadMethod {
        boolean download(String[] selectors);
    }

    public WebFileLoader(WebDriver driver, String downloadDir) {
        this.driver = driver;
        this.downloadDir = Paths.get(downloadDir);
        this.downloadMethods = new HashMap<>();
        this.downloadMethods.put("javascript", this::downloadViaJavascript);
        this.downloadMethods.put("element_click", this::downloadViaElementClick);
        this.downloadMethods.put("function_call", this::downloadViaFunctionCall);

        try (Stream<Path> files = Files.list(this.downloadDir)) {
            this.initialFiles = files
                    .filter(Files::isRegularFile)
                    .map(p -> p.getFileName().toString())
                    .collect(Collectors.toSet());
        } catch (IOException e) {
            throw new RuntimeException("Failed to list files in download directory.", e);
        }
    }

    private boolean downloadViaJavascript(String[] selectors) {
        System.out.println("   Trying method: _download_via_javascript");
        JavascriptExecutor js = (JavascriptExecutor) driver;
        for (String selector : selectors) {
            try {
                js.executeScript(selector);
                TimeUnit.SECONDS.sleep(3);
                return true;
            } catch (Exception e) {
                // System.out.println("   JS execution failed for selector: " + selector);
                continue;
            }
        }
        System.out.println("   JavaScript execution failed.");
        return false;
    }

    private boolean downloadViaElementClick(String[] selectors) {
        System.out.println("   Trying method: _download_via_element_click");
        JavascriptExecutor js = (JavascriptExecutor) driver;
        for (String selector : selectors) {
            try {
                By by;
                if (selector.startsWith("//")) {
                    by = By.xpath(selector);
                } else {
                    by = By.cssSelector(selector);
                }
                WebElement element = driver.findElement(by);

                // Use JS click for robustness, similar to Python implementation
                js.executeScript("arguments[0].click();", element);
                TimeUnit.SECONDS.sleep(3);
                return true;
            } catch (Exception e) {
                // System.out.println("   Element click failed for selector: " + selector);
                continue;
            }
        }
        System.out.println("   Element click failed.");
        return false;
    }

    private boolean downloadViaFunctionCall(String[] selectors) {
        System.out.println("   Trying method: _download_via_function_call");
        JavascriptExecutor js = (JavascriptExecutor) driver;
        for (String call : selectors) {
            try {
                js.executeScript(call);
                TimeUnit.SECONDS.sleep(2);
                // If no error, assume it worked
                return true;
            } catch (Exception e) {
                // System.out.println("   Function call failed for: " + call);
                continue;
            }
        }
        System.out.println("   Function calls failed.");
        return false;
    }

    public Path waitForDownloadToComplete(int timeoutSeconds) {
        System.out.println("⏳ Waiting for download to complete...");
        long lastSize = -1;
        int stableCount = 0;
        long startTime = System.currentTimeMillis();
        long endTime = startTime + (long) timeoutSeconds * 1000;

        while (System.currentTimeMillis() < endTime) {
            try {
                List<Path> newFiles;
                try (Stream<Path> files = Files.list(this.downloadDir)) {
                    newFiles = files
                            .filter(p -> Files.isRegularFile(p) && !initialFiles.contains(p.getFileName().toString()))
                            .collect(Collectors.toList());
                }

                if (!newFiles.isEmpty()) {
                    long currentSize = newFiles.stream()
                            .mapToLong(p -> {
                                try {
                                    return Files.size(p);
                                } catch (IOException e) {
                                    return 0;
                                }
                            })
                            .sum();

                    if (currentSize == lastSize) {
                        stableCount++;
                        if (stableCount >= 2) { // Size stable for 2 seconds
                            for (Path newFile : newFiles) {
                                initialFiles.add(newFile.getFileName().toString());
                            }
                            System.out.printf("✅ Download complete: %d file(s)%n", newFiles.size());
                            return newFiles.get(0); // Return first file
                        }
                    } else {
                        stableCount = 0;
                        lastSize = currentSize;
                    }
                }
                TimeUnit.SECONDS.sleep(1);
            } catch (IOException | InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }

        // Return any found files even if timeout
        try (Stream<Path> files = Files.list(this.downloadDir)) {
            List<Path> newFiles = files
                    .filter(p -> Files.isRegularFile(p) && !initialFiles.contains(p.getFileName().toString()))
                    .collect(Collectors.toList());
            if (!newFiles.isEmpty()) {
                Path filePath = newFiles.get(0);
                System.out.printf("⚠️  Download may be incomplete: %s%n", filePath);
                return filePath;
            }
        } catch (IOException e) {
            // Handle IO exception during final check
        }

        return null;
    }

    public Path downloadXlsFile(Map<String, String[]> downloadDict) {
        System.out.println("💾 Starting XLS file download process...");
        int defaultWaitTime = 30; // Default timeout

        for (Map.Entry<String, String[]> entry : downloadDict.entrySet()) {
            String methodName = entry.getKey();
            String[] selectors = entry.getValue();

            DownloadMethod methodFunc = downloadMethods.get(methodName);
            if (methodFunc == null) {
                throw new IllegalArgumentException("Unknown download method: " + methodName);
            }

            System.out.printf("\n🔄 Trying method: %s%n", methodName);
            boolean result = methodFunc.download(selectors);

            if (result) {
                System.out.printf("✅ %s succeeded%n", methodName);
                
                // Verify download
                Path downloadedFile = waitForDownloadToComplete(defaultWaitTime);
                if (downloadedFile != null) {
                    return downloadedFile;
                } else {
                    System.out.println("⚠️  Approach worked but no file detected");
                }
            } else {
                System.out.printf("❌ %s failed%n", methodName);
            }
        }

        System.out.println("💥 All download methods failed");
        return null;
    }
}