import { describe, expect, it } from "vitest";
import {
  DEFAULT_DISPLAY,
  DISPLAY_STORAGE_KEY,
  loadDisplayPrefs,
  saveDisplayPrefs,
} from "./displayPrefs";

function memoryStore(initial?: string) {
  const items = new Map<string, string>();
  if (initial !== undefined) items.set(DISPLAY_STORAGE_KEY, initial);
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => {
      items.set(key, value);
    },
  };
}

const brokenStore = {
  getItem: () => {
    throw new Error("storage is blocked");
  },
  setItem: () => {
    throw new Error("storage is full");
  },
};

describe("loadDisplayPrefs", () => {
  it("starts with scanlines on, flicker off and links on", () => {
    expect(DEFAULT_DISPLAY).toEqual({ scanlines: true, flicker: false, links: true });
    expect(loadDisplayPrefs(memoryStore())).toEqual(DEFAULT_DISPLAY);
  });

  it("reads a saved choice", () => {
    expect(
      loadDisplayPrefs(memoryStore('{"scanlines":false,"flicker":true,"links":false}')),
    ).toEqual({ scanlines: false, flicker: true, links: false });
  });

  it.each([
    ["text that is not JSON", "not json"],
    ["JSON that is not an object", "[true]"],
    ["null", "null"],
    ["a number", "7"],
  ])("falls back to the defaults for %s", (_label, raw) => {
    expect(loadDisplayPrefs(memoryStore(raw))).toEqual(DEFAULT_DISPLAY);
  });

  it("keeps the default for a field that is not a boolean", () => {
    expect(loadDisplayPrefs(memoryStore('{"scanlines":"no","flicker":true,"links":1}'))).toEqual({
      scanlines: true,
      flicker: true,
      links: true,
    });
  });

  it("falls back to the defaults when the store throws or is missing", () => {
    expect(loadDisplayPrefs(brokenStore)).toEqual(DEFAULT_DISPLAY);
    expect(loadDisplayPrefs(undefined)).toEqual(DEFAULT_DISPLAY);
  });

  it("hands back a copy, so a caller cannot change the defaults", () => {
    const prefs = loadDisplayPrefs(memoryStore());
    prefs.scanlines = false;
    expect(DEFAULT_DISPLAY.scanlines).toBe(true);
  });
});

describe("saveDisplayPrefs", () => {
  it("writes only the three known fields, which load back", () => {
    const store = memoryStore();
    const extra = { scanlines: false, flicker: true, links: false, other: "x" };
    saveDisplayPrefs(extra, store);
    expect(store.items.get(DISPLAY_STORAGE_KEY)).toBe(
      '{"scanlines":false,"flicker":true,"links":false}',
    );
    expect(loadDisplayPrefs(store)).toEqual({ scanlines: false, flicker: true, links: false });
  });

  it("ignores a store that throws or is missing", () => {
    expect(() => saveDisplayPrefs(DEFAULT_DISPLAY, brokenStore)).not.toThrow();
    expect(() => saveDisplayPrefs(DEFAULT_DISPLAY, undefined)).not.toThrow();
  });
});
