import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { I18nProvider } from "../i18n/I18n";
import { enrollCapabilityNode, getCapabilityNodeStatus } from "./capabilityNode";
import { FirstRun } from "./FirstRun";
import { controlService } from "./service";

vi.mock("../api/client", () => ({
  api: {
    pairDevice: vi.fn(),
    updateLLM: vi.fn(),
  },
}));
vi.mock("./environment", () => ({ isTauriRuntime: () => true }));
vi.mock("./capabilityNode", () => ({
  enrollCapabilityNode: vi.fn(),
  getCapabilityNodeStatus: vi.fn(),
}));
vi.mock("./service", () => ({ controlService: vi.fn() }));

const mockApi = vi.mocked(api);
const mockEnroll = vi.mocked(enrollCapabilityNode);
const mockStatus = vi.mocked(getCapabilityNodeStatus);
const mockService = vi.mocked(controlService);

beforeEach(() => {
  vi.clearAllMocks();
  mockStatus.mockResolvedValue({ enrolled: false, endpoint: null, device_id: null, node_name: null });
  mockService.mockResolvedValue({
    unit: "dax-assistant-node.service",
    load_state: "loaded",
    active_state: "inactive",
    sub_state: "dead",
    unit_file_state: "disabled",
  });
  mockApi.pairDevice.mockResolvedValue({
    code: "NODE2345",
    expires_in_seconds: 300,
    backend_url: "https://dax.example",
    pairing_uri: "dax://pair",
    kind: "capability_node",
  });
  mockEnroll.mockResolvedValue({
    enrolled: true,
    endpoint: "https://dax.example",
    device_id: "node-1",
    node_name: "work-laptop",
  });
});

afterEach(cleanup);

describe("FirstRun capability-node enrollment", () => {
  it("requires a name and only enables the service after explicit consent", async () => {
    render(
      <I18nProvider initialLocale="en">
        <FirstRun onDone={() => undefined} />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    const enroll = screen.getByRole("button", { name: "Enroll this laptop" });
    expect((enroll as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Node name"), { target: { value: "work-laptop" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /enable and start/i }));
    fireEvent.click(enroll);

    await waitFor(() => expect(mockEnroll).toHaveBeenCalledWith("NODE2345", "work-laptop"));
    expect(mockService).toHaveBeenCalledWith("capability_node", "enable_now");
    expect(await screen.findByText(/service enabled/i)).toBeTruthy();
  });
});
