import { beforeEach, describe, expect, it, vi } from "vitest";

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke }));

import { replaceNativeAuthorityConfirmed } from "./backend";

describe("native backend bridge", () => {
  beforeEach(() => invoke.mockReset());

  it("uses the fixed confirmed authority replacement command without identity input", async () => {
    invoke.mockResolvedValue({ active_server_id: null });
    await replaceNativeAuthorityConfirmed();
    expect(invoke).toHaveBeenCalledWith("backend_authority_replace_confirmed");
  });
});
