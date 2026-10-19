#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

const IPC_VERSION: u8 = 1;

#[derive(Debug, Serialize)]
struct IpcResponse {
    version: u8,
    request_id: String,
    status: &'static str,
    payload: BTreeMap<String, Value>,
    error: Option<String>,
}

fn ok(request_id: String, payload: BTreeMap<String, Value>) -> IpcResponse {
    IpcResponse { version: IPC_VERSION, request_id, status: "ok", payload, error: None }
}

#[tauri::command]
fn open_media(request_id: String) -> Result<IpcResponse, String> {
    // The Image-Toolkit host will provide the real picker/document transport.
    Ok(ok(request_id, BTreeMap::from([(String::from("available"), json!(false))])))
}

#[tauri::command]
fn export_document(request_id: String) -> Result<IpcResponse, String> {
    // Export routing is intentionally host-owned until the document IPC schema
    // is finalized; this command keeps the standalone seam stable.
    Ok(ok(request_id, BTreeMap::from([(String::from("available"), json!(false))])))
}

#[tauri::command]
fn notify(request_id: String, message: String) -> Result<IpcResponse, String> {
    println!("[HIE] {message}");
    Ok(ok(request_id, BTreeMap::new()))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_media, export_document, notify])
        .run(tauri::generate_context!())
        .expect("error while running HIE Tauri application");
}
