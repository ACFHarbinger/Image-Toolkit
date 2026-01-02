use anyhow::Result;
use pyo3::prelude::*;
use serde_json::Value;
use std::path::Path;
use std::time::Duration;
use thirtyfour::prelude::*;
use tokio::runtime::Runtime;

pub struct ReverseImageSearchRust {
    pub browser_name: String,
}

impl ReverseImageSearchRust {
    pub fn new(config: &Value) -> Self {
        ReverseImageSearchRust {
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
        callback_obj: PyObject,
    ) -> PyResult<String> {
        let config: Value = serde_json::from_str(&config_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
        })?;

        let rt = Runtime::new().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to create runtime: {}",
                e
            ))
        })?;

        let results_json = rt
            .block_on(async { self.run_async(py, config, callback_obj).await })
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Search Error: {}", e))
            })?;

        Ok(results_json)
    }

    async fn run_async(
        &self,
        py: Python<'_>,
        config: Value,
        callback_obj: PyObject,
    ) -> Result<String> {
        let headless = config
            .get("headless")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let image_path = config
            .get("image_path")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let search_mode = config
            .get("search_mode")
            .and_then(|v| v.as_str())
            .unwrap_or("Visual matches");

        if !Path::new(image_path).exists() {
            return Err(anyhow::anyhow!("Image not found: {}", image_path));
        }

        let mut caps = DesiredCapabilities::chrome();
        if headless {
            caps.add_chrome_arg("--headless")?;
        }
        caps.add_chrome_arg("--no-sandbox")?;
        caps.add_chrome_arg("--disable-dev-shm-usage")?;

        let driver = WebDriver::new("http://localhost:9515", caps).await?;

        emit_status(py, &callback_obj, "Navigating to Google Images...")?;
        driver.goto("https://images.google.com/?hl=en").await?;

        // Consent (EU)
        let consent_xpath = "//button[contains(text(), 'Accept all') or contains(text(), 'Reject all')] | //div[text()='Reject all']//ancestor::button";
        if let Ok(btn) = driver.find(By::XPath(consent_xpath)).await {
            btn.click().await?;
            tokio::time::sleep(Duration::from_secs(1)).await;
        }

        // Click Camera Icon
        emit_status(py, &callback_obj, "Opening Google Lens upload...")?;
        let camera_selectors = vec![
            By::Css("svg.Gdd5U"),
            By::XPath("//*[name()='svg' and @viewBox='0 -960 960 960']"),
            By::Css("div[aria-label='Search by image']"),
        ];

        let mut camera_btn = None;
        for selector in camera_selectors {
            if let Ok(btn) = driver.find(selector).await {
                camera_btn = Some(btn);
                break;
            }
        }

        if let Some(btn) = camera_btn {
            btn.click().await?;
        } else {
            // Fallback
            let el = driver.find(By::Css("svg.Gdd5U")).await?;
            driver
                .execute(
                    "arguments[0].parentElement.click();",
                    vec![serde_json::to_value(&el)?],
                )
                .await?;
        }

        tokio::time::sleep(Duration::from_secs(1)).await;

        // Upload Image
        emit_status(py, &callback_obj, "Uploading image...")?;
        let file_input = driver
            .find(By::Css("input[type='file'][name='encoded_image']"))
            .await?;
        file_input.send_keys(image_path).await?;

        emit_status(
            py,
            &callback_obj,
            "Analyzing image (waiting for results/CAPTCHA)...",
        )?;

        // Wait for results
        let mut results_detected = false;
        for _ in 0..50 {
            if let Ok(_) = driver.find(By::Css("div[data-ved] img")).await {
                results_detected = true;
                break;
            }
            tokio::time::sleep(Duration::from_secs(1)).await;
        }

        if !results_detected {
            emit_status(
                py,
                &callback_obj,
                "Timeout waiting for results. Check for CAPTCHA.",
            )?;
        } else {
            emit_status(py, &callback_obj, "Results detected.")?;
        }

        // Search Mode
        if search_mode != "All" {
            emit_status(
                py,
                &callback_obj,
                &format!("Switching to {} mode...", search_mode),
            )?;
            let search_btn_xpath = format!("//a[contains(text(), 'Find image source')] | //span[@class='R1QWuf' and contains(text(), '{}')]", search_mode);
            if let Ok(btn) = driver.find(By::XPath(&search_btn_xpath)).await {
                btn.click().await?;
                tokio::time::sleep(Duration::from_secs(3)).await;
            }
        }

        // Scrape Results
        emit_status(py, &callback_obj, "Scraping search results...")?;
        let potential_links = driver
            .find_all(By::XPath("//a[contains(@href, 'http')]"))
            .await?;

        let mut results = vec![];
        let mut seen_urls = std::collections::HashSet::new();

        for link_elem in potential_links {
            let href = match link_elem.attr("href").await? {
                Some(h) => h,
                None => continue,
            };

            if href.contains("google.com")
                || href.contains("googleusercontent")
                || seen_urls.contains(&href)
            {
                continue;
            }

            let is_direct = href.ends_with(".jpg")
                || href.ends_with(".jpeg")
                || href.ends_with(".png")
                || href.ends_with(".webp");
            let title = link_elem
                .attr("title")
                .await?
                .unwrap_or_else(|| "Result".to_string());

            seen_urls.insert(href.clone());
            results.push(serde_json::json!({
                "url": href,
                "title": title,
                "is_direct": is_direct,
                "resolution": "Unknown" // Scraped from text in python, can be added later
            }));

            if results.len() >= 20 {
                break;
            }
        }

        driver.quit().await?;

        Ok(serde_json::to_string(&results)?)
    }
}

fn emit_status(py: Python<'_>, obj: &PyObject, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_status_emitted", (msg,))?;
    Ok(())
}

#[pyfunction]
pub fn run_reverse_image_search(
    py: Python<'_>,
    config_json: String,
    callback_obj: PyObject,
) -> PyResult<String> {
    let config: Value = serde_json::from_str(&config_json).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
    })?;
    let search = ReverseImageSearchRust::new(&config);
    search.run(py, config_json, callback_obj)
}
