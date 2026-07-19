import { describe, expect, it } from "vitest";
import { providerModelField } from "./Chat";

describe("providerModelField", () => {
  it("keeps Codex independent from Ollama", () => {
    expect(providerModelField("codex")).toBe("codex_model");
    expect(providerModelField("ollama")).toBe("ollama_model");
  });
});
