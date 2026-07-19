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

/* ---------------- session token ---------------- */

#[tauri::command]
fn session_token_get(origin: String) -> Result<Option<String>, String> {
    Ok(secrets::get(&backend::token_origin(&origin)?))
}

#[tauri::command]
fn session_token_set(origin: String, token: String) -> Result<(), String> {
    secrets::set(&backend::token_origin(&origin)?, &token)
}

#[tauri::command]
fn session_token_clear(origin: String) -> Result<(), String> {
    secrets::clear(&backend::token_origin(&origin)?)
}

/* ---------------- backend ---------------- */

#[tauri::command]
async fn backend_resolve(
    state: tauri::State<'_, BackendState>,
    allow_service_start: bool,
) -> Result<BackendResolution, String> {
    backend::resolve(&state, allow_service_start).await
}

#[tauri::command]
fn backend_settings_set(
    state: tauri::State<'_, BackendState>,
    strategy: BackendStrategy,
    local_url: String,
    remote_url: Option<String>,
    onboarding_complete: bool,
) -> Result<BackendSettings, String> {
    state.set(strategy, local_url, remote_url, onboarding_complete)
}

#[tauri::command]
fn backend_settings_get(state: tauri::State<'_, BackendState>) -> Result<BackendSettings, String> {
    state.settings()
}

#[tauri::command]
async fn system_metrics() -> Result<metrics::SystemMetrics, String> {
    tauri::async_runtime::spawn_blocking(metrics::collect)
        .await
        .map_err(|err| format!("cannot collect system metrics: {err}"))
}

#[tauri::command]
async fn media_status(
    state: tauri::State<'_, media::MediaState>,
) -> Result<media::MediaSnapshot, String> {
    media::status(&state).await
}

#[tauri::command]
async fn media_control(
    state: tauri::State<'_, media::MediaState>,
    action: media::MediaAction,
) -> Result<(), String> {
    media::control(&state, action).await
}

#[tauri::command]
async fn media_set_ducking(
    state: tauri::State<'_, media::MediaState>,
    ducking_state: media::DuckingState,
    volume_factor: f64,
) -> Result<(), String> {
    media::set_ducking(&state, ducking_state, volume_factor).await
}

#[tauri::command]
async fn media_spectrum_start(
    app: tauri::AppHandle,
    state: tauri::State<'_, media::MediaState>,
) -> Result<(), String> {
    media::start_spectrum(&state, app).await
}

#[tauri::command]
fn media_spectrum_stop(state: tauri::State<'_, media::MediaState>) -> Result<(), String> {
    media::stop_spectrum(&state)
}

#[tauri::command]
async fn service_control(action: service::ServiceAction) -> Result<service::ServiceStatus, String> {
    service::control(action).await
}

#[tauri::command]
fn voice_hud_show(app: tauri::AppHandle) -> Result<(), String> {
    hud::show(&app)
}

#[tauri::command]
fn voice_hud_hide(app: tauri::AppHandle) -> Result<(), String> {
    hud::hide(&app)
}

#[tauri::command]
fn voice_hud_toggle(app: tauri::AppHandle) -> Result<bool, String> {
    hud::toggle(&app)
}

#[tauri::command]
fn window_frame_get(
    state: tauri::State<'_, window::WindowState>,
) -> Result<window::WindowFrame, String> {
    state.get()
}

#[tauri::command]
fn window_frame_set(
    app: tauri::AppHandle,
    state: tauri::State<'_, window::WindowState>,
    frame: window::WindowFrame,
) -> Result<window::WindowFrame, String> {
    let frame = state.set(frame)?;
    window::apply_frame(&app, frame)?;
    Ok(frame)
}

#[tauri::command]
fn main_window_minimize(app: tauri::AppHandle) -> Result<(), String> {
    window::minimize(&app)
}

#[tauri::command]
fn main_window_toggle_maximize(app: tauri::AppHandle) -> Result<bool, String> {
    window::toggle_maximize(&app)
}

#[tauri::command]
fn main_window_hide(app: tauri::AppHandle) -> Result<(), String> {
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
        .invoke_handler(tauri::generate_handler![
            session_token_get,
            session_token_set,
            session_token_clear,
            backend_resolve,
            backend_settings_set,
            backend_settings_get,
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
