pub mod crawler;
pub mod danbooru;
pub mod dropbox_sync;
pub mod file_loader;
pub mod gelbooru;
pub mod google_drive_sync;
pub mod image_board_crawler;
pub mod image_crawler;
pub mod one_drive_sync;
#[cfg(feature = "python")]
pub mod reverse_image_search;
pub mod sankaku;
pub mod sync;
pub mod web_requests;

#[cfg(feature = "python")]
use pyo3::prelude::*;
use reqwest::blocking::Client;
use serde_json::Value;
use std::time::Duration;

use danbooru::DanbooruCrawlerImpl;
use dropbox_sync::DropboxSyncImpl;
use gelbooru::GelbooruCrawlerImpl;
use google_drive_sync::GoogleDriveSyncImpl;
use image_board_crawler::BoardCrawler;
#[cfg(feature = "python")]
pub use image_crawler::run_image_crawler;
use one_drive_sync::OneDriveSyncImpl;
#[cfg(feature = "python")]
pub use reverse_image_search::run_reverse_image_search;
use sankaku::SankakuCrawlerImpl;
use sync::SyncRunner;

#[cfg(feature = "python")]
#[pyfunction]
pub fn run_board_crawler(
    py: Python<'_>,
    crawler_name: String,
    config_json: String,
    callback_obj: Py<PyAny>,
) -> PyResult<u32> {
    let config_val: Value = serde_json::from_str(&config_json).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
    })?;

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        .build()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create client: {}", e)))?;

    let board_crawler = BoardCrawler::new(&config_val);

    match crawler_name.to_lowercase().as_str() {
        "danbooru" => {
            let crawler = DanbooruCrawlerImpl::new(&config_val);
            board_crawler.run(py, &crawler, &client, callback_obj)
        }
        "gelbooru" => {
            let crawler = GelbooruCrawlerImpl::new(&config_val);
            board_crawler.run(py, &crawler, &client, callback_obj)
        }
        "sankaku" | "sankakucrawler" => {
            let crawler = SankakuCrawlerImpl::new(&config_val);
            board_crawler.run(py, &crawler, &client, callback_obj)
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Unknown crawler: {}",
            crawler_name
        ))),
    }
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn run_sync(
    py: Python<'_>,
    provider_name: String,
    config_json: String,
    callback_obj: Py<PyAny>,
) -> PyResult<String> {
    let config_val: Value = serde_json::from_str(&config_json).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
    })?;

    let client = Client::builder()
        .timeout(Duration::from_secs(60))
        .build()
        .map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to create client: {}",
                e
            ))
        })?;

    let runner = SyncRunner::new(&config_val);

    let stats = match provider_name.to_lowercase().as_str() {
        "dropbox" => {
            let mut sync = DropboxSyncImpl::new(&config_val);
            runner.run(py, &mut sync, &client, callback_obj)
        }
        "google_drive" | "google" | "drive" => {
            let mut sync = GoogleDriveSyncImpl::new(&config_val);
            runner.run(py, &mut sync, &client, callback_obj)
        }
        "one_drive" | "onedrive" | "microsoft" => {
            let mut sync = OneDriveSyncImpl::new(&config_val);
            runner.run(py, &mut sync, &client, callback_obj)
        }
        _ => {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown sync provider: {}",
                provider_name
            )))
        }
    }
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Sync Error: {}", e)))?;

    serde_json::to_string(&stats).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
            "JSON serialization error: {}",
            e
        ))
    })
}
