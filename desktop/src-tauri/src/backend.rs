//! Validated, persistent backend connection settings and health probing.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;
use url::{Host, Url};

pub const DEFAULT_URL: &str = "http://127.0.0.1:8420";
pub const SETTINGS_VERSION: u8 = 3;
const SETTINGS_FILE: &str = "backend.json";
const PROBE_TIMEOUT: Duration = Duration::from_secs(2);
const STARTUP_READINESS_DEADLINE: Duration = Duration::from_secs(8);
const STARTUP_INITIAL_BACKOFF: Duration = Duration::from_millis(100);
const STARTUP_MAX_BACKOFF: Duration = Duration::from_secs(1);

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum BackendStrategy {
    Local,
    Remote,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct BackendSettings {
    pub version: u8,
    pub strategy: BackendStrategy,
    pub local_url: String,
    pub remote_url: Option<String>,
    pub active_url: String,
    pub active_server_id: Option<String>,
    pub onboarding_complete: bool,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
enum VersionTwoStrategy {
    Local,
    Remote,
    Hybrid,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct VersionTwoSettings {
    version: u8,
    strategy: VersionTwoStrategy,
    local_url: String,
    remote_url: Option<String>,
    #[serde(rename = "active_url")]
    _active_url: String,
    onboarding_complete: bool,
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
    pub server_instance_id: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct BackendResolution {
    pub strategy: BackendStrategy,
    pub active_url: String,
    pub previous_url: String,
    pub changed: bool,
    pub healthy: bool,
    pub server_instance_id: Option<String>,
    pub service_start_attempted: bool,
    pub attempts: Vec<ResolutionAttempt>,
}

pub struct BackendState {
    inner: Mutex<BackendStateInner>,
    path: PathBuf,
}

struct BackendStateInner {
    settings: BackendSettings,
    generation: u64,
}

impl BackendSettings {
    fn defaults() -> Self {
        Self {
            version: SETTINGS_VERSION,
            strategy: BackendStrategy::Local,
            local_url: DEFAULT_URL.to_string(),
            remote_url: None,
            active_url: DEFAULT_URL.to_string(),
            active_server_id: None,
            onboarding_complete: false,
        }
    }

    fn validated(
        strategy: BackendStrategy,
        local_url: &str,
        remote_url: Option<&str>,
        active_url: Option<&str>,
        active_server_id: Option<&str>,
        onboarding_complete: bool,
    ) -> Result<Self, String> {
        let local_url = validate_local_url(local_url)?;
        let remote_url = remote_url
            .filter(|value| !value.trim().is_empty())
            .map(validate_remote_url)
            .transpose()?;
        if strategy == BackendStrategy::Remote && remote_url.is_none() {
            return Err("remote_url is required for the remote strategy".into());
        }
        let preferred = match strategy {
            BackendStrategy::Local => local_url.clone(),
            BackendStrategy::Remote => remote_url.clone().unwrap(),
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
            active_server_id: active_server_id.map(str::to_owned),
            onboarding_complete,
        })
    }

    fn candidates(&self) -> Vec<String> {
        match self.strategy {
            BackendStrategy::Local => vec![self.local_url.clone()],
            BackendStrategy::Remote => self.remote_url.iter().cloned().collect(),
        }
    }
}

impl BackendState {
    pub fn load(config_dir: &Path) -> Result<Self, String> {
        let path = config_dir.join(SETTINGS_FILE);
        let (settings, migrated) = match fs::read(&path) {
            Ok(bytes) => match decode_settings(&bytes) {
                Ok(decoded) => decoded,
                Err(err) if err.starts_with("unsupported backend settings version") => {
                    return Err(err);
                }
                Err(err) => {
                    eprintln!("{err}; using safe backend defaults");
                    (BackendSettings::defaults(), false)
                }
            },
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
                (BackendSettings::defaults(), false)
            }
            Err(err) => return Err(format!("cannot read backend settings: {err}")),
        };
        if migrated {
            persist_settings(&path, &settings)?;
        }
        Ok(Self {
            inner: Mutex::new(BackendStateInner {
                settings,
                generation: 0,
            }),
            path,
        })
    }

    pub fn settings(&self) -> Result<BackendSettings, String> {
        self.inner
            .lock()
            .map(|inner| inner.settings.clone())
            .map_err(|_| "backend settings lock is poisoned".into())
    }

    pub fn active_validated_authority(&self) -> Result<(String, String), String> {
        let settings = self.settings()?;
        let instance_id = settings
            .active_server_id
            .clone()
            .ok_or_else(|| "the active backend has not been validated".to_string())?;
        match settings.strategy {
            BackendStrategy::Local if settings.active_url == settings.local_url => {}
            BackendStrategy::Remote
                if settings.remote_url.as_ref() == Some(&settings.active_url) => {}
            _ => return Err("the active backend is not the selected authority".into()),
        }
        Ok((settings.active_url, instance_id))
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
        let preferred_url = match strategy {
            BackendStrategy::Local => validate_local_url(&local_url)?,
            BackendStrategy::Remote => validate_remote_url(
                remote_url
                    .as_deref()
                    .ok_or_else(|| "remote_url is required for the remote strategy".to_string())?,
            )?,
        };
        let same_authority_origin =
            token_origin(&preferred_url)? == token_origin(&guard.settings.active_url)?;
        let next = BackendSettings::validated(
            strategy,
            &local_url,
            remote_url.as_deref(),
            Some(&preferred_url),
            same_authority_origin
                .then_some(guard.settings.active_server_id.as_deref())
                .flatten(),
            onboarding_complete,
        )?;
        persist_settings(&self.path, &next)?;
        guard.settings = next.clone();
        guard.generation = guard.generation.wrapping_add(1);
        Ok(next)
    }

    fn snapshot(&self) -> Result<(BackendSettings, u64), String> {
        self.inner
            .lock()
            .map(|inner| (inner.settings.clone(), inner.generation))
            .map_err(|_| "backend settings lock is poisoned".into())
    }

    fn set_active_if_current(
        &self,
        generation: u64,
        active_url: String,
        server_instance_id: String,
    ) -> Result<bool, String> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| "backend settings lock is poisoned".to_string())?;
        if guard.generation != generation {
            return Ok(false);
        }
        let mut next = guard.settings.clone();
        next.active_url = active_url;
        next.active_server_id = Some(server_instance_id);
        persist_settings(&self.path, &next)?;
        guard.settings = next;
        guard.generation = guard.generation.wrapping_add(1);
        Ok(true)
    }

    fn is_current(&self, generation: u64) -> Result<bool, String> {
        self.inner
            .lock()
            .map(|inner| inner.generation == generation)
            .map_err(|_| "backend settings lock is poisoned".into())
    }

    pub fn token_origin(&self, value: &str) -> Result<String, String> {
        let requested = token_origin(value)?;
        let settings = self.settings()?;
        let allowed = std::iter::once(settings.local_url.as_str())
            .chain(settings.remote_url.as_deref())
            .chain(std::iter::once(settings.active_url.as_str()))
            .filter_map(|url| token_origin(url).ok())
            .any(|origin| origin == requested);
        if allowed {
            Ok(requested)
        } else {
            Err("token origin is not a configured backend origin".into())
        }
    }

    pub fn token_authority(&self, value: &str, instance_id: &str) -> Result<String, String> {
        let origin = self.token_origin(value)?;
        let settings = self.settings()?;
        let active_origin = token_origin(&settings.active_url)?;
        if origin != active_origin || settings.active_server_id.as_deref() != Some(instance_id) {
            return Err("token authority is not the validated active backend".into());
        }
        Ok(origin)
    }

    pub fn reset_authority_pin<F>(&self, clear_credentials: F) -> Result<BackendSettings, String>
    where
        F: FnOnce(&str, Option<&str>) -> Result<(), String>,
    {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| "backend settings lock is poisoned".to_string())?;
        let origin = token_origin(&guard.settings.active_url)?;
        let mut next = guard.settings.clone();
        next.active_server_id = None;
        persist_settings(&self.path, &next)?;
        if let Err(err) = clear_credentials(&origin, guard.settings.active_server_id.as_deref()) {
            persist_settings(&self.path, &guard.settings)?;
            return Err(err);
        }
        guard.settings = next.clone();
        guard.generation = guard.generation.wrapping_add(1);
        Ok(next)
    }
}

