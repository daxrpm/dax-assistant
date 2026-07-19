//! Backend connection mode and health.
//!
//! M1 supports "remote" only — the app connects to an already-running backend
//! (PLAN.md 3.7 option C, which is the default per Q1). Sidecar supervision is
//! deliberately not implemented yet: it requires Python packaging work that the
//! plan defers, and remote mode covers the systemd-unit case exactly.

use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::time::Duration;

pub const DEFAULT_URL: &str = "http://127.0.0.1:8420";

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum BackendMode {
    /// Connect to a backend someone else started (systemd unit, `uv run dax`).
    Remote,
    /// Spawn and supervise the backend ourselves. Not implemented in M1.
    Sidecar,
}

#[derive(Clone, Debug, Serialize)]
pub struct BackendStatus {
    pub mode: BackendMode,
    pub url: String,
    pub healthy: bool,
    /// None until the first probe completes.
    pub pid: Option<u32>,
}

pub struct BackendState {
    inner: Mutex<Settings>,
}

struct Settings {
    mode: BackendMode,
    url: String,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            inner: Mutex::new(Settings {
                mode: BackendMode::Remote,
                url: DEFAULT_URL.to_string(),
            }),
        }
    }
}

impl BackendState {
    pub fn url(&self) -> String {
        self.inner
            .lock()
            .map(|s| s.url.clone())
            .unwrap_or_else(|_| DEFAULT_URL.to_string())
    }

    pub fn mode(&self) -> BackendMode {
        self.inner
            .lock()
            .map(|s| s.mode)
            .unwrap_or(BackendMode::Remote)
    }

    pub fn set(&self, mode: BackendMode, url: Option<String>) -> Result<(), String> {
        if mode == BackendMode::Sidecar {
            return Err("Sidecar mode is not implemented yet; use remote mode.".into());
        }
        let mut guard = self.inner.lock().map_err(|e| e.to_string())?;
        guard.mode = mode;
        if let Some(url) = url {
            guard.url = url.trim_end_matches('/').to_string();
        }
        Ok(())
    }
}

/// Probe `GET /api/health`. Unauthenticated by design, so this works before login.
pub async fn probe(url: &str) -> bool {
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(client) => client,
        Err(_) => return false,
    };
    match client.get(format!("{url}/api/health")).send().await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}
