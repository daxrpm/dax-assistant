import { describe, expect, it, vi } from "vitest";
import { createDisconnectMonitor } from "./notifications";

describe("backend disconnect notifications", () => {
  it("notifies once after persistent failures and rearms after recovery", async () => {
    const probe = vi.fn().mockRejectedValue(new Error("offline"));
    const notify = vi.fn(async () => undefined);
    const onDisconnected = vi.fn(async () => undefined);
    const monitor = createDisconnectMonitor({ probe, notify, onDisconnected, threshold: 3 });

    await monitor.check();
    await monitor.check();
    expect(notify).not.toHaveBeenCalled();
    await monitor.check();
    await monitor.check();
    expect(notify).toHaveBeenCalledTimes(1);
    expect(onDisconnected).toHaveBeenCalledTimes(1);

    probe.mockResolvedValueOnce(undefined);
    await monitor.check();
    probe.mockRejectedValue(new Error("offline again"));
    await monitor.check();
    await monitor.check();
    await monitor.check();
    expect(notify).toHaveBeenCalledTimes(2);
    expect(onDisconnected).toHaveBeenCalledTimes(2);
  });
});
