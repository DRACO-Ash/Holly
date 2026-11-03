// Every fact a maneuver record carries, labelled with its unit, for the record opened in place.
// Each unit is the one the UDL Maneuver schema states for the key (TBC, re-verify).
import type { ManeuverFacts } from "../../types";
import { fullUtc, timeOf } from "../../utils/ops";

export interface DrawerFact {
  label: string;
  value: string;
}

type NumberKey = {
  [K in keyof ManeuverFacts]: ManeuverFacts[K] extends number | null ? K : never;
}[keyof ManeuverFacts];

const NUMBERS: readonly (readonly [NumberKey, string, number])[] = [
  ["delta_vel_kms", "Δv (km/s)", 6],
  ["delta_pos_km", "Δpos (km)", 3],
  ["delta_mass_kg", "Δmass (kg)", 2],
  ["total_burn_time_s", "Burn time (s)", 1],
  ["pre_geo_longitude_deg", "Longitude before (°)", 3],
  ["post_geo_longitude_deg", "Longitude after (°)", 3],
  ["pre_drift_rate_deg_day", "Drift before (°/day)", 4],
  ["post_drift_rate_deg_day", "Drift after (°/day)", 4],
  ["pre_apogee_km", "Apogee before (km)", 1],
  ["post_apogee_km", "Apogee after (km)", 1],
  ["pre_perigee_km", "Perigee before (km)", 1],
  ["post_perigee_km", "Perigee after (km)", 1],
  ["pre_inclination_deg", "Inclination before (°)", 4],
  ["post_inclination_deg", "Inclination after (°)", 4],
  ["pre_period_min", "Period before (min)", 3],
  ["post_period_min", "Period after (min)", 3],
  ["pre_semi_major_axis_km", "Semi-major axis before (km)", 1],
  ["post_semi_major_axis_km", "Semi-major axis after (km)", 1],
  ["pre_eccentricity", "Eccentricity before", 6],
  ["post_eccentricity", "Eccentricity after", 6],
];

const TEXTS = [
  ["status", "Status"],
  ["characterization", "Characterisation"],
  ["event_id", "Event ID"],
  ["orig_object_id", "Originator's object ID"],
] as const;

const TIMES = [
  ["event_end_time", "End (UTC)"],
  ["report_time", "Reported (UTC)"],
] as const;

export function drawerFacts(facts: ManeuverFacts): DrawerFact[] {
  const out: DrawerFact[] = [];
  for (const [key, label] of TEXTS) {
    const value = facts[key];
    if (value !== null) out.push({ label, value });
  }
  for (const [key, label] of TIMES) {
    const time = timeOf(facts[key]);
    if (time !== null) out.push({ label, value: fullUtc(time) });
  }
  for (const [key, label, digits] of NUMBERS) {
    const value = facts[key];
    if (value !== null) {
      out.push({ label, value: value.toLocaleString("en-GB", { maximumFractionDigits: digits }) });
    }
  }
  if (facts.uct !== null) {
    out.push({ label: "Uncorrelated track", value: facts.uct ? "Yes" : "No" });
  }
  return out;
}
