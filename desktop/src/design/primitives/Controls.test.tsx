import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Tabs } from "./Controls";

function TabsHarness() {
  const [value, setValue] = useState("one");
  return (
    <Tabs
      items={[
        { id: "one", label: "One", panelId: "panel-one" },
        { id: "two", label: "Two", panelId: "panel-two" },
        { id: "three", label: "Three", panelId: "panel-three" },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

describe("Tabs", () => {
  it("uses roving tabindex and supports arrow, Home, and End navigation", () => {
    render(<TabsHarness />);
    const tabs = screen.getAllByRole("tab");
    tabs[0]?.focus();

    fireEvent.keyDown(tabs[0]!, { key: "ArrowRight" });
    expect(document.activeElement).toBe(tabs[1]);
    expect(tabs[1]?.getAttribute("aria-selected")).toBe("true");
    expect(tabs[1]?.getAttribute("tabindex")).toBe("0");
    expect(tabs[1]?.getAttribute("aria-controls")).toBe("panel-two");

    fireEvent.keyDown(tabs[1]!, { key: "End" });
    expect(document.activeElement).toBe(tabs[2]);
    fireEvent.keyDown(tabs[2]!, { key: "Home" });
    expect(document.activeElement).toBe(tabs[0]);
  });
});
