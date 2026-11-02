import { describe, expect, it } from "vitest";
import { aManeuverOf, anElset, aNotice } from "../test/activity";
import {
  bySatellite,
  clockSecondsUtc,
  clockUtc,
  dayHeading,
  deltaVMetresPerSecond,
  duration,
  eventKind,
  eventObject,
  foldDuplicates,
  fullUtc,
  groupByDay,
  histogram,
  maneuverEnd,
  maneuverSatIds,
  mostActive,
  noticeSatIds,
  parseEventClass,
  regimeFromElset,
  relativeTime,
  satelliteDirectory,
  searchText,
  sourceSlots,
  stampUtc,
  timeOf,
  urgencyOf,
} from "./ops";

const NOW = Date.parse("2026-11-02T20:00:00Z");

describe("parseEventClass", () => {
  it("reads the kind, the object and its number, and the regime", () => {
    expect(parseEventClass("Maneuver / TEST-SAT 3B (90062) / GEO")).toEqual({
      kind: "maneuver",
      kindLabel: "Maneuver",
      objects: [{ name: "TEST-SAT 3B", id: "90062" }],
      regime: "GEO",
    });
  });

  it("takes a notice without a regime, and spaces inside the brackets or around a slash", () => {
    expect(parseEventClass("Photometric change / TEST-SAT ( 90157)")).toMatchObject({
      kind: "photometric",
      objects: [{ name: "TEST-SAT", id: "90157" }],
      regime: null,
    });
    expect(parseEventClass("Maneuver / TEST-SAT (90524) /GEO")?.regime).toBe("GEO");
  });

  it("splits two objects on vs", () => {
    expect(parseEventClass("RPO / TEST-A (90762) vs TEST-B (90103) / LEO")?.objects).toEqual([
      { name: "TEST-A", id: "90762" },
      { name: "TEST-B", id: "90103" },
    ]);
  });

  it("keeps a part that fits no pattern as a name, and gives null for nothing", () => {
    expect(parseEventClass("Something / odd text (12a)")).toMatchObject({
      kind: "other",
      objects: [{ name: "odd text (12a)", id: null }],
    });
    expect(parseEventClass("Launch")).toMatchObject({ kind: "launch", objects: [] });
    expect(parseEventClass(null)).toBeNull();
    expect(parseEventClass(" / / ")).toBeNull();
  });
});

describe("eventKind and eventObject", () => {
  it.each([
    ["Cancelled Maneuver", "cancelled"],
    ["Manoeuvre", "maneuver"],
    ["Proximity operations", "rpo"],
    ["Rendezvous", "rpo"],
    ["Re-entry", "other"],
  ])("reads %s as %s", (label, kind) => {
    expect(eventKind(label)).toBe(kind);
  });

  it("uses the number as the name when brackets are all there is", () => {
    expect(eventObject("(90001)")).toEqual({ name: "90001", id: "90001" });
    expect(eventObject("TEST (1234567890)")).toEqual({ name: "TEST (1234567890)", id: null });
  });
});

describe("regimeFromElset", () => {
  it.each([
    [{ period: 95 }, "LEO"],
    [{ period: 720 }, "MEO"],
    [{ period: 1436 }, "GEO"],
    [{ period: 2000 }, "XGEO"],
    [{ period: 720, eccentricity: 0.7 }, "HEO"],
    [{ period: null, mean_motion: 1.0027 }, "GEO"],
  ])("reads %o as %s", (fields, regime) => {
    expect(regimeFromElset(anElset(1, fields))).toBe(regime);
  });

  it("gives null with no element set or no usable period", () => {
    expect(regimeFromElset(undefined)).toBeNull();
    expect(regimeFromElset(anElset(1, { period: null, mean_motion: null }))).toBeNull();
    expect(regimeFromElset(anElset(1, { period: -1 }))).toBeNull();
  });
});

describe("satelliteDirectory", () => {
  it("names satellites from the notices, and takes the regime a notice states over a guess", () => {
    const directory = satelliteDirectory(
      [
        aNotice({
          event_class: "RPO / TEST-A (90001) vs TEST-B (90002) / GEO",
          sat_ids: ["90001", "90002"],
        }),
        aNotice({ event_class: "Maneuver / TEST-A RENAMED (90001)", sat_ids: ["90001", "90004"] }),
      ],
      [aManeuverOf({ sat_no: 90003 })],
      [anElset(90001, { period: 95 }), anElset(90002, { period: 95 })],
    );
    expect(directory.get("90001")).toMatchObject({
      name: "TEST-A",
      regime: "GEO",
      regimeFrom: "notice",
    });
    // The regime belongs to the notice's first object: the second's comes from its element set.
    expect(directory.get("90002")).toMatchObject({ regime: "LEO", regimeFrom: "elset" });
    expect(directory.get("90003")).toMatchObject({ name: null, regime: null });
    expect(directory.get("90004")).toMatchObject({ name: null });
  });
});

describe("foldDuplicates", () => {
  it("folds copies of one maneuver and keeps distinct ones apart", () => {
    const a = aManeuverOf({ id: "a", sat_no: 1, event_start_time: "2026-11-02T10:00:00Z" });
    const copy = { ...a, id: "a2" };
    const other = { ...a, id: "b", source: "OTHER" };
    const groups = foldDuplicates([a, copy, other]);
    expect(groups.map((g) => [g.maneuver.id, g.copies, g.ids])).toEqual([
      ["a", 2, ["a", "a2"]],
      ["b", 1, ["b"]],
    ]);
  });
});

