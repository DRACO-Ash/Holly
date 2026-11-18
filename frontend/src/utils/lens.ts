// The Object Lens's reading of Holly's data: which pieces of text name an object or a notice,
// the lens's items and lanes, and the Find palette's matches. Pure functions, so each rule is
// tested on its own.
import type { ActivityNotice, HandoverObject, HandoverStory } from "../types";
import { ENTRY_LABELS, storyEntries, type EntryType } from "./handover";

export type LinkPart =
  | { kind: "text"; text: string; at: number }
  | { kind: "sat"; id: string; at: number }
  | { kind: "notice"; notso: string; at: number };

// A NOTSO number as Holly's notices write it (7afc_19Oct-1726Z), or a run of digits.
const TOKEN = /([0-9A-Za-z]{4}_\d{1,2}[A-Z][a-z]{2}-\d{4}Z)|(\d+)/g;

// Splits text into plain runs and links. A run of digits links only when, whole, it is the
// catalogue number of an object in the window, so a clock time, a distance or a longer number
// stays text; a NOTSO number links only when Holly holds that notice.
export function linkParts(
  text: string,
  isObject: (id: string) => boolean,
  isNotice: (notso: string) => boolean,
): LinkPart[] {
  const parts: LinkPart[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    const [whole, notso, digits] = m;
    const link: LinkPart | null =
      (notso && isNotice(notso) && { kind: "notice", notso, at }) ||
      (digits && isObject(digits) && { kind: "sat", id: digits, at }) ||
      null;
    if (!link) continue;
    if (at > last) parts.push({ kind: "text", text: text.slice(last, at), at: last });
    parts.push(link);
    last = at + whole.length;
  }
  if (last < text.length) parts.push({ kind: "text", text: text.slice(last), at: last });
  return parts;
}

// "2:49:07" until the moment; never negative.
export function countdown(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${Math.floor(s / 3600)}:${mm}:${ss}`;
}

// Where a time sits on a strip from start to end, as a percentage clamped to the strip.
export function stripX(time: number, start: number, end: number): number {
  if (end <= start) return 0;
  return Math.min(100, Math.max(0, ((time - start) / (end - start)) * 100));
}

export type LensTone = EntryType | "suggested";

export interface LensItem {
  key: string;
  at: number | null;
  tone: LensTone;
  tag: string;
  title: string;
  detail: string | null;
  source: string;
}

// Everything the story holds, newest first: the Handover story's entries, and each suggested
// thread marked as not confirmed.
export function lensItems(story: HandoverStory): LensItem[] {
  const entries: LensItem[] = storyEntries(story).map((e) => ({
    key: e.key,
    at: e.at,
    tone: e.type,
    tag: ENTRY_LABELS[e.type],
    title: e.title,
    detail: e.detail,
    source: e.source,
  }));
  const suggested: LensItem[] = story.suggestions.map((s) => {
    const more = s.matching_posts > 1 ? ` · ${s.matching_posts} matching` : "";
    return {
      key: `suggested-${s.thread_id}`,
      at: Date.parse(s.first_post.posted_at),
      tone: "suggested",
      tag: "Chat",
      title: `${s.first_post.author ?? "Unknown author"} in #${s.channel_name ?? "channel"}`,
      detail: s.first_post.message,
      source: `Mattermost · suggested thread, not confirmed${more}`,
    };
  });
  return [...entries, ...suggested].sort((a, b) => (b.at ?? -Infinity) - (a.at ?? -Infinity));
}

// Items after the analyst last looked, and the rest. An item with no time is never new.
export function splitBySeen(items: LensItem[], seenAt: number): [LensItem[], LensItem[]] {
  const fresh = items.filter((i) => i.at !== null && i.at > seenAt);
  const earlier = items.filter((i) => !(i.at !== null && i.at > seenAt));
  return [fresh, earlier];
}

const URGENCY_ORDER = ["high", "medium", "low"] as const;

// The most urgent assistant urgency among the open notices, if any.
export function topUrgency(notices: readonly ActivityNotice[]): string | null {
  const open = notices.filter((n) => n.status === "OPEN");
  return URGENCY_ORDER.find((u) => open.some((n) => n.urgency === u)) ?? null;
}

export function noticesOf(notices: readonly ActivityNotice[], satNo: number): ActivityNotice[] {
  const id = String(satNo);
  return notices.filter((n) => n.sat_ids.includes(id));
}

// Objects a Find query names: by catalogue number, name or kind, most recent first, up to limit.
export function matchObjects(
  objects: Iterable<HandoverObject>,
  query: string,
  limit = 4,
): HandoverObject[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return [...objects]
    .filter(
      (o) =>
        String(o.sat_no).includes(q) ||
        (o.name ?? "").toLowerCase().includes(q) ||
        o.kinds.some((k) => k.toLowerCase().includes(q)),
    )
    .sort(
      (a, b) =>
        Date.parse(b.latest_at ?? "") - Date.parse(a.latest_at ?? "") || a.sat_no - b.sat_no,
    )
    .slice(0, limit);
}

// Notices a Find query names: by NOTSO number or event class.
export function matchNotices(
  notices: readonly ActivityNotice[],
  query: string,
  limit = 3,
): ActivityNotice[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return notices
    .filter(
      (n) =>
        (n.notice ?? "").toLowerCase().includes(q) ||
        (n.event_class ?? "").toLowerCase().includes(q),
    )
    .slice(0, limit);
}

// The first catalogue number in a message that names a known object, if any.
export function firstObjectIn(text: string, isObject: (id: string) => boolean): string | null {
  return (text.match(/\d+/g) ?? []).find(isObject) ?? null;
}
