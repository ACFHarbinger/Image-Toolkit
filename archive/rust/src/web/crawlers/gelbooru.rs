use super::image_board_crawler::Crawler;
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde_json::Value;

pub struct GelbooruCrawlerImpl {
    pub base_url: String,
    pub resource: String,
    pub tags: String,
    pub limit: u32,
    pub username: Option<String>,
    pub api_key: Option<String>,
    pub extra_params: Vec<(String, String)>,
}

impl GelbooruCrawlerImpl {
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

        GelbooruCrawlerImpl {
            base_url: config
                .get("url")
                .and_then(|v| v.as_str())
                .unwrap_or("https://gelbooru.com")
                .to_string(),
            resource: config
                .get("resource")
                .and_then(|v| v.as_str())
                .unwrap_or("posts")
                .to_string(),
            tags: config
                .get("tags")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            limit: config.get("limit").and_then(|v| v.as_u64()).unwrap_or(100) as u32,
            username,
            api_key,
            extra_params,
        }
    }
}

impl Crawler for GelbooruCrawlerImpl {
    fn name(&self) -> &str {
        "Gelbooru"
    }
    fn base_url(&self) -> &str {
        &self.base_url
    }

    fn fetch_posts(&self, client: &Client, page: u32) -> Result<Vec<Value>> {
        let endpoint = format!("{}/index.php", self.base_url.trim_end_matches('/'));
        let s_param = self.resource.trim_end_matches('s');

        let mut params = vec![
            ("page".to_string(), "dapi".to_string()),
            ("s".to_string(), s_param.to_string()),
            ("q".to_string(), "index".to_string()),
            ("json".to_string(), "1".to_string()),
            ("limit".to_string(), self.limit.to_string()),
            ("pid".to_string(), (page - 1).to_string()),
        ];

        if !self.tags.is_empty() {
            match s_param {
                "post" => params.push(("tags".to_string(), self.tags.clone())),
                "tag" | "user" => {
                    params.push(("name_pattern".to_string(), format!("%{}%", self.tags)))
                }
                _ => {}
            }
        }

        for (k, v) in &self.extra_params {
            params.push((k.clone(), v.clone()));
        }

        if let (Some(u), Some(a)) = (&self.username, &self.api_key) {
            params.push(("user_id".to_string(), u.clone()));
            params.push(("api_key".to_string(), a.clone()));
        }

        let response = client
            .get(&endpoint)
            .query(&params)
            .send()
            .context("Request failed")?;
        response.error_for_status_ref().context("Bad status")?;

        let data: Value = response.json().context("Failed to parse JSON")?;

        let mut items = vec![];
        if let Some(arr) = data.as_array() {
            items = arr.clone();
        } else if let Some(obj) = data.as_object() {
            // Gelbooru often wraps results in a key named after the resource
            let possible_keys = vec![s_param, &self.resource, "post", "posts", "tag", "tags"];
            for key in possible_keys {
                if let Some(val) = obj.get(key) {
                    if let Some(arr) = val.as_array() {
                        items = arr.clone();
                    } else if let Some(inner_obj) = val.as_object() {
                        items = vec![Value::Object(inner_obj.clone())];
                    }
                    break;
                }
            }
        }

        Ok(items)
    }

    fn extract_file_url(&self, post: &Value) -> Option<String> {
        post.get("file_url")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_gelbooru_config() {
        let config = json!({
            "url": "https://test.gelbooru",
            "tags": "dog",
            "limit": 50
        });
        let crawler = GelbooruCrawlerImpl::new(&config);
        assert_eq!(crawler.base_url, "https://test.gelbooru");
        assert_eq!(crawler.tags, "dog");
        assert_eq!(crawler.limit, 50);
    }

    #[test]
    fn test_gelbooru_defaults() {
        let config = json!({});
        let crawler = GelbooruCrawlerImpl::new(&config);
        assert_eq!(crawler.base_url, "https://gelbooru.com");
        assert_eq!(crawler.tags, "");
        assert_eq!(crawler.limit, 100);
    }
}
