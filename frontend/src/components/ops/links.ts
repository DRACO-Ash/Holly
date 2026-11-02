import type { ActivityManeuver, ActivityNotice } from "../../types";
import { maneuverStart } from "../../utils/ops";

// The maneuvers in the window on the satellites a notice names, newest first.
export function linkedManeuvers(
  notice: ActivityNotice,
  maneuversBySat: ReadonlyMap<string, readonly ActivityManeuver[]>,
): ActivityManeuver[] {
  const seen = new Set<string>();
  const found: ActivityManeuver[] = [];
  for (const id of notice.sat_ids) {
    for (const maneuver of maneuversBySat.get(id) ?? []) {
      if (seen.has(maneuver.id)) continue;
      seen.add(maneuver.id);
      found.push(maneuver);
    }
  }
  return found.sort((a, b) => (maneuverStart(b) ?? 0) - (maneuverStart(a) ?? 0));
}
