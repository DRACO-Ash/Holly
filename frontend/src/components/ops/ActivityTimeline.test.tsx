// @vitest-environment jsdom
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ActivityTimeline, { type TimelineLane, type TimelineMark } from "./ActivityTimeline";

const HOUR = 3_600_000;
const START = Date.parse("2026-10-31T12:00:00Z");
const END = START + 48 * HOUR;
const NOW = END - HOUR;
// The plot runs from view x 200 to 984; the box below maps one client pixel to one view unit.
const GUTTER = 200;
const PLOT = 784;
const xAt = (fraction: number) => GUTTER + fraction * PLOT;
const timeAt = (fraction: number) => START + fraction * (END - START);

const mark = (id: string, shape: TimelineMark["shape"], extra: Partial<TimelineMark> = {}) => ({
  id,
  time: START + 12 * HOUR,
  tone: "maneuver",
  shape,
  label: `mark ${id}`,
  ...extra,
});

const LANES: TimelineLane[] = [
  {
    key: "a",
    label: "Maneuver",
    tone: "maneuver",
    marks: [
      mark("dot", "dot", { emphasis: true }),
      mark("ring", "ring"),
      mark("diamond", "diamond"),
    ],
  },
  {
    key: "b",
    label: "Other",
    tone: "other",
    marks: [mark("triangle", "triangle"), mark("square", "square"), mark("bar", "bar")],
  },
];

function draw(props: Partial<Parameters<typeof ActivityTimeline>[0]> = {}) {
  const onRange = vi.fn();
  const onPick = vi.fn();
  const view = render(
    <ActivityTimeline
      lanes={LANES}
      start={START}
      end={END}
      now={NOW}
      title="Notices"
      range={null}
      onRange={onRange}
      onPick={onPick}
      {...props}
    />,
  );
  const svg = view.container.querySelector("svg") as SVGSVGElement;
  const brush = view.container.querySelector(".timeline-brush") as SVGRectElement;
  return { ...view, svg, brush, onRange, onPick };
}

function box(svg: SVGSVGElement, width = 1000) {
  vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
    left: 0,
    top: 0,
    width,
    height: 100,
    right: width,
    bottom: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
}

afterEach(() => vi.restoreAllMocks());

