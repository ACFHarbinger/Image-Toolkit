use anyhow::{anyhow, Result};
use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use base64::Engine;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use thirtyfour::prelude::*;
use tokio::runtime::Runtime;

pub struct ImageCrawlerRust {
    pub download_dir: String,
    pub screenshot_dir: String,
    pub browser_name: String,
}

impl ImageCrawlerRust {
    pub fn new(config: &Value) -> Self {
        ImageCrawlerRust {
            download_dir: config
                .get("download_dir")
                .and_then(|v| v.as_str())
                .unwrap_or("downloads")
                .to_string(),
            screenshot_dir: config
                .get("screenshot_dir")
                .and_then(|v| v.as_str())
                .unwrap_or("screenshots")
                .to_string(),
            browser_name: config
                .get("browser")
                .and_then(|v| v.as_str())
                .unwrap_or("brave")
                .to_string(),
        }
    }

    pub fn run(
        &self,
        py: Python<'_>,
        config_json: String,
        callback_obj: Py<PyAny>,
    ) -> PyResult<u32> {
        let config: Value = serde_json::from_str(&config_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
        })?;

        let rt = Runtime::new().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to create runtime: {}",
                e
            ))
        })?;

        let total_downloaded = rt
            .block_on(async { self.run_async(py, config, callback_obj).await })
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Crawler Error: {}", e))
            })?;

        Ok(total_downloaded)
    }

    async fn run_async(
        &self,
        py: Python<'_>,
        config: Value,
        callback_obj: Py<PyAny>,
    ) -> Result<u32> {
        let headless = config
            .get("headless")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let base_url = config
            .get("url")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let mut target_urls = vec![base_url.clone()];
        if let (Some(replace_str), Some(replacements)) = (
            config.get("replace_str").and_then(|v| v.as_str()),
            config.get("replacements").and_then(|v| v.as_array()),
        ) {
            if !replace_str.is_empty() && !replacements.is_empty() {
                for r in replacements {
                    if let Some(r_val) = r.as_str() {
                        let new_url = base_url.replace(replace_str, r_val);
                        // Only add if different from base (which is already first)
                        if new_url != base_url {
                            target_urls.push(new_url);
                        }
                    }
                }
            }
        }

        let mut caps = DesiredCapabilities::chrome();
        if headless {
            caps.add_arg("--headless")?;
        }
        caps.add_arg("--no-sandbox")?;
        caps.add_arg("--disable-dev-shm-usage")?;
        caps.add_arg("--disable-blink-features=AutomationControlled")?;
        caps.add_arg("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")?;
        caps.add_arg("--exclude-switches=enable-automation")?;
        caps.add_arg("--disable-automation")?;
        caps.add_arg("--disable-extensions")?;

        // Note: Assuming chromedriver is running on localhost:9515
        let driver = WebDriver::new("http://localhost:9515", caps).await?;

        // Anti-Detection: Hide webdriver property
        let _ = driver
            .execute(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
                vec![],
            )
            .await;

        emit_status(
            py,
            &callback_obj,
            &format!(
                "Connected to WebDriver. Starting crawl of {} pages...",
                target_urls.len()
            ),
        )?;

        let mut total_downloaded_count = 0;

        for (page_idx, target_url) in target_urls.iter().enumerate() {
            emit_status(
                py,
                &callback_obj,
                &format!(
                    "Navigating to page {}/{}: {}",
                    page_idx + 1,
                    target_urls.len(),
                    target_url
                ),
            )?;

            driver.goto(target_url).await?;

            // Wait for page load and JavaScript to populate images
            tokio::time::sleep(Duration::from_secs(5)).await;

            // Check if browser was redirected to data: URL (anti-bot measure)
            let current_url = driver.current_url().await?;
            if current_url.as_str().starts_with("data:") {
                emit_status(
                    py,
                    &callback_obj,
                    "Browser was redirected to data: URL (anti-bot). Navigating back...",
                )?;
                driver.goto(target_url).await?;
                tokio::time::sleep(Duration::from_secs(5)).await;
            }

            // Retry finding images (they may load via JavaScript)
            let mut total_found = 0;
            // INCREASED RETRIES: User requested "keep trying until success".
            // Increased from 3 to 30 attempts (approx 90-100 seconds max wait).
            for attempt in 0..30 {
                // Check again if redirected
                let current_url = driver.current_url().await?;
                if current_url.as_str().starts_with("data:") {
                    emit_status(
                        py,
                        &callback_obj,
                        &format!(
                            "Still on data: URL after attempt {}. Retrying navigation...",
                            attempt + 1
                        ),
                    )?;
                    driver.goto(target_url).await?;
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }

                let images = driver.find_all(By::Tag("img")).await?;
                total_found = images.len();
                if total_found > 0 {
                    break;
                }

                // If stuck for a while (every 5 attempts), try refreshing the page
                if attempt > 0 && attempt % 5 == 0 {
                    emit_status(
                        py,
                        &callback_obj,
                        &format!(
                            "No images found yet (attempt {}/30). Refreshing page...",
                            attempt + 1
                        ),
                    )?;
                    driver.goto(target_url).await?;
                }

                emit_status(
                    py,
                    &callback_obj,
                    &format!("Waiting for images to load (attempt {}/30)...", attempt + 1),
                )?;
                tokio::time::sleep(Duration::from_secs(3)).await;
            }

            // SCROLL: 4KHD uses lazy loading. Scroll down multiple times.
            emit_status(py, &callback_obj, "Scrolling to trigger lazy loading...")?;
            for _ in 0..5 {
                driver.execute("window.scrollBy(0, 1500);", vec![]).await?;
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
            driver.execute("window.scrollTo(0, 0);", vec![]).await?;
            tokio::time::sleep(Duration::from_millis(500)).await;

            let skip_first = config
                .get("skip_first")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as usize;
            let skip_last = config
                .get("skip_last")
                .and_then(|v| v.as_u64())
                .unwrap_or(0) as usize;

            emit_status(
                py,
                &callback_obj,
                &format!("Found {} img tags on page", total_found),
            )?;

            let mut fallback_urls = Vec::new();

            // FALLBACK: If very few images found, try HTML parsing
            if total_found < 5 && target_url.contains("4khd.com") {
                emit_status(
                    py,
                    &callback_obj,
                    "Detected 4KHD / low image count. Attempting request-based fallback...",
                )?;
                if let Ok(discovered_urls) = self.fetch_images_via_request(target_url).await {
                    if !discovered_urls.is_empty() {
                        emit_status(
                            py,
                            &callback_obj,
                            &format!(
                                "Discovered {} images via request fallback.",
                                discovered_urls.len()
                            ),
                        )?;
                        fallback_urls = discovered_urls;
                    }
                }
            }

            let start_index = skip_first;
            let end_index = if total_found > skip_last {
                total_found - skip_last
            } else {
                0
            };

            if start_index >= end_index && fallback_urls.is_empty() {
                emit_status(
                    py,
                    &callback_obj,
                    "No images left to process after skipping and no fallbacks found.",
                )?;
                continue;
            }

            // Process Selenium images
            // Extract all image URLs first, then download them without opening tabs (to avoid anti-bot)
            if total_found > 0 {
                emit_status(py, &callback_obj, "Extracting image URLs from page...")?;

                let mut image_urls = Vec::new();
                let all_images = driver.find_all(By::Tag("img")).await?;

                for (idx, img) in all_images.iter().enumerate() {
                    if idx < skip_first || idx >= total_found - skip_last {
                        continue;
                    }

                    if let Ok(Some(src)) = img.attr("src").await {
                        if !src.starts_with("data:") && !src.is_empty() {
                            image_urls.push(src);
                        }
                    }
                }

                emit_status(
                    py,
                    &callback_obj,
                    &format!(
                        "Found {} valid image URLs. Downloading...",
                        image_urls.len()
                    ),
                )?;

                // Download images using browser method (but from extracted URLs, not by opening tabs)
                for (idx, url) in image_urls.iter().enumerate() {
                    // Check for cancellation
                    if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
                        if !is_running.extract::<bool>(py)? {
                            emit_status(py, &callback_obj, "Crawl cancelled.")?;
                            let _ = driver.quit().await;
                            return Ok(total_downloaded_count);
                        }
                    }

                    emit_status(
                        py,
                        &callback_obj,
                        &format!("Downloading image {}/{}", idx + 1, image_urls.len()),
                    )?;

                    // Use browser download for Cloudflare-protected images
                    match self
                        .download_via_browser(
                            &driver,
                            url,
                            &serde_json::Map::new(),
                            py,
                            &callback_obj,
                        )
                        .await
                    {
                        Ok(success) => {
                            if success {
                                total_downloaded_count += 1;
                            }
                        }
                        Err(e) => {
                            emit_error(
                                py,
                                &callback_obj,
                                &format!("Download failed for {}: {}", url, e),
                            )?;
                        }
                    }

                    // Small delay between downloads to avoid overwhelming anti-bot
                    tokio::time::sleep(Duration::from_millis(500)).await;
                }
            }

            // Process Fallback URLs if Selenium failed or found very little
            if total_found < 5 && !fallback_urls.is_empty() {
                // Filter to only URLs from googleusercontent.com (pic.4khd.com has SSL errors - Error 526)
                let working_urls: Vec<_> = fallback_urls
                    .iter()
                    .filter(|url| {
                        url.contains("googleusercontent.com") || !url.contains("pic.4khd.com")
                    })
                    .collect();

                if working_urls.is_empty() {
                    emit_status(py, &callback_obj, "No downloadable fallback URLs found (pic.4khd.com has SSL certificate errors)")?;
                } else {
                    emit_status(
                        py,
                        &callback_obj,
                        &format!(
                            "Downloading {} fallback images (filtered {} broken URLs)...",
                            working_urls.len(),
                            fallback_urls.len() - working_urls.len()
                        ),
                    )?;
                }

                for (idx, url) in working_urls.iter().enumerate() {
                    // Check for cancellation
                    if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
                        if !is_running.extract::<bool>(py)? {
                            let _ = driver.quit().await;
                            return Ok(total_downloaded_count);
                        }
                    }

                    // Close extra tabs to prevent browser from running out of resources
                    let windows = driver.windows().await.unwrap_or_default();
                    if windows.len() > 2 {
                        // Keep only the first tab, close all others except current
                        if let Some(first) = windows.first() {
                            for window in windows.iter().skip(1).take(windows.len() - 2) {
                                let _ = driver.switch_to_window(window.clone()).await;
                                let _ = driver.close_window().await;
                            }
                            let _ = driver.switch_to_window(first.clone()).await;
                        }
                    }

                    emit_status(
                        py,
                        &callback_obj,
                        &format!(
                            "Downloading fallback image {}/{}",
                            idx + 1,
                            fallback_urls.len()
                        ),
                    )?;

                    // For Cloudflare-protected images, use browser-based download
                    match self
                        .download_via_browser(
                            &driver,
                            url,
                            &serde_json::Map::new(),
                            py,
                            &callback_obj,
                        )
                        .await
                    {
                        Ok(success) => {
                            if success {
                                total_downloaded_count += 1;
                            }
                        }
                        Err(e) => {
                            let error_msg = e.to_string();
                            // Check if browser session died
                            if error_msg.contains("invalid session id")
                                || error_msg.contains("session deleted")
                            {
                                emit_status(
                                    py,
                                    &callback_obj,
                                    "Browser session ended. Stopping download.",
                                )?;
                                let _ = driver.quit().await;
                                return Ok(total_downloaded_count);
                            }
                            emit_error(
                                py,
                                &callback_obj,
                                &format!("Fallback browser download failed for {}: {}", url, e),
                            )?;
                        }
                    }
                }
            }
        }

        // Try to quit the driver, but ignore errors if session already ended
        let _ = driver.quit().await;
        Ok(total_downloaded_count)
    }

    async fn execute_sequence(
        &self,
        driver: &WebDriver,
        element: &WebElement,
        actions: &[Value],
        original_handle: &WindowHandle,
        py: Python<'_>,
        callback_obj: &Py<PyAny>,
    ) -> Result<bool> {
        let mut current_element = element.clone();
        let mut downloaded = false;
        let mut scraped_data = serde_json::Map::new();

        for action in actions {
            let action_type = action.get("type").and_then(|v| v.as_str()).unwrap_or("");
            let param = action.get("param").and_then(|v| v.as_str()).unwrap_or("");

            match action_type {
                "Find Parent Link (<a>)" => {
                    current_element = current_element.find(By::XPath("./ancestor::a")).await?;
                }
                "Open Link in New Tab" => {
                    if let Some(href) = current_element.attr("href").await? {
                        driver
                            .execute(&format!("window.open('{}', '_blank');", href), vec![])
                            .await?;
                        let handles = driver.windows().await?;
                        driver
                            .switch_to_window(handles.last().unwrap().clone())
                            .await?;
                        tokio::time::sleep(Duration::from_secs(2)).await;
                    }
                }
                "Download Image from Element" => {
                    let url = current_element
                        .attr("src")
                        .await?
                        .or(current_element.attr("href").await?);
                    if let Some(src) = url {
                        // Try browser-based download first (works with Cloudflare-protected sites)
                        match self
                            .download_via_browser(driver, &src, &scraped_data, py, callback_obj)
                            .await
                        {
                            Ok(success) => {
                                if success {
                                    downloaded = true;
                                } else {
                                    // Fallback to direct download if browser download didn't work
                                    if self
                                        .download_from_url(&src, &scraped_data, py, callback_obj)
                                        .await?
                                    {
                                        downloaded = true;
                                    }
                                }
                            }
                            Err(_) => {
                                // Fallback to direct download on error
                                if self
                                    .download_from_url(&src, &scraped_data, py, callback_obj)
                                    .await?
                                {
                                    downloaded = true;
                                }
                            }
                        }
                    }
                }
                "Scrape Text (Saves to JSON)" => {
                    if let Some((key, selector)) = param.split_once(':') {
                        let text = driver.find(By::Css(selector.trim())).await?.text().await?;
                        scraped_data.insert(
                            key.trim().to_string(),
                            Value::String(text.trim().to_string()),
                        );
                        emit_status(
                            py,
                            callback_obj,
                            &format!("Extracted {}: {}", key.trim(), text.trim()),
                        )?;
                    }
                }
                "Wait X Seconds" => {
                    if let Ok(secs) = param.parse::<u64>() {
                        tokio::time::sleep(Duration::from_secs(secs)).await;
                    }
                }
                "Close Current Tab" => {
                    driver.close_window().await?;
                    driver.switch_to_window(original_handle.clone()).await?;
                }
                "Click Element by Text" => {
                    let el = driver.find(By::LinkText(param)).await?;
                    el.click().await?;
                    tokio::time::sleep(Duration::from_secs(2)).await;
                }
                _ => {
                    // TODO: Implement more actions
                }
            }
        }
        Ok(downloaded)
    }

    async fn download_from_url(
        &self,
        url: &str,
        metadata: &serde_json::Map<String, Value>,
        py: Python<'_>,
        callback_obj: &Py<PyAny>,
    ) -> Result<bool> {
        // Strip proxy URLs (i0.wp.com, i1.wp.com, etc.)
        let actual_url = if url.contains("://i") && url.contains(".wp.com/") {
            // Extract the actual URL from WordPress Photon CDN proxy
            if let Some(pos) = url.find(".wp.com/") {
                let after_proxy = &url[pos + 8..]; // Skip ".wp.com/"
                                                   // Remove query parameters that are proxy-specific
                let without_query = if let Some(qpos) = after_proxy.find('?') {
                    &after_proxy[..qpos]
                } else {
                    after_proxy
                };
                format!("https://{}", without_query)
            } else {
                url.to_string()
            }
        } else {
            url.to_string()
        };

        // Use async reqwest to download (we're in an async function)
        let client = reqwest::Client::builder()
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            .build()?;

        // Extract domain from URL for referer header (prevents hotlink blocking)
        let referer = if let Ok(parsed_url) = url::Url::parse(&actual_url) {
            format!(
                "{}://{}/",
                parsed_url.scheme(),
                parsed_url.host_str().unwrap_or("")
            )
        } else {
            "https://www.4khd.com/".to_string()
        };

        let res = client
            .get(&actual_url)
            .header("Referer", referer)
            .header(
                "Accept",
                "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            )
            .header("Accept-Language", "en-US,en;q=0.9")
            .send()
            .await?;

        if res.status().is_success() {
            let filename = url
                .split('/')
                .last()
                .and_then(|s| s.split('?').next())
                .unwrap_or("image.jpg");
            let mut save_path = PathBuf::from(&self.download_dir).join(filename);

            // Ensure unique filename
            let mut counter = 1;
            while save_path.exists() {
                let stem = save_path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("image");
                let ext = save_path
                    .extension()
                    .and_then(|s| s.to_str())
                    .unwrap_or("jpg");
                save_path = PathBuf::from(&self.download_dir)
                    .join(format!("{} ({}).{}", stem, counter, ext));
                counter += 1;
            }

            fs::write(&save_path, res.bytes().await?)?;
            emit_status(
                py,
                callback_obj,
                &format!("Saved image: {}", save_path.to_string_lossy()),
            )?;
            let _ = callback_obj.call_method1(
                py,
                "on_image_saved",
                (save_path.to_string_lossy().to_string(),),
            );

            if !metadata.is_empty() {
                let json_path = save_path.with_extension("json");
                let json_val = Value::Object(metadata.clone());
                fs::write(json_path, serde_json::to_string_pretty(&json_val)?)?;
            }
            return Ok(true);
        } else {
            emit_error(
                py,
                callback_obj,
                &format!(
                    "Download failed for URL: {} (Status: {})",
                    url,
                    res.status()
                ),
            )?;
        }
        Ok(false)
    }

    async fn download_via_browser(
        &self,
        driver: &WebDriver,
        url: &str,
        metadata: &serde_json::Map<String, Value>,
        py: Python<'_>,
        callback_obj: &Py<PyAny>,
    ) -> Result<bool> {
        // Use the URL as-is (WordPress Photon proxy works better than direct access)
        let actual_url = url.to_string();

        // Save original window handle
        let original_window = driver.window().await?;

        // Open image in new tab
        driver
            .execute(
                &format!(
                    "window.open('{}', '_blank');",
                    actual_url.replace('\'', "\\'")
                ),
                vec![],
            )
            .await?;

        // Wait 1 second for tab to open
        tokio::time::sleep(Duration::from_secs(1)).await;

        // Switch to the new tab (last window)
        let windows = driver.windows().await?;
        if let Some(new_window) = windows.last() {
            driver.switch_to_window(new_window.clone()).await?;

            // Wait for image to load
            tokio::time::sleep(Duration::from_secs(2)).await;

            // Try to extract image data using canvas
            let script = r#"
                return new Promise((resolve) => {
                    const images = document.querySelectorAll('img');
                    if (images.length === 0) {
                        resolve(null);
                        return;
                    }

                    const img = images[0];
                    if (!img.complete || img.naturalHeight === 0) {
                        // Image not loaded yet, wait a bit
                        img.onload = function() {
                            const canvas = document.createElement('canvas');
                            canvas.width = img.naturalWidth;
                            canvas.height = img.naturalHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(img, 0, 0);
                            try {
                                const dataUrl = canvas.toDataURL('image/png');
                                resolve(dataUrl.split(',')[1]);
                            } catch(e) {
                                resolve(null);
                            }
                        };
                        setTimeout(() => resolve(null), 3000);
                    } else {
                        const canvas = document.createElement('canvas');
                        canvas.width = img.naturalWidth;
                        canvas.height = img.naturalHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        try {
                            const dataUrl = canvas.toDataURL('image/png');
                            resolve(dataUrl.split(',')[1]);
                        } catch(e) {
                            resolve(null);
                        }
                    }
                });
            "#;

            let result = driver.execute(script, vec![]).await?;

            // Close the tab and switch back
            driver.close_window().await?;
            driver.switch_to_window(original_window).await?;

            // Wait 1 second between actions
            tokio::time::sleep(Duration::from_secs(1)).await;

            // Convert ScriptRet to JSON value
            if let Ok(base64_data) = result.convert::<String>() {
                if !base64_data.is_empty() && base64_data != "null" {
                    // Decode base64 and save
                    if let Ok(image_data) = BASE64_STANDARD.decode(base64_data) {
                        let filename = actual_url
                            .split('/')
                            .last()
                            .and_then(|s| s.split('?').next())
                            .unwrap_or("image.jpg");
                        let mut save_path = PathBuf::from(&self.download_dir).join(filename);

                        // Ensure unique filename
                        let mut counter = 1;
                        while save_path.exists() {
                            let stem = save_path
                                .file_stem()
                                .and_then(|s| s.to_str())
                                .unwrap_or("image");
                            let ext = save_path
                                .extension()
                                .and_then(|s| s.to_str())
                                .unwrap_or("jpg");
                            save_path = PathBuf::from(&self.download_dir)
                                .join(format!("{} ({}).{}", stem, counter, ext));
                            counter += 1;
                        }

                        fs::write(&save_path, image_data)?;
                        emit_status(
                            py,
                            callback_obj,
                            &format!("Saved image via browser: {}", save_path.to_string_lossy()),
                        )?;
                        let _ = callback_obj.call_method1(
                            py,
                            "on_image_saved",
                            (save_path.to_string_lossy().to_string(),),
                        );

                        if !metadata.is_empty() {
                            let json_path = save_path.with_extension("json");
                            let json_val = Value::Object(metadata.clone());
                            fs::write(json_path, serde_json::to_string_pretty(&json_val)?)?;
                        }

                        return Ok(true);
                    }
                }
            }
        } else {
            // If we couldn't switch to new tab, switch back to original
            driver.switch_to_window(original_window).await?;
        }

        Ok(false)
    }

    async fn fetch_images_via_request(&self, url: &str) -> Result<Vec<String>> {
        let client = reqwest::Client::builder()
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            .build()?;

        let html_content = client.get(url).send().await?.text().await?;
        let document = scraper::Html::parse_document(&html_content);
        let selector =
            scraper::Selector::parse("img").map_err(|e| anyhow!("Invalid selector: {:?}", e))?;

        let mut found_urls = Vec::new();
        for element in document.select(&selector) {
            let attrs = ["src", "data-src", "href", "data-lazy-src", "data-original"];
            for attr in attrs {
                if let Some(val) = element.value().attr(attr) {
                    let img_url = val.to_string();
                    let lower_url = img_url.to_lowercase();
                    if lower_url.ends_with(".jpg")
                        || lower_url.ends_with(".jpeg")
                        || lower_url.ends_with(".png")
                        || lower_url.ends_with(".webp")
                        || img_url.contains("pic.4khd.com")
                        || img_url.contains("ggpht.com")
                        || img_url.contains("blogspot.com")
                    {
                        found_urls.push(img_url);
                    }
                }
            }
        }

        // Also check <a> tags for direct image links
        let a_selector =
            scraper::Selector::parse("a").map_err(|e| anyhow!("Invalid selector: {:?}", e))?;
        for element in document.select(&a_selector) {
            if let Some(href) = element.value().attr("href") {
                let lower_href = href.to_lowercase();
                if lower_href.ends_with(".jpg")
                    || lower_href.ends_with(".jpeg")
                    || lower_href.ends_with(".png")
                    || lower_href.ends_with(".webp")
                {
                    found_urls.push(href.to_string());
                }
            }
        }

        found_urls.sort();
        found_urls.dedup();
        Ok(found_urls)
    }
}

