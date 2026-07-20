//! Session tokens isolated by normalized backend origin and authority identity.

const SERVICE: &str = "dev.dax.desktop";
const LEGACY_ACCOUNT: &str = "session-token";

fn encode(value: &str) -> String {
    value
        .as_bytes()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn account(origin: &str, instance_id: &str) -> String {
    format!(
        "session-token-v3:{}:{}",
        encode(origin),
        encode(instance_id)
    )
}

fn origin_only_account(origin: &str) -> String {
    format!("session-token-v2:{}", encode(origin))
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

pub fn get(origin: &str, instance_id: &str) -> Result<Option<String>, String> {
    let scoped = account(origin, instance_id);
    if let Some(token) = read(&scoped)? {
        return Ok(Some(token));
    }
    // Neither legacy format proves which authority instance issued the token.
    delete(&origin_only_account(origin))?;
    delete(LEGACY_ACCOUNT)?;
    Ok(None)
}

pub fn set(origin: &str, instance_id: &str, token: &str) -> Result<(), String> {
    let scoped = account(origin, instance_id);
    entry(&scoped)?
        .set_password(token)
        .map_err(|err| format!("keyring write failed: {err}"))
}

pub fn clear(origin: &str, instance_id: &str) -> Result<(), String> {
    delete(&account(origin, instance_id))
}

pub fn clear_authority(origin: &str, instance_id: Option<&str>) -> Result<(), String> {
    let mut accounts = Vec::with_capacity(3);
    if let Some(instance_id) = instance_id {
        accounts.push(account(origin, instance_id));
    }
    accounts.push(origin_only_account(origin));
    accounts.push(LEGACY_ACCOUNT.to_string());
    let saved = accounts
        .iter()
        .map(|account| read(account).map(|token| (account.clone(), token)))
        .collect::<Result<Vec<_>, _>>()?;

    for (index, (account, _)) in saved.iter().enumerate() {
        if let Err(err) = delete(account) {
            for (removed_account, token) in &saved[..index] {
                if let Some(token) = token {
                    entry(removed_account)?
                        .set_password(token)
                        .map_err(|restore_err| {
                            format!("{err}; credential rollback failed: {restore_err}")
                        })?;
                }
            }
            return Err(err);
        }
    }
    Ok(())
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
            account("https://one.example", "one"),
            account("https://one.example", "one")
        );
        assert_ne!(
            account("https://one.example", "one"),
            account("https://two.example", "one")
        );
        assert_ne!(
            account("https://one.example", "one"),
            account("https://one.example", "two")
        );
        assert!(!account("https://one.example", "one").contains("https"));
    }

    #[test]
    fn recovery_targets_scoped_and_legacy_account_formats() {
        assert_ne!(
            account("https://one.example", "one"),
            origin_only_account("https://one.example")
        );
        assert_eq!(LEGACY_ACCOUNT, "session-token");
    }
}
