//! Native tray. Closing labeled windows hides them; Quit leaves daemons.

use tauri::menu::{MenuBuilder, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{App, AppHandle};

const TRAY_SHOW: &str = "tray-show";
const TRAY_STOP_CLOUD: &str = "tray-stop-cloud";
const TRAY_QUIT: &str = "tray-quit";

fn on_menu(app: &AppHandle, id: &str) {
    match id {
        TRAY_SHOW => {
            let _ = crate::window_registry::restore(app);
        }
        TRAY_STOP_CLOUD => log::warn!("cloud stop requires the authenticated daemon command path"),
        TRAY_QUIT => app.exit(0),
        _ => {}
    }
}

pub fn install(app: &App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, TRAY_SHOW, "Show Window", true, None::<&str>)?;
    let stop_cloud = MenuItem::with_id(
        app,
        TRAY_STOP_CLOUD,
        "Stop all cloud activity",
        false,
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, TRAY_QUIT, "Quit", true, None::<&str>)?;
    let menu = MenuBuilder::new(app)
        .items(&[&show, &stop_cloud])
        .separator()
        .item(&quit)
        .build()?;

    TrayIconBuilder::with_id("main")
        .icon(tauri::include_image!("icons/32x32.png"))
        .tooltip("Image Toolkit")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| on_menu(app, event.id.as_ref()))
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let _ = crate::window_registry::restore(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}
