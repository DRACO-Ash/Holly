import type { ManeuverFacts } from "./maneuver";

// GET /api/v1/activity: one window of notices, maneuvers and the latest element set of each
// satellite they name (src/app/schemas/activity.py).
export interface ActivityNotice {
  id: string;
  notice: string | null;
  event_class: string | null;
  event_type: string | null;
  status: string | null;
  region: string | null;
  udl_created_at: string | null;
  sat_ids: string[];
  // A FeedUrgency as a rule; the server types it as any string.
  urgency: string;
  top_action: string | null;
}

export interface ActivityManeuver {
  id: string;
  sat_no: number | null;
  source: string | null;
  event_start_time: string | null;
  event_stop_time: string | null;
  mnvr_type: string | null;
  maneuver_status: string | null;
  delta_v: number | null;
  facts: ManeuverFacts;
}

export interface ActivityElset {
  sat_no: number;
  epoch: string;
  period: number | null;
  inclination: number | null;
  eccentricity: number | null;
  apogee: number | null;
  perigee: number | null;
  mean_motion: number | null;
}

export interface ActivityOverview {
  window_hours: number;
  window_start: string;
  generated_at: string;
  notices: ActivityNotice[];
  maneuvers: ActivityManeuver[];
  elsets: ActivityElset[];
  // True where the window held more than the overview carries; the newest are kept.
  truncated: { notices: boolean; maneuvers: boolean; elsets: boolean };
}
