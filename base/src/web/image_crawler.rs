use anyhow::Result;
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
        let target_url = config.get("url").and_then(|v| v.as_str()).unwrap_or("");

        let mut caps = DesiredCapabilities::chrome();
        if headless {
            caps.add_arg("--headless")?;
        }
        caps.add_arg("--no-sandbox")?;
        caps.add_arg("--disable-dev-shm-usage")?;

        // Note: Assuming chromedriver is running on localhost:9515
        let driver = WebDriver::new("http://localhost:9515", caps).await?;

        emit_status(
            py,
            &callback_obj,
            &format!("Connected to WebDriver. Navigating to {}", target_url),
        )?;

        driver.goto(target_url).await?;

        // Wait for page load
        tokio::time::sleep(Duration::from_secs(3)).await;

        let actions = config
            .get("actions")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        let skip_first = config
            .get("skip_first")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;
        let skip_last = config
            .get("skip_last")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;

        let images = driver.find_all(By::Tag("img")).await?;
        let total_found = images.len();

        let start_index = skip_first;
        let end_index = if total_found > skip_last {
            total_found - skip_last
        } else {
            0
        };

        if start_index >= end_index {
            emit_status(
                py,
                &callback_obj,
                "No images left to process after skipping.",
            )?;
            driver.quit().await?;
            return Ok(0);
        }

        let mut downloaded_count = 0;
        let original_handle = driver.window().await?;

        for i in start_index..end_index {
            // Check for cancellation
            if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
                if !is_running.extract::<bool>(py)? {
                    emit_status(py, &callback_obj, "Crawl cancelled.")?;
                    break;
                }
            }

            emit_status(
                py,
                &callback_obj,
                &format!("Processing image {}/{}", i + 1, end_index),
            )?;

            // Re-locate images to avoid staleness
            let current_images = driver.find_all(By::Tag("img")).await?;
            if i >= current_images.len() {
                break;
            }
            let el = &current_images[i];

            match self
                .execute_sequence(&driver, el, &actions, &original_handle, py, &callback_obj)
                .await
            {
                Ok(success) => {
                    if success {
                        downloaded_count += 1;
                    }
                }
                Err(e) => {
                    emit_error(
                        py,
                        &callback_obj,
                        &format!("Sequence failed for image {}: {}", i + 1, e),
                    )?;
                }
            }

            // Return to original window if needed
            let current_handle = driver.window().await?;
            if current_handle != original_handle {
                driver.switch_to_window(original_handle.clone()).await?;
            }
        }

        driver.quit().await?;
        Ok(downloaded_count)
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
                        if self
                            .download_from_url(&src, &scraped_data, py, callback_obj)
                            .await?
                        {
                            downloaded = true;
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
        // Resolve relative URL if needed (we should ideally get full URL from thirtyfour)
        // Use reqwest to download
        let client = reqwest::blocking::Client::new();
        let res = client.get(url).send()?;
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

            fs::write(&save_path, res.bytes()?)?;
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
        }
        Ok(false)
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
