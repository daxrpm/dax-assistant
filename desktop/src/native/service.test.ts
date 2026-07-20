import { beforeEach, describe, expect, it, vi } from "vitest";

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke }));

import { controlService } from "./service";

describe("native service bridge", () => {
  beforeEach(() => invoke.mockReset());

  it("selects the backend through the closed target contract", async () => {
    invoke.mockResolvedValue({ unit: "dax-assistant.service" });
    await controlService("backend", "status");
    expect(invoke).toHaveBeenCalledWith("service_control", {
      target: "backend",
      action: "status",
    });
  });

  it("selects the capability node without accepting a unit name", async () => {
    invoke.mockResolvedValue({ unit: "dax-assistant-node.service" });
    await controlService("capability_node", "restart");
    expect(invoke).toHaveBeenCalledWith("service_control", {
      target: "capability_node",
      action: "restart",
    });
  });

  it("exposes the fixed enable-now operation", async () => {
    invoke.mockResolvedValue({ unit: "dax-assistant-node.service" });
    await controlService("capability_node", "enable_now");
    expect(invoke).toHaveBeenCalledWith("service_control", {
      target: "capability_node",
      action: "enable_now",
    });
  });
});
