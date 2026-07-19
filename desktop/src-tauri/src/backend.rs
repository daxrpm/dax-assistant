//! Validated, persistent backend connection settings and health probing.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;
use url::{Host, Url};

pub const DEFAULT_URL: &str = "http://127.0.0.1:8420";
pub const SETTINGS_VERSION: u8 = 2;
const SETTINGS_FILE: &str = "backend.json";
const PROBE_TIMEOUT: Duration = Duration::from_secs(2);

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum BackendStrategy {
    Local,
    Remote,
    Hybrid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct BackendSettings {
    pub version: u8,
    pub strategy: BackendStrategy,
    pub local_url: String,
    pub remote_url: Option<String>,
    pub active_url: String,
    pub onboarding_complete: bool,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct LegacySettings {
    mode: LegacyMode,
    url: String,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
enum LegacyMode {
    Remote,
    Sidecar,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResolutionAttempt {
    pub url: String,
    pub healthy: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct BackendResolution {
    pub strategy: BackendStrategy,
    pub active_url: String,
    pub previous_url: String,
    pub changed: bool,
    pub healthy: bool,
    pub service_start_attempted: bool,
    pub attempts: Vec<ResolutionAttempt>,
}

pub struct BackendState {
    inner: Mutex<BackendSettings>,
    path: PathBuf,
}

impl BackendSettings {
    fn defaults() -> Self {
        Self {
            version: SETTINGS_VERSION,
            strategy: BackendStrategy::Local,
            local_url: DEFAULT_URL.to_string(),
            remote_url: None,
            active_url: DEFAULT_URL.to_string(),
            onboarding_complete: false,
        }
    }

    fn validated(
        strategy: BackendStrategy,
        local_url: &str,
        remote_url: Option<&str>,
        active_url: Option<&str>,
        onboarding_complete: bool,
    ) -> Result<Self, String> {
        let local_url = validate_local_url(local_url)?;
        let remote_url = remote_url
            .filter(|value| !value.trim().is_empty())
            .map(validate_remote_url)
            .transpose()?;
        if matches!(strategy, BackendStrategy::Remote | BackendStrategy::Hybrid)
            && remote_url.is_none()
        {
            return Err("remote_url is required for remote and hybrid strategies".into());
        }
        let preferred = match strategy {
            BackendStrategy::Local => local_url.clone(),
            BackendStrategy::Remote | BackendStrategy::Hybrid => remote_url.clone().unwrap(),
        };
        let active_url = active_url
            .map(validate_remote_url)
            .transpose()?
            .filter(|url| url == &local_url || remote_url.as_ref() == Some(url))
            .unwrap_or(preferred);
        Ok(Self {
            version: SETTINGS_VERSION,
            strategy,
            local_url,
            remote_url,
            active_url,
            onboarding_complete,
        })
    }

    fn candidates(&self) -> Vec<String> {
        match self.strategy {
            BackendStrategy::Local => vec![self.local_url.clone()],
            BackendStrategy::Remote => self.remote_url.iter().cloned().collect(),
            BackendStrategy::Hybrid => self
                .remote_url
                .iter()
                .cloned()
                .chain(std::iter::once(self.local_url.clone()))
                .collect(),
        }
    }
}

impl BackendState {
    pub fn load(config_dir: &Path) -> Result<Self, String> {
        let path = config_dir.join(SETTINGS_FILE);
        let (settings, migrated) = match fs::read(&path) {
            Ok(bytes) => decode_settings(&bytes)?,
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
                (BackendSettings::defaults(), false)
            }
            Err(err) => return Err(format!("cannot read backend settings: {err}")),
        };
        if migrated {
            persist_settings(&path, &settings)?;
        }
        Ok(Self {
            inner: Mutex::new(settings),
            path,
        })
    }

    pub fn settings(&self) -> Result<BackendSettings, String> {
        self.inner
            .lock()
            .map(|settings| settings.clone())
            .map_err(|_| "backend settings lock is poisoned".into())
    }

    pub fn set(
        &self,
        strategy: BackendStrategy,
        local_url: String,
        remote_url: Option<String>,
        onboarding_complete: bool,
    ) -> Result<BackendSettings, String> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| "backend settings lock is poisoned".to_string())?;
        let next = BackendSettings::validated(
            strategy,
            &local_url,
            remote_url.as_deref(),
            Some(&guard.active_url),
            onboarding_complete,
        )?;
        persist_settings(&self.path, &next)?;
        *guard = next.clone();
        Ok(next)
    }

    fn set_active(&self, active_url: String) -> Result<(), String> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| "backend settings lock is poisoned".to_string())?;
        let mut next = guard.clone();
        next.active_url = active_url;
        persist_settings(&self.path, &next)?;
        *guard = next;
        Ok(())
    }
}

