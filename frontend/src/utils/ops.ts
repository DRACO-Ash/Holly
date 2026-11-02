// The console views' reading of the activity overview: what kind of event a notice reports and
// about which objects, each satellite's orbital regime, the satellites a notice and a maneuver
// share, and the times and counts the views draw. Every input is untrusted text from UDL; a
// value that does not fit a pattern here is shown as written, never guessed at.
import type { ActivityElset, ActivityManeuver, ActivityNotice } from "../types";

export type EventKind = "maneuver" | "photometric" | "rpo" | "launch" | "cancelled" | "other";
export const EVENT_KINDS: readonly EventKind[] = [
  "maneuver",
  "photometric",
  "rpo",
  "launch",
  "cancelled",
  "other",
];
export const KIND_LABELS: Readonly<Record<EventKind, string>> = {
  maneuver: "Maneuver",
  photometric: "Photometric change",
  rpo: "RPO",
  launch: "Launch",
  cancelled: "Cancelled",
  other: "Other",
};

export const REGIMES = ["LEO", "MEO", "HEO", "GEO", "XGEO"] as const;
export type Regime = (typeof REGIMES)[number];
const REGIME_WORDS: ReadonlySet<string> = new Set(REGIMES);

export interface EventObject {
  name: string;
  // The NORAD catalogue number the notice gives in brackets after the name, if any.
  id: string | null;
}

export interface ParsedEvent {
  kind: EventKind;
  // The kind as the notice writes it, spaces tidied: "Photometric change", "Cancelled Maneuver".
  kindLabel: string;
  objects: EventObject[];
  regime: Regime | null;
}

function tidy(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(" ");
}

export function eventKind(label: string): EventKind {
  const lower = label.toLowerCase();
  if (lower.startsWith("cancel")) return "cancelled";
  if (lower.includes("maneuver") || lower.includes("manoeuvre")) return "maneuver";
  if (lower.includes("photometric")) return "photometric";
  if (lower.includes("rpo") || lower.includes("proximity") || lower.includes("rendezvous")) {
    return "rpo";
  }
  if (lower.includes("launch")) return "launch";
  return "other";
}

// "CHINASAT 3B (64062)" to its name and number. The number must be digits in the last brackets.
export function eventObject(text: string): EventObject {
  const trimmed = tidy(text);
  const open = trimmed.lastIndexOf("(");
  if (open !== -1 && trimmed.endsWith(")")) {
    const inside = trimmed.slice(open + 1, -1).trim();
    if (/^\d{1,9}$/.test(inside)) {
      const name = trimmed.slice(0, open).trim();
      return { name: name || inside, id: inside };
    }
  }
  return { name: trimmed, id: null };
}

// "Maneuver / CHINASAT 3B (64062) / GEO": the kind, the objects and the regime. A part that does
// not fit is kept as an object's name, so nothing the notice says is dropped.
export function parseEventClass(eventClass: string | null | undefined): ParsedEvent | null {
  if (!eventClass) return null;
  const parts = eventClass
    .split("/")
    .map(tidy)
    .filter((part) => part !== "");
  if (parts.length === 0) return null;
  const kindLabel = parts[0];
  let rest = parts.slice(1);
  const last = rest.length > 0 ? rest[rest.length - 1].toUpperCase() : undefined;
  const regime = last !== undefined && REGIME_WORDS.has(last) ? (last as Regime) : null;
  if (regime) rest = rest.slice(0, -1);
  const objects = rest
    .flatMap((part) => part.split(/\svs\.?\s/i))
    .map(eventObject)
    .filter((object) => object.name !== "");
  return { kind: eventKind(kindLabel), kindLabel, objects, regime };
}

// The orbital regime of an element set: highly elliptical first, then by period in minutes.
// Inference from the element set, never a fact the notice states.
export function regimeFromElset(elset: ActivityElset | undefined): Regime | null {
  if (!elset) return null;
  if (elset.eccentricity !== null && elset.eccentricity >= 0.25) return "HEO";
  let period = elset.period;
  if (period === null && elset.mean_motion !== null && elset.mean_motion > 0) {
    period = 1440 / elset.mean_motion;
  }
  if (period === null || !Number.isFinite(period) || period <= 0) return null;
  if (period < 128) return "LEO";
  if (period < 1400) return "MEO";
  if (period <= 1480) return "GEO";
  return "XGEO";
}

export interface Satellite {
  id: string;
  // The name a notice in the window gives it, if any.
  name: string | null;
  regime: Regime | null;
  // Where the regime came from: a notice's own words, or the latest element set.
  regimeFrom: "notice" | "elset" | null;
  elset: ActivityElset | null;
}

