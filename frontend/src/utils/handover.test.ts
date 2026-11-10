import { describe, expect, it } from "vitest";
import { NO_FACTS, aManeuver, aStory } from "../test/handover";
import { maneuverChanges, storyEntries } from "./handover";

describe("a provider record's changes", () => {
  it("states the period, apogee, perigee, delta-v and longitude it gives", () => {
    const m = aManeuver({
      facts: {
        ...NO_FACTS,
        pre_period_min: 1436,
        post_period_min: 1436.42,
        pre_apogee_km: 35800,
        post_apogee_km: 35790,
        pre_perigee_km: 35780,
        post_perigee_km: 35797,
        delta_vel_kms: 0.0021,
        post_geo_longitude_deg: 75.25,
      },
    });
    expect(maneuverChanges(m)).toEqual([
      "period +0.42 min",
      "apogee -10 km",
      "perigee +17 km",
      "Δv 2.1 m/s",
      "now at 75.25°",
    ]);
  });

  it("states nothing a record leaves out, or gives only one side of", () => {
    expect(maneuverChanges(aManeuver({ facts: { ...NO_FACTS, pre_period_min: 1436 } }))).toEqual(
      [],
    );
  });
});

describe("the story's entries", () => {
  it("brings every source together, oldest first, untimed last, each with its source", () => {
    const story = aStory({
      notices: [
        {
          id: "n-1",
          event_key: "EVT-1",
          notice: "ABC-0001",
          event_class: "Maneuver / TEST-SAT 1 (90001)",
          kind: "Maneuver",
          status: "OPEN",
          udl_created_at: "2026-01-05T09:00:00Z",
          source: "JCO",
          udl_id: "UDL-1",
        },
        {
          id: "n-2",
          event_key: "EVT-2",
          notice: null,
          event_class: null,
          kind: null,
          status: null,
          udl_created_at: null,
          source: null,
          udl_id: null,
        },
      ],
      maneuvers: [aManeuver({ source: null, udl_id: null })],
      threads: [
        {
          thread_id: "t-1",
          event_key: "EVT-1",
          channel_name: null,
          confirmed_at: "2026-01-05T12:00:00Z",
          posts: [
            {
              post_id: "p-1",
              posted_at: "2026-01-05T11:00:00Z",
              author: null,
              message: "Burn seen.",
            },
          ],
          truncated: false,
        },
      ],
      notes: [
        {
          id: "note-1",
          author_id: null,
          author: null,
          text: "Watch the approach.",
          created_at: "2026-01-05T12:30:00Z",
        },
      ],
    });
    const entries = storyEntries(story);
    expect(entries.map((e) => [e.type, e.title, e.source])).toEqual([
      ["notice", "Maneuver · ABC-0001", "NOTSO · UDL UDL-1"],
      ["maneuver", "Maneuver record · provider not named", "Provider record · UDL"],
      ["post", "Unknown author", "Mattermost · channel · confirmed thread"],
      ["note", "Note · former user", "Analyst note"],
      ["notice", "Notice · no NOTSO number", "NOTSO · UDL"],
    ]);
    expect(entries[0].detail).toBe("OPEN · Maneuver / TEST-SAT 1 (90001)");
    expect(entries[0].kind).toBe("maneuver");
    expect(entries[1].detail).toBe("POSSIBLE");
    expect(entries[4].detail).toBeNull();
    expect(entries[4].at).toBeNull();
  });
});
