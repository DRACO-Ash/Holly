// The Handover tab's reading of an object's story: every item Holly holds about the object, in
// time order, each with where it came from. Every value is untrusted text from UDL or chat; it is
// shown as written, never guessed at.
import type { HandoverStory, StoryManeuver } from "../types";
import { eventKind, type EventKind } from "./ops";

export type EntryType = "notice" | "maneuver" | "post" | "note";

export interface StoryEntry {
  key: string;
  type: EntryType;
  at: number | null;
  title: string;
  detail: string | null;
  // Where it came from, as the source chip shows it.
  source: string;
  kind: EventKind | null;
  author: string | null;
}

const time = (value: string | null): number | null => {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const fixed = (value: number, digits: number) =>
  value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

function change(before: number | null, after: number | null, unit: string, digits: number) {
  if (before === null || after === null) return null;
  const delta = after - before;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${fixed(delta, digits)} ${unit}`;
}

// The changes a provider's record states, in words: what the handover needs to compare.
export function maneuverChanges(m: StoryManeuver): string[] {
  const f = m.facts;
  const parts: string[] = [];
  const period = change(f.pre_period_min, f.post_period_min, "min", 3);
  if (period) parts.push(`period ${period}`);
  const apogee = change(f.pre_apogee_km, f.post_apogee_km, "km", 1);
  if (apogee) parts.push(`apogee ${apogee}`);
  const perigee = change(f.pre_perigee_km, f.post_perigee_km, "km", 1);
  if (perigee) parts.push(`perigee ${perigee}`);
  if (f.delta_vel_kms !== null) parts.push(`Δv ${fixed(f.delta_vel_kms * 1000, 3)} m/s`);
  if (f.post_geo_longitude_deg !== null) {
    parts.push(`now at ${fixed(f.post_geo_longitude_deg, 2)}°`);
  }
  return parts;
}

function noticeEntries(story: HandoverStory): StoryEntry[] {
  return story.notices.map((n) => ({
    key: `notice-${n.id}`,
    type: "notice",
    at: time(n.udl_created_at),
    title: `${n.kind ?? "Notice"} · ${n.notice ?? "no NOTSO number"}`,
    detail: [n.status, n.event_class].filter(Boolean).join(" · ") || null,
    source: n.udl_id ? `NOTSO · UDL ${n.udl_id}` : "NOTSO · UDL",
    kind: n.kind ? eventKind(n.kind) : null,
    author: null,
  }));
}

function maneuverEntries(story: HandoverStory): StoryEntry[] {
  return story.maneuvers.map((m) => {
    const changes = maneuverChanges(m);
    return {
      key: `maneuver-${m.id}`,
      type: "maneuver",
      at: time(m.event_start_time),
      title: `Maneuver record · ${m.source ?? "provider not named"}`,
      detail: changes.length > 0 ? changes.join(", ") : m.maneuver_status,
      source: m.udl_id ? `Provider record · UDL ${m.udl_id}` : "Provider record · UDL",
      kind: "maneuver",
      author: null,
    };
  });
}

// Each post once, even if a thread were ever told twice.
function threadEntries(story: HandoverStory): StoryEntry[] {
  const seen = new Set<string>();
  const entries: StoryEntry[] = [];
  for (const t of story.threads) {
    for (const p of t.posts) {
      if (seen.has(p.post_id)) continue;
      seen.add(p.post_id);
      entries.push({
        key: `post-${p.post_id}`,
        type: "post",
        at: time(p.posted_at),
        title: p.author ?? "Unknown author",
        detail: p.message,
        source: `Mattermost · ${t.channel_name ?? "channel"} · confirmed thread`,
        kind: null,
        author: p.author,
      });
    }
  }
  return entries;
}

function noteEntries(story: HandoverStory): StoryEntry[] {
  return story.notes.map((n) => ({
    key: `note-${n.id}`,
    type: "note",
    at: time(n.created_at),
    title: `Note · ${n.author ?? "former user"}`,
    detail: n.text,
    source: "Analyst note",
    kind: null,
    author: n.author,
  }));
}

// Oldest first; an item with no time goes last, and two with none keep their order.
function byTime(a: StoryEntry, b: StoryEntry): number {
  if (a.at === b.at) return 0;
  if (a.at === null) return 1;
  if (b.at === null) return -1;
  return a.at - b.at;
}

// Every item, oldest first; an item with no time goes last.
export function storyEntries(story: HandoverStory): StoryEntry[] {
  return [
    ...noticeEntries(story),
    ...maneuverEntries(story),
    ...threadEntries(story),
    ...noteEntries(story),
  ].sort(byTime);
}

export const ENTRY_LABELS: Readonly<Record<EntryType, string>> = {
  notice: "NOTSO",
  maneuver: "Provider",
  post: "Chat",
  note: "Note",
};
