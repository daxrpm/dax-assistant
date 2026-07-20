import { beforeEach, describe, expect, it, vi } from "vitest";

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke }));

import { enrollCapabilityNode, getCapabilityNodeStatus } from "./capabilityNode";

describe("native capability-node bridge", () => {
  beforeEach(() => invoke.mockReset());

  it("passes only the one-time code and node name to the narrow command", async () => {
    invoke.mockResolvedValue({ enrolled: true });
    await enrollCapabilityNode("CODE1234", "work-laptop");
    expect(invoke).toHaveBeenCalledWith("capability_node_enroll", {
      code: "CODE1234",
      nodeName: "work-laptop",
    });
  });

  it("reads redacted local enrollment status", async () => {
    invoke.mockResolvedValue({ enrolled: false });
    await getCapabilityNodeStatus();
    expect(invoke).toHaveBeenCalledWith("capability_node_status");
  });
});
