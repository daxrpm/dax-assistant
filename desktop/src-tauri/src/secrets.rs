//! Session tokens isolated by normalized backend origin.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

const SERVICE: &str = "dev.dax.desktop";
const LEGACY_ACCOUNT: &str = "session-token";
static MEMORY_FALLBACK: OnceLock<Mutex<HashMap<String, String>>> = OnceLock::new();

fn memory_fallback() -> &'static Mutex<HashMap<String, String>> {
    MEMORY_FALLBACK.get_or_init(|| Mutex::new(HashMap::new()))
}

fn account(origin: &str) -> String {
    let encoded = origin
        .as_bytes()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    format!("session-token-v2:{encoded}")
}

fn entry(account: &str) -> Option<keyring::Entry> {
    match keyring::Entry::new(SERVICE, account) {
        Ok(entry) => Some(entry),
        Err(err) => {
            eprintln!("keyring unavailable, using in-memory token store: {err}");
            None
        }
    }
}

fn read(account: &str) -> Option<String> {
    if let Some(entry) = entry(account) {
        match entry.get_password() {
            Ok(token) => return Some(token),
            Err(keyring::Error::NoEntry) => {}
            Err(err) => eprintln!("keyring read failed, falling back to memory: {err}"),
        }
    }
    memory_fallback()
        .lock()
        .ok()
        .and_then(|guard| guard.get(account).cloned())
}

pub fn get(origin: &str) -> Option<String> {
    let scoped = account(origin);
    if let Some(token) = read(&scoped) {
        return Some(token);
    }
    // A legacy token can only be attributed safely to the active origin asking
    // for it. Move it once; it is never copied across origins.
    let token = read(LEGACY_ACCOUNT)?;
    if set(origin, &token).is_ok() {
        let _ = delete(LEGACY_ACCOUNT);
    }
    Some(token)
}

pub fn set(origin: &str, token: &str) -> Result<(), String> {
    let scoped = account(origin);
    if let Some(entry) = entry(&scoped) {
        match entry.set_password(token) {
            Ok(()) => return Ok(()),
            Err(err) => eprintln!("keyring write failed, falling back to memory: {err}"),
        }
    }
    memory_fallback()
        .lock()
        .map_err(|err| err.to_string())?
        .insert(scoped, token.to_string());
    Ok(())
}

pub fn clear(origin: &str) -> Result<(), String> {
    delete(&account(origin))
}

fn delete(account: &str) -> Result<(), String> {
    if let Some(entry) = entry(account) {
        match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => {}
            Err(err) => eprintln!("keyring delete failed: {err}"),
        }
    }
    memory_fallback()
        .lock()
        .map_err(|err| err.to_string())?
        .remove(account);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accounts_are_stable_and_origin_isolated() {
        assert_eq!(
            account("https://one.example"),
            account("https://one.example")
        );
        assert_ne!(
            account("https://one.example"),
            account("https://two.example")
        );
        assert!(!account("https://one.example").contains("https"));
    }
}
