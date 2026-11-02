// What the stored UDL record says beyond the typed columns, read on the server with the UDL
// Maneuver schema's keys. Each name carries the unit that schema states (TBC, re-verify).
export interface ManeuverFacts {
  status: string | null;
  characterization: string | null;
  event_id: string | null;
  orig_object_id: string | null;
  event_end_time: string | null;
  report_time: string | null;
  delta_vel_kms: number | null;
  delta_pos_km: number | null;
  delta_mass_kg: number | null;
  total_burn_time_s: number | null;
  pre_geo_longitude_deg: number | null;
  post_geo_longitude_deg: number | null;
  pre_drift_rate_deg_day: number | null;
  post_drift_rate_deg_day: number | null;
  pre_apogee_km: number | null;
  post_apogee_km: number | null;
  pre_perigee_km: number | null;
  post_perigee_km: number | null;
  pre_inclination_deg: number | null;
  post_inclination_deg: number | null;
  pre_period_min: number | null;
  post_period_min: number | null;
  pre_semi_major_axis_km: number | null;
  post_semi_major_axis_km: number | null;
  pre_eccentricity: number | null;
  post_eccentricity: number | null;
  uct: boolean | null;
}

export interface Maneuver {
  id: string;
  udl_id: string | null;
  data_mode: string | null;
  source: string | null;
  classification_marking: string | null;
  created_by: string | null;
  orig_network: string | null;
  origin: string | null;
  udl_created_at: string | null;
  sat_no: number | null;
  event_start_time: string | null;
  event_stop_time: string | null;
  mnvr_type: string | null;
  description: string | null;
  delta_v: number | null;
  thrust_magnitude: number | null;
  thrust_duration: number | null;
  propulsion_type: string | null;
  maneuver_status: string | null;
  responsible_nation: string | null;
  created_at: string;
  updated_at: string;
  facts: ManeuverFacts;
}

export interface ManeuverDetail extends Maneuver {
  raw: Record<string, unknown>;
}

export interface ManeuverPage {
  items: Maneuver[];
  total: number;
  limit: number;
  offset: number;
}

export type ManeuverSortColumn =
  | "sat_no"
  | "event_start_time"
  | "event_stop_time"
  | "mnvr_type"
  | "udl_created_at"
  | "created_at";

export interface ManeuverListQuery {
  sat_no?: number;
  mnvr_type?: string;
  event_start_time_gte?: string;
  event_start_time_lte?: string;
  limit?: number;
  offset?: number;
  sort_by?: ManeuverSortColumn;
  sort_dir?: "asc" | "desc";
}
