use anyhow::Result;
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;
use std::time::{Duration, Instant};
use thirtyfour::prelude::*;

pub struct WebFileLoaderRust {
    pub download_dir: PathBuf,
}

impl WebFileLoaderRust {
    pub fn new(download_dir: &str) -> Self {
        WebFileLoaderRust {
            download_dir: PathBuf::from(download_dir),
        }
    }

    pub fn get_initial_files(&self) -> HashSet<String> {
        fs::read_dir(&self.download_dir)
            .map(|rd| {
                rd.filter_map(|e| {
                    e.ok()
                        .map(|ent| ent.file_name().to_string_lossy().to_string())
                })
                .collect()
            })
            .unwrap_or_default()
    }

    pub async fn download_via_javascript(
        &self,
        driver: &WebDriver,
        selectors: &[String],
    ) -> Result<bool> {
        for selector in selectors {
            if let Err(_) = driver.execute(selector, vec![]).await {
                continue;
            }
            tokio::time::sleep(Duration::from_secs(3)).await;
            return Ok(true);
        }
        Ok(false)
    }

    pub async fn download_via_element_click(
        &self,
        driver: &WebDriver,
        selectors: &[String],
    ) -> Result<bool> {
        for selector in selectors {
            let res = if selector.starts_with("//") {
                driver.find(By::XPath(selector)).await
            } else {
                driver.find(By::Css(selector)).await
            };

            if let Ok(element) = res {
                if let Err(_) = driver
                    .execute(
                        "arguments[0].click();",
                        vec![serde_json::to_value(&element)?],
                    )
                    .await
                {
                    continue;
                }
                tokio::time::sleep(Duration::from_secs(3)).await;
                return Ok(true);
            }
        }
        Ok(false)
    }

    pub async fn wait_for_download_to_complete(
        &self,
        initial_files: &HashSet<String>,
        timeout_secs: u64,
    ) -> Result<Option<PathBuf>> {
        let start_time = Instant::now();
        let timeout = Duration::from_secs(timeout_secs);
        let mut last_size: i64 = -1;
        let mut stable_count = 0;

        while start_time.elapsed() < timeout {
            let current_files = self.get_current_files()?;
            let new_files: Vec<_> = current_files
                .iter()
                .filter(|f| !initial_files.contains(*f))
                .collect();

            if !new_files.is_empty() {
                let current_size: i64 = new_files
                    .iter()
                    .map(|f| self.download_dir.join(f))
                    .filter_map(|p| fs::metadata(p).ok().map(|m| m.len() as i64))
                    .sum();

                if current_size == last_size && current_size > 0 {
                    stable_count += 1;
                    if stable_count >= 2 {
                        let path = self.download_dir.join(new_files[0]);
                        return Ok(Some(path));
                    }
                } else {
                    stable_count = 0;
                    last_size = current_size;
                }
            }
            tokio::time::sleep(Duration::from_secs(1)).await;
        }

        // Fallback to whatever appeared even if not stable
        let current_files = self.get_current_files()?;
        let mut new_files: Vec<_> = current_files
            .iter()
            .filter(|f| !initial_files.contains(*f))
            .collect();

        if !new_files.is_empty() {
            Ok(Some(self.download_dir.join(new_files.remove(0))))
        } else {
            Ok(None)
        }
    }

    fn get_current_files(&self) -> Result<HashSet<String>> {
        let mut files = HashSet::new();
        for entry in fs::read_dir(&self.download_dir)? {
            let entry = entry?;
            files.insert(entry.file_name().to_string_lossy().to_string());
        }
        Ok(files)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_file_loader_new() {
        let loader = WebFileLoaderRust::new("/tmp/test");
        assert_eq!(loader.download_dir, PathBuf::from("/tmp/test"));
    }

    #[test]
    fn test_get_initial_files() {
        let temp = tempdir().unwrap();
        let dir = temp.path();
        std::fs::write(dir.join("a.txt"), "a").unwrap();
        std::fs::write(dir.join("b.txt"), "b").unwrap();

        let loader = WebFileLoaderRust::new(dir.to_str().unwrap());
        let files = loader.get_initial_files();
        assert!(files.contains("a.txt"));
        assert!(files.contains("b.txt"));
        assert_eq!(files.len(), 2);
    }
}