fn decode_settings(bytes: &[u8]) -> Result<(BackendSettings, bool), String> {
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|err| format!("invalid backend settings file: {err}"))?;
    if value.get("version").is_some() {
        let stored: BackendSettings = serde_json::from_value(value)
            .map_err(|err| format!("invalid backend settings file: {err}"))?;
        if stored.version != SETTINGS_VERSION {
            return Err(format!(
                "unsupported backend settings version {}",
                stored.version
            ));
        }
        let validated = BackendSettings::validated(
            stored.strategy,
            &stored.local_url,
            stored.remote_url.as_deref(),
            Some(&stored.active_url),
            stored.onboarding_complete,
        )?;
        return Ok((validated, false));
    }

    let legacy: LegacySettings = serde_json::from_value(value)
        .map_err(|err| format!("invalid legacy backend settings file: {err}"))?;
    let migrated = match legacy.mode {
        LegacyMode::Remote if is_loopback_url(&legacy.url)? => BackendSettings::validated(
            BackendStrategy::Local,
            &legacy.url,
            None,
            Some(&legacy.url),
            true,
        )?,
        LegacyMode::Remote => BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some(&legacy.url),
            Some(&legacy.url),
            true,
        )?,
        LegacyMode::Sidecar if is_loopback_url(&legacy.url)? => BackendSettings::validated(
            BackendStrategy::Local,
            &legacy.url,
            None,
            Some(&legacy.url),
            true,
        )?,
        LegacyMode::Sidecar => BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some(&legacy.url),
            Some(&legacy.url),
            true,
        )?,
    };
    Ok((migrated, true))
}

pub async fn resolve(
    state: &BackendState,
    allow_service_start: bool,
) -> Result<BackendResolution, String> {
    let settings = state.settings()?;
    let previous_url = settings.active_url.clone();
    let candidates = settings.candidates();
    let mut attempts = Vec::with_capacity(candidates.len() + 1);
    let mut selected = None;
    let mut service_start_attempted = false;

    for candidate in candidates {
        let mut healthy = probe(&candidate).await;
        attempts.push(ResolutionAttempt {
            url: candidate.clone(),
            healthy,
        });
        if !healthy
            && candidate == settings.local_url
            && allow_service_start
            && settings.onboarding_complete
        {
            service_start_attempted = true;
            if crate::service::control(crate::service::ServiceAction::Start)
                .await
                .is_ok()
            {
                healthy = probe(&candidate).await;
                attempts.push(ResolutionAttempt {
                    url: candidate.clone(),
                    healthy,
                });
            }
        }
        if healthy {
            selected = Some(candidate);
            break;
        }
    }

    let healthy = selected.is_some();
    let active_url = selected.unwrap_or_else(|| previous_url.clone());
    let changed = active_url != previous_url;
    if changed {
        state.set_active(active_url.clone())?;
    }
    Ok(BackendResolution {
        strategy: settings.strategy,
        active_url,
        previous_url,
        changed,
        healthy,
        service_start_attempted,
        attempts,
    })
}

pub fn validate_local_url(value: &str) -> Result<String, String> {
    let normalized = validate_remote_url(value)?;
    if !is_loopback_url(&normalized)? {
        return Err("local_url must use a loopback host".into());
    }
    Ok(normalized)
}

pub fn validate_remote_url(value: &str) -> Result<String, String> {
    let trimmed = value.trim();
    let mut parsed = Url::parse(trimmed).map_err(|err| format!("invalid backend URL: {err}"))?;
    if parsed.host().is_none() {
        return Err("backend URL must include a host".into());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("backend URL must not contain credentials".into());
    }
    if parsed.query().is_some() || parsed.fragment().is_some() {
        return Err("backend URL must not contain a query or fragment".into());
    }
    let loopback = is_loopback_host(parsed.host());
    match parsed.scheme() {
        "https" => {}
        "http" if loopback => {}
        "http" => return Err("remote backend URLs must use HTTPS".into()),
        _ => return Err("backend URL scheme must be HTTP or HTTPS".into()),
    }
    let normalized_path = parsed.path().trim_end_matches('/').to_string();
    parsed.set_path(if normalized_path.is_empty() {
        "/"
    } else {
        &normalized_path
    });
    Ok(parsed.as_str().trim_end_matches('/').to_string())
}

pub fn token_origin(value: &str) -> Result<String, String> {
    let parsed = Url::parse(&validate_remote_url(value)?)
        .map_err(|err| format!("invalid backend URL: {err}"))?;
    Ok(parsed.origin().ascii_serialization())
}

fn is_loopback_url(value: &str) -> Result<bool, String> {
    let parsed = Url::parse(value).map_err(|err| format!("invalid backend URL: {err}"))?;
    Ok(is_loopback_host(parsed.host()))
}

