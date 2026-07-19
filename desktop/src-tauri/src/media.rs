use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::io::ErrorKind;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Emitter};
use tokio::io::AsyncReadExt;
use tokio::process::Command;
use tokio::sync::oneshot;
use tokio::time::timeout;

const OUTPUT_LIMIT: u64 = 64 * 1024;
const COMMAND_TIMEOUT: Duration = Duration::from_millis(1500);
const FIELD_SEPARATOR: char = '\u{1f}';
const SPECTRUM_BANDS: usize = 40;
const SPECTRUM_FRAMES: usize = 2048;
const SPECTRUM_RATE: f32 = 48_000.0;
type SpectrumStop = Arc<Mutex<Option<(u64, oneshot::Sender<()>)>>>;

#[derive(Default)]
pub struct MediaState {
    active_player: Mutex<Option<String>>,
    ducking: Mutex<DuckingSession>,
    spectrum_stop: SpectrumStop,
    spectrum_id: AtomicU64,
}

#[derive(Clone, Debug, Serialize)]
pub struct SpectrumFrame {
    bands: Vec<f32>,
    bass: f32,
    level: f32,
}

fn analyze_spectrum(bytes: &[u8], previous: &mut [f32; SPECTRUM_BANDS]) -> SpectrumFrame {
    let mut samples = Vec::with_capacity(SPECTRUM_FRAMES);
    for frame in bytes.chunks_exact(4).take(SPECTRUM_FRAMES) {
        let left = i16::from_le_bytes([frame[0], frame[1]]) as f32 / i16::MAX as f32;
        let right = i16::from_le_bytes([frame[2], frame[3]]) as f32 / i16::MAX as f32;
        samples.push((left + right) * 0.5);
    }

    let level = (samples.iter().map(|sample| sample * sample).sum::<f32>()
        / samples.len().max(1) as f32)
        .sqrt();
    let minimum = 55.0_f32;
    let maximum = 12_000.0_f32;
    let mut bands = Vec::with_capacity(SPECTRUM_BANDS);
    for (index, smoothed) in previous.iter_mut().enumerate() {
        let ratio = index as f32 / (SPECTRUM_BANDS - 1) as f32;
        let frequency = minimum * (maximum / minimum).powf(ratio);
        let omega = std::f32::consts::TAU * frequency / SPECTRUM_RATE;
        let coefficient = 2.0 * omega.cos();
        let mut first = 0.0;
        let mut second = 0.0;
        for (sample_index, sample) in samples.iter().enumerate() {
            let window = 0.5
                - 0.5
                    * (std::f32::consts::TAU * sample_index as f32
                        / (samples.len() - 1).max(1) as f32)
                        .cos();
            let next = sample * window + coefficient * first - second;
            second = first;
            first = next;
        }
        let power = (first * first + second * second - coefficient * first * second)
            .max(0.0)
            .sqrt()
            / samples.len().max(1) as f32;
        let normalized = (power * 28.0).sqrt().clamp(0.0, 1.0);
        let smoothing = if normalized > *smoothed { 0.42 } else { 0.14 };
        *smoothed += (normalized - *smoothed) * smoothing;
        bands.push(*smoothed);
    }
    let bass = bands.iter().take(7).sum::<f32>() / 7.0;
    SpectrumFrame {
        bands,
        bass,
        level: (level * 5.0).clamp(0.0, 1.0),
    }
}