fn decode_settings(bytes: &[u8]) -> Result<(BackendSettings, bool), String> {
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|err| format!("invalid backend settings file: {err}"))?;
    if value.get("version").and_then(serde_json::Value::as_u64) == Some(2) {
        let stored: VersionTwoSettings = serde_json::from_value(value)
            .map_err(|err| format!("invalid backend settings file: {err}"))?;
        debug_assert_eq!(stored.version, 2);
        let strategy = match stored.strategy {
            VersionTwoStrategy::Local => BackendStrategy::Local,
            VersionTwoStrategy::Remote | VersionTwoStrategy::Hybrid => BackendStrategy::Remote,
        };
        let active_url = match strategy {
            BackendStrategy::Local => stored.local_url.as_str(),
            BackendStrategy::Remote => stored
                .remote_url
                .as_deref()
                .ok_or_else(|| "version 2 hybrid/remote settings require remote_url".to_string())?,
        };
        let migrated = BackendSettings::validated(
            strategy,
            &stored.local_url,
            stored.remote_url.as_deref(),
            Some(active_url),
            None,
            stored.onboarding_complete,
        )?;
        return Ok((migrated, true));
    }
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
            stored.active_server_id.as_deref(),
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
            None,
            true,
        )?,
        LegacyMode::Remote => BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some(&legacy.url),
            Some(&legacy.url),
            None,
            true,
        )?,
        LegacyMode::Sidecar if is_loopback_url(&legacy.url)? => BackendSettings::validated(
            BackendStrategy::Local,
            &legacy.url,
            None,
            Some(&legacy.url),
            None,
            true,
        )?,
        LegacyMode::Sidecar => BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some(&legacy.url),
            Some(&legacy.url),
            None,
            true,
        )?,
    };
    Ok((migrated, true))
}

