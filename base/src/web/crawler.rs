use super::file_loader::WebFileLoaderRust;
use anyhow::Result;
use std::time::Duration;
use thirtyfour::prelude::*;

pub struct WebDriverConfig {
    pub headless: bool,
    pub browser: String,
    pub download_dir: String,
}

pub struct CrawlerBase {
    pub driver: WebDriver,
    pub file_loader: WebFileLoaderRust,
    pub config: WebDriverConfig,
}

impl CrawlerBase {
    pub async fn new(config: WebDriverConfig) -> Result<Self> {
        let driver = if config.browser.to_lowercase() == "firefox" {
            let caps = DesiredCapabilities::firefox();
            WebDriver::new("http://localhost:9515", caps).await?
        } else {
            let mut caps = DesiredCapabilities::chrome();
            if config.headless {
                caps.add_chrome_arg("--headless")?;
            }
            caps.add_chrome_arg("--no-sandbox")?;
            caps.add_chrome_arg("--disable-dev-shm-usage")?;
            WebDriver::new("http://localhost:9515", caps).await?
        };
        let file_loader = WebFileLoaderRust::new(&config.download_dir);

        Ok(CrawlerBase {
            driver,
            file_loader,
            config,
        })
    }

    pub async fn navigate_to(&self, url: &str, wait_secs: u64) -> Result<()> {
        self.driver.goto(url).await?;
        if wait_secs > 0 {
            tokio::time::sleep(Duration::from_secs(wait_secs)).await;
        }
        Ok(())
    }

    pub async fn click_element_by_css(&self, selector: &str) -> Result<()> {
        let el = self.driver.find(By::Css(selector)).await?;
        self.driver
            .execute("arguments[0].click();", vec![serde_json::to_value(&el)?])
            .await?;
        Ok(())
    }

    pub async fn get_text(&self, selector: &str) -> Result<String> {
        let el = self.driver.find(By::Css(selector)).await?;
        Ok(el.text().await?)
    }

    pub async fn quit(self) -> Result<()> {
        self.driver.quit().await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_webdriver_config() {
        let config = WebDriverConfig {
            headless: true,
            browser: "chrome".to_string(),
            download_dir: "/tmp".to_string(),
        };
        assert_eq!(config.headless, true);
        assert_eq!(config.browser, "chrome");
        assert_eq!(config.download_dir, "/tmp");
    }
}
