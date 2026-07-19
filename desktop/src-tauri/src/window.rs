//! Persistent main-window frame preference and tightly scoped window actions.

use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::Mutex,
};
use tauri::{AppHandle, Manager, Runtime};

const SETTINGS_FILE: &str = "window.json";
const SETTINGS_VERSION: u8 = 1;

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum WindowFrame {
    Native,
    #[default]
    Custom,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct WindowSettings {
    version: u8,
    frame: WindowFrame,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct LegacyWindowSettings {
    decorations: bool,
}

pub struct WindowState {
    frame: Mutex<WindowFrame>,
    path: PathBuf,
}

impl WindowState {
    pub fn load(config_dir: &Path) -> Result<Self, String> {
        let path = config_dir.join(SETTINGS_FILE);
        let (frame, migrated) = match fs::read(&path) {
            Ok(bytes) => match decode_settings(&bytes) {
                Ok(decoded) => decoded,
                Err(err) if err.starts_with("unsupported window settings version") => {
                    return Err(err);
                }
                Err(err) => {
                    eprintln!("{err}; using safe window defaults");
                    (WindowFrame::default(), false)
                }
            },
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => (WindowFrame::Custom, false),
            Err(err) => return Err(format!("cannot read window settings: {err}")),
        };
        if migrated {
            persist_settings(&path, frame)?;
        }
        Ok(Self {
            frame: Mutex::new(frame),
            path,
        })
    }

    pub fn get(&self) -> Result<WindowFrame, String> {
        self.frame
            .lock()
            .map(|frame| *frame)
            .map_err(|_| "window settings lock is poisoned".into())
    }

    pub fn set(&self, frame: WindowFrame) -> Result<WindowFrame, String> {
        persist_settings(&self.path, frame)?;
        *self
            .frame
            .lock()
            .map_err(|_| "window settings lock is poisoned".to_string())? = frame;
        Ok(frame)
    }
}

pub fn apply_saved_frame<R: Runtime>(
    app: &AppHandle<R>,
    state: &WindowState,
) -> Result<(), String> {
    apply_frame(app, state.get()?)
}

pub fn apply_frame<R: Runtime>(app: &AppHandle<R>, frame: WindowFrame) -> Result<(), String> {
    main_window(app)?
        .set_decorations(frame == WindowFrame::Native)
        .map_err(|err| format!("cannot apply main window frame: {err}"))
}

pub fn minimize<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    main_window(app)?
        .minimize()
        .map_err(|err| format!("cannot minimize main window: {err}"))
}

pub fn toggle_maximize<R: Runtime>(app: &AppHandle<R>) -> Result<bool, String> {
    let window = main_window(app)?;
    let maximized = window
        .is_maximized()
        .map_err(|err| format!("cannot inspect main window: {err}"))?;
    if maximized {
        window
            .unmaximize()
            .map_err(|err| format!("cannot restore main window: {err}"))?;
    } else {
        window
            .maximize()
            .map_err(|err| format!("cannot maximize main window: {err}"))?;
    }
    Ok(!maximized)
}

pub fn hide<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    main_window(app)?
        .hide()
        .map_err(|err| format!("cannot hide main window: {err}"))
}

pub fn show_main<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let window = main_window(app)?;
    if let Some(state) = app.try_state::<WindowState>() {
        window
            .set_decorations(state.get()? == WindowFrame::Native)
            .map_err(|err| format!("cannot restore main window frame: {err}"))?;
    }
    window
        .show()
        .and_then(|_| window.unminimize())
        .and_then(|_| window.set_focus())
        .map_err(|err| format!("cannot show main window: {err}"))
}

fn main_window<R: Runtime>(app: &AppHandle<R>) -> Result<tauri::WebviewWindow<R>, String> {
    get_or_create(app, "main")
}

pub fn get_or_create<R: Runtime>(
    app: &AppHandle<R>,
    label: &str,
) -> Result<tauri::WebviewWindow<R>, String> {
    if let Some(window) = app.get_webview_window(label) {
        return Ok(window);
    }
    let config = app
        .config()
        .app
        .windows
        .iter()
        .find(|config| config.label == label)
        .ok_or_else(|| format!("window configuration for '{label}' is unavailable"))?;
    tauri::WebviewWindowBuilder::from_config(app, config)
        .map_err(|err| format!("cannot prepare '{label}' window: {err}"))?
        .build()
        .map_err(|err| format!("cannot recreate '{label}' window: {err}"))
}

fn decode_settings(bytes: &[u8]) -> Result<(WindowFrame, bool), String> {
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|err| format!("invalid window settings file: {err}"))?;
    if let Some(frame) = value.as_str() {
        let frame = serde_json::from_value(serde_json::Value::String(frame.to_owned()))
            .map_err(|err| format!("invalid legacy window frame: {err}"))?;
        return Ok((frame, true));
    }
    if value.get("decorations").is_some() {
        let legacy: LegacyWindowSettings = serde_json::from_value(value)
            .map_err(|err| format!("invalid legacy window settings file: {err}"))?;
        return Ok((
            if legacy.decorations {
                WindowFrame::Native
            } else {
                WindowFrame::Custom
            },
            true,
        ));
    }
    let settings: WindowSettings = serde_json::from_value(value)
        .map_err(|err| format!("invalid window settings file: {err}"))?;
    if settings.version != SETTINGS_VERSION {
        return Err(format!(
            "unsupported window settings version {}",
            settings.version
        ));
    }
    Ok((settings.frame, false))
}

fn persist_settings(path: &Path, frame: WindowFrame) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "window settings path has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|err| format!("cannot create config directory: {err}"))?;
    let bytes = serde_json::to_vec_pretty(&WindowSettings {
        version: SETTINGS_VERSION,
        frame,
    })
    .map_err(|err| format!("cannot serialize window settings: {err}"))?;
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, bytes).map_err(|err| format!("cannot write window settings: {err}"))?;
    fs::rename(&temp, path).map_err(|err| {
        let _ = fs::remove_file(&temp);
        format!("cannot commit window settings: {err}")
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_to_compact_custom_frame() {
        assert_eq!(WindowFrame::default(), WindowFrame::Custom);
    }

    #[test]
    fn migrates_legacy_frame_formats() {
        assert_eq!(
            decode_settings(br#""native""#).unwrap(),
            (WindowFrame::Native, true)
        );
        assert_eq!(
            decode_settings(br#"{"decorations":false}"#).unwrap(),
            (WindowFrame::Custom, true)
        );
    }

    #[test]
    fn validates_versioned_settings() {
        assert_eq!(
            decode_settings(br#"{"version":1,"frame":"custom"}"#).unwrap(),
            (WindowFrame::Custom, false)
        );
        assert!(decode_settings(br#"{"version":2,"frame":"custom"}"#).is_err());
    }

    #[test]
    fn malformed_settings_recover_to_custom_frame() {
        let directory =
            std::env::temp_dir().join(format!("dax-malformed-window-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        fs::write(directory.join(SETTINGS_FILE), b"not json").unwrap();
        let state = WindowState::load(&directory).unwrap();
        assert_eq!(state.get().unwrap(), WindowFrame::Custom);
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn newer_settings_versions_are_not_silently_overwritten() {
        let directory =
            std::env::temp_dir().join(format!("dax-newer-window-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        fs::write(
            directory.join(SETTINGS_FILE),
            br#"{"version":2,"frame":"native"}"#,
        )
        .unwrap();
        assert!(WindowState::load(&directory).is_err());
        let _ = fs::remove_dir_all(directory);
    }
}
