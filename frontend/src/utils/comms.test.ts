// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CHANNEL_HUES,
  ago,
  channelHue,
  channelHues,
  channelLabel,
  closedReason,
  dayLabel,
  everyLabel,
  fullTime,
  hourPosition,
  loadLastSeen,
  loadView,
  matchParts,
  plural,
  sameUtcDay,
  saveLastSeen,
  saveView,
  sweepSummary,
  timeOfDay,
} from "./comms";

const NOW = new Date("2026-01-10T12:00:00Z");

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("a channel's hue and name", () => {
  it("gives the channels the hues in the order Holly found them, the first six all different", () => {
    const found = (id: string, day: number) => ({
      mm_channel_id: id,
      first_seen_at: `2026-01-0${day}T00:00:00Z`,
    });
    // Two found in one sweep take their order from their ids.
    const hues = channelHues([
      found("golf", 7),
      found("bravo", 1),
      found("alpha", 1),
      found("charlie", 2),
      found("delta", 3),
      found("echo", 4),
      found("foxtrot", 5),
    ]);
    expect([...hues]).toEqual([
      ["alpha", 1],
      ["bravo", 2],
      ["charlie", 3],
      ["delta", 4],
      ["echo", 5],
      ["foxtrot", 6],
      ["golf", 1],
    ]);
    expect(channelHue("delta", hues)).toBe(4);
  });

  it("gives a channel Holly no longer lists a hue of its own, the same every time", () => {
    const none = new Map<string, number>();
    for (const id of ["gone-1", "gone-2", "gone-3"]) {
      expect(channelHue(id, none)).toBe(channelHue(id, none));
      expect(channelHue(id, none)).toBeGreaterThanOrEqual(1);
      expect(channelHue(id, none)).toBeLessThanOrEqual(CHANNEL_HUES);
    }
  });

  it("shows the display name, or the name when there is none", () => {
    expect(channelLabel({ display_name: "Ops Floor", name: "ops-floor" })).toBe("Ops Floor");
    expect(channelLabel({ display_name: null, name: "ops-floor" })).toBe("ops-floor");
    expect(channelLabel({ display_name: "", name: "ops-floor" })).toBe("ops-floor");
  });
});

describe("times, in UTC", () => {
  it("names today and yesterday, and dates anything earlier", () => {
    expect(dayLabel("2026-01-10T00:00:01Z", NOW)).toBe("Today");
    expect(dayLabel("2026-01-09T23:59:59Z", NOW)).toBe("Yesterday");
    expect(dayLabel("2026-01-05T08:00:00Z", NOW)).toBe("Mon, 5 Jan 2026");
  });

  it("tells whether two times fall on one UTC day", () => {
    expect(sameUtcDay("2026-01-10T00:00:00Z", "2026-01-10T23:59:59Z")).toBe(true);
    expect(sameUtcDay("2026-01-09T23:59:59Z", "2026-01-10T00:00:00Z")).toBe(false);
  });

  it("reads a time of day and a full time", () => {
    expect(timeOfDay("2026-01-10T14:05:09Z")).toBe("14:05");
    expect(fullTime("2026-01-10T14:05:09.123Z")).toBe("2026-01-10 14:05:09 UTC");
  });

  it("says how long ago, in the largest whole unit", () => {
    expect(ago("2026-01-10T11:59:30Z", NOW)).toBe("just now");
    expect(ago("2026-01-10T12:00:30Z", NOW)).toBe("just now");
    expect(ago("2026-01-10T11:56:00Z", NOW)).toBe("4 min ago");
    expect(ago("2026-01-10T09:00:00Z", NOW)).toBe("3 h ago");
    expect(ago("2026-01-08T12:00:00Z", NOW)).toBe("2 d ago");
    expect(ago(new Date().toISOString())).toBe("just now");
  });
});