fn emit_status(py: Python<'_>, obj: &Py<PyAny>, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_status_emitted", (msg,))?;
    Ok(())
}

fn emit_error(py: Python<'_>, obj: &Py<PyAny>, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_error_emitted", (msg,))?;
    Ok(())
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn run_image_crawler(
    py: Python<'_>,
    config_json: String,
    callback_obj: Py<PyAny>,
) -> PyResult<u32> {
    let config: Value = serde_json::from_str(&config_json).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
    })?;
    let crawler = ImageCrawlerRust::new(&config);
    crawler.run(py, config_json, callback_obj)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_image_crawler_config() {
        let config = json!({
            "download_dir": "/tmp/img",
            "screenshot_dir": "/tmp/scr",
            "browser": "firefox"
        });
        let crawler = ImageCrawlerRust::new(&config);
        assert_eq!(crawler.download_dir, "/tmp/img");
        assert_eq!(crawler.screenshot_dir, "/tmp/scr");
        assert_eq!(crawler.browser_name, "firefox");
    }

    #[test]
    fn test_image_crawler_defaults() {
        let config = json!({});
        let crawler = ImageCrawlerRust::new(&config);
        assert_eq!(crawler.download_dir, "downloads");
        assert_eq!(crawler.screenshot_dir, "screenshots");
        assert_eq!(crawler.browser_name, "brave");
    }
}
