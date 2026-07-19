import { describe, expect, it } from "vitest";
import { searchFields, searchGroups, sectionsForLocale, type GroupSpec } from "./registry";
import { buildGroupBodies } from "./useSettingsDraft";

describe("settings registry search", () => {
  it("searches Spanish labels without requiring accents", () => {
    const keys = searchFields("duracion sesion voz").map((hit) => hit.field.key);
    expect(keys).toContain("voice.session_ttl_minutes");
  });

  it("searches technical config keys", () => {
    const hits = searchFields("max_tool_iterations");
    expect(hits).toHaveLength(1);
    expect(hits[0]?.group.id).toBe("int-enrutado");
  });

  it("finds custom groups without declarative fields", () => {
    expect(searchGroups("perfil de voz").some((hit) => hit.group.id === "voz-perfil")).toBe(true);
  });

  it("searches the localized English registry by stable field keys", () => {
    const english = sectionsForLocale("en");
    const hits = searchFields("voice session lifetime", english);
    expect(hits.map((hit) => hit.field.key)).toContain("voice.session_ttl_minutes");
    expect(english.find((section) => section.id === "sistema")?.title).toBe("System");
  });
});

describe("settings group drafts", () => {
  it("builds one nested PATCH body per API section", () => {
    const group: GroupSpec = {
      id: "policy",
      title: "Policy",
      fields: [
        { key: "tools.policy.ask", api: "tools", path: "policy.ask", label: "Ask", control: "lines" },
        { key: "tools.policy.deny", api: "tools", path: "policy.deny", label: "Deny", control: "lines" },
      ],
    };
    const bodies = buildGroupBodies(
      group,
      (field) => field.path === "policy.ask",
      () => ["filesystem.delete"],
    );
    expect(Object.fromEntries(bodies)).toEqual({
      tools: { policy: { ask: ["filesystem.delete"] } },
    });
  });
});
