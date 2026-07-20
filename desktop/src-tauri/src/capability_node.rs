use crate::backend::{probe, BackendState};
use reqwest::redirect::Policy;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const ENROLL_TIMEOUT: Duration = Duration::from_secs(15);
const MAX_ENROLL_RESPONSE_BYTES: u64 = 16 * 1024;

#[derive(Deserialize, Serialize)]
struct NodeCredentials {
    endpoint: String,
    device_id: String,
    device_secret: String,
    node_name: String,
}

#[derive(Deserialize)]
struct EnrollResponse {
    ok: bool,
    device_id: Option<String>,
    device_secret: Option<String>,
    instance_id: Option<String>,
}

#[derive(Serialize, PartialEq, Eq)]
pub struct EnrollmentStatus {
    pub enrolled: bool,
    pub endpoint: Option<String>,
    pub device_id: Option<String>,
    pub node_name: Option<String>,
}

pub async fn enroll(
    state: &BackendState,
    code: String,
    node_name: String,
) -> Result<EnrollmentStatus, String> {
    let (endpoint, instance_id) = state.active_validated_authority()?;
    let credentials_path = credentials_path()?;
    if credentials_path.exists() {
        return Err("this machine is already enrolled; revoke and remove its local credential before replacing it".into());
    }
    let code = code.trim();
    let node_name = validate_node_name(&node_name)?;
    if code.is_empty()
        || code.len() > 32
        || !code
            .chars()
            .all(|character| character.is_ascii_alphanumeric())
    {
        return Err("invalid capability-node enrollment code".into());
    }

    let client = reqwest::Client::builder()
        .redirect(Policy::none())
        .timeout(ENROLL_TIMEOUT)
        .build()
        .map_err(|_| "cannot create capability-node enrollment client".to_string())?;
    let response = client
        .post(format!("{endpoint}/api/auth/devices/enroll"))
        .json(&serde_json::json!({
            "code": code,
            "name": node_name,
            "platform": std::env::consts::OS,
        }))
        .send()
        .await
        .map_err(|_| "capability-node enrollment request failed".to_string())?;
    if !response.status().is_success() {
        return Err(format!(
            "capability-node enrollment was rejected (HTTP {})",
            response.status().as_u16()
        ));
    }
    if response.content_length().unwrap_or(0) > MAX_ENROLL_RESPONSE_BYTES {
        return Err("capability-node enrollment response is too large".into());
    }
    let bytes = response
        .bytes()
        .await
        .map_err(|_| "capability-node enrollment returned an invalid response".to_string())?;
    if bytes.len() as u64 > MAX_ENROLL_RESPONSE_BYTES {
        return Err("capability-node enrollment response is too large".into());
    }
    let payload: EnrollResponse = serde_json::from_slice(&bytes)
        .map_err(|_| "capability-node enrollment returned an invalid response".to_string())?;
    let device_id = payload
        .device_id
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "capability-node enrollment was rejected".to_string())?;
    let device_secret = payload
        .device_secret
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "capability-node enrollment was rejected".to_string())?;
    if !payload.ok {
        return Err("capability-node enrollment was rejected".into());
    }
    if payload
        .instance_id
        .as_deref()
        .is_some_and(|value| value != instance_id)
    {
        return Err("the backend authority changed during capability-node enrollment".into());
    }
    if probe(&endpoint).await.as_deref() != Some(instance_id.as_str()) {
        return Err("the backend authority could not be revalidated after enrollment".into());
    }

    let credentials = NodeCredentials {
        endpoint: endpoint.clone(),
        device_id: device_id.clone(),
        device_secret,
        node_name: node_name.clone(),
    };
    if state.active_validated_authority()? != (endpoint.clone(), instance_id) {
        return Err("the active backend changed during capability-node enrollment".into());
    }
    write_credentials(&credentials_path, &credentials)?;
    Ok(EnrollmentStatus {
        enrolled: true,
        endpoint: Some(endpoint),
        device_id: Some(device_id),
        node_name: Some(node_name),
    })
}

pub fn status() -> Result<EnrollmentStatus, String> {
    let path = credentials_path()?;
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            return Ok(EnrollmentStatus {
                enrolled: false,
                endpoint: None,
                device_id: None,
                node_name: None,
            });
        }
        Err(err) => return Err(format!("cannot read capability-node credentials: {err}")),
    };
    let credentials: NodeCredentials = serde_json::from_slice(&bytes)
        .map_err(|_| "capability-node credentials are invalid".to_string())?;
    Ok(EnrollmentStatus {
        enrolled: true,
        endpoint: Some(credentials.endpoint),
        device_id: Some(credentials.device_id),
        node_name: Some(credentials.node_name),
    })
}

