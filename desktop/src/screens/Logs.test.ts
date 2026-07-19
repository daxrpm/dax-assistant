import { describe, expect, it } from "vitest";
import { calculateVirtualWindow, ROW_HEIGHT } from "./Logs";

describe("calculateVirtualWindow", () => {
  it("uses the 22px CSS row height and symmetric overscan", () => {
    expect(ROW_HEIGHT).toBe(22);
    expect(calculateVirtualWindow(100, 440, 44)).toEqual({ first: 8, last: 34 });
  });

  it("clamps the virtual window at both ends", () => {
    expect(calculateVirtualWindow(10, -50, 44)).toEqual({ first: 0, last: 10 });
    expect(calculateVirtualWindow(100, 2178, 44)).toEqual({ first: 87, last: 100 });
  });
});
