import { describe, expect, it } from "vitest";
import { aManeuverOf, aNotice } from "../../test/activity";
import { linkedManeuvers } from "./links";

describe("linkedManeuvers", () => {
  it("gathers each satellite's maneuvers once, newest first", () => {
    const older = aManeuverOf({ id: "older", event_start_time: "2026-11-02T10:00:00Z" });
    const newer = aManeuverOf({ id: "newer", event_start_time: "2026-11-02T12:00:00Z" });
    const timeless = aManeuverOf({ id: "timeless", event_start_time: null });
    const index = new Map([
      ["1", [older, newer]],
      ["2", [newer, timeless]],
    ]);
    const found = linkedManeuvers(aNotice({ sat_ids: ["1", "2", "3"] }), index);
    expect(found.map((m) => m.id)).toEqual(["newer", "older", "timeless"]);
  });

  it("finds none for a notice whose satellites have none", () => {
    expect(linkedManeuvers(aNotice({ sat_ids: [] }), new Map())).toEqual([]);
  });
});
