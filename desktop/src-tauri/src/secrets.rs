//! Session token storage in the OS secret store.
//!
//! PLAN.md 3.2: the token is a credential, so it lives in the keyring rather
//! than `localStorage`. On Fedora that is the Secret Service (gnome-keyring).
//!
//! The keyring can be unavailable — a headless session, a locked keyring, no
//! Secret Service provider. Rather than making login impossible in that case,
//! we fall back to an in-memory store for the lifetime of the process. That is
//! a real (documented) downgrade: the user re-authenticates on next launch.

use std::sync::Mutex;

const SERVICE: &str = "dev.dax.desktop";
const ACCOUNT: &str = "session-token";

/// Process-lifetime fallback used when the OS keyring is not usable.
static MEMORY_FALLBACK: Mutex<Option<String>> = Mutex::new(None);

fn entry() -> Option<keyring::Entry> {
    match keyring::Entry::new(SERVICE, ACCOUNT) {
        Ok(entry) => Some(entry),
        Err(err) => {
            eprintln!("keyring unavailable, using in-memory token store: {err}");
            None
        }
    }
}

pub fn get() -> Option<String> {
    if let Some(entry) = entry() {
        match entry.get_password() {
            Ok(token) => return Some(token),
            Err(keyring::Error::NoEntry) => return None,
            Err(err) => {
                eprintln!("keyring read failed, falling back to memory: {err}");
            }
        }
    }
    MEMORY_FALLBACK.lock().ok().and_then(|guard| guard.clone())
}

pub fn set(token: &str) -> Result<(), String> {
    if let Some(entry) = entry() {
        match entry.set_password(token) {
            Ok(()) => return Ok(()),
            Err(err) => eprintln!("keyring write failed, falling back to memory: {err}"),
        }
    }
    let mut guard = MEMORY_FALLBACK.lock().map_err(|e| e.to_string())?;
    *guard = Some(token.to_string());
    Ok(())
}

pub fn clear() -> Result<(), String> {
    if let Some(entry) = entry() {
        // NoEntry just means there was nothing to clear.
        match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => {}
            Err(err) => eprintln!("keyring delete failed: {err}"),
        }
    }
    let mut guard = MEMORY_FALLBACK.lock().map_err(|e| e.to_string())?;
    *guard = None;
    Ok(())
}
