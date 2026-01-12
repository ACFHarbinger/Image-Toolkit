mod core_commands;
mod wallpaper_commands;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            wallpaper_commands::set_wallpaper,
            wallpaper_commands::get_monitors,
            wallpaper_commands::update_slideshow_config,
            wallpaper_commands::toggle_slideshow_daemon,
            core_commands::scan_files,
            core_commands::convert_image_batch
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
