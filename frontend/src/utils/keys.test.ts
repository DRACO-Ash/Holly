import { describe, expect, it } from "vitest";
import { withContentKeys } from "./keys";

describe("withContentKeys", () => {
  it("keys each item by its content, in order", () => {
    expect(withContentKeys(["a", "b"], (s) => s)).toEqual([
      { key: "a", item: "a" },
      { key: "b", item: "b" },
    ]);
  });

  it("gives a repeated item its occurrence, so no two keys match", () => {
    const keys = withContentKeys(["a", "b", "a", "a"], (s) => s).map((k) => k.key);
    expect(keys).toEqual(["a", "b", "a#2", "a#3"]);
  });

  it("never issues a key twice, even where content looks like a suffixed key", () => {
    const keys = withContentKeys(["a", "a", "a#2", "a#2"], (s) => s).map((k) => k.key);
    expect(keys).toEqual(["a", "a#2", "a#2#2", "a#2#3"]);
  });

  it("returns nothing for an empty list", () => {
    expect(withContentKeys([], String)).toEqual([]);
  });
});
