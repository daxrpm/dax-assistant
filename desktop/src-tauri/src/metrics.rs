use serde::Serialize;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use sysinfo::{Disks, System, MINIMUM_CPU_UPDATE_INTERVAL};

const CACHE_TTL: Duration = Duration::from_secs(1);

#[derive(Clone, Debug, Serialize)]
pub struct DiskMetrics {
    pub name: String,
    pub mount_point: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
    pub removable: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct SystemMetrics {
    pub cpu_usage_percent: f32,
    pub logical_cpu_count: usize,
    pub memory_total_bytes: u64,
    pub memory_used_bytes: u64,
    pub memory_available_bytes: u64,
    pub uptime_seconds: u64,
    pub disks: Vec<DiskMetrics>,
}

#[derive(Clone, Default)]
pub struct MetricsState {
    cache: Arc<Mutex<Option<(Instant, SystemMetrics)>>>,
}

impl MetricsState {
    pub fn collect(&self) -> Result<SystemMetrics, String> {
        let mut cache = self
            .cache
            .lock()
            .map_err(|_| "system metrics cache is unavailable".to_string())?;
        if let Some((collected_at, metrics)) = cache.as_ref() {
            if collected_at.elapsed() < CACHE_TTL {
                return Ok(metrics.clone());
            }
        }
        let metrics = collect();
        *cache = Some((Instant::now(), metrics.clone()));
        Ok(metrics)
    }
}

fn collect() -> SystemMetrics {
    let mut system = System::new_all();
    std::thread::sleep(MINIMUM_CPU_UPDATE_INTERVAL);
    system.refresh_cpu_usage();
    system.refresh_memory();

    let disks = Disks::new_with_refreshed_list()
        .list()
        .iter()
        .map(|disk| DiskMetrics {
            name: disk.name().to_string_lossy().into_owned(),
            mount_point: disk.mount_point().to_string_lossy().into_owned(),
            total_bytes: disk.total_space(),
            available_bytes: disk.available_space(),
            removable: disk.is_removable(),
        })
        .collect();

    SystemMetrics {
        cpu_usage_percent: system.global_cpu_usage(),
        logical_cpu_count: system.cpus().len(),
        memory_total_bytes: system.total_memory(),
        memory_used_bytes: system.used_memory(),
        memory_available_bytes: system.available_memory(),
        uptime_seconds: System::uptime(),
        disks,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recent_metrics_are_cached() {
        let state = MetricsState::default();
        let first = state.collect().unwrap();
        let second = state.collect().unwrap();
        assert_eq!(first.uptime_seconds, second.uptime_seconds);
        assert_eq!(first.logical_cpu_count, second.logical_cpu_count);
    }
}
