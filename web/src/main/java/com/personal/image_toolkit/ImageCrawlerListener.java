package com.example.image_toolkit;

/**
 * Interface to replace PySide6 Signals for ImageCrawler status updates.
 */
public interface ImageCrawlerListener {
    void onProgress(int current, int total);
    void onStatus(String message);
    void onImageSaved(String savedFilePath);
}