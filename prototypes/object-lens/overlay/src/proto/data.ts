// The prototype's synthetic world: every object, notice, record, message, timer and note below is
// invented for the hallway test. Names start SAMPLE-, catalogue numbers are 90xxx, people are
// sample.*. Times are set relative to the moment the page loads, so countdowns stay live.
import type {
  ActivityElset,
  ActivityNotice,
  AssistantEvaluation,
  EventTimer,
  Maneuver,
  ManeuverFacts,
  MattermostChannel,
  MattermostMessage,
  NotificationDetail,
  ShiftNote,
  StoryNote,
  User,
} from "../types";

export const NOW = Date.now();
export const H = 3_600_000;
export const iso = (t: number) => new Date(t).toISOString();

let seed = 20261117;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const pick = <T,>(list: readonly T[]): T => list[Math.floor(rnd() * list.length)];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function notsoId(hex: string, t: number): string {
  const d = new Date(t);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hex}_${d.getUTCDate()}${MONTHS[d.getUTCMonth()]}-${hh}${mm}Z`;
}

export const USER: User = {
  id: "u-analyst",
  username: "sample.analyst",
  email: null,
  role: "analyst",
  is_active: true,
  must_change_password: false,
  created_at: iso(NOW - 900 * H),
};

type Sat = { name: string; id: string; regime: "LEO" | "GEO" };
const SATS: Sat[] = [
  { name: "SAMPLE-GEO 3B", id: "90062", regime: "GEO" },
  { name: "SAMPLE-GEO 2589", id: "90467", regime: "GEO" },
  { name: "SAMPLE-TJ 15", id: "90157", regime: "GEO" },
  { name: "SAMPLE-SY 12-01", id: "90321", regime: "GEO" },
  { name: "SAMPLE-SY 32-03", id: "90379", regime: "LEO" },
  { name: "SAMPLE-SJ 21", id: "90330", regime: "GEO" },
  { name: "SAMPLE-TJ 19", id: "90924", regime: "GEO" },
  { name: "SAMPLE-TJ 17", id: "90524", regime: "GEO" },
  { name: "SAMPLE-LEO 2612", id: "90762", regime: "LEO" },
  { name: "SAMPLE-OBJ C", id: "90627", regime: "LEO" },
  { name: "SAMPLE-EL 3", id: "90903", regime: "GEO" },
  { name: "SAMPLE-SAR X36", id: "90103", regime: "LEO" },
  { name: "SAMPLE-NAV 7", id: "90415", regime: "GEO" },
  { name: "SAMPLE-COM 44", id: "90588", regime: "GEO" },
];
const SAT = (id: string) => SATS.find((s) => s.id === id)!;

// The two matched test objects. Each has the same shape of story, so the two task sets are equal
// in difficulty: one open RPO notice, three provider records, a concern raised in chat and
// answered, a later passing mention, one timer and one analyst note.
export interface Target {
  set: "A" | "B";
  sat: Sat;
  partner: Sat;
  noticeAt: number;
  hex: string;
  eventKey: string;
  maneuvers: Array<{ at: number; source: string }>;
  concern: { channel: string; author: string; at: number; text: string };
  reply: { author: string; at: number; text: string };
  mention: { channel: string; author: string; at: number; text: string };
  timer: { label: string; at: number };
  note: { author: string; at: number; text: string };
}

export const TARGETS: Target[] = [
  {
    set: "A",
    sat: SAT("90762"),
    partner: SAT("90103"),
    noticeAt: NOW - 30 * H,
    hex: "7afc",
    eventKey: "EVT-A-0001",
    maneuvers: [
      { at: NOW - 70 * H, source: "PROVIDER-A" },
      { at: NOW - 41 * H, source: "PROVIDER-A" },
      { at: NOW - 3.2 * H, source: "PROVIDER-B" },
    ],
    concern: {
      channel: "ch-leo",
      author: "sample.charlie",
      at: NOW - 27 * H,
      text: "Can someone check 90762 vs 90103? Closest approach looks tighter than this morning.",
    },
    reply: { author: "sample.alpha", at: NOW - 26.5 * H, text: "Ran it again, miss distance down. Briefing the duty officer." },
    mention: { channel: "ch-ops", author: "sample.bravo", at: NOW - 6 * H, text: "Elset for 90762 updated, nothing new in it." },
    timer: { label: "Closest approach 90762 / 90103", at: NOW + 2.83 * H },
    note: {
      author: "sample.lead",
      at: NOW - 5 * H,
      text: "Duty officer briefed. Re-run the conjunction after the next elset and update the partner cell.",
    },
  },
  {
    set: "B",
    sat: SAT("90330"),
    partner: SAT("90062"),
    noticeAt: NOW - 26 * H,
    hex: "3b2e",
    eventKey: "EVT-B-0001",
    maneuvers: [
      { at: NOW - 60 * H, source: "PROVIDER-B" },
      { at: NOW - 22 * H, source: "PROVIDER-B" },
      { at: NOW - 4.1 * H, source: "PROVIDER-A" },
    ],
    concern: {
      channel: "ch-geo",
      author: "sample.delta",
      at: NOW - 20 * H,
      text: "90330 is closing on 90062 faster than yesterday. Can someone confirm the drift?",
    },
    reply: { author: "sample.echo", at: NOW - 19.6 * H, text: "Confirmed, drift rate up. Flagged to the duty officer." },
    mention: { channel: "ch-coord", author: "sample.bravo", at: NOW - 7 * H, text: "Partner cell asked for a 90330 update by end of shift." },
    timer: { label: "Closest approach 90330 / 90062", at: NOW + 3.17 * H },
    note: {
      author: "sample.lead",
      at: NOW - 6 * H,
      text: "Ask the owner-operator to confirm the planned burn before the next pass.",
    },
  },
];

export const noticeIdOf = (t: Target) => `n-${t.set.toLowerCase()}`;
export const notsoOf = (t: Target) => notsoId(t.hex, t.noticeAt);

const NO_FACTS: ManeuverFacts = {
  status: null, characterization: null, event_id: null, orig_object_id: null, event_end_time: null,
  report_time: null, delta_vel_kms: null, delta_pos_km: null, delta_mass_kg: null, total_burn_time_s: null,
  pre_geo_longitude_deg: null, post_geo_longitude_deg: null, pre_drift_rate_deg_day: null,
  post_drift_rate_deg_day: null, pre_apogee_km: null, post_apogee_km: null, pre_perigee_km: null,
  post_perigee_km: null, pre_inclination_deg: null, post_inclination_deg: null, pre_period_min: null,
  post_period_min: null, pre_semi_major_axis_km: null, post_semi_major_axis_km: null, pre_eccentricity: null,
  post_eccentricity: null, uct: null,
};

export interface WorldNotice {
  activity: ActivityNotice;
  detail: NotificationDetail;
  evaluation: AssistantEvaluation | null;
}

export interface WorldThreadLink {
  thread_id: string;
  event_key: string;
  decision: "confirmed" | "rejected";
}

export interface World {
  notices: WorldNotice[];
  maneuvers: Maneuver[];
  elsets: ActivityElset[];
  channels: MattermostChannel[];
  messages: Array<MattermostMessage & { root_id: string | null }>;
  links: WorldThreadLink[];
  timers: EventTimer[];
  notes: Array<StoryNote & { sat_no: number }>;
  shiftNotes: ShiftNote[];
}

const CHANNELS: Array<[string, string, string, boolean]> = [
  ["ch-ops", "sda-watch-floor", "SDA watch floor", true],
  ["ch-geo", "geo-cell", "GEO cell", true],
  ["ch-leo", "leo-cell", "LEO cell", true],
  ["ch-coord", "partner-coord", "Partner coordination", true],
  ["ch-social", "social", "Social", false],
];
const PEOPLE = ["sample.alpha", "sample.bravo", "sample.charlie", "sample.delta", "sample.echo"];

function notice(
  id: string,
  notso: string,
  eventClass: string,
  at: number,
  sats: string[],
  urgency: string,
  topAction: string | null,
  eventKey: string,
  status = "OPEN",
): WorldNotice {
  const activity: ActivityNotice = {
    id, notice: notso, event_class: eventClass, event_type: "other", status, region: null,
    udl_created_at: iso(at), sat_ids: sats, urgency, top_action: topAction,
  };
  const detail: NotificationDetail = {
    id, udl_id: `udl-${id}`, msg_type: "TACREP_NOTSO", data_mode: "TEST", source: "sample-source",
    classification_marking: "U", created_by: "sample.creator", orig_network: "sample-net",
    udl_created_at: iso(at), notso_identifier: notso, notice_id: notso, event_id: eventKey,
    event_class: eventClass, event_type: "other", status, subject: null,
    description: "Synthetic notice text for the hallway test. No real event is described.",
    region: null, notso_link: null, company_name: "Sample Analytics", publish_date: iso(at),
    effective_from: iso(at), effective_until: null, sat_no: null, sat_ids: sats,
    created_at: iso(at), updated_at: iso(at), raw: { msgBody: { Event_Class: eventClass } },
  };
  const pending = urgency === "pending";
  const evaluation: AssistantEvaluation | null = pending
    ? null
    : {
        id: `e-${id}`, notification_id: id,
        summary: urgency === "none" ? "Routine; no procedure trigger met." : "Procedure trigger met; action needed.",
        structured: {
          summary: urgency === "none" ? "Routine; no procedure trigger met." : "Procedure trigger met; action needed.",
          applicable_procedures: [],
          next_actions: topAction ? [{ action: topAction, urgency, deadline: null, rationale: "Synthetic." }] : [],
          open_questions: [],
        },
        procedures_used: [], model: "sample-model", error: null, withheld: false, evaluated_at: iso(at),
      };
  return { activity, detail, evaluation };
}

function maneuver(id: string, satNo: number, source: string, at: number, geo: boolean): Maneuver {
  return {
    id, udl_id: `udl-${id}`, data_mode: "TEST", source, classification_marking: "U", created_by: null,
    orig_network: null, origin: null, udl_created_at: iso(at), sat_no: satNo, event_start_time: iso(at),
    event_stop_time: null, mnvr_type: null, description: null, delta_v: null, thrust_magnitude: null,
    thrust_duration: null, propulsion_type: null, maneuver_status: null, responsible_nation: null,
    created_at: iso(at), updated_at: iso(at),
    facts: {
      ...NO_FACTS,
      status: rnd() > 0.5 ? "CONFIRMED" : "POSSIBLE",
      delta_vel_kms: Math.round(rnd() * 4000) / 1_000_000,
      post_geo_longitude_deg: geo ? Math.round((-180 + rnd() * 360) * 100) / 100 : null,
      post_drift_rate_deg_day: geo ? Math.round((rnd() - 0.5) * 40) / 100 : null,
    },
  };
}

function message(
  id: string,
  channel: string,
  author: string,
  at: number,
  text: string,
  rootId: string | null = null,
): MattermostMessage & { root_id: string | null } {
  const chan = CHANNELS.find((c) => c[0] === channel)!;
  return {
    id: `mm-${id}`, mm_post_id: id, channel_id: channel, channel_name: chan[2], user_id: author,
    user_display_name: author, posted_at: iso(at), message: text, post_type: null,
    created_at: iso(at), updated_at: iso(at), root_id: rootId,
  };
}

function timer(id: string, label: string, at: number, eventKey: string | null): EventTimer {
  return {
    id, event_key: eventKey, label, target_time: iso(at), pre_alert_minutes: 30, recurrence: "none",
    pre_alert_fired_at: null, dismissed_at: null, dismissed_by: null, created_by: USER.id,
    shift_date: iso(NOW).slice(0, 10), created_at: iso(NOW - 8 * H), updated_at: iso(NOW - 8 * H),
  };
}

const NOISE_LINES = [
  "%s burn seen, looks like routine E-W station keeping",
  "Drift rate on %s back inside the box",
  "Photometric change on %s, flagging for the next pass",
  "No new tasking from partner cell",
  "Owner-operator confirmed the planned manoeuvre for %s",
  "Closing the %s notice, burn complete",
  "%s drifted east 0.2 deg/day, watching",
  "Anyone seen the new elset for %s?",
  "Shift change brief at 18:00Z",
  "Sweep of the GEO belt done, 3 burns logged",
];

export function buildWorld(): World {
  seed = 20261117;
  const others = SATS.filter((s) => !TARGETS.some((t) => t.sat.id === s.id || t.partner.id === s.id));
  const notices: WorldNotice[] = [];
  TARGETS.forEach((t) => {
    notices.push(
      notice(
        noticeIdOf(t), notsoOf(t),
        `RPO / ${t.sat.name} (${t.sat.id}) vs ${t.partner.name} (${t.partner.id}) / ${t.sat.regime}`,
        t.noticeAt, [t.sat.id, t.partner.id], "high", "Brief the duty officer on the closest approach.", t.eventKey,
      ),
    );
  });
  const kinds = ["Maneuver", "Maneuver", "Maneuver", "Photometric Change", "Maneuver", "Cancelled Maneuver"];
  const urgencies = ["medium", "low", "none", "none", "low", "pending", "none", "medium"];
  for (let i = 0; i < 26; i++) {
    const s = pick(others);
    const at = NOW - (2 + rnd() * 116) * H;
    const hex = (0x1000 + i * 977).toString(16).slice(-4);
    const urgency = urgencies[i % urgencies.length];
    notices.push(
      notice(
        `n-${i}`, notsoId(hex, at), `${pick(kinds)} / ${s.name} (${s.id}) / ${s.regime}`, at, [s.id], urgency,
        urgency === "none" || urgency === "pending" ? null : "Confirm the station-keeping box with the owner-operator.",
        `EVT-${i}`, i % 9 === 4 ? "CLOSED" : "OPEN",
      ),
    );
  }
  notices.sort((a, b) => Date.parse(b.activity.udl_created_at!) - Date.parse(a.activity.udl_created_at!));

  const maneuvers: Maneuver[] = [];
  TARGETS.forEach((t) =>
    t.maneuvers.forEach((m, i) =>
      maneuvers.push(maneuver(`m-${t.set}${i}`, Number(t.sat.id), m.source, m.at, t.sat.regime === "GEO")),
    ),
  );
  for (let i = 0; i < 130; i++) {
    const s = rnd() > 0.3 ? pick(others) : null;
    const satNo = s ? Number(s.id) : 40000 + Math.floor(rnd() * 20000);
    maneuvers.push(
      maneuver(`m-${i}`, satNo, rnd() > 0.55 ? "PROVIDER-B" : "PROVIDER-A", NOW - rnd() * 118 * H, s ? s.regime === "GEO" : rnd() > 0.5),
    );
  }
  maneuvers.sort((a, b) => Date.parse(b.event_start_time!) - Date.parse(a.event_start_time!));

  const elsets: ActivityElset[] = SATS.map((s) => ({
    sat_no: Number(s.id), epoch: iso(NOW - (2 + rnd() * 10) * H),
    period: s.regime === "GEO" ? 1436.1 : 96.4, inclination: s.regime === "GEO" ? 0.08 : 97.6,
    eccentricity: 0.0004, apogee: s.regime === "GEO" ? 35800 : 560, perigee: s.regime === "GEO" ? 35772 : 548,
    mean_motion: null,
  }));

  const messages: World["messages"] = [];
  const links: WorldThreadLink[] = [];
  TARGETS.forEach((t) => {
    const root = `p-${t.set}-concern`;
    messages.push(message(root, t.concern.channel, t.concern.author, t.concern.at, t.concern.text));
    messages.push(message(`p-${t.set}-reply`, t.concern.channel, t.reply.author, t.reply.at, t.reply.text, root));
    messages.push(message(`p-${t.set}-mention`, t.mention.channel, t.mention.author, t.mention.at, t.mention.text));
    links.push({ thread_id: root, event_key: t.eventKey, decision: "confirmed" });
  });
  for (let i = 0; i < 70; i++) {
    const chan = CHANNELS[i % 5][0];
    const line = pick(NOISE_LINES).replace("%s", pick(others).id);
    messages.push(message(`p${i}`, chan, pick(PEOPLE), NOW - rnd() * 30 * H, line));
  }
  messages.sort((a, b) => Date.parse(b.posted_at) - Date.parse(a.posted_at));

  const channels: MattermostChannel[] = CHANNELS.map(([id, name, display, following], i) => {
    const own = messages.filter((m) => m.channel_id === id);
    const activity = Array.from({ length: 24 }, (_, h) =>
      own.filter((m) => Math.floor((NOW - Date.parse(m.posted_at)) / H) === 23 - h).length,
    );
    return {
      mm_channel_id: id, name, display_name: display, team_name: "sample-team", channel_type: "O",
      status: "open", archived: false, accessible: true, following, is_new: false, pulled: true,
      first_seen_at: iso(NOW - 900 * H), last_seen_at: iso(NOW), closed_at: null,
      message_count: own.length, last_message_at: own[0]?.posted_at ?? null, activity, new_since: i === 3 ? 2 : null,
    };
  });

  const timers: EventTimer[] = [
    ...TARGETS.map((t) => timer(`t-${t.set}`, t.timer.label, t.timer.at, t.eventKey)),
    timer("t-1", "Next pass 90157 photometry", NOW + 0.8 * H, null),
    timer("t-2", "Shift change brief", NOW + 5.5 * H, null),
    timer("t-3", "Partner cell sync", NOW + 1.6 * H, null),
  ];

  const notes: World["notes"] = [
    ...TARGETS.map((t) => ({
      id: `note-${t.set}`, author_id: "u-lead", author: t.note.author, text: t.note.text,
      created_at: iso(t.note.at), sat_no: Number(t.sat.id),
    })),
    { id: "note-x1", author_id: "u-lead", author: "sample.lead", text: "Routine. Nothing to hand over.", created_at: iso(NOW - 9 * H), sat_no: 90157 },
  ];

  const today = iso(NOW).slice(0, 10);
  const shiftNotes: ShiftNote[] = [
    "Sweep of the GEO belt, 3 burns logged.",
    "Partner cell asked for updates on the open RPOs.",
    "Elsets refreshed, no gaps.",
  ].map((text, i) => ({
    id: `s-${i}`, author_id: USER.id, shift_date: today, raw_text: text, polished_text: null,
    polish_error: null, model: null, created_at: iso(NOW - (7 - i * 2) * H), updated_at: iso(NOW - (7 - i * 2) * H),
  }));

  return { notices, maneuvers, elsets, channels, messages, links, timers, notes, shiftNotes };
}

export const SAT_NAMES: ReadonlyMap<string, string> = new Map(SATS.map((s) => [s.id, s.name]));
