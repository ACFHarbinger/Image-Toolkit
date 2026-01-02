use super::image_board_crawler::Crawler;
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde_json::Value;

pub struct DanbooruCrawlerImpl {
    pub base_url: String,
    pub resource: String,
    pub tags: String,
    pub limit: u32,
    pub username: Option<String>,
    pub api_key: Option<String>,
    pub extra_params: Vec<(String, String)>,
}

impl DanbooruCrawlerImpl {
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

        DanbooruCrawlerImpl {
            base_url: config
                .get("url")
                .and_then(|v| v.as_str())
                .unwrap_or("https://danbooru.donmai.us")
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
            limit: config.get("limit").and_then(|v| v.as_u64()).unwrap_or(20) as u32,
            username,
            api_key,
            extra_params,
        }
    }
}

impl Crawler for DanbooruCrawlerImpl {
    fn name(&self) -> &str {
        "Danbooru"
    }
    fn base_url(&self) -> &str {
        &self.base_url
    }

    fn fetch_posts(&self, client: &Client, page: u32) -> Result<Vec<Value>> {
        let endpoint = format!(
            "{}/{}.json",
            self.base_url.trim_end_matches('/'),
            self.resource
        );

        let mut params = vec![
            ("page".to_string(), page.to_string()),
            ("limit".to_string(), self.limit.to_string()),
        ];

        if !self.tags.is_empty() {
            match self.resource.as_str() {
                "posts" => params.push(("tags".to_string(), self.tags.clone())),
                "tags" | "users" => {
                    params.push(("search[name_matches]".to_string(), self.tags.clone()))
                }
                "comments" => params.push(("search[body_matches]".to_string(), self.tags.clone())),
                _ => {}
            }
        }

        for (k, v) in &self.extra_params {
            params.push((k.clone(), v.clone()));
        }

        if let (Some(u), Some(a)) = (&self.username, &self.api_key) {
            params.push(("login".to_string(), u.clone()));
            params.push(("api_key".to_string(), a.clone()));
        }

        let response = client
            .get(&endpoint)
            .query(&params)
            .send()
            .context("Request failed")?;
        response.error_for_status_ref().context("Bad status")?;

        let data: Value = response.json().context("Failed to parse JSON")?;

        if let Some(arr) = data.as_array() {
            Ok(arr.clone())
        } else if let Some(obj) = data.as_object() {
            Ok(vec![Value::Object(obj.clone())])
        } else {
            Ok(vec![])
        }
    }

    fn extract_file_url(&self, post: &Value) -> Option<String> {
        post.get("file_url")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    }
}