pub async fn resolve(
    state: &BackendState,
    allow_service_start: bool,
) -> Result<BackendResolution, String> {
    let (settings, generation) = state.snapshot()?;
    let previous_url = settings.active_url.clone();
    let candidates = settings.candidates();
    let mut attempts = Vec::with_capacity(candidates.len() + 1);
    let mut selected = None;
    let mut service_start_attempted = false;

    for candidate in candidates {
        let mut server_instance_id = probe(&candidate).await;
        let mut healthy = server_instance_id.is_some();
        let mut observed_server_instance_id = server_instance_id.clone();
        if candidate == settings.active_url
            && settings.active_server_id.is_some()
            && settings.active_server_id != server_instance_id
        {
            healthy = false;
            server_instance_id = None;
        }
        attempts.push(ResolutionAttempt {
            url: candidate.clone(),
            healthy,
            server_instance_id: observed_server_instance_id.clone(),
        });
        if !healthy
            && candidate == settings.local_url
            && allow_service_start
            && settings.onboarding_complete
        {
            if !state.is_current(generation)? {
                return Err(
                    "backend settings changed during resolution; retry with current settings"
                        .into(),
                );
            }
            service_start_attempted = true;
            if crate::service::control(crate::service::ServiceAction::Start)
                .await
                .is_ok()
            {
                server_instance_id = match tokio::time::timeout(
                    STARTUP_READINESS_DEADLINE,
                    poll_startup_readiness(
                        || probe(&candidate),
                        tokio::time::sleep,
                        || state.is_current(generation),
                    ),
                )
                .await
                {
                    Ok(result) => result?,
                    Err(_) => None,
                };
                healthy = server_instance_id.is_some();
                observed_server_instance_id = server_instance_id.clone();
                if candidate == settings.active_url
                    && settings.active_server_id.is_some()
                    && settings.active_server_id != server_instance_id
                {
                    healthy = false;
                    server_instance_id = None;
                }
                attempts.push(ResolutionAttempt {
                    url: candidate.clone(),
                    healthy,
                    server_instance_id: observed_server_instance_id.clone(),
                });
            }
        }
        if healthy {
            selected = server_instance_id.map(|instance_id| (candidate, instance_id));
            break;
        }
    }

    let healthy = selected.is_some();
    let (active_url, server_instance_id) = selected.clone().unwrap_or_else(|| {
        (
            previous_url.clone(),
            settings.active_server_id.clone().unwrap_or_default(),
        )
    });
    let changed = active_url != previous_url;
    if healthy && (changed || settings.active_server_id.as_ref() != Some(&server_instance_id)) {
        if !state.set_active_if_current(
            generation,
            active_url.clone(),
            server_instance_id.clone(),
        )? {
            return Err(
                "backend settings changed during resolution; retry with current settings".into(),
            );
        }
    } else if !state.is_current(generation)? {
        return Err(
            "backend settings changed during resolution; retry with current settings".into(),
        );
    }
    Ok(BackendResolution {
        strategy: settings.strategy,
        active_url,
        previous_url,
        changed,
        healthy,
        server_instance_id: healthy.then_some(server_instance_id),
        service_start_attempted,
        attempts,
    })
}

