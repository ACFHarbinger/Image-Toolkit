use anyhow::{Context, Result};
use pyo3::prelude::*;
use reqwest::blocking::Client;
use serde_json::Value;
use std::fs;
use std::path::Path;
use std::time::Duration;
use std::{thread, time};

pub trait Crawler {
    fn name(&self) -> &str;
    fn base_url(&self) -> &str;
    fn fetch_posts(&self, client: &Client, page: u32) -> Result<Vec<Value>>;
    fn extract_file_url(&self, post: &Value) -> Option<String>;
    fn extract_id(&self, post: &Value) -> String {
        post.get("id")
            .and_then(|id| {
                if id.is_number() {
                    Some(id.to_string())
                } else {
                    id.as_str().map(|s| s.to_string())
                }
            })
            .unwrap_or_else(|| "unknown".to_string())
    }
    fn extract_md5(&self, post: &Value) -> String {
        post.get("md5")
            .and_then(|m| m.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| "none".to_string())
    }
}

pub struct BoardCrawler {
    pub download_dir: String,
    pub max_pages: u32,
    pub limit: u32,
    pub tags: String,
    pub request_limit: u32,
    pub sleep_time: f32,
    pub current_request_count: std::cell::Cell<u32>,
}

impl BoardCrawler {
    pub fn new(config_val: &Value) -> Self {
        BoardCrawler {
            download_dir: config_val
                .get("download_dir")
                .and_then(|v| v.as_str())
                .unwrap_or("downloads")
                .to_string(),
            max_pages: config_val
                .get("max_pages")
                .and_then(|v| v.as_u64())
                .unwrap_or(5) as u32,
            limit: config_val
                .get("limit")
                .and_then(|v| v.as_u64())
                .unwrap_or(20) as u32,
            tags: config_val
                .get("tags")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            request_limit: 5,
            sleep_time: 1.0,
            current_request_count: std::cell::Cell::new(0),
        }
    }

    pub fn check_rate_limit(&self, py: Python<'_>, callback_obj: &Py<PyAny>) -> PyResult<()> {
        let count = self.current_request_count.get() + 1;
        self.current_request_count.set(count);
        if count % self.request_limit == 0 {
            emit_status(
                py,
                callback_obj,
                &format!("Rate limiting active: Waiting {}s...", self.sleep_time),
            )?;
            thread::sleep(Duration::from_secs_f32(self.sleep_time));
        }
        Ok(())
    }

    pub fn run<T: Crawler>(
        &self,
        py: Python<'_>,
        crawler: &T,
        client: &Client,
        callback_obj: Py<PyAny>,
    ) -> PyResult<u32> {
        let mut total_downloaded = 0;
        emit_status(
            py,
            &callback_obj,
            &format!(
                "Starting {} Crawl on: {}",
                crawler.name(),
                crawler.base_url()
            ),
        )?;

        if let Err(e) = fs::create_dir_all(&self.download_dir) {
            emit_error(
                py,
                &callback_obj,
                &format!("Failed to create download directory: {}", e),
            )?;
            return Ok(0);
        }

        for page in 1..=self.max_pages {
            // Check for cancellation
            if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
                if !is_running.extract::<bool>(py)? {
                    emit_status(py, &callback_obj, "Crawl cancelled.")?;
                    return Ok(total_downloaded);
                }
            }

            emit_status(py, &callback_obj, &format!("Fetching page {}...", page))?;
            self.check_rate_limit(py, &callback_obj)?;

            match crawler.fetch_posts(client, page) {
                Ok(posts) => {
                    if posts.is_empty() {
                        emit_status(py, &callback_obj, "No posts found or end of results.")?;
                        break;
                    }

                    for post in posts {
                        let file_url = match crawler.extract_file_url(&post) {
                            Some(url) => url,
                            None => continue,
                        };

                        let ext = Path::new(&file_url)
                            .extension()
                            .and_then(|s| s.to_str())
                            .unwrap_or("jpg");
                        let id = crawler.extract_id(&post);
                        let md5 = crawler.extract_md5(&post);

                        let filename = format!("{}_{}.{}", id, md5, ext);
                        let save_path = Path::new(&self.download_dir).join(&filename);

                        if save_path.exists() {
                            emit_status(
                                py,
                                &callback_obj,
                                &format!("Skipping existing file: {}", filename),
                            )?;
                            continue;
                        }

                        emit_status(py, &callback_obj, &format!("Downloading: {}", filename))?;
                        self.check_rate_limit(py, &callback_obj)?;

                        match download_image(client, &file_url, &save_path) {
                            Ok(_) => {
                                total_downloaded += 1;
                                let _ = callback_obj.call_method1(
                                    py,
                                    "on_image_saved",
                                    (save_path.to_string_lossy().to_string(),),
                                );
                                save_metadata(&save_path, &post);
                                thread::sleep(Duration::from_millis(500));
                            }
                            Err(e) => {
                                emit_error(
                                    py,
                                    &callback_obj,
                                    &format!("Download failed for {}: {}", file_url, e),
                                )?;
                            }
                        }
                    }
                }
                Err(e) => {
                    emit_error(py, &callback_obj, &format!("Fetch failed: {}", e))?;
                    break;
                }
            }
            thread::sleep(time::Duration::from_millis(500));
        }