describe("what the strip and the lanes say", () => {
  it("says how often Holly sweeps, in minutes when it can", () => {
    expect(everyLabel(60)).toBe("every minute");
    expect(everyLabel(300)).toBe("every 5 minutes");
    expect(everyLabel(90)).toBe("every 90 seconds");
    expect(everyLabel(10)).toBe("every 10 seconds");
  });

  it("places a time among the last 24 hours, or nowhere outside them", () => {
    // At 12:00 the lanes run from 13:00 the day before to the end of this hour.
    expect(hourPosition("2026-01-09T13:00:00Z", NOW)).toBe(0);
    expect(hourPosition("2026-01-10T06:30:00Z", NOW)).toBe(17.5);
    expect(hourPosition("2026-01-10T13:00:00Z", NOW)).toBe(24);
    expect(hourPosition("2026-01-09T12:59:00Z", NOW)).toBeNull();
    expect(hourPosition("2026-01-10T13:01:00Z", NOW)).toBeNull();
    expect(hourPosition(null, NOW)).toBeNull();
  });

  it("says why a channel is closed", () => {
    expect(closedReason({ archived: true })).toBe("Archived");
    expect(closedReason({ archived: false })).toBe("Closed by name");
  });
});

describe("matchParts", () => {
  it("leaves a message whole when nothing is searched for", () => {
    expect(matchParts("Burn at 14:05", "  ")).toEqual([{ text: "Burn at 14:05", match: false }]);
  });

  it("marks every match, in any case, keeping the message's own case", () => {
    expect(matchParts("Burn now. BURN later", "burn")).toEqual([
      { text: "Burn", match: true },
      { text: " now. ", match: false },
      { text: "BURN", match: true },
      { text: " later", match: false },
    ]);
    expect(matchParts("no hit here", "burn")).toEqual([{ text: "no hit here", match: false }]);
  });
});

describe("what a sweep found", () => {
  it("counts in words, one or many", () => {
    expect(plural(1, "channel")).toBe("1 channel");
    expect(plural(3, "channel")).toBe("3 channels");
    expect(plural(2, "entry", "entries")).toBe("2 entries");
  });

  const quiet = {
    ok: true,
    problem: null,
    found: 4,
    new: 0,
    closed: 0,
    reopened: 0,
    lost: 0,
    channels_polled: 3,
    channels_failed: 0,
    inserted: 1,
  };

  it("says what it found and pulled", () => {
    expect(sweepSummary(quiet)).toBe("Found 4 channels. Pulled 1 new message from 3 channels.");
  });

  it("names each change, and any channel it could not read", () => {
    const busy = { ...quiet, new: 1, closed: 2, reopened: 1, lost: 1, channels_failed: 2 };
    expect(sweepSummary(busy)).toBe(
      "Found 4 channels: 1 new, 2 closed, 1 reopened, 1 the bot can no longer read. " +
        "Pulled 1 new message from 3 channels; 2 could not be read.",
    );
  });
});

describe("what this browser remembers", () => {
  it("remembers the layout, the feed by default", () => {
    expect(loadView()).toBe("feed");
    saveView("channels");
    expect(loadView()).toBe("channels");
    saveView("feed");
    expect(loadView()).toBe("feed");
  });

  it("remembers when each user last looked, and ignores a stored value that is not a time", () => {
    expect(loadLastSeen("user-a")).toBeNull();
    saveLastSeen("user-a", "2026-01-10T12:00:00.000Z");
    expect(loadLastSeen("user-a")).toBe("2026-01-10T12:00:00.000Z");
    expect(loadLastSeen("user-b")).toBeNull();
    localStorage.setItem("holly.comms.seen.user-b", "not a time");
    expect(loadLastSeen("user-b")).toBeNull();
  });

  it("works as on a first visit when the store refuses", () => {
    const refusing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("full");
      },
    };
    vi.stubGlobal("localStorage", refusing);
    expect(loadView()).toBe("feed");
    expect(() => saveView("channels")).not.toThrow();
    expect(loadLastSeen("user-a")).toBeNull();
    expect(() => saveLastSeen("user-a", NOW.toISOString())).not.toThrow();
  });

  it("works as on a first visit when the store cannot be reached at all", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(loadView()).toBe("feed");
    expect(loadLastSeen("user-a")).toBeNull();
    expect(() => saveView("channels")).not.toThrow();
  });
});
