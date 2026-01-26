#[cfg(feature = "python")]
use anyhow::Context;
use anyhow::Result;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
#[cfg(feature = "python")]
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncItem {
    pub rel_path: String,
    pub abs_path_or_id: String,
    pub mtime: i64,
    pub is_folder: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncStats {
    pub uploaded: u32,
    pub downloaded: u32,
    pub deleted_local: u32,
    pub deleted_remote: u32,
    pub skipped: u32,
    pub ignored: u32,
}

pub trait CloudSync {
    fn name(&self) -> &str;
    fn authenticate(&mut self, client: &Client) -> Result<()>;
    fn get_remote_files(&self, client: &Client) -> Result<HashMap<String, SyncItem>>;
    fn upload_file(&self, client: &Client, local_path: &str, rel_path: &str) -> Result<()>;
    fn download_file(&self, client: &Client, remote_id: &str, local_dest: &str) -> Result<()>;
    fn create_remote_folder(&self, client: &Client, rel_path: &str) -> Result<()>;
    fn delete_remote(&self, client: &Client, remote_id: &str, rel_path: &str) -> Result<()>;
}

pub struct SyncRunner {
    pub local_path: String,
    pub remote_path: String,
    pub action_local: String,
    pub action_remote: String,
    pub dry_run: bool,
}

impl SyncRunner {
    pub fn new(config: &Value) -> Self {
        SyncRunner {
            local_path: config
                .get("local_path")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            remote_path: config
                .get("remote_path")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            action_local: config
                .get("action_local")
                .and_then(|v| v.as_str())
                .unwrap_or("upload")
                .to_string(),
            action_remote: config
                .get("action_remote")
                .and_then(|v| v.as_str())
                .unwrap_or("download")
                .to_string(),
            dry_run: config
                .get("dry_run")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        }
    }

    #[cfg(feature = "python")]
    pub fn run<T: CloudSync>(
        &self,
        py: Python<'_>,
        sync: &mut T,
        client: &Client,
        callback_obj: Py<PyAny>,
    ) -> Result<SyncStats> {
        emit_status(
            py,
            &callback_obj,
            &format!("Starting sync for {}", sync.name()),
        )?;

        sync.authenticate(client).context("Authentication failed")?;
        emit_status(py, &callback_obj, "Authentication successful.")?;

        if !Path::new(&self.local_path).exists() {
            return Err(anyhow::anyhow!(
                "Local path does not exist: {}",
                self.local_path
            ));
        }

        emit_status(py, &callback_obj, "Scanning local and remote files...")?;
        let local_items = self.get_local_files()?;
        let mut remote_items = sync.get_remote_files(client)?;

        emit_status(
            py,
            &callback_obj,
            &format!(
                "Found {} local items and {} remote items.",
                local_items.len(),
                remote_items.len()
            ),
        )?;

        let mut stats = SyncStats {
            uploaded: 0,
            downloaded: 0,
            deleted_local: 0,
            deleted_remote: 0,
            skipped: 0,
            ignored: 0,
        };

        // Process Local Items
        for (rel_path, local_item) in &local_items {
            self.check_stop(py, &callback_obj)?;

            if local_item.is_folder {
                if remote_items.contains_key(rel_path) {
                    remote_items.remove(rel_path);
                } else {
                    if self.action_local == "upload" {
                        if !self.dry_run {
                            sync.create_remote_folder(client, rel_path)?;
                        }
                        stats.uploaded += 1;
                    }
                }
                continue;
            }

            if let Some(_remote_item) = remote_items.remove(rel_path) {
                stats.skipped += 1;
            } else {
                // Local Orphan
                match self.action_local.as_str() {
                    "upload" => {
                        emit_status(py, &callback_obj, &format!("Uploading: {}", rel_path))?;
                        if !self.dry_run {
                            sync.upload_file(client, &local_item.abs_path_or_id, rel_path)?;
                        }
                        stats.uploaded += 1;
                    }
                    "delete_local" => {
                        emit_status(py, &callback_obj, &format!("Deleting Local: {}", rel_path))?;
                        if !self.dry_run {
                            std::fs::remove_file(&local_item.abs_path_or_id)?;
                        }
                        stats.deleted_local += 1;
                    }
                    _ => stats.ignored += 1,
                }
            }
        }

        // Process Remote Orphans
        let sorted_remote_keys: Vec<String> = {
            let mut keys: Vec<String> = remote_items.keys().cloned().collect();
            keys.sort_by(|a, b| b.len().cmp(&a.len())); // Deepest first for deletions
            keys
        };

        for rel_path in sorted_remote_keys {
            self.check_stop(py, &callback_obj)?;
            let remote_item = remote_items.get(&rel_path).unwrap();

            if remote_item.is_folder {
                if self.action_remote == "delete_remote" {
                    emit_status(
                        py,
                        &callback_obj,
                        &format!("Deleting Remote Folder: {}", rel_path),
                    )?;
                    if !self.dry_run {
                        sync.delete_remote(client, &remote_item.abs_path_or_id, &rel_path)?;
                    }
                    stats.deleted_remote += 1;
                }
                continue;
            }

            match self.action_remote.as_str() {
                "download" => {
                    emit_status(py, &callback_obj, &format!("Downloading: {}", rel_path))?;
                    if !self.dry_run {
                        let local_dest = Path::new(&self.local_path).join(&rel_path);
                        if let Some(parent) = local_dest.parent() {
                            std::fs::create_dir_all(parent)?;
                        }
                        sync.download_file(
                            client,
                            &remote_item.abs_path_or_id,
                            local_dest.to_str().unwrap(),
                        )?;
                    }
                    stats.downloaded += 1;
                }
                "delete_remote" => {
                    emit_status(py, &callback_obj, &format!("Deleting Remote: {}", rel_path))?;
                    if !self.dry_run {
                        sync.delete_remote(client, &remote_item.abs_path_or_id, &rel_path)?;
                    }
                    stats.deleted_remote += 1;
                }
                _ => stats.ignored += 1,
            }
        }

        Ok(stats)
    }

    #[cfg(feature = "python")]
    fn get_local_files(&self) -> Result<HashMap<String, SyncItem>> {
        let mut items = HashMap::new();
        let base_path = Path::new(&self.local_path);

        for entry in walkdir::WalkDir::new(base_path) {
            let entry = entry?;
            let rel_path = entry
                .path()
                .strip_prefix(base_path)?
                .to_string_lossy()
                .to_string()
                .replace('\\', "/");
            if rel_path.is_empty() {
                continue;
            }

            let metadata = entry.metadata()?;
            items.insert(
                rel_path.clone(),
                SyncItem {
                    rel_path,
                    abs_path_or_id: entry.path().to_string_lossy().to_string(),
                    mtime: metadata
                        .modified()
                        .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                        .duration_since(std::time::SystemTime::UNIX_EPOCH)
                        .unwrap()
                        .as_secs() as i64,
                    is_folder: metadata.is_dir(),
                },
            );
        }
        Ok(items)
    }

    #[cfg(feature = "python")]
    fn check_stop(&self, py: Python<'_>, callback_obj: &Py<PyAny>) -> Result<()> {
        if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
            if !is_running.extract::<bool>(py)? {
                return Err(anyhow::anyhow!("Synchronization manually interrupted."));
            }
        }
        Ok(())
    }
}

