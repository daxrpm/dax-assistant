use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutEvent, ShortcutState};

const HUD_LABEL: &str = "voice-hud";

pub fn show<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let window = crate::window::get_or_create(app, HUD_LABEL)?;
    window.show().map_err(|err| err.to_string())
}

pub fn hide<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    if let Some(window) = app.get_webview_window(HUD_LABEL) {
        window.hide().map_err(|err| err.to_string())?;
    }
    Ok(())
}

pub fn toggle<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let window = crate::window::get_or_create(app, HUD_LABEL)?;
    let visible = window.is_visible().map_err(|err| err.to_string())?;
    if visible {
        window.hide().map_err(|err| err.to_string())?;
        Ok(false)
    } else {
        window.show().map_err(|err| err.to_string())?;
        Ok(true)
    }
}

#[derive(Debug, PartialEq, Eq)]
enum ShortcutAction {
    FocusMain,
    PushToTalkDown,
    PushToTalkUp,
}

fn shortcut_action(shortcut: &Shortcut, state: ShortcutState) -> Option<ShortcutAction> {
    if shortcut.matches(Modifiers::SUPER | Modifiers::SHIFT, Code::KeyD) {
        return (state == ShortcutState::Pressed).then_some(ShortcutAction::FocusMain);
    }
    if shortcut.matches(Modifiers::CONTROL, Code::Space) {
        return Some(if state == ShortcutState::Pressed {
            ShortcutAction::PushToTalkDown
        } else {
            ShortcutAction::PushToTalkUp
        });
    }
    None
}

pub fn handle_shortcut(app: &AppHandle, shortcut: &Shortcut, event: ShortcutEvent) {
    match shortcut_action(shortcut, event.state) {
        Some(ShortcutAction::FocusMain) => crate::tray::focus_main(app),
        Some(ShortcutAction::PushToTalkDown) => {
            if let Err(err) = show(app) {
                eprintln!("cannot show voice HUD: {err}");
            }
            if let Err(err) = app.emit("hotkey://push-to-talk-down", ()) {
                eprintln!("cannot emit push-to-talk down: {err}");
            }
        }
        Some(ShortcutAction::PushToTalkUp) => {
            if let Err(err) = app.emit("hotkey://push-to-talk-up", ()) {
                eprintln!("cannot emit push-to-talk up: {err}");
            }
        }
        None => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn control_space_has_distinct_press_and_release_actions() {
        let shortcut = Shortcut::new(Some(Modifiers::CONTROL), Code::Space);
        assert_eq!(
            shortcut_action(&shortcut, ShortcutState::Pressed),
            Some(ShortcutAction::PushToTalkDown)
        );
        assert_eq!(
            shortcut_action(&shortcut, ShortcutState::Released),
            Some(ShortcutAction::PushToTalkUp)
        );
    }

    #[test]
    fn main_shortcut_only_fires_on_press() {
        let shortcut = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyD);
        assert_eq!(
            shortcut_action(&shortcut, ShortcutState::Pressed),
            Some(ShortcutAction::FocusMain)
        );
        assert_eq!(shortcut_action(&shortcut, ShortcutState::Released), None);
    }
}
