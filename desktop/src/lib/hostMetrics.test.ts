import { describe, expect, it } from "vitest";
import { isLoopbackBackend, normalizeNativeMetrics } from "./hostMetrics";

describe("host metrics", () => {
  it("normalizes native percentages and selects the root disk", () => {
    expect(
      normalizeNativeMetrics({
        cpu_usage_percent: 25,
        logical_cpu_count: 8,
        memory_total_bytes: 1000,
        memory_used_bytes: 400,
        memory_available_bytes: 600,
        uptime_seconds: 90,
        disks: [
          {
            name: "data",
            mount_point: "/data",
            total_bytes: 100,
            available_bytes: 10,
            removable: false,
          },
          {
            name: "root",
            mount_point: "/",
            total_bytes: 200,
            available_bytes: 50,
            removable: false,
          },
        ],
      }),
    ).toEqual({ cpu: 0.25, memory: 0.4, disk: 0.75, uptimeSeconds: 90 });
  });

  it("recognizes loopback backends", () => {
    expect(isLoopbackBackend("http://127.0.0.1:8420")).toBe(true);
    expect(isLoopbackBackend("http://[::1]:8420")).toBe(true);
    expect(isLoopbackBackend("https://dax.example.com")).toBe(false);
  });
});
