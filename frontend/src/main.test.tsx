// @vitest-environment jsdom
import { act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({ default: () => <p>The app</p> }));

describe("the entry point", () => {
  it("mounts the app into the page's root element", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    await act(async () => {
      await import("./main");
    });
    expect(document.getElementById("root")?.textContent).toBe("The app");
  });
});
