//! Dax Desktop — Rust core.
//!
//! Owns only what the webview cannot do or should not be trusted with
//! (PLAN.md 3.2): secret storage, the tray, single-instance, window
//! management, and backend mode. It does NOT proxy API calls — the webview
//! talks HTTP/WebSocket to the backend directly (3.1).

mod backend;
mod hud;
mod media;
mod metrics;
mod secrets;
mod service;
mod tray;
mod window;

use backend::{BackendResolution, BackendSettings, BackendState, BackendStrategy};
use tauri::Manager;
use tauri_plugin_global_shortcut::GlobalShortcutExt;

const MAIN_WINDOW: &str = "main";
const HUD_WINDOW: &str = "voice-hud";

fn authorize_caller(window: &tauri::WebviewWindow, allowed: &[&str]) -> Result<(), String> {
    authorize_label(window.label(), allowed)
}

fn authorize_label(label: &str, allowed: &[&str]) -> Result<(), String> {
    if allowed.contains(&label) {
        Ok(())
    } else {
        Err(format!(
            "window '{label}' is not authorized for this command"
        ))
    }
}

fn authorize_token_origin(
    state: &BackendState,
    requested: &str,
    instance_id: &str,
) -> Result<String, String> {
    state.token_authority(requested, instance_id)
}

/* ---------------- session token ---------------- */

#[tauri::command]
fn session_token_get(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
    origin: String,
    instance_id: String,
) -> Result<Option<String>, String> {
    authorize_caller(&window, &[MAIN_WINDOW, HUD_WINDOW])?;
    let origin = authorize_token_origin(&state, &origin, &instance_id)?;
    secrets::get(&origin, &instance_id)
}

#[tauri::command]
fn session_token_set(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
    origin: String,
    instance_id: String,
    token: String,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    let origin = state.token_authority(&origin, &instance_id)?;
    secrets::set(&origin, &instance_id, &token)
}

#[tauri::command]
fn session_token_clear(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
    origin: String,
    instance_id: String,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    let origin = state.token_authority(&origin, &instance_id)?;
    secrets::clear(&origin, &instance_id)
}

/* ---------------- backend ---------------- */

#[tauri::command]
async fn backend_resolve(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
    allow_service_start: bool,
) -> Result<BackendResolution, String> {
    authorize_caller(&window, &[MAIN_WINDOW, HUD_WINDOW])?;
    if window.label() == HUD_WINDOW && allow_service_start {
        return Err("voice HUD may not start the backend service".into());
    }
    backend::resolve(&state, allow_service_start).await
}

#[tauri::command]
fn backend_settings_set(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
    strategy: BackendStrategy,
    local_url: String,
    remote_url: Option<String>,
    onboarding_complete: bool,
) -> Result<BackendSettings, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    let current = state.settings()?;
    let next_url = match strategy {
        BackendStrategy::Local => backend::validate_local_url(&local_url)?,
        BackendStrategy::Remote => backend::validate_remote_url(
            remote_url
                .as_deref()
                .ok_or_else(|| "remote_url is required for the remote strategy".to_string())?,
        )?,
    };
    if backend::token_origin(&current.active_url)? != backend::token_origin(&next_url)? {
        if let Some(instance_id) = current.active_server_id.as_deref() {
            secrets::clear(&backend::token_origin(&current.active_url)?, instance_id)?;
        }
    }
    state.set(strategy, local_url, remote_url, onboarding_complete)
}

#[tauri::command]
fn backend_settings_get(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
) -> Result<BackendSettings, String> {
    authorize_caller(&window, &[MAIN_WINDOW, HUD_WINDOW])?;
    state.settings()
}

#[tauri::command]
fn backend_authority_replace_confirmed(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, BackendState>,
) -> Result<BackendSettings, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    state.reset_authority_pin(secrets::clear_authority)
}

#[tauri::command]
async fn system_metrics(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, metrics::MetricsState>,
) -> Result<metrics::SystemMetrics, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || state.collect())
        .await
        .map_err(|err| format!("cannot collect system metrics: {err}"))?
}

#[tauri::command]
async fn media_status(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, media::MediaState>,
) -> Result<media::MediaSnapshot, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    media::status(&state).await
}

