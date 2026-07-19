//! Dax Desktop — Rust core.
//!
//! Owns only what the webview cannot do or should not be trusted with
//! (PLAN.md 3.2): secret storage, the tray, single-instance, window
//! management, and backend mode. It does NOT proxy API calls — the webview
//! talks HTTP/WebSocket to the backend directly (3.1).

mod backend;
mod secrets;
mod tray;

use backend::{BackendMode, BackendState, BackendStatus};

/* ---------------- session token ---------------- */

#[tauri::command]
fn session_token_get() -> Option<String> {
    secrets::get()
}

#[tauri::command]
fn session_token_set(token: String) -> Result<(), String> {
    secrets::set(&token)
}

#[tauri::command]
fn session_token_clear() -> Result<(), String> {
    secrets::clear()
}

/* ---------------- backend ---------------- */

#[tauri::command]
async fn backend_status(state: tauri::State<'_, BackendState>) -> Result<BackendStatus, String> {
    let url = state.url();
    let mode = state.mode();
    let healthy = backend::probe(&url).await;
    Ok(BackendStatus {
        mode,
        url,
        healthy,
        pid: None,
    })
}

#[tauri::command]
fn backend_set_mode(
    state: tauri::State<'_, BackendState>,
    mode: BackendMode,
    url: Option<String>,
) -> Result<(), String> {
    state.set(mode, url)
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
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![
            session_token_get,
            session_token_set,
            session_token_clear,
            backend_status,
            backend_set_mode,
        ])
        .setup(|app| {
            if let Err(err) = tray::build(app.handle()) {
                // A missing appindicator provider should degrade, not abort.
                eprintln!("tray unavailable: {err}");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Dax Desktop");
}
