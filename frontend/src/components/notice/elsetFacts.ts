import type { Fact } from "../ops/maneuverFacts";
import { type Satellite, relativeTime, stampUtc, timeOf } from "../../utils/ops";

export const number = (value: number, digits: number) =>
  value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

// The latest element set Holly holds for the satellite, in words and units.
export function elsetFacts(satellite: Satellite | undefined, now: number): Fact[] {
  const elset = satellite?.elset;
  if (!elset) return [];
  const facts: Fact[] = [];
  const add = (label: string, value: number | null, unit: string, digits: number) => {
    if (value !== null) facts.push({ label, value: `${number(value, digits)}${unit}` });
  };
  add("Period", elset.period, " min", 1);
  add("Inclination", elset.inclination, "°", 2);
  add("Apogee", elset.apogee, " km", 0);
  add("Perigee", elset.perigee, " km", 0);
  add("Eccentricity", elset.eccentricity, "", 5);
  const epoch = timeOf(elset.epoch);
  if (epoch !== null)
    facts.push({ label: "Epoch", value: relativeTime(epoch, now), title: stampUtc(epoch) });
  return facts;
}
