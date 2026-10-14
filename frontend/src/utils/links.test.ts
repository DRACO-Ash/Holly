import { describe, expect, it } from "vitest";
import { NEW_TAB_REL, safeHttpUrl } from "./links";

describe("safeHttpUrl", () => {
  it.each([
    ["https://notso.example/notso/1", "https://notso.example/notso/1"],
    ["http://images.example/a.png", "http://images.example/a.png"],
    ["HTTPS://NOTSO.EXAMPLE/X", "https://notso.example/X"],
  ])("keeps an absolute web link: %s", (value, expected) => {
    expect(safeHttpUrl(value)).toBe(expected);
  });

  it.each([
    "javascript:alert(1)",
    " javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/hosts",
    "/relative/path",
    "not a url",
    "",
  ])("refuses anything else: %s", (value) => {
    expect(safeHttpUrl(value)).toBeNull();
  });

  it("treats a missing value as no link", () => {
    expect(safeHttpUrl(null)).toBeNull();
    expect(safeHttpUrl(undefined)).toBeNull();
  });

  it("opens new tabs without a window reference or a referrer", () => {
    expect(NEW_TAB_REL).toBe("noopener noreferrer");
  });
});