describe("bySatellite", () => {
  it("indexes each item under each satellite once", () => {
    const n = aNotice({ sat_ids: ["1", "1", "2"] });
    const index = bySatellite([n], noticeSatIds);
    expect(index.get("1")).toEqual([n]);
    expect(index.get("2")).toEqual([n]);
    expect(bySatellite([aManeuverOf({ sat_no: null })], maneuverSatIds).size).toBe(0);
  });
});

describe("histogram", () => {
  it("counts times into equal bins and ignores times outside", () => {
    expect(histogram([0, 1, 5, 9, 10, 11, -1], 0, 10, 2)).toEqual([2, 3]);
    expect(histogram([1], 5, 5, 3)).toEqual([0, 0, 0]);
  });
});

describe("times", () => {
  it.each([
    [NOW - 10_000, "just now"],
    [NOW - 12 * 60_000, "12 min ago"],
    [NOW - 3 * 3_600_000, "3 h ago"],
    [NOW - 2 * 86_400_000, "2 d ago"],
    [NOW + 5 * 60_000, "in 5 min"],
  ])("relativeTime(%d)", (time, text) => {
    expect(relativeTime(time, NOW)).toBe(text);
  });

  it("formats UTC clocks, days and stamps", () => {
    const t = Date.parse("2026-11-02T07:05:09Z");
    expect(clockUtc(t)).toBe("07:05Z");
    expect(clockSecondsUtc(t)).toBe("07:05:09Z");
    expect(stampUtc(t)).toBe("02 Nov 07:05Z");
    expect(fullUtc(t)).toBe("2026-11-02 07:05:09Z");
  });

  it("names days relative to now", () => {
    expect(dayHeading(NOW - 3_600_000, NOW)).toBe("Today");
    expect(dayHeading(NOW - 86_400_000, NOW)).toBe("Yesterday");
    expect(dayHeading(Date.parse("2026-10-31T12:00:00Z"), NOW)).toBe("Sat 31 Oct");
  });

  it("reads a time, or null for none or nonsense", () => {
    expect(timeOf("2026-11-02T00:00:00Z")).toBe(Date.parse("2026-11-02T00:00:00Z"));
    expect(timeOf(null)).toBeNull();
    expect(timeOf("not a time")).toBeNull();
  });

  it("formats durations", () => {
    expect(duration(42_000)).toBe("42 s");
    expect(duration(12 * 60_000)).toBe("12 min");
    expect(duration(3 * 3_600_000 + 5 * 60_000)).toBe("3 h 05 min");
    expect(duration(-5)).toBe("0 s");
  });
});

describe("groupByDay", () => {
  it("groups newest day first, timeless items last", () => {
    const items = ["2026-11-01T10:00:00Z", null, "2026-11-02T10:00:00Z", "2026-11-01T09:00:00Z"];
    const groups = groupByDay(items, timeOf);
    expect(groups.map((g) => g.items)).toEqual([
      ["2026-11-02T10:00:00Z"],
      ["2026-11-01T10:00:00Z", "2026-11-01T09:00:00Z"],
      [null],
    ]);
    expect(groups[2].day).toBeNull();
  });
});

describe("mostActive", () => {
  it("ranks satellites by events, the newest breaking ties", () => {
    const notices = [
      aNotice({ sat_ids: ["1", "2"], udl_created_at: "2026-11-02T10:00:00Z" }),
      aNotice({ sat_ids: ["3"], udl_created_at: "2026-11-02T12:00:00Z" }),
    ];
    const groups = foldDuplicates([
      aManeuverOf({ sat_no: 1, event_start_time: "2026-11-02T08:00:00Z" }),
      aManeuverOf({ sat_no: null }),
    ]);
    const ranked = mostActive(notices, groups, 3);
    expect(ranked.map((r) => r.id)).toEqual(["1", "3", "2"]);
    expect(ranked[0].times).toHaveLength(2);
    expect(mostActive(notices, groups, 1)).toHaveLength(1);
  });
});

describe("small readings", () => {
  it("reads urgency, falling back to info only", () => {
    expect(urgencyOf("HIGH")).toBe("high");
    expect(urgencyOf("severe")).toBe("none");
  });

  it("gives each source a slot in turn, alphabetically", () => {
    expect([...sourceSlots(["NorthStar", "KBR", null, "KBR"], 2)]).toEqual([
      ["KBR", 1],
      ["NorthStar", 2],
      ["Unknown", 1],
    ]);
  });

  it("converts the UDL delta-v to m/s, falling back to the typed column", () => {
    expect(deltaVMetresPerSecond(aManeuverOf({ facts: { delta_vel_kms: 0.0015 } }))).toBeCloseTo(
      1.5,
    );
    expect(deltaVMetresPerSecond(aManeuverOf({ delta_v: 2 }))).toBe(2);
    expect(deltaVMetresPerSecond(aManeuverOf())).toBeNull();
  });

  it("takes the end from the record's facts first", () => {
    expect(
      maneuverEnd(
        aManeuverOf({
          event_stop_time: "2026-11-02T01:00:00Z",
          facts: { event_end_time: "2026-11-02T02:00:00Z" },
        }),
      ),
    ).toBe(Date.parse("2026-11-02T02:00:00Z"));
    expect(maneuverEnd(aManeuverOf({ event_stop_time: "2026-11-02T01:00:00Z" }))).toBe(
      Date.parse("2026-11-02T01:00:00Z"),
    );
  });

  it("builds lower-cased search text from the parts present", () => {
    expect(searchText(["TEST", null, 42, undefined])).toBe("test 42");
  });
});
