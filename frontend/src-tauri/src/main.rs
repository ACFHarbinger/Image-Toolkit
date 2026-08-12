#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[tauri::command]
fn open_media() -> Result<(), String> {
    // The Image-Toolkit host will provide the real picker/document transport.
    Ok(())
}

#[tauri::command]
fn export_document() -> Result<(), String> {
    // Export routing is intentionally host-owned until the document IPC schema
    // is finalized; this command keeps the standalone seam stable.
    Ok(())
}

#[tauri::command]
fn notify(message: String) -> Result<(), String> {
    println!("[HIE] {message}");
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_media, export_document, notify])
        .run(tauri::generate_context!())
        .expect("error while running HIE Tauri application");
}
