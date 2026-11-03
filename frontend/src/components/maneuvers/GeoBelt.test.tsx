// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { aManeuverOf } from "../../test/activity";
import { foldDuplicates } from "../../utils/ops";
import GeoBelt, { type BeltMark } from "./GeoBelt";

const mark = (longitude: number, source: string, slot: number, drift: number | null = null) => {
  const [group] = foldDuplicates([aManeuverOf({ source })]);
  return { group, longitude, drift, slot, source, label: `${source} ${longitude}` } as BeltMark;
};
const cx = (container: HTMLElement, index: number) =>
  Number(container.querySelectorAll("circle")[index].getAttribute("cx"));
const cy = (container: HTMLElement, index: number) =>
  Number(container.querySelectorAll("circle")[index].getAttribute("cy"));

describe("GeoBelt", () => {
  it("names each provider beside its colour, once", () => {
    render(
      <GeoBelt
        marks={[mark(10, "B-PROVIDER", 2), mark(20, "A-PROVIDER", 1), mark(30, "A-PROVIDER", 1)]}
      />,
    );
    const legend = screen.getByRole("list", { name: "Providers" });
    expect([...legend.querySelectorAll("li")].map((li) => li.textContent)).toEqual([
      "A-PROVIDER",
      "B-PROVIDER",
    ]);
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe(
      "GEO belt: 3 maneuvers by longitude after the burn.",
    );
  });

  it("reads a longitude east of Greenwich past 180 as west", () => {
    const { container } = render(<GeoBelt marks={[mark(350, "P", 1), mark(-10, "P", 1)]} />);
    expect(cx(container, 0)).toBeCloseTo(cx(container, 1));
  });

  it("stacks marks that would overlap, and keeps apart ones on the axis row", () => {
    const { container } = render(
      <GeoBelt marks={[mark(0, "P", 1), mark(0.5, "P", 1), mark(90, "P", 1)]} />,
    );
    expect(cy(container, 0)).not.toBe(cy(container, 1));
    expect(cy(container, 2)).toBe(cy(container, 0));
  });

  it("draws a drift line only when the record gives a drift, capped in length", () => {
    const { container } = render(
      <GeoBelt marks={[mark(0, "P", 1, 5), mark(90, "P", 1, null), mark(-90, "P", 1, -0.01)]} />,
    );
    const lines = [...container.querySelectorAll(".geo-belt-drift")];
    expect(lines).toHaveLength(2);
    const reach = (line: Element) =>
      Number(line.getAttribute("x2")) - Number(line.getAttribute("x1"));
    expect(reach(lines[0])).toBe(60);
    expect(reach(lines[1])).toBeCloseTo(-3);
  });

  it("stacks a column three high, the fourth mark on the lowest row", () => {
    const { container } = render(
      <GeoBelt
        marks={[mark(0, "P", 1), mark(0.1, "P", 1), mark(0.2, "P", 1), mark(0.3, "P", 1)]}
      />,
    );
    const rows = [0, 1, 2, 3].map((index) => cy(container, index));
    expect(new Set(rows.slice(0, 3)).size).toBe(3);
    expect(rows[3]).toBe(rows[0]);
  });

  it("puts each tick at its own longitude, 180°W at the left end and 180°E at the right", () => {
    const { container } = render(<GeoBelt marks={[mark(0, "P", 1)]} />);
    const ticks = [...container.querySelectorAll(".geo-belt-tick text")];
    const at = (label: string) =>
      Number(ticks.find((t) => t.textContent === label)?.getAttribute("x"));
    expect(at("180°W")).toBeLessThan(at("0°"));
    expect(at("180°E")).toBeGreaterThan(at("120°E"));
    expect(new Set(ticks.map((t) => t.getAttribute("x"))).size).toBe(ticks.length);
  });
});