// Every satellite the window names, with what the notices and element sets say about it.
export function satelliteDirectory(
  notices: readonly ActivityNotice[],
  maneuvers: readonly ActivityManeuver[],
  elsets: readonly ActivityElset[],
): Map<string, Satellite> {
  const directory = new Map<string, Satellite>();
  const entry = (id: string): Satellite => {
    let found = directory.get(id);
    if (!found) {
      found = { id, name: null, regime: null, regimeFrom: null, elset: null };
      directory.set(id, found);
    }
    return found;
  };
  for (const notice of notices) {
    const parsed = parseEventClass(notice.event_class);
    for (const id of notice.sat_ids) entry(id);
    for (const object of parsed?.objects ?? []) {
      if (object.id === null) continue;
      const satellite = entry(object.id);
      satellite.name ??= object.name;
      // The regime a notice states belongs to its first object, the one it is about.
      if (parsed?.regime && object === parsed.objects[0] && satellite.regimeFrom === null) {
        satellite.regime = parsed.regime;
        satellite.regimeFrom = "notice";
      }
    }
  }
  for (const maneuver of maneuvers) {
    if (maneuver.sat_no !== null) entry(String(maneuver.sat_no));
  }
  for (const elset of elsets) {
    const satellite = entry(String(elset.sat_no));
    satellite.elset = elset;
    const regime = regimeFromElset(elset);
    if (regime && satellite.regimeFrom !== "notice") {
      satellite.regime = regime;
      satellite.regimeFrom = "elset";
    }
  }
  return directory;
}

export function maneuverStart(maneuver: ActivityManeuver): number | null {
  return timeOf(maneuver.event_start_time);
}

