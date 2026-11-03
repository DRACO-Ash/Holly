import { describe, expect, it } from "vitest";
import { aManeuverOf, aNotice } from "../../test/activity";
import type { ActivityNotice } from "../../types";
import { foldDuplicates, parseEventClass } from "../../utils/ops";
import { maneuverLanes, noticeLanesByKind, noticeLanesByUrgency, noticeTitle } from "./lanes";

const parsedOf = (n: ActivityNotice) => parseEventClass(n.event_class);

describe("noticeTitle", () => {
  it("names the objects, or falls back to the class, the notice and a word", () => {
    const rpo = aNotice({ event_class: "RPO / TEST-A (1) vs TEST-B / LEO" });
    expect(noticeTitle(rpo, parsedOf(rpo))).toBe("TEST-A (1) vs TEST-B");
    expect(noticeTitle(aNotice({ event_class: "Launch" }), parseEventClass("Launch"))).toBe(
      "Launch",
    );
    expect(noticeTitle(aNotice({ event_class: null, notice: "N-1" }), null)).toBe("N-1");
    expect(noticeTitle(aNotice({ event_class: null, notice: null }), null)).toBe("Notice");
  });
});

describe("noticeLanesByKind", () => {
  it("makes a lane per kind present, in the kinds' order, skipping timeless notices", () => {
    const lanes = noticeLanesByKind(
      [
        aNotice({ id: "p", event_class: "Photometric change / TEST (1)" }),
        aNotice({ id: "m", event_class: "Maneuver / TEST (2) / GEO", urgency: "high" }),
        aNotice({ id: "x", event_class: null }),
        aNotice({ id: "t", udl_created_at: null }),
      ],
      parsedOf,
    );
    expect(lanes.map((l) => [l.key, l.label, l.marks.map((m) => m.id)])).toEqual([
      ["maneuver", "Maneuver", ["m"]],
      ["photometric", "Photometric change", ["p"]],
      ["other", "Other", ["x"]],
    ]);
    const [mark] = lanes[0].marks;
    expect(mark).toMatchObject({ shape: "dot", tone: "maneuver", emphasis: true });
    expect(mark.label).toBe("Maneuver: TEST (2), 02 Nov 18:00Z");
    expect(lanes[1].marks[0]).toMatchObject({ shape: "square", emphasis: false });
    expect(lanes[2].marks[0]).toMatchObject({ shape: "bar", tone: "other" });
    expect(lanes[2].marks[0].label.startsWith("Other: ")).toBe(true);
  });
});

describe("noticeLanesByUrgency", () => {
  it("makes a lane per urgency present, most urgent first", () => {
    const lanes = noticeLanesByUrgency(
      [
        aNotice({ id: "a", urgency: "low" }),
        aNotice({ id: "b", urgency: "HIGH" }),
        aNotice({ id: "c", urgency: "severe" }),
        aNotice({ id: "d", urgency: "pending", udl_created_at: null }),
      ],
      parsedOf,
    );
    expect(lanes.map((l) => [l.key, l.label, l.tone, l.marks.map((m) => m.id)])).toEqual([
      ["high", "High", "high", ["b"]],
      ["low", "Low", "low", ["a"]],
      ["none", "Info only", "none", ["c"]],
    ]);
    // Each mark keeps its kind's hue.
    expect(lanes[0].marks[0].tone).toBe("maneuver");
  });
});

describe("maneuverLanes", () => {
  it("makes a lane per source, alphabetically, in its slot's hue, skipping timeless ones", () => {
    const groups = foldDuplicates([
      aManeuverOf({ id: "z", source: "ZED", sat_no: 5 }),
      aManeuverOf({ id: "a", source: "ALPHA" }),
      aManeuverOf({ id: "u", source: null }),
      aManeuverOf({ id: "t", source: "ALPHA", event_start_time: null }),
    ]);
    const slots = new Map([
      ["ALPHA", 1],
      ["ZED", 2],
    ]);
    const lanes = maneuverLanes(groups, slots, (n) => `SAT ${n}`);
    expect(lanes.map((l) => [l.key, l.tone, l.marks.map((m) => m.id)])).toEqual([
      ["ALPHA", "source-1", ["a"]],
      ["Unknown", "source-4", ["u"]],
      ["ZED", "source-2", ["z"]],
    ]);
    expect(lanes[2].marks[0]).toMatchObject({
      tone: "source-2",
      shape: "dot",
      label: "SAT 5, ZED, 02 Nov 17:00Z",
    });
  });
});
