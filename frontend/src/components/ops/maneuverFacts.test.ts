import { describe, expect, it } from "vitest";
import { aManeuverOf } from "../../test/activity";
import type { ActivityManeuver } from "../../types";
import { maneuverFacts } from "./maneuverFacts";

const group = (maneuver: ActivityManeuver) => ({ maneuver, copies: 1, ids: [maneuver.id] });
const facts = (maneuver: ActivityManeuver) => maneuverFacts(group(maneuver));

describe("maneuverFacts", () => {
  it("has nothing to say about a record with no facts", () => {
    expect(facts(aManeuverOf())).toEqual([]);
  });

  it("shows the UDL km/s delta-v in m/s, and says where it came from", () => {
    const [dv] = facts(aManeuverOf({ facts: { delta_vel_kms: 0.0015 } }));
    expect(dv).toMatchObject({ label: "Δv", value: "1.5 m/s" });
    expect(dv.title).toContain("deltaVel");
  });

  it("falls back to the typed column, said to be the original dashboard's m/s", () => {
    const [dv] = facts(aManeuverOf({ delta_v: 2.25 }));
    expect(dv).toMatchObject({ label: "Δv", value: "2.25 m/s" });
    expect(dv.title).toContain("deltaV,");
  });

  it("gives the duration from start to end, before the burn time", () => {
    const list = facts(
      aManeuverOf({
        event_start_time: "2026-11-02T10:00:00Z",
        facts: { event_end_time: "2026-11-02T10:12:00Z", total_burn_time_s: 30 },
      }),
    );
    expect(list).toEqual([{ label: "Duration", value: "12 min" }]);
  });

  it("gives the burn time when there is no usable end", () => {
    const list = facts(
      aManeuverOf({
        event_start_time: "2026-11-02T10:00:00Z",
        facts: { event_end_time: "2026-11-02T09:00:00Z", total_burn_time_s: 42 },
      }),
    );
    expect(list).toEqual([{ label: "Burn", value: "42 s" }]);
  });

  it("lists position change, longitude, drift and mass in their units", () => {
    const list = facts(
      aManeuverOf({
        facts: {
          delta_pos_km: 1.23456,
          post_geo_longitude_deg: 110.456,
          post_drift_rate_deg_day: -0.0123,
          delta_mass_kg: 0.555,
        },
      }),
    );
    expect(list.map((f) => [f.label, f.value])).toEqual([
      ["Δpos", "1.235 km"],
      ["Longitude", "110.46°"],
      ["Drift", "-0.012°/day"],
      ["Δmass", "0.56 kg"],
    ]);
  });
});
