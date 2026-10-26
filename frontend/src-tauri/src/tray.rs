//! Native tray. Closing labeled windows hides them; Quit leaves daemons.

use tauri::menu::{MenuBuilder, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{App, AppHandle};

const TRAY_SHOW: &str = "tray-show";
const TRAY_STOP_CLOUD: &str = "tray-stop-cloud";
const TRAY_QUIT: &str = "tray-quit";

/// Menu and click routing. Show and a left-button release restore windows.
/// Quit exits. Stop-cloud stays a no-op until the daemon command exists.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayAction {
    Restore,
    StopCloud,
    Quit,
    Ignore,
}

pub fn tray_action(id: &str) -> TrayAction {
    match id {
        TRAY_SHOW => TrayAction::Restore,
        TRAY_STOP_CLOUD => TrayAction::StopCloud,
        TRAY_QUIT => TrayAction::Quit,
        _ => TrayAction::Ignore,
    }
}

pub fn tray_click_action(button: MouseButton, state: MouseButtonState) -> TrayAction {
    if button == MouseButton::Left && state == MouseButtonState::Up {
        TrayAction::Restore
    } else {
        TrayAction::Ignore
    }
}

fn on_menu(app: &AppHandle, id: &str) {
    match tray_action(id) {
        TrayAction::Restore => {
            let _ = crate::window_registry::restore(app);
        }
        TrayAction::StopCloud => {
            log::warn!("cloud stop requires the authenticated daemon command path")
        }
        TrayAction::Quit => app.exit(0),
        TrayAction::Ignore => {}
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
                button,
                button_state,
                ..
            } = event
            {
                if tray_click_action(button, button_state) == TrayAction::Restore {
                    let _ = crate::window_registry::restore(tray.app_handle());
                }
            }
        })
        .build(app)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        tray_action, tray_click_action, TrayAction, TRAY_QUIT, TRAY_SHOW, TRAY_STOP_CLOUD,
    };
    use tauri::tray::{MouseButton, MouseButtonState};

    #[test]
    fn show_restores_and_quit_exits() {
        assert_eq!(tray_action(TRAY_SHOW), TrayAction::Restore);
        assert_eq!(tray_action(TRAY_QUIT), TrayAction::Quit);
        assert_eq!(tray_action(TRAY_STOP_CLOUD), TrayAction::StopCloud);
        assert_eq!(tray_action("tray-other"), TrayAction::Ignore);
    }

    #[test]
    fn left_release_restores_and_other_clicks_do_not() {
        assert_eq!(
            tray_click_action(MouseButton::Left, MouseButtonState::Up),
            TrayAction::Restore
        );
        assert_eq!(
            tray_click_action(MouseButton::Left, MouseButtonState::Down),
            TrayAction::Ignore
        );
        assert_eq!(
            tray_click_action(MouseButton::Right, MouseButtonState::Up),
            TrayAction::Ignore
        );
    }
}
