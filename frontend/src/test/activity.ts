// Synthetic activity records for the console views' tests. Every value is made up for the tests;
// none is drawn from a real notice, satellite, provider or event.
import type {
  ActivityElset,
  ActivityManeuver,
  ActivityNotice,
  ActivityOverview,
  ManeuverFacts,
} from "../types";

let next = 0;
const nextId = (prefix: string) => {
  next += 1;
  return `${prefix}-${next}`;
};

export const NO_FACTS: ManeuverFacts = {
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

export function aNotice(overrides: Partial<ActivityNotice> = {}): ActivityNotice {
  return {
    id: nextId("notice"),
    notice: "TEST-NOTICE",
    event_class: "Maneuver / TEST-SAT (90001) / GEO",
    event_type: "other",
    status: "OPEN",
    region: null,
    udl_created_at: "2026-11-02T18:00:00Z",
    sat_ids: ["90001"],
    urgency: "none",
    top_action: null,
    ...overrides,
  };
}

export function aManeuverOf(
  overrides: Partial<Omit<ActivityManeuver, "facts">> & { facts?: Partial<ManeuverFacts> } = {},
): ActivityManeuver {
  const { facts, ...rest } = overrides;
  return {
    id: nextId("mnvr"),
    sat_no: 90001,
    source: "TEST-PROVIDER",
    event_start_time: "2026-11-02T17:00:00Z",
    event_stop_time: null,
    mnvr_type: null,
    maneuver_status: null,
    delta_v: null,
    ...rest,
    facts: { ...NO_FACTS, ...facts },
  };
}

export function anElset(sat_no: number, overrides: Partial<ActivityElset> = {}): ActivityElset {
  return {
    sat_no,
    epoch: "2026-11-02T06:00:00Z",
    period: 1436,
    inclination: 0.1,
    eccentricity: 0.0003,
    apogee: 35800,
    perigee: 35780,
    mean_motion: 1.0027,
    ...overrides,
  };
}

export function anOverview(overrides: Partial<ActivityOverview> = {}): ActivityOverview {
  return {
    window_hours: 120,
    window_start: "2026-10-28T20:00:00Z",
    generated_at: "2026-11-02T20:00:00Z",
    notices: [],
    maneuvers: [],
    elsets: [],
    truncated: { notices: false, maneuvers: false, elsets: false },
    ...overrides,
  };
}
