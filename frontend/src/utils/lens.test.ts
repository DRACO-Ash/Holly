import { describe, expect, it } from "vitest";
import { aStory } from "../test/handover";
import type { ActivityNotice, HandoverObject } from "../types";
import {
  countdown,
  firstObjectIn,
  namesNumber,
  lensItems,
  linkParts,
  matchNotices,
  matchObjects,
  noticesOf,
  splitBySeen,
  stripX,
  topUrgency,
} from "./lens";

const known = (id: string) => ["90001", "90002"].includes(id);
const held = (notso: string) => notso === "7afc_19Oct-1726Z";

function notice(overrides: Partial<ActivityNotice> = {}): ActivityNotice {
  return {
    id: "n-1",
    notice: "7afc_19Oct-1726Z",
    event_class: "RPO / TEST-SAT 1 (90001) vs TEST-SAT 2 (90002) / LEO",
    event_type: "other",
    status: "OPEN",
    region: null,
    udl_created_at: "2026-01-05T09:00:00Z",
    sat_ids: ["90001", "90002"],
    urgency: "medium",
    top_action: null,
    ...overrides,
  };
}

function object(overrides: Partial<HandoverObject> = {}): HandoverObject {
  return {
    sat_no: 90001,
    name: "TEST-SAT 1",
    kinds: ["RPO"],
    latest_at: "2026-01-05T09:00:00Z",
    events: 1,
    maneuvers: 2,
    ...overrides,
  };
}

describe("which text links", () => {
  it("links whole catalogue numbers of known objects and NOTSO numbers Holly holds", () => {
    expect(linkParts("Check 90001 vs 90002, see 7afc_19Oct-1726Z.", known, held)).toEqual([
      { kind: "text", text: "Check ", at: 0 },
      { kind: "sat", id: "90001", at: 6 },
      { kind: "text", text: " vs ", at: 11 },
      { kind: "sat", id: "90002", at: 15 },
      { kind: "text", text: ", see ", at: 20 },
      { kind: "notice", notso: "7afc_19Oct-1726Z", at: 26 },
      { kind: "text", text: ".", at: 42 },
    ]);
  });

  it.each([
    ["a longer number holding one", "190001 and 900010"],
    ["a number of no known object", "90003 drifted"],
    ["a clock time", "at 14:10Z"],
    ["a NOTSO number Holly does not hold", "see 1234_1Nov-0000Z"],
  ])("leaves %s as text", (_label, text) => {
    expect(linkParts(text, known, held).every((p) => p.kind === "text")).toBe(true);
  });

  it("tells a number named whole from one inside a longer number", () => {
    expect(namesNumber("Pass 90001 / 90002", "90001")).toBe(true);
    expect(namesNumber("Pass 190001", "90001")).toBe(false);
    expect(namesNumber("Pass 900010", "90001")).toBe(false);
    expect(namesNumber("no digits", "90001")).toBe(false);
  });

  it("finds the first known object a message names", () => {
    expect(firstObjectIn("190001 then 90002 then 90001", known)).toBe("90002");
    expect(firstObjectIn("nothing here", known)).toBeNull();
  });
});

describe("the lens's time helpers", () => {
  it("counts down to the moment, never below zero", () => {
    expect(countdown(2 * 3_600_000 + 49 * 60_000 + 7_400)).toBe("2:49:07");
    expect(countdown(-5_000)).toBe("0:00:00");
  });

  it("places a time on a strip, clamped to it", () => {
    expect(stripX(150, 100, 200)).toBe(50);
    expect(stripX(50, 100, 200)).toBe(0);
    expect(stripX(250, 100, 200)).toBe(100);
    expect(stripX(150, 200, 200)).toBe(0);
  });
});

describe("the lens's items", () => {
  const story = aStory({
    notes: [
      {
        id: "note-1",
        author_id: null,
        author: "a",
        text: "Note.",
        created_at: "2026-01-05T12:00:00Z",
      },
    ],
    suggestions: [
      {
        thread_id: "t-9",
        event_key: "EVT-1",
        channel_name: null,
        reason: "names 90001",
        matching_posts: 2,
        first_post: {
          post_id: "p-9",
          posted_at: "2026-01-05T14:00:00Z",
          author: null,
          message: "90001 again",
        },
      },
    ],
  });

  it("puts suggested threads beside the story, newest first, marked as not confirmed", () => {
    const items = lensItems(story);
    expect(items.map((i) => [i.tone, i.title])).toEqual([
      ["suggested", "Unknown author in #channel"],
      ["note", "Note · a"],
    ]);
    expect(items[0].source).toBe("Mattermost · suggested thread, not confirmed · 2 matching");
  });

  it("splits what is new since the analyst last looked; an item with no time is never new", () => {
    const items = [...lensItems(story), { ...lensItems(story)[1], key: "untimed", at: null }];
    const [fresh, earlier] = splitBySeen(items, Date.parse("2026-01-05T13:00:00Z"));
    // An item from the very moment of the last look was seen then.
    expect(splitBySeen(items, Date.parse("2026-01-05T14:00:00Z"))[0]).toEqual([]);
    expect(fresh.map((i) => i.key)).toEqual(["suggested-t-9"]);
    expect(earlier.map((i) => i.key)).toEqual(["note-note-1", "untimed"]);
  });
});

describe("notices and urgency", () => {
  it("keeps the object's notices and names the most urgent open one", () => {
    const list = [
      notice(),
      notice({ id: "n-2", urgency: "high", status: "CLOSED" }),
      notice({ id: "n-3", sat_ids: ["90003"] }),
    ];
    expect(noticesOf(list, 90001).map((n) => n.id)).toEqual(["n-1", "n-2"]);
    expect(topUrgency(noticesOf(list, 90001))).toBe("medium");
    expect(topUrgency([notice({ urgency: "none" })])).toBeNull();
  });
});

describe("Find's matches", () => {
  const objects = [
    object(),
    object({
      sat_no: 90002,
      name: "OTHER",
      kinds: ["Maneuver"],
      latest_at: "2026-01-06T09:00:00Z",
    }),
  ];

  it("matches objects by number, name or kind, latest first, and nothing for an empty query", () => {
    expect(matchObjects(objects, "900").map((o) => o.sat_no)).toEqual([90002, 90001]);
    expect(matchObjects(objects, "test-sat").map((o) => o.sat_no)).toEqual([90001]);
    expect(matchObjects(objects, "maneuver").map((o) => o.sat_no)).toEqual([90002]);
    expect(matchObjects(objects, "  ")).toEqual([]);
    expect(matchObjects(objects, "900", 1)).toHaveLength(1);
  });

  it("matches notices by NOTSO number or event class", () => {
    const list = [notice(), notice({ id: "n-2", notice: null, event_class: null })];
    expect(matchNotices(list, "7AFC").map((n) => n.id)).toEqual(["n-1"]);
    expect(matchNotices(list, "rpo /").map((n) => n.id)).toEqual(["n-1"]);
    expect(matchNotices(list, "")).toEqual([]);
  });
});