        emit_status(
            py,
            &callback_obj,
            &format!("Crawl complete. Downloaded {} images.", total_downloaded),
        )?;
        Ok(total_downloaded)
    }
}

fn download_image(client: &Client, url: &str, save_path: &Path) -> Result<()> {
    let mut response = client.get(url).send().context("Request failed")?;
    response.error_for_status_ref().context("Bad status")?;
    let mut file = fs::File::create(save_path).context("Failed to create file")?;
    response
        .copy_to(&mut file)
        .context("Failed to save content")?;
    Ok(())
}

fn save_metadata(image_path: &Path, post: &Value) {
    let json_path = image_path.with_extension("json");
    if let Ok(content) = serde_json::to_string_pretty(post) {
        let _ = fs::write(json_path, content);
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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    struct TestCrawler;
    impl Crawler for TestCrawler {
        fn name(&self) -> &str {
            "test"
        }
        fn base_url(&self) -> &str {
            "http://test"
        }
        fn fetch_posts(&self, _client: &Client, _page: u32) -> Result<Vec<Value>> {
            Ok(vec![])
        }
        fn extract_file_url(&self, _post: &Value) -> Option<String> {
            None
        }
    }

    #[test]
    fn test_extract_id() {
        let crawler = TestCrawler;
        let p1 = json!({"id": 123});
        assert_eq!(crawler.extract_id(&p1), "123");

        let p2 = json!({"id": "456"});
        assert_eq!(crawler.extract_id(&p2), "456");

        let p3 = json!({});
        assert_eq!(crawler.extract_id(&p3), "unknown");
    }

    #[test]
    fn test_extract_md5() {
        let crawler = TestCrawler;
        let p1 = json!({"md5": "abc"});
        assert_eq!(crawler.extract_md5(&p1), "abc");

        let p2 = json!({});
        assert_eq!(crawler.extract_md5(&p2), "none");
    }

    #[test]
    fn test_board_crawler_config() {
        let config = json!({
            "download_dir": "/tmp/test",
            "max_pages": 10,
            "limit": 50,
            "tags": "cat"
        });
        let bc = BoardCrawler::new(&config);
        assert_eq!(bc.download_dir, "/tmp/test");
        assert_eq!(bc.max_pages, 10);
        assert_eq!(bc.limit, 50);
        assert_eq!(bc.tags, "cat");
    }

    #[test]
    fn test_board_crawler_defaults() {
        let config = json!({});
        let bc = BoardCrawler::new(&config);
        assert_eq!(bc.download_dir, "downloads");
        assert_eq!(bc.max_pages, 5);
        assert_eq!(bc.limit, 20);
        assert_eq!(bc.tags, "");
    }
}
