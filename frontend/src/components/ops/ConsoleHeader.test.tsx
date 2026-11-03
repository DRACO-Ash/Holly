// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConsoleHeader from "./ConsoleHeader";

const NOW = Date.parse("2026-11-02T20:00:00Z");

describe("ConsoleHeader", () => {
  it("says it is connecting before the first load, with no intro or actions", () => {
    const { container } = render(
      <ConsoleHeader title="Maneuvers" eyebrow="Ops" loadedAt={null} refreshing now={NOW} />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Maneuvers" })).toBeTruthy();
    expect(screen.getByText("Ops").className).toBe("console-eyebrow");
    expect(container.querySelector(".console-live")?.textContent).toBe("Connecting...");
    expect(container.querySelector(".live-dot")?.className).toBe("live-dot live-busy");
    expect(container.querySelector(".console-intro")).toBeNull();
    expect(container.querySelector(".console-actions")).toBeNull();
  });

  it("says how fresh it is, whether it is refreshing, and shows the intro and actions", () => {
    const { container, rerender } = render(
      <ConsoleHeader
        title="Notifications"
        eyebrow="Ops"
        loadedAt={NOW - 2 * 60_000}
        refreshing={false}
        now={NOW}
        actions={<button type="button">Pull</button>}
      >
        The window.
      </ConsoleHeader>,
    );
    expect(container.querySelector(".console-live")?.textContent).toBe("Live · updated 2 min ago");
    expect(container.querySelector(".live-dot")?.className).toBe("live-dot");
    expect(screen.getByText("The window.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Pull" })).toBeTruthy();
    // A load after the clock last moved reads as just now, never in the future.
    rerender(
      <ConsoleHeader title="N" eyebrow="Ops" loadedAt={NOW + 90_000} refreshing now={NOW} />,
    );
    expect(container.querySelector(".console-live")?.textContent).toBe(
      "Live · updated just now · refreshing",
    );
  });
});
