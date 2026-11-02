// The facts a maneuver record carries, in words and units, for its row and its page.
import {
  type ManeuverGroup,
  deltaVMetresPerSecond,
  duration,
  maneuverEnd,
  maneuverStart,
} from "../../utils/ops";

const number = (value: number, digits: number) =>
  value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export interface Fact {
  label: string;
  value: string;
  title?: string;
}

// The facts a maneuver record carries, in words and units; an absent one is left out.
export function maneuverFacts(group: ManeuverGroup): Fact[] {
  const m = group.maneuver;
  const facts: Fact[] = [];
  const dv = deltaVMetresPerSecond(m);
  if (dv !== null) {
    facts.push({
      label: "Δv",
      value: `${number(dv, 3)} m/s`,
      title:
        m.facts.delta_vel_kms === null
          ? "The record's deltaV, which the original dashboard read as m/s"
          : "The record's deltaVel, published in km/s by the UDL schema (TBC), shown in m/s",
    });
  }
  if (m.facts.delta_pos_km !== null) {
    facts.push({ label: "Δpos", value: `${number(m.facts.delta_pos_km, 3)} km` });
  }
  const start = maneuverStart(m);
  const end = maneuverEnd(m);
  if (start !== null && end !== null && end >= start) {
    facts.push({ label: "Duration", value: duration(end - start) });
  } else if (m.facts.total_burn_time_s !== null) {
    facts.push({ label: "Burn", value: duration(m.facts.total_burn_time_s * 1000) });
  }
  const lon = m.facts.post_geo_longitude_deg;
  if (lon !== null) facts.push({ label: "Longitude", value: `${number(lon, 2)}°` });
  const drift = m.facts.post_drift_rate_deg_day;
  if (drift !== null) facts.push({ label: "Drift", value: `${number(drift, 3)}°/day` });
  if (m.facts.delta_mass_kg !== null) {
    facts.push({ label: "Δmass", value: `${number(m.facts.delta_mass_kg, 2)} kg` });
  }
  return facts;
}
