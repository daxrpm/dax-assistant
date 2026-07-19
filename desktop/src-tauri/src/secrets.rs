//! Session tokens isolated by normalized backend origin.

const SERVICE: &str = "dev.dax.desktop";
const LEGACY_ACCOUNT: &str = "session-token";

fn account(origin: &str) -> String {
    let encoded = origin
        .as_bytes()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    format!("session-token-v2:{encoded}")
}

fn entry(account: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, account).map_err(|err| format!("keyring unavailable: {err}"))
}

fn read(account: &str) -> Result<Option<String>, String> {
    match entry(account)?.get_password() {
        Ok(token) => Ok(Some(token)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(format!("keyring read failed: {err}")),
    }
}

pub fn get(origin: &str) -> Result<Option<String>, String> {
    let scoped = account(origin);
    if let Some(token) = read(&scoped)? {
        return Ok(Some(token));
    }
    // A legacy token can only be attributed safely to the active origin asking
    // for it. Move it once; it is never copied across origins.
    let Some(token) = read(LEGACY_ACCOUNT)? else {
        return Ok(None);
    };
    // Write first so a transient keyring failure cannot destroy the only copy.
    set(origin, &token)?;
    delete(LEGACY_ACCOUNT)?;
    Ok(Some(token))
}

pub fn set(origin: &str, token: &str) -> Result<(), String> {
    let scoped = account(origin);
    entry(&scoped)?
        .set_password(token)
        .map_err(|err| format!("keyring write failed: {err}"))
}

pub fn clear(origin: &str) -> Result<(), String> {
    delete(&account(origin))
}

fn delete(account: &str) -> Result<(), String> {
    match entry(account)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(format!("keyring delete failed: {err}")),
    }
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
