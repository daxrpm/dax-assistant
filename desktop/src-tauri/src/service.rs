use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Duration;

const STATUS_TIMEOUT: Duration = Duration::from_secs(3);
const ACTION_TIMEOUT: Duration = Duration::from_secs(10);

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ServiceAction {
    Status,
    Start,
    Stop,
    Restart,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ServiceTarget {
    Backend,
    CapabilityNode,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct ServiceStatus {
    pub unit: &'static str,
    pub load_state: String,
    pub active_state: String,
    pub sub_state: String,
}

impl ServiceAction {
    fn systemctl_verb(self) -> Option<&'static str> {
        match self {
            Self::Status => None,
            Self::Start => Some("start"),
            Self::Stop => Some("stop"),
            Self::Restart => Some("restart"),
        }
    }
}

impl ServiceTarget {
    fn unit(self) -> &'static str {
        match self {
            Self::Backend => "dax-assistant.service",
            Self::CapabilityNode => "dax-assistant-node.service",
        }
    }
}

#[cfg(target_os = "linux")]
pub async fn control(action: ServiceAction) -> Result<ServiceStatus, String> {
    control_target(ServiceTarget::Backend, action).await
}

#[cfg(target_os = "linux")]
pub async fn control_target(
    target: ServiceTarget,
    action: ServiceAction,
) -> Result<ServiceStatus, String> {
    let unit = target.unit();
    if let Some(verb) = action.systemctl_verb() {
        run_systemctl(&["--user", verb, unit], ACTION_TIMEOUT).await?;
    }
    let output = run_systemctl(
        &[
            "--user",
            "show",
            unit,
            "--no-pager",
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
        ],
        STATUS_TIMEOUT,
    )
    .await?;
    parse_status(unit, &output)
}

#[cfg(not(target_os = "linux"))]
pub async fn control(action: ServiceAction) -> Result<ServiceStatus, String> {
    control_target(ServiceTarget::Backend, action).await
}

#[cfg(not(target_os = "linux"))]
pub async fn control_target(
    _target: ServiceTarget,
    _action: ServiceAction,
) -> Result<ServiceStatus, String> {
    Err("systemd user service control is only available on Linux".into())
}

#[cfg(target_os = "linux")]
async fn run_systemctl(args: &[&str], timeout: Duration) -> Result<String, String> {
    use tokio::process::Command;

    let mut command = Command::new("systemctl");
    command.args(args).kill_on_drop(true);
    let output = tokio::time::timeout(timeout, command.output())
        .await
        .map_err(|_| format!("systemctl timed out after {} seconds", timeout.as_secs()))?
        .map_err(|err| format!("cannot execute systemctl: {err}"))?;
    if !output.status.success() {
        let detail = concise_output(&output.stderr);
        return Err(if detail.is_empty() {
            format!("systemctl failed with status {}", output.status)
        } else {
            format!("systemctl failed: {detail}")
        });
    }
    String::from_utf8(output.stdout).map_err(|_| "systemctl returned invalid UTF-8".into())
}

fn concise_output(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes)
        .trim()
        .chars()
        .take(512)
        .collect()
}

fn parse_status(unit: &'static str, output: &str) -> Result<ServiceStatus, String> {
    let values: HashMap<_, _> = output
        .lines()
        .filter_map(|line| line.split_once('='))
        .collect();
    let value = |key: &str| {
        values
            .get(key)
            .filter(|value| !value.is_empty())
            .map(|value| (*value).to_string())
            .ok_or_else(|| format!("systemctl response is missing {key}"))
    };
    Ok(ServiceStatus {
        unit,
        load_state: value("LoadState")?,
        active_state: value("ActiveState")?,
        sub_state: value("SubState")?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn action_mapping_is_a_fixed_allowlist() {
        assert_eq!(ServiceAction::Status.systemctl_verb(), None);
        assert_eq!(ServiceAction::Start.systemctl_verb(), Some("start"));
        assert_eq!(ServiceAction::Stop.systemctl_verb(), Some("stop"));
        assert_eq!(ServiceAction::Restart.systemctl_verb(), Some("restart"));
    }

    #[test]
    fn target_mapping_is_a_fixed_allowlist() {
        assert_eq!(ServiceTarget::Backend.unit(), "dax-assistant.service");
        assert_eq!(
            ServiceTarget::CapabilityNode.unit(),
            "dax-assistant-node.service"
        );
    }

    #[test]
    fn parses_systemctl_properties_independent_of_order() {
        let parsed = parse_status(
            ServiceTarget::Backend.unit(),
            "SubState=running\nLoadState=loaded\nActiveState=active\n",
        )
        .unwrap();
        assert_eq!(parsed.unit, ServiceTarget::Backend.unit());
        assert_eq!(parsed.load_state, "loaded");
        assert_eq!(parsed.active_state, "active");
        assert_eq!(parsed.sub_state, "running");
    }

    #[test]
    fn rejects_incomplete_status() {
        assert!(parse_status(
            ServiceTarget::CapabilityNode.unit(),
            "LoadState=loaded\nActiveState=active\n"
        )
        .is_err());
    }

    #[test]
    fn error_output_is_bounded() {
        assert_eq!(concise_output(&vec![b'x'; 600]).len(), 512);
    }
}
