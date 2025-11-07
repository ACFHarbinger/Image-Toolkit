package com.example.image_toolkit;

import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/**
 * Downloads all images from a webpage using Selenium and a Java HTTP client.
 * Implements the WebCrawler abstract class.
 */
public class ImageCrawler extends WebCrawler {

    private final String targetUrl;
    private final int skipFirst;
    private final int skipLast;
    private final ImageCrawlerListener listener;

    public ImageCrawler(String url, int skipFirst, int skipLast, boolean headless, String downloadDir, String screenshotDir, String browser, ImageCrawlerListener listener) {
        super(headless, downloadDir, screenshotDir, browser);
        this.targetUrl = url;
        this.skipFirst = skipFirst;
        this.skipLast = skipLast;
        this.listener = listener;
        System.out.printf("ImageCrawler ready: %s%n", url);
    }

    @Override
    public boolean login(Map<String, String> credentials) {
        listener.onStatus("No login needed.");
        return true;
    }
    
    // Helper to get a unique filename like: cat.jpg -> cat (1).jpg
    private Path getUniqueFilename(Path filepath) {
        Path parent = filepath.getParent();
        String filename = filepath.getFileName().toString();
        int dotIndex = filename.lastIndexOf('.');
        String base = (dotIndex == -1) ? filename : filename.substring(0, dotIndex);
        String ext = (dotIndex == -1) ? "" : filename.substring(dotIndex);
        
        int counter = 1;
        Path newPath = filepath;
        while (Files.exists(newPath)) {
            newPath = parent.resolve(String.format("%s (%d)%s", base, counter, ext));
            counter++;
        }
        return newPath;
    }

    @Override
    public void processData() {
        listener.onStatus("Loading page...");
        if (!navigateToUrl(targetUrl, false)) {
            listener.onStatus("Failed to load page.");
            return;
        }

        waitBeforePageLoad(10, new String[]{}, null);
        listener.onStatus("Scanning for images...");

        try {
            List<WebElement> images = driver.findElements(By.tagName("img"));
            int totalFound = images.size();
            int skipTotal = skipFirst + skipLast;
            
            if (skipTotal >= totalFound) {
                listener.onStatus("Not enough images to skip.");
                return;
            }

            // Sublist equivalent to Python slice images[skipFirst:-skipLast]
            List<WebElement> imagesToProcess = images.subList(skipFirst, totalFound - skipLast);
            int totalImagesToDownload = imagesToProcess.size();

            listener.onProgress(0, totalImagesToDownload);
            listener.onStatus(String.format("Found %d images. Skipping %d. Downloading %d...", 
                                            totalFound, skipTotal, totalImagesToDownload));

            Set<String> uniqueUrls = imagesToProcess.stream()
                .map(img -> img.getAttribute("src"))
                .filter(src -> src != null && !src.startsWith("data:"))
                .map(src -> {
                    try {
                        return new URL(new URL(driver.getCurrentUrl()), src).toExternalForm();
                    } catch (Exception e) {
                        return null; // Ignore invalid URLs
                    }
                })
                .filter(url -> url != null)
                .collect(Collectors.toSet());

            listener.onStatus(String.format("Downloading %d unique images...", uniqueUrls.size()));
            
            AtomicLong downloadedCount = new AtomicLong(0);

            for (String url : uniqueUrls) {
                if (_downloadImageFromUrl(url)) {
                    downloadedCount.incrementAndGet();
                    listener.onProgress((int) downloadedCount.get(), uniqueUrls.size());
                }
                TimeUnit.MILLISECONDS.sleep(100);
            }

            listener.onStatus(String.format("Downloaded %d images! Skipped %d.", downloadedCount.get(), skipTotal));

        } catch (Exception e) {
            listener.onStatus("Error: " + e.getMessage());
        }
    }

    private boolean _downloadImageFromUrl(String url) {
        try {
            URI uri = new URI(url);
            String path = uri.getPath();
            String filename = path.substring(path.lastIndexOf('/') + 1).split("\\?")[0];
            
            if (filename.isEmpty() || !filename.contains(".")) {
                filename = String.format("image_%d.jpg", System.currentTimeMillis());
            }

            Path savePath = downloadDir.resolve(filename);
            savePath = getUniqueFilename(savePath);

            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(15))
                    .build();

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(uri)
                    .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                    .GET()
                    .build();

            HttpResponse<InputStream> response = client.send(request, HttpResponse.BodyHandlers.ofInputStream());

            if (response.statusCode() == 200) {
                try (InputStream is = response.body()) {
                    Files.copy(is, savePath);
                }
                listener.onImageSaved(savePath.toString());
                return true;
            } else {
                throw new IOException("HTTP error code: " + response.statusCode());
            }

        } catch (Exception e) {
            System.err.printf("Failed %s: %s%n", url, e.getMessage());
            return false;
        }
    }

    public int run() {
        try {
            login(null);
            processData();
            return 0;
        } finally {
            close();
        }
    }
}