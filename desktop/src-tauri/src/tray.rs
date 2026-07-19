//! Tray icon and menu.
//!
//! Needs `libappindicator-gtk3` at runtime on Linux.

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Runtime,
};

const TALK_EVENT: &str = "tray://talk-to-dax";
const TOGGLE_VOICE_EVENT: &str = "tray://toggle-voice-listening";

#[derive(Debug, PartialEq, Eq)]
enum MenuAction {
    Show,
    Talk,
    ToggleVoice,
    Quit,
}

fn menu_action(id: &str) -> Option<MenuAction> {
    match id {
        "show" => Some(MenuAction::Show),
        "talk" => Some(MenuAction::Talk),
        "toggle-voice" => Some(MenuAction::ToggleVoice),
        "quit" => Some(MenuAction::Quit),
        _ => None,
    }
}

pub fn build<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Show Dax", true, None::<&str>)?;
    let talk = MenuItem::with_id(app, "talk", "Talk to Dax / HUD", true, None::<&str>)?;
    let toggle_voice = MenuItem::with_id(
        app,
        "toggle-voice",
        "Toggle voice listening",
        true,
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &talk, &toggle_voice, &quit])?;

    TrayIconBuilder::with_id("main-tray")
        .icon(
            app.default_window_icon()
                .cloned()
                .ok_or_else(|| tauri::Error::AssetNotFound("default window icon".into()))?,
        )
        .tooltip("Dax")
        .menu(&menu)
        // The menu must not open on a plain left click, or the click handler
        // below never fires.
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match menu_action(event.id.as_ref()) {
            Some(MenuAction::Show) => focus_main(app),
            Some(MenuAction::Talk) => {
                if let Err(err) = app.emit_to("main", TALK_EVENT, ()) {
                    eprintln!("cannot emit tray talk event: {err}");
                }
            }
            Some(MenuAction::ToggleVoice) => {
                if let Err(err) = app.emit_to("main", TOGGLE_VOICE_EVENT, ()) {
                    eprintln!("cannot emit tray voice event: {err}");
                }
            }
            Some(MenuAction::Quit) => app.exit(0),
            None => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                focus_main(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

pub fn focus_main<R: Runtime>(app: &AppHandle<R>) {
    if let Err(err) = crate::window::show_main(app) {
        eprintln!("cannot restore main window: {err}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tray_ids_map_to_frontend_actions() {
        assert_eq!(menu_action("talk"), Some(MenuAction::Talk));
        assert_eq!(menu_action("toggle-voice"), Some(MenuAction::ToggleVoice));
        assert_eq!(menu_action("unknown"), None);
    }
}