async fn poll_startup_readiness<P, ProbeFuture, S, SleepFuture, C>(
    mut probe_fn: P,
    mut sleep_fn: S,
    mut is_current: C,
) -> Result<Option<String>, String>
where
    P: FnMut() -> ProbeFuture,
    ProbeFuture: std::future::Future<Output = Option<String>>,
    S: FnMut(Duration) -> SleepFuture,
    SleepFuture: std::future::Future<Output = ()>,
    C: FnMut() -> Result<bool, String>,
{
    let mut elapsed = Duration::ZERO;
    let mut backoff = STARTUP_INITIAL_BACKOFF;
    while elapsed < STARTUP_READINESS_DEADLINE {
        if !is_current()? {
            return Err(
                "backend settings changed during resolution; retry with current settings".into(),
            );
        }
        let delay = backoff.min(STARTUP_READINESS_DEADLINE - elapsed);
        sleep_fn(delay).await;
        elapsed += delay;
        if !is_current()? {
            return Err(
                "backend settings changed during resolution; retry with current settings".into(),
            );
        }
        if let Some(instance_id) = probe_fn().await {
            return Ok(Some(instance_id));
        }
        backoff = (backoff * 2).min(STARTUP_MAX_BACKOFF);
    }
    Ok(None)
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
    if !parsed.path().trim_matches('/').is_empty() {
        return Err("backend URL must not contain a path".into());
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
    let parsed = Url::parse(value.trim()).map_err(|err| format!("invalid backend URL: {err}"))?;
    let origin = parsed.origin().ascii_serialization();
    validate_remote_url(&origin)?;
    Ok(origin)
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

#[derive(Deserialize)]
struct HealthResponse {
    status: String,
    instance_id: String,
    role: String,
    api_protocol: String,
    api_version: u8,
    liveness: bool,
    readiness: bool,
}

fn validated_health_identity(health: HealthResponse) -> Option<String> {
    (health.status == "ok"
        && health.role == "authoritative"
        && health.api_protocol == "dax"
        && health.api_version == 1
        && health.liveness
        && health.readiness
        && !health.instance_id.is_empty())
    .then_some(health.instance_id)
}

/// Return the identity only for a ready authoritative Dax API.
pub async fn probe(url: &str) -> Option<String> {
    let client = match reqwest::Client::builder()
        .timeout(PROBE_TIMEOUT)
        .redirect(reqwest::redirect::Policy::none())
        .build()
    {
        Ok(client) => client,
        Err(_) => return None,
    };
    match client.get(format!("{url}/api/health")).send().await {
        Ok(response) if response.status().is_success() => {
            match response.json::<HealthResponse>().await {
                Ok(health) => validated_health_identity(health),
                _ => None,
            }
        }
        _ => None,
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
            validate_remote_url("https://example.com/").unwrap(),
            "https://example.com"
        );
    }

    #[test]
    fn rejects_unsafe_urls() {
        for value in [
            "file:///tmp/socket",
            "https://user:secret@example.com",
            "https://example.com?a=1",
            "https://example.com/#fragment",
            "https://example.com/api",
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
            BackendSettings::validated(BackendStrategy::Local, DEFAULT_URL, None, None, None, true)
                .unwrap();
        assert_eq!(local.candidates(), vec![DEFAULT_URL]);
        let remote = BackendSettings::validated(
            BackendStrategy::Remote,
            DEFAULT_URL,
            Some("https://remote.example"),
            None,
            None,
            true,
        )
        .unwrap();
        assert_eq!(remote.candidates(), vec!["https://remote.example"]);
        assert!(local.candidates().len() == 1 && remote.candidates().len() == 1);
    }

    #[test]
    fn migrates_version_two_hybrid_to_remote_only_and_discards_local_active_url() {
        let (settings, migrated) = decode_settings(
            br#"{"version":2,"strategy":"hybrid","local_url":"http://127.0.0.1:8420","remote_url":"https://remote.example","active_url":"http://127.0.0.1:8420","onboarding_complete":true}"#,
        )
        .unwrap();

        assert!(migrated);
        assert_eq!(settings.version, 3);
        assert_eq!(settings.strategy, BackendStrategy::Remote);
        assert_eq!(settings.active_url, "https://remote.example");
        assert_eq!(settings.candidates(), vec!["https://remote.example"]);
        assert_eq!(settings.active_server_id, None);
    }

    #[test]
    fn health_requires_ready_authoritative_dax_identity() {
        let health = |role: &str, readiness| HealthResponse {
            status: "ok".into(),
            instance_id: "authority-1".into(),
            role: role.into(),
            api_protocol: "dax".into(),
            api_version: 1,
            liveness: true,
            readiness,
        };
        assert_eq!(
            validated_health_identity(health("authoritative", true)).as_deref(),
            Some("authority-1")
        );
        assert!(validated_health_identity(health("authoritative", false)).is_none());
        assert!(validated_health_identity(health("edge", true)).is_none());
    }

    #[test]
    fn token_origin_excludes_paths() {
        assert_eq!(
            token_origin("https://example.com/dax").unwrap(),
            "https://example.com"
        );
    }

    #[test]
    fn loading_persists_version_two_hybrid_migration() {
        let directory =
            std::env::temp_dir().join(format!("dax-hybrid-migration-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        let path = directory.join(SETTINGS_FILE);
        fs::write(
            &path,
            br#"{"version":2,"strategy":"hybrid","local_url":"http://127.0.0.1:8420","remote_url":"https://remote.example","active_url":"http://127.0.0.1:8420","onboarding_complete":true}"#,
        )
        .unwrap();

        let state = BackendState::load(&directory).unwrap();
        let persisted: serde_json::Value =
            serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();

        assert_eq!(state.settings().unwrap().strategy, BackendStrategy::Remote);
        assert_eq!(persisted["version"], 3);
        assert_eq!(persisted["strategy"], "remote");
        assert_eq!(persisted["active_url"], "https://remote.example");
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn token_origin_must_match_a_configured_backend() {
        let directory = std::env::temp_dir().join(format!(
            "dax-backend-test-{}-{}",
            std::process::id(),
            std::thread::current().name().unwrap_or("origin")
        ));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        assert_eq!(
            state.token_origin("http://127.0.0.1:8420/path").unwrap(),
            "http://127.0.0.1:8420"
        );
        assert!(state.token_origin("https://attacker.example").is_err());
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn active_url_requires_a_validated_selected_authority() {
        let directory =
            std::env::temp_dir().join(format!("dax-active-backend-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        assert!(state.active_validated_authority().is_err());

        let (_, generation) = state.snapshot().unwrap();
        state
            .set_active_if_current(generation, DEFAULT_URL.into(), "authority-1".into())
            .unwrap();
        assert_eq!(
            state.active_validated_authority().unwrap(),
            (DEFAULT_URL.to_string(), "authority-1".to_string())
        );
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn malformed_settings_recover_to_safe_defaults() {
        let directory =
            std::env::temp_dir().join(format!("dax-malformed-backend-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        fs::write(directory.join(SETTINGS_FILE), b"not json").unwrap();
        let state = BackendState::load(&directory).unwrap();
        assert_eq!(state.settings().unwrap(), BackendSettings::defaults());
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn newer_settings_versions_are_not_silently_overwritten() {
        let directory =
            std::env::temp_dir().join(format!("dax-newer-backend-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        fs::create_dir_all(&directory).unwrap();
        fs::write(
            directory.join(SETTINGS_FILE),
            br#"{"version":4,"strategy":"local","local_url":"http://127.0.0.1:8420","remote_url":null,"active_url":"http://127.0.0.1:8420","active_server_id":null,"onboarding_complete":true}"#,
        )
        .unwrap();
        assert!(BackendState::load(&directory).is_err());
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn stale_resolution_cannot_replace_newer_settings() {
        let directory =
            std::env::temp_dir().join(format!("dax-generation-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        let (_, generation) = state.snapshot().unwrap();
        let current = state
            .set(
                BackendStrategy::Remote,
                DEFAULT_URL.into(),
                Some("https://current.example".into()),
                true,
            )
            .unwrap();
        assert!(!state
            .set_active_if_current(generation, DEFAULT_URL.into(), "stale-id".into())
            .unwrap());
        assert_eq!(state.settings().unwrap(), current);
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn unchanged_settings_save_preserves_the_authority_pin() {
        let directory =
            std::env::temp_dir().join(format!("dax-authority-reset-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        let (_, generation) = state.snapshot().unwrap();
        assert!(state
            .set_active_if_current(generation, DEFAULT_URL.into(), "old-authority".into())
            .unwrap());

        let settings = state
            .set(BackendStrategy::Local, DEFAULT_URL.into(), None, true)
            .unwrap();

        assert_eq!(settings.active_server_id.as_deref(), Some("old-authority"));
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn explicit_authority_switch_clears_the_pin() {
        let directory =
            std::env::temp_dir().join(format!("dax-authority-switch-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        let (_, generation) = state.snapshot().unwrap();
        state
            .set_active_if_current(generation, DEFAULT_URL.into(), "old-authority".into())
            .unwrap();

        let settings = state
            .set(
                BackendStrategy::Remote,
                DEFAULT_URL.into(),
                Some("https://new.example".into()),
                true,
            )
            .unwrap();

        assert_eq!(settings.active_url, "https://new.example");
        assert_eq!(settings.active_server_id, None);
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn confirmed_authority_reset_clears_credentials_and_pin_as_one_state_change() {
        let directory = std::env::temp_dir().join(format!(
            "dax-authority-recovery-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        let (_, generation) = state.snapshot().unwrap();
        state
            .set_active_if_current(generation, DEFAULT_URL.into(), "old-authority".into())
            .unwrap();

        let cleared = std::cell::RefCell::new(None);
        let settings = state
            .reset_authority_pin(|origin, instance_id| {
                *cleared.borrow_mut() = Some((origin.to_owned(), instance_id.map(str::to_owned)));
                Ok(())
            })
            .unwrap();

        assert_eq!(
            cleared.into_inner(),
            Some((DEFAULT_URL.to_string(), Some("old-authority".to_string())))
        );
        assert_eq!(settings.active_server_id, None);
        assert_eq!(state.settings().unwrap().active_server_id, None);
        let _ = fs::remove_dir_all(directory);
    }

    #[test]
    fn failed_credential_clear_preserves_the_authority_pin() {
        let directory = std::env::temp_dir().join(format!(
            "dax-authority-recovery-failure-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&directory);
        let state = BackendState::load(&directory).unwrap();
        let (_, generation) = state.snapshot().unwrap();
        state
            .set_active_if_current(generation, DEFAULT_URL.into(), "old-authority".into())
            .unwrap();

        assert!(state
            .reset_authority_pin(|_, _| Err("keyring failure".into()))
            .is_err());
        assert_eq!(
            state.settings().unwrap().active_server_id.as_deref(),
            Some("old-authority")
        );
        let _ = fs::remove_dir_all(directory);
    }

    #[tokio::test]
    async fn startup_poll_accepts_a_backend_that_becomes_ready_later() {
        let mut probes =
            std::collections::VecDeque::from([None, None, Some("authority-1".to_string())]);
        let delays = std::sync::Mutex::new(Vec::new());

        let result = poll_startup_readiness(
            || std::future::ready(probes.pop_front().flatten()),
            |delay| {
                delays.lock().unwrap().push(delay);
                std::future::ready(())
            },
            || Ok(true),
        )
        .await
        .unwrap();

        assert_eq!(result.as_deref(), Some("authority-1"));
        assert_eq!(
            *delays.lock().unwrap(),
            vec![
                Duration::from_millis(100),
                Duration::from_millis(200),
                Duration::from_millis(400)
            ]
        );
    }

    #[tokio::test]
    async fn startup_poll_aborts_when_settings_generation_changes() {
        let checks = std::cell::Cell::new(0);
        let result = poll_startup_readiness(
            || std::future::ready(None),
            |_| std::future::ready(()),
            || {
                checks.set(checks.get() + 1);
                Ok(checks.get() < 2)
            },
        )
        .await;

        assert!(result.unwrap_err().contains("settings changed"));
    }
}