pub async fn start_spectrum(state: &MediaState, app: AppHandle) -> Result<(), String> {
    let mut active = state
        .spectrum_stop
        .lock()
        .map_err(|_| "media spectrum state unavailable")?;
    if active.is_some() {
        return Ok(());
    }

    let mut child = Command::new("pw-record")
        .args([
            "--properties=stream.capture.sink=true",
            "--rate=48000",
            "--channels=2",
            "--format=s16",
            "--raw",
            "-",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .map_err(|error| format!("cannot start PipeWire spectrum capture: {error}"))?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| "cannot capture PipeWire spectrum output".to_owned())?;
    let (stop_tx, mut stop_rx) = oneshot::channel();
    let capture_id = state.spectrum_id.fetch_add(1, Ordering::Relaxed);
    *active = Some((capture_id, stop_tx));
    drop(active);

    let spectrum_stop = Arc::clone(&state.spectrum_stop);
    tauri::async_runtime::spawn(async move {
        let mut bytes = vec![0_u8; SPECTRUM_FRAMES * 4];
        let mut smoothed = [0.0; SPECTRUM_BANDS];
        loop {
            tokio::select! {
                result = stdout.read_exact(&mut bytes) => {
                    if result.is_err() {
                        break;
                    }
                    let _ = app.emit("media://spectrum", analyze_spectrum(&bytes, &mut smoothed));
                }
                _ = &mut stop_rx => break,
            }
        }
        let _ = child.kill().await;
        if let Ok(mut active) = spectrum_stop.lock() {
            if active.as_ref().is_some_and(|(id, _)| *id == capture_id) {
                *active = None;
            }
        }
    });
    Ok(())
}

pub fn stop_spectrum(state: &MediaState) -> Result<(), String> {
    if let Some((_, stop)) = state
        .spectrum_stop
        .lock()
        .map_err(|_| "media spectrum state unavailable")?
        .take()
    {
        let _ = stop.send(());
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DuckingState {
    #[default]
    Idle,
    Listening,
    Processing,
    Speaking,
}

impl DuckingState {
    fn volume_factor(self) -> Option<f64> {
        match self {
            Self::Idle => None,
            Self::Listening => Some(0.20),
            Self::Processing => Some(0.55),
            Self::Speaking => Some(0.15),
        }
    }
}

#[derive(Default)]
struct DuckingSession {
    player: Option<String>,
    original_volume: Option<f64>,
    paused_by_dax: bool,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum RestoreAction {
    Volume(f64),
    Play,
    None,
}

fn restoration(original_volume: Option<f64>, paused_by_dax: bool) -> RestoreAction {
    match (original_volume, paused_by_dax) {
        (Some(volume), _) => RestoreAction::Volume(volume),
        (None, true) => RestoreAction::Play,
        (None, false) => RestoreAction::None,
    }
}

fn fallback_should_pause(state: DuckingState, playing: bool) -> bool {
    playing && matches!(state, DuckingState::Listening | DuckingState::Speaking)
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MediaAction {
    Previous,
    PlayPause,
    Next,
}

impl MediaAction {
    fn playerctl_arg(self) -> &'static str {
        match self {
            Self::Previous => "previous",
            Self::PlayPause => "play-pause",
            Self::Next => "next",
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize)]
pub struct MediaSnapshot {
    pub available: bool,
    pub player: Option<String>,
    pub identity: Option<String>,
    pub status: Option<String>,
    pub title: Option<String>,
    pub artist: Option<String>,
    pub album: Option<String>,
    pub position_seconds: Option<f64>,
    pub duration_seconds: Option<f64>,
}

#[derive(Debug)]
enum PlayerctlError {
    Missing,
    Failed(String),
}

struct CommandOutput {
    success: bool,
    stdout: String,
}

async fn run_playerctl(args: &[String]) -> Result<CommandOutput, PlayerctlError> {
    let mut child = Command::new("playerctl")
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .map_err(|error| {
            if error.kind() == ErrorKind::NotFound {
                PlayerctlError::Missing
            } else {
                PlayerctlError::Failed(format!("cannot start playerctl: {error}"))
            }
        })?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| PlayerctlError::Failed("cannot capture playerctl output".into()))?;
    let reader = tokio::spawn(async move {
        let mut bytes = Vec::new();
        stdout
            .take(OUTPUT_LIMIT + 1)
            .read_to_end(&mut bytes)
            .await?;
        Ok::<_, std::io::Error>(bytes)
    });

    let wait_result = match timeout(COMMAND_TIMEOUT, child.wait()).await {
        Ok(result) => result,
        Err(_) => {
            let _ = child.kill().await;
            reader.abort();
            return Err(PlayerctlError::Failed("playerctl timed out".into()));
        }
    };
    let bytes = reader
        .await
        .map_err(|error| PlayerctlError::Failed(format!("cannot join playerctl reader: {error}")))?
        .map_err(|error| PlayerctlError::Failed(format!("cannot read playerctl: {error}")))?;
    if bytes.len() as u64 > OUTPUT_LIMIT {
        return Err(PlayerctlError::Failed(
            "playerctl output exceeded limit".into(),
        ));
    }
    let status = wait_result
        .map_err(|error| PlayerctlError::Failed(format!("cannot wait for playerctl: {error}")))?;
    Ok(CommandOutput {
        success: status.success(),
        stdout: String::from_utf8_lossy(&bytes).trim().to_owned(),
    })
}

fn parse_players(output: &str) -> Vec<String> {
    let mut seen = HashSet::new();
    output
        .lines()
        .map(str::trim)
        .filter(|player| !player.is_empty() && seen.insert((*player).to_owned()))
        .map(str::to_owned)
        .collect()
}

fn select_player(candidates: &[(String, String)]) -> Option<String> {
    candidates
        .iter()
        .find(|(_, status)| status.eq_ignore_ascii_case("playing"))
        .or_else(|| {
            candidates
                .iter()
                .find(|(_, status)| status.eq_ignore_ascii_case("paused"))
        })
        .map(|(player, _)| player.clone())
}

fn optional(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
}

#[derive(Default)]
struct ParsedMetadata {
    identity: Option<String>,
    title: Option<String>,
    artist: Option<String>,
    album: Option<String>,
    duration_seconds: Option<f64>,
}

fn parse_metadata(output: &str) -> ParsedMetadata {
    let mut fields = output.split(FIELD_SEPARATOR);
    ParsedMetadata {
        identity: optional(fields.next()),
        title: optional(fields.next()),
        artist: optional(fields.next()),
        album: optional(fields.next()),
        duration_seconds: fields
            .next()
            .and_then(|value| value.trim().parse::<f64>().ok())
            .filter(|value| *value >= 0.0)
            .map(|microseconds| microseconds / 1_000_000.0),
    }
}

async fn discover_players() -> Result<Vec<String>, PlayerctlError> {
    let output = run_playerctl(&["-l".into()]).await?;
    Ok(if output.success {
        parse_players(&output.stdout)
    } else {
        Vec::new()
    })
}

pub async fn status(state: &MediaState) -> Result<MediaSnapshot, String> {
    let players = match discover_players().await {
        Ok(players) => players,
        Err(PlayerctlError::Missing) => {
            *state
                .active_player
                .lock()
                .map_err(|_| "media state unavailable")? = None;
            return Ok(MediaSnapshot::default());
        }
        Err(PlayerctlError::Failed(error)) => return Err(error),
    };

    let mut candidates = Vec::new();
    for player in players {
        let output = run_playerctl(&["--player".into(), player.clone(), "status".into()])
            .await
            .map_err(|error| match error {
                PlayerctlError::Missing => "playerctl is not installed".into(),
                PlayerctlError::Failed(error) => error,
            })?;
        if output.success {
            candidates.push((player, output.stdout));
        }
    }

    let Some(player) = select_player(&candidates) else {
        *state
            .active_player
            .lock()
            .map_err(|_| "media state unavailable")? = None;
        return Ok(MediaSnapshot {
            available: true,
            ..MediaSnapshot::default()
        });
    };
    let player_status = candidates
        .iter()
        .find(|(name, _)| name == &player)
        .map(|(_, status)| status.clone());
    *state
        .active_player
        .lock()
        .map_err(|_| "media state unavailable")? = Some(player.clone());

    let metadata = run_playerctl(&[
        "--player".into(),
        player.clone(),
        "metadata".into(),
        "--format".into(),
        "{{playerName}}\u{1f}{{title}}\u{1f}{{artist}}\u{1f}{{album}}\u{1f}{{mpris:length}}".into(),
    ])
    .await
    .ok()
    .filter(|output| output.success)
    .map(|output| parse_metadata(&output.stdout))
    .unwrap_or_default();
    let position = run_playerctl(&["--player".into(), player.clone(), "position".into()])
        .await
        .ok()
        .filter(|output| output.success)
        .and_then(|output| output.stdout.parse::<f64>().ok())
        .filter(|value| *value >= 0.0);

    Ok(MediaSnapshot {
        available: true,
        player: Some(player),
        identity: metadata.identity,
        status: player_status,
        title: metadata.title,
        artist: metadata.artist,
        album: metadata.album,
        position_seconds: position,
        duration_seconds: metadata.duration_seconds,
    })
}

pub async fn control(state: &MediaState, action: MediaAction) -> Result<(), String> {
    let active = state
        .active_player
        .lock()
        .map_err(|_| "media state unavailable")?
        .clone()
        .ok_or_else(|| "no active media player".to_owned())?;
    let players = discover_players().await.map_err(|error| match error {
        PlayerctlError::Missing => "playerctl is not installed".into(),
        PlayerctlError::Failed(error) => error,
    })?;
    if !players.iter().any(|player| player == &active) {
        *state
            .active_player
            .lock()
            .map_err(|_| "media state unavailable")? = None;
        return Err("active media player is no longer available".into());
    }
    let output = run_playerctl(&["--player".into(), active, action.playerctl_arg().into()])
        .await
        .map_err(|error| match error {
            PlayerctlError::Missing => "playerctl is not installed".into(),
            PlayerctlError::Failed(error) => error,
        })?;
    if output.success {
        Ok(())
    } else {
        Err("playerctl action failed".into())
    }
}

async fn player_exists(player: &str) -> Result<bool, String> {
    discover_players()
        .await
        .map(|players| players.iter().any(|candidate| candidate == player))
        .map_err(|error| match error {
            PlayerctlError::Missing => "playerctl is not installed".into(),
            PlayerctlError::Failed(error) => error,
        })
}

async fn player_command(player: &str, command: &str) -> Result<CommandOutput, String> {
    run_playerctl(&["--player".into(), player.into(), command.into()])
        .await
        .map_err(|error| match error {
            PlayerctlError::Missing => "playerctl is not installed".into(),
            PlayerctlError::Failed(error) => error,
        })
}

async fn current_player(state: &MediaState) -> Result<String, String> {
    if let Some(player) = state
        .active_player
        .lock()
        .map_err(|_| "media state unavailable")?
        .clone()
    {
        return Ok(player);
    }

    let players = discover_players().await.map_err(|error| match error {
        PlayerctlError::Missing => "playerctl is not installed".to_owned(),
        PlayerctlError::Failed(error) => error,
    })?;
    let mut candidates = Vec::new();
    for player in players {
        let output = player_command(&player, "status").await?;
        if output.success {
            candidates.push((player, output.stdout));
        }
    }
    let player = select_player(&candidates).ok_or_else(|| "no active media player".to_owned())?;
    *state
        .active_player
        .lock()
        .map_err(|_| "media state unavailable")? = Some(player.clone());
    Ok(player)
}

async fn restore_ducking(session: DuckingSession) {
    let Some(player) = session.player else {
        return;
    };
    if !player_exists(&player).await.unwrap_or(false) {
        return;
    }
    let command = match restoration(session.original_volume, session.paused_by_dax) {
        RestoreAction::Volume(volume) => Some(("volume", Some(volume.to_string()))),
        RestoreAction::Play => {
            let paused = player_command(&player, "status")
                .await
                .is_ok_and(|output| output.success && output.stdout.eq_ignore_ascii_case("paused"));
            paused.then_some(("play", None))
        }
        RestoreAction::None => None,
    };
    if let Some((action, value)) = command {
        let mut args = vec!["--player".into(), player, action.into()];
        if let Some(value) = value {
            args.push(value);
        }
        let _ = run_playerctl(&args).await;
    }
}

pub async fn set_ducking(state: &MediaState, next: DuckingState) -> Result<(), String> {
    if next == DuckingState::Idle {
        let session = {
            let mut ducking = state
                .ducking
                .lock()
                .map_err(|_| "media state unavailable")?;
            std::mem::take(&mut *ducking)
        };
        restore_ducking(session).await;
        return Ok(());
    }

    let existing_player = state
        .ducking
        .lock()
        .map_err(|_| "media state unavailable")?
        .player
        .clone();
    let player = if let Some(player) = existing_player {
        player
    } else {
        current_player(state).await?
    };
    if !player_exists(&player).await? {
        *state
            .ducking
            .lock()
            .map_err(|_| "media state unavailable")? = DuckingSession::default();
        return Err("active media player is no longer available".into());
    }

    let needs_capture = state
        .ducking
        .lock()
        .map_err(|_| "media state unavailable")?
        .player
        .is_none();
    if needs_capture {
        let volume = player_command(&player, "volume")
            .await
            .ok()
            .filter(|output| output.success)
            .and_then(|output| output.stdout.parse::<f64>().ok())
            .filter(|volume| volume.is_finite() && *volume >= 0.0);
        let mut ducking = state
            .ducking
            .lock()
            .map_err(|_| "media state unavailable")?;
        ducking.player = Some(player.clone());
        ducking.original_volume = volume;
    }

    let original_volume = state
        .ducking
        .lock()
        .map_err(|_| "media state unavailable")?
        .original_volume;
    if let (Some(original), Some(factor)) = (original_volume, next.volume_factor()) {
        let output = run_playerctl(&[
            "--player".into(),
            player.clone(),
            "volume".into(),
            (original * factor).to_string(),
        ])
        .await
        .map_err(|error| match error {
            PlayerctlError::Missing => "playerctl is not installed".to_owned(),
            PlayerctlError::Failed(error) => error,
        })?;
        if output.success {
            return Ok(());
        }
        state
            .ducking
            .lock()
            .map_err(|_| "media state unavailable")?
            .original_volume = None;
    }

    let status = player_command(&player, "status").await?;
    if fallback_should_pause(
        next,
        status.success && status.stdout.eq_ignore_ascii_case("playing"),
    ) {
        let paused = player_command(&player, "pause").await?;
        if paused.success {
            state
                .ducking
                .lock()
                .map_err(|_| "media state unavailable")?
                .paused_by_dax = true;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_and_deduplicates_player_list() {
        assert_eq!(
            parse_players("spotify\nfirefox.instance\nspotify\n\n"),
            vec!["spotify", "firefox.instance"]
        );
    }

    #[test]
    fn parses_metadata_without_exposing_art_urls() {
        let parsed = parse_metadata("Spotify\u{1f}Song\u{1f}Artist\u{1f}Album\u{1f}245000000");
        assert_eq!(parsed.identity.as_deref(), Some("Spotify"));
        assert_eq!(parsed.title.as_deref(), Some("Song"));
        assert_eq!(parsed.duration_seconds, Some(245.0));
    }

    #[test]
    fn selects_playing_before_paused() {
        let candidates = vec![
            ("browser".into(), "Paused".into()),
            ("spotify".into(), "Playing".into()),
        ];
        assert_eq!(select_player(&candidates).as_deref(), Some("spotify"));
    }

    #[test]
    fn maps_only_supported_actions() {
        assert_eq!(MediaAction::Previous.playerctl_arg(), "previous");
        assert_eq!(MediaAction::PlayPause.playerctl_arg(), "play-pause");
        assert_eq!(MediaAction::Next.playerctl_arg(), "next");
        assert!(serde_json::from_str::<MediaAction>("\"seek\"").is_err());
    }

    #[test]
    fn maps_ducking_states_to_relative_volume_factors() {
        assert_eq!(DuckingState::Idle.volume_factor(), None);
        assert_eq!(DuckingState::Listening.volume_factor(), Some(0.20));
        assert_eq!(DuckingState::Processing.volume_factor(), Some(0.55));
        assert_eq!(DuckingState::Speaking.volume_factor(), Some(0.15));
    }

    #[test]
    fn restoration_prefers_exact_original_volume_and_owned_pause() {
        assert_eq!(restoration(Some(0.73), true), RestoreAction::Volume(0.73));
        assert_eq!(restoration(None, true), RestoreAction::Play);
        assert_eq!(restoration(None, false), RestoreAction::None);
    }

    #[test]
    fn fallback_pauses_only_active_listening_or_speaking_playback() {
        assert!(fallback_should_pause(DuckingState::Listening, true));
        assert!(fallback_should_pause(DuckingState::Speaking, true));
        assert!(!fallback_should_pause(DuckingState::Processing, true));
        assert!(!fallback_should_pause(DuckingState::Listening, false));
    }

    #[test]
    fn spectrum_analysis_is_bounded_and_tracks_low_frequency_energy() {
        let mut bytes = Vec::with_capacity(SPECTRUM_FRAMES * 4);
        for index in 0..SPECTRUM_FRAMES {
            let sample = ((std::f32::consts::TAU * 110.0 * index as f32 / SPECTRUM_RATE).sin()
                * 0.6
                * i16::MAX as f32) as i16;
            bytes.extend_from_slice(&sample.to_le_bytes());
            bytes.extend_from_slice(&sample.to_le_bytes());
        }
        let mut previous = [0.0; SPECTRUM_BANDS];
        let frame = analyze_spectrum(&bytes, &mut previous);
        assert_eq!(frame.bands.len(), SPECTRUM_BANDS);
        assert!(frame.bands.iter().all(|value| (0.0..=1.0).contains(value)));
        assert!(frame.bass > 0.0);
        assert!((0.0..=1.0).contains(&frame.level));
    }
}
