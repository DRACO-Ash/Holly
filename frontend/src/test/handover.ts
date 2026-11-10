// Builders for the Handover tab's tests. Test support only: nothing the build bundles imports it.
import type { HandoverStory, StoryManeuver } from "../types";

export const NO_FACTS = {
  status: null,
  characterization: null,
  event_id: null,
  orig_object_id: null,
  event_end_time: null,
  report_time: null,
  delta_vel_kms: null,
  delta_pos_km: null,
  delta_mass_kg: null,
  total_burn_time_s: null,
  pre_geo_longitude_deg: null,
  post_geo_longitude_deg: null,
  pre_drift_rate_deg_day: null,
  post_drift_rate_deg_day: null,
  pre_apogee_km: null,
  post_apogee_km: null,
  pre_perigee_km: null,
  post_perigee_km: null,
  pre_inclination_deg: null,
  post_inclination_deg: null,
  pre_period_min: null,
  post_period_min: null,
  pre_semi_major_axis_km: null,
  post_semi_major_axis_km: null,
  pre_eccentricity: null,
  post_eccentricity: null,
  uct: null,
};

export function aManeuver(overrides: Partial<StoryManeuver> = {}): StoryManeuver {
  return {
    id: "m-1",
    source: "TEST-PROVIDER",
    event_start_time: "2026-01-05T10:00:00Z",
    maneuver_status: "POSSIBLE",
    udl_id: "UDL-M-1",
    facts: { ...NO_FACTS },
    ...overrides,
  };
}

export function aStory(overrides: Partial<HandoverStory> = {}): HandoverStory {
  return {
    sat_no: 90001,
    name: "TEST-SAT 1",
    window_hours: 120,
    window_start: "2026-01-01T12:00:00Z",
    generated_at: "2026-01-06T12:00:00Z",
    notices: [],
    maneuvers: [],
    threads: [],
    suggestions: [],
    timers: [],
    notes: [],
    truncated: false,
    ...overrides,
  };
}
