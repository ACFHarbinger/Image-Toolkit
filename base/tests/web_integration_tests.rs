use anyhow::Result;
use base::web::image_board_crawler::{BoardCrawler, Crawler};
use base::web::sync::{CloudSync, SyncItem, SyncRunner};
use mockito::Server;
use pyo3::prelude::*;
use reqwest::blocking::Client;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tempfile::tempdir;

// --- Mocks ---

struct MockSync {
    remote_files: Arc<Mutex<HashMap<String, SyncItem>>>,
    actions: Arc<Mutex<Vec<String>>>,
}

impl CloudSync for MockSync {
    fn name(&self) -> &str {
        "Mock"
    }
    fn authenticate(&mut self, _client: &Client) -> Result<()> {
        Ok(())
    }
    fn get_remote_files(&self, _client: &Client) -> Result<HashMap<String, SyncItem>> {
        Ok(self.remote_files.lock().unwrap().clone())
    }
    fn upload_file(&self, _client: &Client, _local_path: &str, rel_path: &str) -> Result<()> {
        self.actions
            .lock()
            .unwrap()
            .push(format!("upload:{}", rel_path));
        Ok(())
    }
    fn download_file(&self, _client: &Client, _remote_id: &str, local_dest: &str) -> Result<()> {
        self.actions
            .lock()
            .unwrap()
            .push(format!("download:{}", local_dest));
        std::fs::write(local_dest, "mock data")?;
        Ok(())
    }
    fn create_remote_folder(&self, _client: &Client, rel_path: &str) -> Result<()> {
        self.actions
            .lock()
            .unwrap()
            .push(format!("mkdir:{}", rel_path));
        Ok(())
    }
    fn delete_remote(&self, _client: &Client, _remote_id: &str, rel_path: &str) -> Result<()> {
        self.actions
            .lock()
            .unwrap()
            .push(format!("delete_remote:{}", rel_path));
        Ok(())
    }
}

struct MockCrawler {
    base_url: String,
}

impl Crawler for MockCrawler {
    fn name(&self) -> &str {
        "MockCrawler"
    }
    fn base_url(&self) -> &str {
        &self.base_url
    }
    fn fetch_posts(&self, client: &Client, _page: u32) -> Result<Vec<Value>> {
        let url = format!("{}/posts", self.base_url);
        let res = client.get(url).send()?.json::<Vec<Value>>()?;
        Ok(res)
    }
    fn extract_file_url(&self, post: &Value) -> Option<String> {
        post.get("file_url")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    }
}

#[pyclass]
struct MockCallback {
    pub messages: Arc<Mutex<Vec<String>>>,
    pub _is_running: bool,
}

#[pymethods]
impl MockCallback {
    #[new]
    fn new() -> Self {
        MockCallback {
            messages: Arc::new(Mutex::new(Vec::new())),
            _is_running: true,
        }
    }
    fn on_status_emitted(&self, msg: String) {
        self.messages.lock().unwrap().push(msg);
    }
    fn on_error_emitted(&self, msg: String) {
        self.messages.lock().unwrap().push(format!("ERROR:{}", msg));
    }
    fn on_image_saved(&self, msg: String) {
        self.messages
            .lock()
            .unwrap()
            .push(format!("image_saved:{}", msg));
    }
}

// --- Tests ---

#[test]
fn test_sync_runner_upload() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let temp = tempdir().unwrap();
        let local_dir = temp.path().join("local");
        std::fs::create_dir(&local_dir).unwrap();

        let file1 = local_dir.join("test.txt");
        std::fs::write(&file1, "hello").unwrap();

        let config = json!({
            "local_path": local_dir.to_str().unwrap(),
            "remote_path": "remote",
            "action_local": "upload",
            "action_remote": "download",
            "dry_run": false
        });

        let runner = SyncRunner::new(&config);
        let remote_files = Arc::new(Mutex::new(HashMap::new()));
        let actions = Arc::new(Mutex::new(Vec::new()));
        let mut sync = MockSync {
            remote_files: remote_files.clone(),
            actions: actions.clone(),
        };

        let callback = Bound::new(py, MockCallback::new()).unwrap();
        let client = Client::new();

        let _stats = runner
            .run(
                py,
                &mut sync,
                &client,
                callback.to_owned().into_any().unbind(),
            )
            .unwrap();

        let act = actions.lock().unwrap();
        assert!(act.contains(&"upload:test.txt".to_string()));
    });
}

