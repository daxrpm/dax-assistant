use serde::Serialize;
use sysinfo::{Disks, System, MINIMUM_CPU_UPDATE_INTERVAL};

#[derive(Debug, Serialize)]
pub struct DiskMetrics {
    pub name: String,
    pub mount_point: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
    pub removable: bool,
}

#[derive(Debug, Serialize)]
pub struct SystemMetrics {
    pub cpu_usage_percent: f32,
    pub logical_cpu_count: usize,
    pub memory_total_bytes: u64,
    pub memory_used_bytes: u64,
    pub memory_available_bytes: u64,
    pub uptime_seconds: u64,
    pub disks: Vec<DiskMetrics>,
}

pub fn collect() -> SystemMetrics {
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