describe("ActivityTimeline", () => {
  it("summarises its lanes for assistive technology", () => {
    draw();
    expect(
      screen.getByRole("img", {
        name: "Notices: 6 events in 2 lanes, Maneuver 3, Other 3.",
      }),
    ).toBeTruthy();
  });

  it("labels each lane with its count and marks each UTC day and now", () => {
    const { container } = draw();
    expect(
      [...container.querySelectorAll(".timeline-lane-label")].map((t) => t.textContent),
    ).toEqual(["Maneuver", "Other"]);
    expect(
      [...container.querySelectorAll(".timeline-lane-count")].map((t) => t.textContent),
    ).toEqual(["3", "3"]);
    expect([...container.querySelectorAll(".timeline-day text")].map((t) => t.textContent)).toEqual(
      ["01 Nov", "02 Nov"],
    );
    expect(container.querySelector(".timeline-now text")?.textContent).toBe("now");
    // Each lane's density sits behind its marks: all three marks share one bin.
    expect(container.querySelectorAll(".timeline-density")).toHaveLength(2);
  });

  it("leaves now out once it is past the window", () => {
    const { container } = draw({ now: END + 2 * HOUR });
    expect(container.querySelector(".timeline-now")).toBeNull();
  });

  it("draws every shape, emphasis larger, each with its tooltip", () => {
    const { container } = draw();
    const byShape = (shape: string) => container.querySelector(`.mark-${shape}`) as Element;
    expect(byShape("dot").tagName).toBe("circle");
    expect(byShape("dot").getAttribute("r")).toBe("7");
    expect(byShape("dot").getAttribute("class")).toContain("mark-emphasis");
    expect(byShape("ring").tagName).toBe("circle");
    expect(byShape("ring").getAttribute("r")).toBe("5");
    expect(byShape("diamond").tagName).toBe("polygon");
    expect(byShape("triangle").tagName).toBe("polygon");
    expect(byShape("square").tagName).toBe("rect");
    expect(byShape("bar").tagName).toBe("rect");
    expect(byShape("bar").getAttribute("width")).toBe("10");
    expect(byShape("bar").getAttribute("height")).toBe("5");
    expect(byShape("diamond").querySelector("title")?.textContent).toBe("mark diamond");
    // The mark sits at its time: half a day into a two-day window.
    expect(Number(byShape("dot").getAttribute("cx"))).toBeCloseTo(xAt(0.25));
  });

  it("picks a mark by click, without starting a drag", () => {
    const { container, svg, brush, onPick, onRange } = draw();
    box(svg);
    const dot = container.querySelector(".mark-dot") as Element;
    expect(dot.getAttribute("class")).toContain("mark-pickable");
    fireEvent.pointerDown(dot, { clientX: 300 });
    fireEvent.pointerUp(brush, { clientX: 600 });
    fireEvent.click(dot);
    expect(onPick).toHaveBeenCalledWith("dot");
    expect(onRange).not.toHaveBeenCalled();
  });

  it("does not offer picking without a handler", () => {
    const { container } = draw({ onPick: undefined });
    expect(container.querySelector(".mark-dot")?.getAttribute("class")).not.toContain(
      "mark-pickable",
    );
  });

  it("picks a range by dragging, showing it while dragging, in either direction", () => {
    const { container, svg, brush, onRange } = draw();
    box(svg);
    fireEvent.pointerMove(brush, { clientX: 500 });
    expect(container.querySelector(".timeline-range")).toBeNull();
    fireEvent.pointerDown(brush, { clientX: xAt(0.5) });
    fireEvent.pointerMove(brush, { clientX: xAt(0.25) });
    const shown = container.querySelector(".timeline-range") as Element;
    expect(Number(shown.getAttribute("x"))).toBeCloseTo(xAt(0.25));
    expect(Number(shown.getAttribute("width"))).toBeCloseTo(PLOT / 4);
    fireEvent.pointerUp(brush, { clientX: xAt(0.25) });
    const [[range]] = onRange.mock.calls as [[readonly [number, number]]];
    expect(range[0]).toBeCloseTo(timeAt(0.25), -3);
    expect(range[1]).toBeCloseTo(timeAt(0.5), -3);
    expect(container.querySelector(".timeline-range")).toBeNull();
  });

  it("clamps a drag to the plot", () => {
    const { svg, brush, onRange } = draw();
    box(svg);
    fireEvent.pointerDown(brush, { clientX: 10 });
    fireEvent.pointerMove(brush, { clientX: 2000 });
    fireEvent.pointerUp(brush);
    expect(onRange).toHaveBeenCalledWith([START, END]);
  });

  it("clears the range on a click, and forgets a cancelled drag", () => {
    const { container, svg, brush, onRange } = draw({ range: [START, START + HOUR] });
    expect(container.querySelector(".timeline-range")).toBeTruthy();
    box(svg);
    fireEvent.pointerDown(brush, { clientX: 400 });
    fireEvent.pointerUp(brush, { clientX: 403 });
    expect(onRange).toHaveBeenCalledWith(null);
    fireEvent.pointerDown(brush, { clientX: 400 });
    fireEvent.pointerCancel(brush);
    fireEvent.pointerUp(brush, { clientX: 700 });
    expect(onRange).toHaveBeenCalledTimes(1);
  });

  it("reads a box it cannot measure as a click", () => {
    const { svg, brush, onRange } = draw();
    box(svg, 0);
    fireEvent.pointerDown(brush, { clientX: 300 });
    fireEvent.pointerUp(brush, { clientX: 700 });
    expect(onRange).toHaveBeenCalledWith(null);
  });

  it("draws an empty window without lanes", () => {
    const { container } = draw({ lanes: [], start: START, end: START });
    expect(container.querySelectorAll(".timeline-lane")).toHaveLength(0);
    expect(screen.getByRole("img", { name: "Notices: 0 events in 0 lanes, ." })).toBeTruthy();
  });

  describe("drawn at its measured width", () => {
    let observed: ((entries: { contentRect: { width: number } }[]) => void) | null = null;
    const disconnect = vi.fn();
    class FakeObserver {
      constructor(callback: (entries: { contentRect: { width: number } }[]) => void) {
        observed = callback;
      }
      observe() {}
      disconnect() {
        disconnect();
      }
    }
    const measure = (width: number) => act(() => observed?.([{ contentRect: { width } }]));

    beforeEach(() => {
      observed = null;
      disconnect.mockReset();
      vi.stubGlobal("ResizeObserver", FakeObserver);
    });
    afterEach(() => vi.unstubAllGlobals());

    it("narrows its gutter on a phone and maps a drag at that width", () => {
      const { container, svg, brush, onRange } = draw();
      measure(500);
      expect(svg.getAttribute("viewBox")).toMatch(/^0 0 500 /);
      const lane = container.querySelector(".timeline-lane-bg") as SVGRectElement;
      // 500 wide, a 110 gutter and 16 on the right leave 374 for the plot.
      expect([lane.getAttribute("x"), lane.getAttribute("width")]).toEqual(["110", "374"]);
      box(svg, 500);
      fireEvent.pointerDown(brush, { clientX: 110 + 374 * 0.25, pointerId: 1 });
      fireEvent.pointerMove(brush, { clientX: 110 + 374 * 0.5, pointerId: 1 });
      fireEvent.pointerUp(brush, { clientX: 110 + 374 * 0.5, pointerId: 1 });
      const [range] = onRange.mock.calls[0] as [[number, number]];
      expect(range[0]).toBeCloseTo(timeAt(0.25), -3);
      expect(range[1]).toBeCloseTo(timeAt(0.5), -3);
    });

    it("cuts a lane's name to fit, its whole name on hover, and leaves a short one alone", () => {
      const long = "A very long lane name indeed";
      const { container } = draw({
        lanes: [
          { key: "l", label: long, tone: "other", marks: [] },
          { key: "s", label: "Short", tone: "other", marks: [] },
        ],
      });
      measure(400);
      const [first, second] = [...container.querySelectorAll(".timeline-lane-label")];
      expect(first.textContent).toMatch(/…$/);
      expect(first.textContent?.length).toBeLessThan(long.length);
      expect(first.parentElement?.querySelector("title")?.textContent).toBe(long);
      expect(second.textContent).toBe("Short");
      expect(second.parentElement?.querySelector("title")).toBeNull();
    });

    it("keeps its width when measured at nothing, and stops measuring when it goes", () => {
      const { svg, unmount } = draw();
      measure(0);
      expect(svg.getAttribute("viewBox")).toMatch(/^0 0 1000 /);
      unmount();
      expect(disconnect).toHaveBeenCalledTimes(1);
    });
  });

  it("draws the marks of a lane of more than 80 smaller, so its density shows", () => {
    const many = (count: number, key: string): TimelineLane => ({
      key,
      label: key,
      tone: "maneuver",
      marks: Array.from({ length: count }, (_, i) => mark(`${key}-${i}`, "dot")),
    });
    const { container } = draw({ lanes: [many(81, "dense"), many(80, "sparse")] });
    const dense = container.querySelectorAll("circle")[0];
    const sparse = container.querySelectorAll("circle")[81];
    expect(dense.getAttribute("r")).toBe("3");
    expect(sparse.getAttribute("r")).toBe("5");
  });

  it("starts a drag on a mark that is not picked, as on the plot", () => {
    const { svg, onRange, container } = draw({ onPick: undefined });
    box(svg);
    const markOnPlot = container.querySelector("circle") as SVGCircleElement;
    fireEvent.pointerDown(markOnPlot, { clientX: GUTTER + PLOT * 0.25, pointerId: 1 });
    fireEvent.pointerMove(markOnPlot, { clientX: GUTTER + PLOT * 0.5, pointerId: 1 });
    fireEvent.pointerUp(markOnPlot, { clientX: GUTTER + PLOT * 0.5, pointerId: 1 });
    expect(onRange).toHaveBeenCalledTimes(1);
    expect(onRange.mock.calls[0][0]).not.toBeNull();
  });
});