#[tauri::command]
async fn media_control(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, media::MediaState>,
    action: media::MediaAction,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    media::control(&state, action).await
}

#[tauri::command]
async fn media_set_ducking(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, media::MediaState>,
    ducking_state: media::DuckingState,
    volume_factor: f64,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    media::set_ducking(&state, ducking_state, volume_factor).await
}

#[tauri::command]
async fn media_spectrum_start(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    state: tauri::State<'_, media::MediaState>,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    media::start_spectrum(&state, app).await
}

#[tauri::command]
fn media_spectrum_stop(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, media::MediaState>,
) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    media::stop_spectrum(&state)
}

#[tauri::command]
async fn service_control(
    window: tauri::WebviewWindow,
    target: service::ServiceTarget,
    action: service::ServiceAction,
) -> Result<service::ServiceStatus, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    service::control_target(target, action).await
}

#[tauri::command]
fn voice_hud_show(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    hud::show(&app)
}

#[tauri::command]
fn voice_hud_hide(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW, HUD_WINDOW])?;
    hud::hide(&app)
}

#[tauri::command]
fn voice_hud_toggle(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<bool, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    hud::toggle(&app)
}

#[tauri::command]
fn window_frame_get(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, window::WindowState>,
) -> Result<window::WindowFrame, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    state.get()
}

#[tauri::command]
fn window_frame_set(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    state: tauri::State<'_, window::WindowState>,
    frame: window::WindowFrame,
) -> Result<window::WindowFrame, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    let frame = state.set(frame)?;
    window::apply_frame(&app, frame)?;
    Ok(frame)
}

#[tauri::command]
fn main_window_minimize(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    window::minimize(&app)
}

#[tauri::command]
fn main_window_toggle_maximize(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
) -> Result<bool, String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    window::toggle_maximize(&app)
}

#[tauri::command]
fn main_window_hide(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<(), String> {
    authorize_caller(&window, &[MAIN_WINDOW])?;
    window::hide(&app)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // A second launch focuses the running window instead of starting a
        // second app. Must be registered before any other plugin.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            tray::focus_main(app);
        }))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(hud::handle_shortcut)
                .build(),
        )
        .on_window_event(|window, event| {
            if matches!(window.label(), MAIN_WINDOW | HUD_WINDOW) {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    if let Err(err) = window.hide() {
                        eprintln!("cannot hide {} window on close: {err}", window.label());
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            session_token_get,
            session_token_set,
            session_token_clear,
            backend_resolve,
            backend_settings_set,
            backend_settings_get,
            backend_authority_replace_confirmed,
            system_metrics,
            media_status,
            media_control,
            media_set_ducking,
            media_spectrum_start,
            media_spectrum_stop,
            service_control,
            voice_hud_show,
            voice_hud_hide,
            voice_hud_toggle,
            window_frame_get,
            window_frame_set,
            main_window_minimize,
            main_window_toggle_maximize,
            main_window_hide,
        ])
        .setup(|app| {
            let config_dir = app
                .path()
                .app_config_dir()
                .map_err(|err| format!("cannot resolve app config directory: {err}"))?;
            app.manage(BackendState::load(&config_dir)?);
            app.manage(media::MediaState::default());
            app.manage(metrics::MetricsState::default());
            let window_state = window::WindowState::load(&config_dir)?;
            window::apply_saved_frame(app.handle(), &window_state)?;
            app.manage(window_state);

            if let Err(err) = tray::build(app.handle()) {
                // A missing appindicator provider should degrade, not abort.
                eprintln!("tray unavailable: {err}");
            }
            for shortcut in ["Super+Shift+D", "Ctrl+Space"] {
                if let Err(err) = app.global_shortcut().register(shortcut) {
                    eprintln!("global shortcut {shortcut} unavailable: {err}");
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Dax Desktop");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn privileged_commands_are_main_window_only() {
        assert!(authorize_label(MAIN_WINDOW, &[MAIN_WINDOW]).is_ok());
        assert!(authorize_label(HUD_WINDOW, &[MAIN_WINDOW]).is_err());
        assert!(authorize_label(HUD_WINDOW, &[MAIN_WINDOW, HUD_WINDOW]).is_ok());
    }
}
