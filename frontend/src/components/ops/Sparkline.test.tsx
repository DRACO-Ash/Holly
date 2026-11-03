// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("draws a bar per busy bin, the busiest full height, hidden from assistive technology", () => {
    const { container } = render(<Sparkline times={[1, 2, 2, 9]} start={0} end={10} bins={5} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.getAttribute("class")).toBe("sparkline tone-accent");
    const bars = [...container.querySelectorAll(".sparkline-bar")];
    // Bins of 2: one time in the first, two in the second, one in the last.
    expect(bars.map((b) => b.getAttribute("height"))).toEqual(["11", "22", "11"]);
    expect(bars.map((b) => b.getAttribute("x"))).toEqual(["0.5", "24.5", "96.5"]);
  });

  it("draws only the baseline with no activity, in the tone asked for", () => {
    const { container } = render(<Sparkline times={[]} start={0} end={10} tone="maneuver" />);
    expect(container.querySelectorAll(".sparkline-bar")).toHaveLength(0);
    expect(container.querySelector(".sparkline-base")).toBeTruthy();
    expect(container.querySelector("svg")?.getAttribute("class")).toBe("sparkline tone-maneuver");
  });
});
