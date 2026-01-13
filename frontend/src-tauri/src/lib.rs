mod auth_commands;
mod core_commands;
mod database_commands;
mod db;
mod video_commands;
mod wallpaper_commands;

use std::env;
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
            core_commands::convert_image_batch,
            core_commands::delete_files,
            core_commands::delete_directory,
            core_commands::merge_images,
            // Authentication commands
            auth_commands::authenticate_user,
            auth_commands::create_user_account,
            auth_commands::load_user_settings,
            auth_commands::save_user_settings,
            auth_commands::update_master_password,
            // Video processing commands
            video_commands::extract_video_clip,
            video_commands::extract_video_frames,
            video_commands::get_video_metadata,
            // Database commands
            database_commands::search_images,
            database_commands::get_all_tags,
            database_commands::get_all_groups,
            database_commands::get_subgroups_for_group,
            database_commands::add_image_to_database,
            database_commands::delete_image_from_database,
            database_commands::get_database_stats,
            database_commands::test_database_connection,
            database_commands::batch_add_images
        ])
        .setup(|app| {
            // Setup logging
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Initialize database connection
            tauri::async_runtime::block_on(async {
                // Load DATABASE_URL from environment or .env file
                dotenv::dotenv().ok();

                let database_url = env::var("DATABASE_URL")
                    .unwrap_or_else(|_| {
                        log::warn!("DATABASE_URL not found, using default");
                        "postgresql://localhost/image_toolkit".to_string()
                    });

                match db::Db::new(&database_url).await {
                    Ok(db_instance) => {
                        // Initialize schema (ensure pgvector extension)
                        if let Err(e) = db_instance.init_schema().await {
                            log::error!("Failed to initialize database schema: {}", e);
                        } else {
                            log::info!("Database connected successfully");
                        }

                        app.manage(db_instance);
                    }
                    Err(e) => {
                        log::error!("Failed to connect to database: {}", e);
                        log::warn!("Running without database support");
                        // Continue without database - some features will be unavailable
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
