import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { I18nProvider } from "../i18n/I18n";
import { getCapabilityNodeStatus } from "../native/capabilityNode";
import { CapabilityNodes } from "./CapabilityNodes";

vi.mock("../api/client", () => ({
  api: { nodes: vi.fn(), updateNodePolicy: vi.fn() },
}));
vi.mock("../native/environment", () => ({ isTauriRuntime: () => true }));
vi.mock("../native/capabilityNode", () => ({ getCapabilityNodeStatus: vi.fn() }));

const mockApi = vi.mocked(api);
const mockStatus = vi.mocked(getCapabilityNodeStatus);

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.nodes.mockResolvedValue({ enabled: true, prefer_when_available: false, nodes: [] });
  mockStatus.mockResolvedValue({
    enrolled: true,
    endpoint: "https://dax.example",
    device_id: "node-1",
    node_name: "work-laptop",
  });
});

afterEach(cleanup);

describe("CapabilityNodes local status", () => {
  it("shows the redacted local enrollment alongside the server fleet", async () => {
    render(
      <I18nProvider initialLocale="en">
        <CapabilityNodes />
      </I18nProvider>,
    );
    expect(await screen.findByText("This machine is enrolled as work-laptop.")).toBeTruthy();
    expect(screen.queryByText("node-1")).toBeNull();
  });
});
