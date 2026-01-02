use super::image_board_crawler::Crawler;
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE, HOST};
use serde_json::Value;

pub struct SankakuCrawlerImpl {
    pub base_url: String,
    pub login_url: String,
    pub tags: String,
    pub limit: u32,
    pub username: Option<String>,
    pub api_key: Option<String>,
    pub extra_params: Vec<(String, String)>,
    pub token: std::cell::RefCell<Option<String>>,
}

impl SankakuCrawlerImpl {
    pub fn new(config: &Value) -> Self {
        let login_config = config.get("login_config");
        let username = login_config
            .and_then(|c| c.get("username"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let api_key = login_config
            .and_then(|c| c.get("password"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let extra_params = config
            .get("extra_params")
            .and_then(|v| v.as_object())
            .map(|obj| {
                obj.iter()
                    .map(|(k, v)| (k.clone(), v.as_str().unwrap_or("").to_string()))
                    .collect()
            })
            .unwrap_or_default();

        SankakuCrawlerImpl {
            base_url: "https://capi-v2.sankakucomplex.com".to_string(),
            login_url: "https://login.sankakucomplex.com/auth/token".to_string(),
            tags: config
                .get("tags")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            limit: config.get("limit").and_then(|v| v.as_u64()).unwrap_or(20) as u32,
            username,
            api_key,
            extra_params,
            token: std::cell::RefCell::new(None),
        }
    }

    pub fn authenticate(&self, client: &Client) -> Result<()> {
        if self.username.is_none() || self.api_key.is_none() {
            return Ok(());
        }

        let payload = serde_json::json!({
            "login": self.username,
            "password": self.api_key,
        });

        let mut headers = HeaderMap::new();
        headers.insert(HOST, HeaderValue::from_static("login.sankakucomplex.com"));
        headers.insert(
            CONTENT_TYPE,
            HeaderValue::from_static("application/json; charset=utf-8"),
        );

        let response = client
            .post(&self.login_url)
            .json(&payload)
            .headers(headers)
            .send()
            .context("Auth request failed")?;

        response.error_for_status_ref().context("Auth failed")?;
        let data: Value = response.json().context("Failed to parse auth response")?;

        if let (Some(token), Some(token_type)) = (
            data.get("access_token").and_then(|v| v.as_str()),
            data.get("token_type").and_then(|v| v.as_str()),
        ) {
            *self.token.borrow_mut() = Some(format!("{} {}", token_type, token));
        }

        Ok(())
    }
}

impl Crawler for SankakuCrawlerImpl {
    fn name(&self) -> &str {
        "Sankaku"
    }
    fn base_url(&self) -> &str {
        &self.base_url
    }

    fn fetch_posts(&self, client: &Client, page: u32) -> Result<Vec<Value>> {
        // Authenticate if we haven't already
        if self.token.borrow().is_none() && self.username.is_some() {
            self.authenticate(client)?;
        }

        let endpoint = format!("{}/posts", self.base_url);

        let mut params = vec![
            ("lang".to_string(), "en".to_string()),
            ("page".to_string(), page.to_string()),
            ("limit".to_string(), self.limit.to_string()),
            ("tags".to_string(), self.tags.clone()),
        ];

        for (k, v) in &self.extra_params {
            params.push((k.clone(), v.clone()));
        }

        let mut request = client.get(&endpoint).query(&params);

        if let Some(token) = self.token.borrow().as_ref() {
            request = request.header(AUTHORIZATION, token);
        }

        let response = request.send().context("Request failed")?;
        response.error_for_status_ref().context("Bad status")?;

        let data: Value = response.json().context("Failed to parse JSON")?;

        if let Some(arr) = data.as_array() {
            Ok(arr.clone())
        } else if let Some(obj) = data.get("data").and_then(|v| v.as_array()) {
            Ok(obj.clone())
        } else {
            Ok(vec![])
        }
    }

    fn extract_file_url(&self, post: &Value) -> Option<String> {
        post.get("file_url")
            .or_else(|| post.get("sample_url"))
            .or_else(|| post.get("preview_url"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_sankaku_config() {
        let config = json!({
            "tags": "cat",
            "limit": 50
        });
        let crawler = SankakuCrawlerImpl::new(&config);
        assert_eq!(crawler.tags, "cat");
        assert_eq!(crawler.limit, 50);
        assert_eq!(crawler.base_url, "https://capi-v2.sankakucomplex.com");
    }

    #[test]
    fn test_sankaku_extract_file_url_priority() {
        let config = json!({});
        let crawler = SankakuCrawlerImpl::new(&config);

        let p1 = json!({
            "file_url": "original.jpg",
            "sample_url": "sample.jpg",
            "preview_url": "preview.jpg"
        });
        assert_eq!(
            crawler.extract_file_url(&p1),
            Some("original.jpg".to_string())
        );

        let p2 = json!({
            "sample_url": "sample.jpg",
            "preview_url": "preview.jpg"
        });
        assert_eq!(
            crawler.extract_file_url(&p2),
            Some("sample.jpg".to_string())
        );

        let p3 = json!({
            "preview_url": "preview.jpg"
        });
        assert_eq!(
            crawler.extract_file_url(&p3),
            Some("preview.jpg".to_string())
        );
    }
}
