import { describe, expect, it } from "vitest";
import { inRange, resolveRange, toggled } from "./consoleFilters";

const HOUR = 3_600_000;

describe("toggled", () => {
  it("adds a value that is absent and removes one that is present, leaving the input alone", () => {
    const start = new Set(["a"]);
    expect([...toggled(start, "b")]).toEqual(["a", "b"]);
    expect([...toggled(start, "a")]).toEqual([]);
    expect([...start]).toEqual(["a"]);
  });
});

describe("resolveRange", () => {
  it("resolves the whole window, a preset and a dragged range", () => {
    expect(resolveRange(null, 10 * HOUR)).toBeNull();
    expect(resolveRange({ hours: 6 }, 10 * HOUR)).toEqual([4 * HOUR, 10 * HOUR]);
    expect(resolveRange({ from: 1, to: 2 }, 10 * HOUR)).toEqual([1, 2]);
  });
});

describe("inRange", () => {
  it("lets everything through with no range, and only times inside one", () => {
    expect(inRange(null, null)).toBe(true);
    expect(inRange(5, [1, 10])).toBe(true);
    expect(inRange(1, [1, 10])).toBe(true);
    expect(inRange(10, [1, 10])).toBe(true);
    expect(inRange(11, [1, 10])).toBe(false);
    expect(inRange(0, [1, 10])).toBe(false);
    expect(inRange(null, [1, 10])).toBe(false);
  });
});