fn validate_node_name(value: &str) -> Result<String, String> {
    let value = value.trim();
    if value.is_empty() || value.len() > 64 || value.chars().any(char::is_control) {
        return Err("node name must be between 1 and 64 characters".into());
    }
    Ok(value.to_string())
}

fn credentials_path() -> Result<PathBuf, String> {
    // The managed systemd unit uses this canonical path. Keeping the native
    // writer identical prevents a successful enrollment that the service cannot see.
    let base = PathBuf::from(
        std::env::var_os("HOME").ok_or_else(|| "cannot resolve home directory".to_string())?,
    )
    .join(".local/state");
    Ok(base.join("dax-assistant/edge.json"))
}

fn write_credentials(path: &Path, credentials: &NodeCredentials) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "invalid capability-node credentials path".to_string())?;
    fs::create_dir_all(parent)
        .map_err(|err| format!("cannot create capability-node state directory: {err}"))?;
    if fs::symlink_metadata(parent)
        .map_err(|err| format!("cannot inspect capability-node state directory: {err}"))?
        .file_type()
        .is_symlink()
    {
        return Err("capability-node state directory must not be a symlink".into());
    }
    if path.symlink_metadata().is_ok() {
        return Err("capability-node credentials already exist".into());
    }
    set_mode(parent, 0o700)?;

    let payload = serde_json::to_vec(credentials)
        .map_err(|_| "cannot encode capability-node credentials".to_string())?;
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let temporary = parent.join(format!(".edge.json.{}.{nonce}", std::process::id()));
    let result = (|| {
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options
            .open(&temporary)
            .map_err(|err| format!("cannot create capability-node credentials: {err}"))?;
        file.write_all(&payload)
            .and_then(|()| file.write_all(b"\n"))
            .and_then(|()| file.sync_all())
            .map_err(|err| format!("cannot write capability-node credentials: {err}"))?;
        // Link without replacement so a concurrent enrollment cannot overwrite
        // an existing long-lived node credential.
        fs::hard_link(&temporary, path)
            .map_err(|err| format!("cannot install capability-node credentials: {err}"))?;
        let _ = fs::remove_file(&temporary);
        set_mode(path, 0o600)
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

#[cfg(unix)]
fn set_mode(path: &Path, mode: u32) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(mode))
        .map_err(|err| format!("cannot secure capability-node state: {err}"))
}

#[cfg(not(unix))]
fn set_mode(_path: &Path, _mode: u32) -> Result<(), String> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_node_names() {
        assert_eq!(validate_node_name("  laptop  ").unwrap(), "laptop");
        assert!(validate_node_name("").is_err());
        assert!(validate_node_name("bad\nname").is_err());
        assert!(validate_node_name(&"x".repeat(65)).is_err());
    }

    #[test]
    fn enrollment_status_has_no_secret_field() {
        let status = EnrollmentStatus {
            enrolled: true,
            endpoint: Some("https://dax.example".into()),
            device_id: Some("device-1".into()),
            node_name: Some("laptop".into()),
        };
        let value = serde_json::to_value(status).unwrap();
        assert!(value.get("device_secret").is_none());
    }

    #[cfg(unix)]
    #[test]
    fn writes_daemon_compatible_owner_only_credentials() {
        use std::os::unix::fs::PermissionsExt;

        let root = std::env::temp_dir().join(format!(
            "dax-capability-node-test-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = root.join("dax-assistant/edge.json");
        let credentials = NodeCredentials {
            endpoint: "https://dax.example".into(),
            device_id: "device-1".into(),
            device_secret: "never-return-this".into(),
            node_name: "laptop".into(),
        };
        write_credentials(&path, &credentials).unwrap();

        assert_eq!(
            fs::metadata(path.parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        let value: serde_json::Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(value["device_secret"], "never-return-this");
        assert_eq!(value["node_name"], "laptop");
        assert!(write_credentials(&path, &credentials).is_err());
        let unchanged: serde_json::Value =
            serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(unchanged["device_secret"], "never-return-this");
        fs::remove_dir_all(root).unwrap();
    }
}
