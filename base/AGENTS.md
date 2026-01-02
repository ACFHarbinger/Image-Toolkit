# Base Directory Agents

The `base` directory contains the high-performance Rust implementation of the core logic for the Image Toolkit. It is designed to expose a Foreign Function Interface (FFI) to the Python backend using PyO3, as well as providing standalone utilities.

## Core Agents (`src/core`)
These modules handle computationally intensive tasks such as image processing and file system operations, leveraging Rust's concurrency capabilities (Rayon) for performance.

- **`file_system`**: Performs high-speed recursive file scanning, filtering, and batch deletion operations.
- **`image_converter`**: Handles parallel image format conversion, resizing, cropping, and aspect-ratio maintenance.
- **`image_finder`**: Implements algorithms for identifying duplicate images (exact match) and similar images (perceptual hashing).
- **`image_merger`**: Provides functionality to stitch multiple images together into horizontal strips, vertical strips, or grids.
- **`video_converter`**: Wraps FFmpeg for efficient video thumbnail extraction.
- **`wallpaper`**: Integrates with desktop environments (KDE Plasma, GNOME) to set wallpapers programmatically.

## Web Agents (`src/web`)
These modules manage all network interactions, including API-based crawling, browser automation, and cloud synchronization.

### Image Board Crawlers
- **`image_board_crawler`**: Defines the base `Crawler` trait and implements the generic `BoardCrawler` struct which handles rate limiting, pagination, and download queues.
- **`danbooru`**: Implementation for Danbooru-style APIs.
- **`gelbooru`**: Implementation for Gelbooru-style APIs.
- **`sankaku`**: Implementation for Sankaku Complex API (v2).

### Browser Automation (Selenium)
- **`crawler`**: Manages the life-cycle of the headless Selenium WebDriver (supported browsers: Chrome, Firefox, Brave).
- **`image_crawler`**: A generic crawler that can execute a sequence of actions (click, scroll, wait) to scrape images from dynamic websites.
- **`reverse_image_search`**: Automates the process of uploading a local image to Google Images and scraping the visual matches.
- **`file_loader`**: Observes directory changes to detect when browser-initiated downloads complete.

### Cloud Synchronization
- **`sync`**: Core synchronization logic (`SyncRunner`) that diffs local and remote states.
- **`dropbox_sync`**: Dropbox API v2 implementation.
- **`google_drive_sync`**: Google Drive API v3 implementation.
- **`one_drive_sync`**: Microsoft Graph API implementation for OneDrive.

### Utilities
- **`web_requests`**: A configurable executor for running sequences of HTTP requests (GET/POST) and performing actions on the responses.

## Utility Agents (`src/utils`)
Standalone binaries that run independently of the main Python application.

- **`slideshow_daemon`**: A background process that manages wallpaper slideshows. It supports per-monitor configuration, image queues, and configurable intervals.

## Interface
- **`lib.rs`**: The central entry point for the library. It defines the `#[pymodule]` and registers all Rust functions to be accessible from the `base` Python package.