#[test]
fn test_sync_runner_download() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let temp = tempdir().unwrap();
        let local_dir = temp.path().join("local");
        std::fs::create_dir(&local_dir).unwrap();

        let config = json!({
            "local_path": local_dir.to_str().unwrap(),
            "remote_path": "remote",
            "action_local": "upload",
            "action_remote": "download",
            "dry_run": false
        });

        let runner = SyncRunner::new(&config);
        let mut remote_files = HashMap::new();
        remote_files.insert(
            "remote_file.txt".to_string(),
            SyncItem {
                rel_path: "remote_file.txt".to_string(),
                abs_path_or_id: "id123".to_string(),
                mtime: 0,
                is_folder: false,
            },
        );

        let remote_files_arc = Arc::new(Mutex::new(remote_files));
        let actions = Arc::new(Mutex::new(Vec::new()));
        let mut sync = MockSync {
            remote_files: remote_files_arc,
            actions,
        };

        let callback = Bound::new(py, MockCallback::new()).unwrap();
        let client = Client::new();

        let _stats = runner
            .run(
                py,
                &mut sync,
                &client,
                callback.to_owned().into_any().unbind(),
            )
            .unwrap();

        assert!(local_dir.join("remote_file.txt").exists());
    });
}

#[tokio::test]
async fn test_file_loader_wait() {
    use base::web::file_loader::WebFileLoaderRust;
    use std::collections::HashSet;
    use std::time::Duration;

    let temp = tempdir().unwrap();
    let download_dir = temp.path().to_str().unwrap().to_string();
    let loader = WebFileLoaderRust::new(&download_dir);
    let initial_files = HashSet::new();

    // Spawn a thread to "download" a file after a short delay
    let download_dir_clone = download_dir.clone();
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_millis(1500)).await;
        std::fs::write(
            std::path::Path::new(&download_dir_clone).join("new_file.jpg"),
            "data",
        )
        .unwrap();
    });

    let result = loader
        .wait_for_download_to_complete(&initial_files, 5)
        .await
        .unwrap();

    assert!(result.is_some());
    assert_eq!(
        result.unwrap().file_name().unwrap().to_str().unwrap(),
        "new_file.jpg"
    );
}

#[test]
fn test_board_crawler_run() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let mut server = Server::new();
        let _m1 = server
            .mock("GET", "/posts")
            .with_status(200)
            .with_header("content-type", "application/json")
            .with_body(
                json!([
                    {
                        "id": 1,
                        "md5": "abc12345",
                        "file_url": format!("{}/image1.jpg", server.url())
                    }
                ])
                .to_string(),
            )
            .create();

        let _m2 = server
            .mock("GET", "/image1.jpg")
            .with_status(200)
            .with_body("fake-image-bytes")
            .create();

        let temp = tempdir().unwrap();
        let download_dir = temp.path().join("downloads");

        let config = json!({
            "download_dir": download_dir.to_str().unwrap(),
            "max_pages": 1,
            "limit": 10,
            "tags": "test"
        });

        let crawler_handler = BoardCrawler::new(&config);
        let mock_crawler = MockCrawler {
            base_url: server.url(),
        };

        let callback = Bound::new(py, MockCallback::new()).unwrap();
        let client = Client::new();

        let downloaded = crawler_handler
            .run(
                py,
                &mock_crawler,
                &client,
                callback.to_owned().into_any().unbind(),
            )
            .unwrap();

        assert_eq!(downloaded, 1);
        assert!(download_dir.join("1_abc12345.jpg").exists());
        assert!(download_dir.join("1_abc12345.json").exists());

        let msgs = callback.borrow().messages.lock().unwrap().clone();
        assert!(msgs.iter().any(|m| m.contains("image_saved:")));
    });
}