fn is_loopback_host(host: Option<Host<&str>>) -> bool {
    match host {
        Some(Host::Domain(host)) => host.eq_ignore_ascii_case("localhost"),
        Some(Host::Ipv4(ip)) => ip.is_loopback(),
        Some(Host::Ipv6(ip)) => ip.is_loopback(),
        None => false,
    }
}

fn persist_settings(path: &Path, settings: &BackendSettings) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "backend settings path has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|err| format!("cannot create settings directory: {err}"))?;
    restrict_dir(parent)?;
    let temp = path.with_extension("json.tmp");
    let bytes = serde_json::to_vec_pretty(settings)
        .map_err(|err| format!("cannot serialize backend settings: {err}"))?;
    write_private(&temp, &bytes)?;
    fs::rename(&temp, path).map_err(|err| {
        let _ = fs::remove_file(&temp);
        format!("cannot commit backend settings: {err}")
    })?;
    restrict_file(path)
}

#[cfg(unix)]
fn restrict_dir(path: &Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|err| format!("cannot secure settings directory: {err}"))
}

#[cfg(not(unix))]
fn restrict_dir(_path: &Path) -> Result<(), String> {
    Ok(())
}

#[cfg(unix)]
fn write_private(path: &Path, bytes: &[u8]) -> Result<(), String> {
    use std::io::Write;
    use std::os::unix::fs::OpenOptionsExt;
    let mut file = fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .mode(0o600)
        .open(path)
        .map_err(|err| format!("cannot write backend settings: {err}"))?;
    file.write_all(bytes)
        .and_then(|_| file.sync_all())
        .map_err(|err| format!("cannot flush backend settings: {err}"))
}

#[cfg(not(unix))]
fn write_private(path: &Path, bytes: &[u8]) -> Result<(), String> {
    fs::write(path, bytes).map_err(|err| format!("cannot write backend settings: {err}"))
}

#[cfg(unix)]
fn restrict_file(path: &Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))
        .map_err(|err| format!("cannot secure backend settings: {err}"))
}

#[cfg(not(unix))]
fn restrict_file(_path: &Path) -> Result<(), String> {
    Ok(())
}

/// Probe `GET /api/health`. It is intentionally unauthenticated.
pub async fn probe(url: &str) -> bool {
    let client = match reqwest::Client::builder().timeout(PROBE_TIMEOUT).build() {
        Ok(client) => client,
        Err(_) => return false,
    };
    match client.get(format!("{url}/api/health")).send().await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_local_and_remote_urls_separately() {
        assert_eq!(
            validate_local_url(" http://127.0.0.1:8420/ ").unwrap(),
            DEFAULT_URL
        );
        assert!(validate_local_url("https://example.com").is_err());
        assert!(validate_remote_url("http://example.com:8420").is_err());
        assert_eq!(
            validate_remote_url("https://example.com/api/").unwrap(),
            "https://example.com/api"
        );
    }

    #[test]
    fn rejects_unsafe_urls() {
        for value in [
            "file:///tmp/socket",
            "https://user:secret@example.com",
            "https://example.com?a=1",
            "https://example.com/#fragment",
        ] {
            assert!(validate_remote_url(value).is_err(), "accepted {value}");
        }
    }

    #[test]
    fn migrates_loopback_and_remote_legacy_settings_without_losing_url() {
        let (local, migrated) =
            decode_settings(br#"{"mode":"remote","url":"http://localhost:9000"}"#).unwrap();
        assert!(migrated);
        assert_eq!(local.strategy, BackendStrategy::Local);
        assert_eq!(local.active_url, "http://localhost:9000");
        assert!(local.onboarding_complete);

        let (remote, _) =
            decode_settings(br#"{"mode":"remote","url":"https://dax.example.com"}"#).unwrap();
        assert_eq!(remote.strategy, BackendStrategy::Remote);
        assert_eq!(
            remote.remote_url.as_deref(),
            Some("https://dax.example.com")
        );
    }

    #[test]
    fn resolution_order_matches_strategy_and_never_falls_back_for_remote() {
        let local =
            BackendSettings::validated(BackendStrategy::Local, DEFAULT_URL, None, None, true)
                .unwrap();
        assert_eq!(local.candidates(), vec![DEFAULT_URL]);
        let remote = BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some("https://remote.example"),
            None,
            true,
        )
        .unwrap();
        assert_eq!(remote.candidates(), vec!["https://remote.example"]);
        let hybrid = BackendSettings::validated(
            BackendStrategy::Hybrid,
            DEFAULT_URL,
            Some("https://remote.example"),
            None,
            true,
        )
        .unwrap();
        assert_eq!(
            hybrid.candidates(),
            vec!["https://remote.example", DEFAULT_URL]
        );
    }

    #[test]
    fn token_origin_excludes_paths() {
        assert_eq!(
            token_origin("https://example.com/dax").unwrap(),
            "https://example.com"
        );
    }
}