#[cfg(feature = "python")]
fn emit_status(py: Python<'_>, obj: &Py<PyAny>, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_status_emitted", (msg,))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_sync_runner_config_parsing() {
        let config = json!({
            "local_path": "/local",
            "remote_path": "/remote",
            "action_local": "delete",
            "action_remote": "delete",
            "dry_run": true
        });
        let runner = SyncRunner::new(&config);
        assert_eq!(runner.local_path, "/local");
        assert_eq!(runner.remote_path, "/remote");
        assert_eq!(runner.action_local, "delete");
        assert_eq!(runner.action_remote, "delete");
        assert_eq!(runner.dry_run, true);
    }

    #[test]
    fn test_sync_runner_defaults() {
        let config = json!({});
        let runner = SyncRunner::new(&config);
        assert_eq!(runner.local_path, "");
        assert_eq!(runner.remote_path, "");
        assert_eq!(runner.action_local, "upload");
        assert_eq!(runner.action_remote, "download");
        assert_eq!(runner.dry_run, false);
    }

    #[test]
    fn test_sync_item_serialization() {
        let item = SyncItem {
            rel_path: "foo.txt".to_string(),
            abs_path_or_id: "id_1".to_string(),
            mtime: 100,
            is_folder: false,
        };
        let serialized = serde_json::to_string(&item).unwrap();
        assert!(serialized.contains("foo.txt"));
        assert!(serialized.contains("id_1"));

        let deserialized: SyncItem = serde_json::from_str(&serialized).unwrap();
        assert_eq!(deserialized.rel_path, "foo.txt");
        assert_eq!(deserialized.mtime, 100);
    }
}
