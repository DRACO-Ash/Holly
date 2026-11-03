// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Stamp } from "./Stamp";

const NOW = Date.parse("2026-11-02T20:00:00Z");

describe("Stamp", () => {
  it("says so when the time is unknown", () => {
    render(<Stamp time={null} now={NOW} />);
    expect(screen.getByText("time unknown").className).toBe("stamp stamp-unknown");
  });

  it("gives the relative time, the UTC stamp and the full time", () => {
    const time = NOW - 3 * 3_600_000;
    const { container } = render(<Stamp time={time} now={NOW} />);
    const stamp = container.querySelector("time");
    expect(stamp?.getAttribute("datetime")).toBe("2026-11-02T17:00:00.000Z");
    expect(stamp?.getAttribute("title")).toBe("2026-11-02 17:00:00Z");
    expect(screen.getByText("3 h ago")).toBeTruthy();
    expect(screen.getByText("02 Nov 17:00Z")).toBeTruthy();
  });

  it("leaves the clock out when asked", () => {
    const { container } = render(<Stamp time={NOW} now={NOW} withClock={false} />);
    expect(container.querySelector(".stamp-clock")).toBeNull();
    expect(screen.getByText("just now")).toBeTruthy();
  });
});
