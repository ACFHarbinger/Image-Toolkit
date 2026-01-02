use super::sync::{CloudSync, SyncItem};
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde_json::Value;
use std::collections::HashMap;

pub struct DropboxSyncImpl {
    pub access_token: String,
    pub remote_path: String,
}

impl DropboxSyncImpl {
    pub fn new(config: &Value) -> Self {
        let mut remote = config
            .get("remote_path")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        if !remote.starts_with('/') && !remote.is_empty() {
            remote = format!("/{}", remote);
        }
        DropboxSyncImpl {
            access_token: config
                .get("access_token")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            remote_path: remote,
        }
    }
}

impl CloudSync for DropboxSyncImpl {
    fn name(&self) -> &str {
        "Dropbox"
    }

    fn authenticate(&mut self, client: &Client) -> Result<()> {
        let res = client
            .post("https://api.dropboxapi.com/2/users/get_current_account")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .send()?;

        if res.status().is_success() {
            Ok(())
        } else {
            Err(anyhow::anyhow!(
                "Invalid Dropbox Access Token: {}",
                res.text()?
            ))
        }
    }

    fn get_remote_files(&self, client: &Client) -> Result<HashMap<String, SyncItem>> {
        let mut items = HashMap::new();
        let mut url = "https://api.dropboxapi.com/2/files/list_folder".to_string();
        let mut body = serde_json::json!({
            "path": self.remote_path,
            "recursive": true,
            "include_non_downloadable_files": false
        });

        loop {
            let res = client
                .post(&url)
                .header("Authorization", format!("Bearer {}", self.access_token))
                .header("Content-Type", "application/json")
                .json(&body)
                .send()?;

            if !res.status().is_success() {
                let err_text = res.text()?;
                if err_text.contains("path/not_found") {
                    return Ok(items);
                }
                return Err(anyhow::anyhow!("Dropbox API Error (list): {}", err_text));
            }

            let data: Value = res.json()?;
            let entries = data
                .get("entries")
                .and_then(|v| v.as_array())
                .context("Missing entries")?;

            for entry in entries {
                let full_path = entry
                    .get("path_display")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let rel_path = if self.remote_path.is_empty() {
                    full_path.trim_start_matches('/').to_string()
                } else if full_path
                    .to_lowercase()
                    .starts_with(&self.remote_path.to_lowercase())
                {
                    full_path[self.remote_path.len()..]
                        .trim_start_matches('/')
                        .to_string()
                } else {
                    continue;
                };

                if rel_path.is_empty() {
                    continue;
                }

                let is_folder = entry.get(".tag").and_then(|v| v.as_str()) == Some("folder");
                let mtime = if !is_folder {
                    entry
                        .get("client_modified")
                        .and_then(|v| v.as_str())
                        .map(|s| {
                            chrono::DateTime::parse_from_rfc3339(s)
                                .map(|dt| dt.timestamp())
                                .unwrap_or(0)
                        })
                        .unwrap_or(0)
                } else {
                    0
                };

                items.insert(
                    rel_path.clone(),
                    SyncItem {
                        rel_path,
                        abs_path_or_id: full_path.to_string(), // For dropbox, path works as ID
                        mtime,
                        is_folder,
                    },
                );
            }

            if data
                .get("has_more")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
            {
                url = "https://api.dropboxapi.com/2/files/list_folder/continue".to_string();
                body = serde_json::json!({
                    "cursor": data.get("cursor").context("Missing cursor")?
                });
            } else {
                break;
            }
        }

        Ok(items)
    }

    fn upload_file(&self, client: &Client, local_path: &str, rel_path: &str) -> Result<()> {
        let target_path = format!("{}/{}", self.remote_path, rel_path).replace("//", "/");
        let arg = serde_json::json!({
            "path": target_path,
            "mode": "overwrite",
            "autorename": true,
            "mute": false,
            "strict_conflict": false
        });

        let file_bytes = std::fs::read(local_path)?;
        let res = client
            .post("https://content.dropboxapi.com/2/files/upload")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .header("Dropbox-API-Arg", serde_json::to_string(&arg)?)
            .header("Content-Type", "application/octet-stream")
            .body(file_bytes)
            .send()?;

        if res.status().is_success() {
            Ok(())
        } else {
            Err(anyhow::anyhow!("Dropbox Upload Error: {}", res.text()?))
        }
    }

    fn download_file(&self, client: &Client, remote_id: &str, local_dest: &str) -> Result<()> {
        let arg = serde_json::json!({ "path": remote_id });
        let res = client
            .post("https://content.dropboxapi.com/2/files/download")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .header("Dropbox-API-Arg", serde_json::to_string(&arg)?)
            .send()?;

        if res.status().is_success() {
            let bytes = res.bytes()?;
            std::fs::write(local_dest, bytes)?;
            Ok(())
        } else {
            Err(anyhow::anyhow!("Dropbox Download Error: {}", res.text()?))
        }
    }

    fn create_remote_folder(&self, client: &Client, rel_path: &str) -> Result<()> {
        let target_path = format!("{}/{}", self.remote_path, rel_path).replace("//", "/");
        let res = client
            .post("https://api.dropboxapi.com/2/files/create_folder_v2")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .header("Content-Type", "application/json")
            .json(&serde_json::json!({
                "path": target_path,
                "autorename": false
            }))
            .send()?;

        if res.status().is_success() || res.status().as_u16() == 409 {
            // 409 Conflict often means group already exists
            Ok(())
        } else {
            Err(anyhow::anyhow!(
                "Dropbox Folder Creation Error: {}",
                res.text()?
            ))
        }
    }

    fn delete_remote(&self, client: &Client, remote_id: &str, _rel_path: &str) -> Result<()> {
        let res = client
            .post("https://api.dropboxapi.com/2/files/delete_v2")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .header("Content-Type", "application/json")
            .json(&serde_json::json!({ "path": remote_id }))
            .send()?;

        if res.status().is_success() {
            Ok(())
        } else {
            Err(anyhow::anyhow!("Dropbox Delete Error: {}", res.text()?))
        }
    }
}
