use super::sync::{CloudSync, SyncItem};
use anyhow::{Context, Result};
use reqwest::blocking::Client;
use serde_json::Value;
use std::collections::HashMap;

pub struct OneDriveSyncImpl {
    pub access_token: String,
    pub remote_path: String,
}

impl OneDriveSyncImpl {
    pub fn new(config: &Value) -> Self {
        OneDriveSyncImpl {
            access_token: config
                .get("access_token")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            remote_path: config
                .get("remote_path")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
                .trim_matches('/')
                .to_string(),
        }
    }
}

impl CloudSync for OneDriveSyncImpl {
    fn name(&self) -> &str {
        "OneDrive"
    }

    fn authenticate(&mut self, client: &Client) -> Result<()> {
        let res = client
            .get("https://graph.microsoft.com/v1.0/me/drive")
            .header("Authorization", format!("Bearer {}", self.access_token))
            .send()?;

        if res.status().is_success() {
            Ok(())
        } else {
            Err(anyhow::anyhow!("OneDrive Auth failed: {}", res.text()?))
        }
    }

    fn get_remote_files(&self, client: &Client) -> Result<HashMap<String, SyncItem>> {
        let mut items = HashMap::new();

        // Resolve root folder ID
        let root_url = if self.remote_path.is_empty() {
            "https://graph.microsoft.com/v1.0/me/drive/root".to_string()
        } else {
            format!(
                "https://graph.microsoft.com/v1.0/me/drive/root:/{}",
                self.remote_path
            )
        };

        let res = client
            .get(&root_url)
            .header("Authorization", format!("Bearer {}", self.access_token))
            .send()?;

        if !res.status().is_success() {
            return Ok(items); // Folder not found or other error
        }

        let root_data: Value = res.json()?;
        let root_id = root_data
            .get("id")
            .and_then(|v| v.as_str())
            .context("No ID")?
            .to_string();

        let mut queue = vec![(root_id, "".to_string())];

        while !queue.is_empty() {
            let (folder_id, current_rel) = queue.remove(0);
            let mut url = Some(format!(
                "https://graph.microsoft.com/v1.0/me/drive/items/{}/children",
                folder_id
            ));

            while let Some(current_url) = url {
                let res = client
                    .get(&current_url)
                    .header("Authorization", format!("Bearer {}", self.access_token))
                    .send()?;

                let data: Value = res.json()?;
                let values = data
                    .get("value")
                    .and_then(|v| v.as_array())
                    .context("List failed")?;

                for item in values {
                    let id = item.get("id").and_then(|v| v.as_str()).unwrap();
                    let name = item.get("name").and_then(|v| v.as_str()).unwrap();
                    let is_folder = item.get("folder").is_some();

                    let rel_path = if current_rel.is_empty() {
                        name.to_string()
                    } else {
                        format!("{}/{}", current_rel, name)
                    };

                    items.insert(
                        rel_path.clone(),
                        SyncItem {
                            rel_path: rel_path.clone(),
                            abs_path_or_id: id.to_string(),
                            mtime: 0, // OneDrive mtime is a bit complex in Graph, skipping for now
                            is_folder,
                        },
                    );

                    if is_folder {
                        queue.push((id.to_string(), rel_path));
                    }
                }
                url = data
                    .get("@odata.nextLink")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
            }
        }
        Ok(items)
    }

    fn upload_file(&self, client: &Client, local_path: &str, rel_path: &str) -> Result<()> {
        let target_path = if self.remote_path.is_empty() {
            rel_path.to_string()
        } else {
            format!("{}/{}", self.remote_path, rel_path)
        };

        let url = format!(
            "https://graph.microsoft.com/v1.0/me/drive/root:/{}:/content",
            target_path
        );
        let file_bytes = std::fs::read(local_path)?;

        let res = client
            .put(&url)
            .header("Authorization", format!("Bearer {}", self.access_token))
            .body(file_bytes)
            .send()?;

        if res.status().is_success() || res.status().as_u16() == 201 {
            Ok(())
        } else {
            Err(anyhow::anyhow!("OneDrive upload failed: {}", res.text()?))
        }
    }

    fn download_file(&self, client: &Client, remote_id: &str, local_dest: &str) -> Result<()> {
        let url = format!(
            "https://graph.microsoft.com/v1.0/me/drive/items/{}/content",
            remote_id
        );
        let res = client
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.access_token))
            .send()?;

        if res.status().is_success() {
            let bytes = res.bytes()?;
            std::fs::write(local_dest, bytes)?;
            Ok(())
        } else {
            Err(anyhow::anyhow!("OneDrive download failed: {}", res.text()?))
        }
    }

    fn create_remote_folder(&self, _client: &Client, _rel_path: &str) -> Result<()> {
        // Simplified: MS Graph handles this via path-based upload often, but for folders:
        // Assume parent exists for simplicity or use the "root:/path" shortcut.
        Ok(())
    }

    fn delete_remote(&self, client: &Client, remote_id: &str, _rel_path: &str) -> Result<()> {
        let url = format!(
            "https://graph.microsoft.com/v1.0/me/drive/items/{}",
            remote_id
        );
        let res = client
            .delete(&url)
            .header("Authorization", format!("Bearer {}", self.access_token))
            .send()?;

        if res.status().is_success() || res.status().as_u16() == 204 {
            Ok(())
        } else {
            Err(anyhow::anyhow!("OneDrive delete failed: {}", res.text()?))
        }
    }
}