export function timeOf(value: string | null | undefined): number | null {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

export interface ManeuverGroup {
  // The record shown for the group: the first of its copies in the order given.
  maneuver: ActivityManeuver;
  // How many records the provider published for the same satellite, start and source.
  copies: number;
  ids: string[];
}

// Records for the same satellite, start time and source are one maneuver published more than
// once; they are folded into one row that says how many copies there were.
export function foldDuplicates(maneuvers: readonly ActivityManeuver[]): ManeuverGroup[] {
  const groups = new Map<string, ManeuverGroup>();
  const order: ManeuverGroup[] = [];
  for (const maneuver of maneuvers) {
    const key = [maneuver.sat_no ?? "?", maneuver.event_start_time ?? "?", maneuver.source ?? "?"]
      .map(String)
      .join("|");
    const found = groups.get(key);
    if (found) {
      found.copies += 1;
      found.ids.push(maneuver.id);
    } else {
      const group = { maneuver, copies: 1, ids: [maneuver.id] };
      groups.set(key, group);
      order.push(group);
    }
  }
  return order;
}

// The maneuvers on each satellite, and the notices naming each satellite.
export function bySatellite<T>(
  items: readonly T[],
  idsOf: (item: T) => readonly string[],
): Map<string, T[]> {
  const index = new Map<string, T[]>();
  for (const item of items) {
    for (const id of new Set(idsOf(item))) {
      const list = index.get(id);
      if (list) list.push(item);
      else index.set(id, [item]);
    }
  }
  return index;
}

export const maneuverSatIds = (m: ActivityManeuver): string[] =>
  m.sat_no === null ? [] : [String(m.sat_no)];
export const noticeSatIds = (n: ActivityNotice): string[] => n.sat_ids;

// Counts of `times` in `bins` equal slices of [start, end]; a time outside is not counted.
export function histogram(
  times: readonly number[],
  start: number,
  end: number,
  bins: number,
): number[] {
  const counts = new Array<number>(bins).fill(0);
  const span = end - start;
  if (span <= 0 || bins <= 0) return counts;
  for (const time of times) {
    if (time < start || time > end) continue;
    const bin = Math.min(bins - 1, Math.floor(((time - start) / span) * bins));
    counts[bin] += 1;
  }
  return counts;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

// "just now", "12 min ago", "3 h ago", "2 d ago", or "in 5 min" for a time ahead.
export function relativeTime(time: number, now: number): string {
  const delta = now - time;
  const ahead = delta < 0;
  const size = Math.abs(delta);
  let text: string;
  if (size < MINUTE) return "just now";
  if (size < HOUR) text = `${Math.floor(size / MINUTE)} min`;
  else if (size < DAY) text = `${Math.floor(size / HOUR)} h`;
  else text = `${Math.floor(size / DAY)} d`;
  return ahead ? `in ${text}` : `${text} ago`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (value: number) => String(value).padStart(2, "0");

// "17:52Z", "17:52:54Z", "02 Nov", "02 Nov 17:52Z", all in UTC.
export const clockUtc = (time: number) => {
  const d = new Date(time);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}Z`;
};
export const clockSecondsUtc = (time: number) => {
  const d = new Date(time);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}Z`;
};
export const dayUtc = (time: number) => {
  const d = new Date(time);
  return `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]}`;
};
export const stampUtc = (time: number) => `${dayUtc(time)} ${clockUtc(time)}`;
export const fullUtc = (time: number) =>
  new Date(time).toISOString().replace("T", " ").slice(0, 19) + "Z";

export const startOfDayUtc = (time: number) => Math.floor(time / DAY) * DAY;

// "Today", "Yesterday", or "Fri 31 Oct", for a list grouped by UTC day.
export function dayHeading(time: number, now: number): string {
  const days = Math.round((startOfDayUtc(now) - startOfDayUtc(time)) / DAY);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${WEEKDAYS[new Date(time).getUTCDay()]} ${dayUtc(time)}`;
}

// Items in groups by UTC day, newest day first, each group keeping the order given.
export function groupByDay<T>(
  items: readonly T[],
  timeOfItem: (item: T) => number | null,
): { day: number | null; items: T[] }[] {
  const groups = new Map<number | null, T[]>();
  for (const item of items) {
    const time = timeOfItem(item);
    const day = time === null ? null : startOfDayUtc(time);
    const list = groups.get(day);
    if (list) list.push(item);
    else groups.set(day, [item]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (b ?? -Infinity) - (a ?? -Infinity))
    .map(([day, list]) => ({ day, items: list }));
}

export interface ObjectActivity {
  id: string;
  notices: ActivityNotice[];
  maneuvers: ManeuverGroup[];
  times: number[];
}

// The satellites with the most events in the window, most first, the newest breaking ties.
export function mostActive(
  notices: readonly ActivityNotice[],
  groups: readonly ManeuverGroup[],
  limit: number,
): ObjectActivity[] {
  const table = new Map<string, ObjectActivity>();
  const row = (id: string) => {
    let found = table.get(id);
    if (!found) {
      found = { id, notices: [], maneuvers: [], times: [] };
      table.set(id, found);
    }
    return found;
  };
  for (const notice of notices) {
    const time = timeOf(notice.udl_created_at);
    for (const id of new Set(notice.sat_ids)) {
      const entry = row(id);
      entry.notices.push(notice);
      if (time !== null) entry.times.push(time);
    }
  }
  for (const group of groups) {
    const id = group.maneuver.sat_no;
    if (id === null) continue;
    const entry = row(String(id));
    entry.maneuvers.push(group);
    const time = maneuverStart(group.maneuver);
    if (time !== null) entry.times.push(time);
  }
  const score = (entry: ObjectActivity) => entry.notices.length + entry.maneuvers.length;
  const latest = (entry: ObjectActivity) => Math.max(-Infinity, ...entry.times);
  return [...table.values()]
    .sort((a, b) => score(b) - score(a) || latest(b) - latest(a))
    .slice(0, limit);
}

export const URGENCY_ORDER = ["high", "medium", "low", "none", "pending"] as const;
export type Urgency = (typeof URGENCY_ORDER)[number];
export function urgencyOf(value: string): Urgency {
  const lower = value.toLowerCase();
  return (URGENCY_ORDER as readonly string[]).includes(lower) ? (lower as Urgency) : "none";
}
export const URGENCY_LABELS: Readonly<Record<Urgency, string>> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "Info only",
  pending: "Awaiting analysis",
};

// The source providers present, alphabetically, each given one of `slots` hue slots in turn,
// so two providers in one view never share a hue until there are more than `slots` of them.
export function sourceSlots(
  sources: readonly (string | null)[],
  slots: number,
): Map<string, number> {
  const names = [...new Set(sources.map((s) => s ?? "Unknown"))].sort((a, b) => a.localeCompare(b));
  return new Map(names.map((name, index) => [name, (index % slots) + 1]));
}

// Delta-v for display in m/s, from the UDL km/s figure when the record carries one, else from
// the typed column, which the original dashboard labelled m/s. Null when neither is present.
export function deltaVMetresPerSecond(maneuver: ActivityManeuver): number | null {
  if (maneuver.facts.delta_vel_kms !== null) return maneuver.facts.delta_vel_kms * 1000;
  return maneuver.delta_v;
}

export function maneuverEnd(maneuver: ActivityManeuver): number | null {
  return timeOf(maneuver.facts.event_end_time ?? maneuver.event_stop_time);
}

// "42 s", "12 min", "3 h 05 min": a burn's length.
export function duration(ms: number): string {
  if (ms < MINUTE) return `${Math.max(0, Math.round(ms / 1000))} s`;
  if (ms < HOUR) return `${Math.round(ms / MINUTE)} min`;
  const hours = Math.floor(ms / HOUR);
  return `${hours} h ${pad(Math.round((ms - hours * HOUR) / MINUTE))} min`;
}

// A notice's or maneuver's text, lower-cased, for the search box.
export function searchText(parts: readonly (string | number | null | undefined)[]): string {
  return parts
    .filter((part) => part !== null && part !== undefined)
    .join(" ")
    .toLowerCase();
}
