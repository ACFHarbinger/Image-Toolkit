mod benchmark_commands;
mod bridge_commands;
mod comfy_commands;
mod core_commands;
mod gui_gate;
mod settings_commands;
mod tray;
mod wallpaper_commands;
mod window_registry;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            // Wallpaper commands
            wallpaper_commands::set_wallpaper,
            wallpaper_commands::get_monitors,
            wallpaper_commands::update_slideshow_config,
            wallpaper_commands::toggle_slideshow_daemon,
            // Core file commands
            core_commands::scan_files,
            core_commands::delete_files,
            core_commands::delete_directory,
            // Settings commands (#917). Vault unlock is auth.status, not a Rust command.
            settings_commands::load_user_settings,
            settings_commands::save_user_settings,
            settings_commands::update_master_password,
            // Benchmark analytics
            benchmark_commands::load_benchmark_reports,
            window_registry::window_popout,
            window_registry::window_hide_all,
            window_registry::window_restore,
            window_registry::window_focus,
            comfy_commands::open_comfy_browser,
            bridge_commands::bridge_request
        ])
        .on_window_event(|window, event| window_registry::on_window_event(window, event))
        .setup(|app| {
            // Setup logging
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            app.manage(window_registry::TrayHidden::default());
            tray::install(app)?;
            gui_gate::start(app.handle())?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
