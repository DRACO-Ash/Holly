import type { MattermostSweepResult } from "../types";

// What the Comms page works out for itself: each channel's hue, how a time reads, which part of
// a message matches a search, and what this browser remembers between visits. Times are UTC
// throughout, as on every other page of Holly.

// The channel hues the theme defines (--channel-1 to --channel-6 in tokens.css).
export const CHANNEL_HUES = 6;

// Each channel takes the next hue in the order Holly first found them, so the first six never
// share one, and a channel keeps its hue as later ones arrive.
export function channelHues(
  channels: Iterable<{ mm_channel_id: string; first_seen_at: string }>,
): Map<string, number> {
  const ordered = [...channels].sort(
    (a, b) =>
      a.first_seen_at.localeCompare(b.first_seen_at) ||
      a.mm_channel_id.localeCompare(b.mm_channel_id),
  );
  return new Map(ordered.map((c, index) => [c.mm_channel_id, (index % CHANNEL_HUES) + 1]));
}

// A channel's hue, or, for one Holly holds messages from but no longer lists, a hue from its id
// that is the same every time.
export function channelHue(channelId: string, hues: ReadonlyMap<string, number>): number {
  const assigned = hues.get(channelId);
  if (assigned !== undefined) return assigned;
  let hash = 0;
  for (const char of channelId) hash = (hash * 31 + (char.codePointAt(0) ?? 0)) >>> 0;
  return (hash % CHANNEL_HUES) + 1;
}

export function channelLabel(channel: { display_name: string | null; name: string }): string {
  return channel.display_name || channel.name;
}

const DAY_MS = 86_400_000;

function utcDay(value: Date): number {
  return Math.floor(value.getTime() / DAY_MS);
}

// "Today", "Yesterday", or the date: the heading over a day's messages.
export function dayLabel(iso: string, now: Date = new Date()): string {
  const at = new Date(iso);
  const days = utcDay(now) - utcDay(at);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return at.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function sameUtcDay(a: string, b: string): boolean {
  return utcDay(new Date(a)) === utcDay(new Date(b));
}

// "14:05", in UTC.
export function timeOfDay(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16);
}

// "2026-10-20 14:05:09 UTC", for a time's title.
export function fullTime(iso: string): string {
  return `${new Date(iso).toISOString().replace("T", " ").slice(0, 19)} UTC`;
}

// "every minute", "every 5 minutes", "every 90 seconds": how often Holly sweeps.
export function everyLabel(seconds: number): string {
  if (seconds === 60) return "every minute";
  if (seconds % 60 === 0) return `every ${seconds / 60} minutes`;
  return `every ${seconds} seconds`;
}

// Where `iso` falls among the last 24 whole UTC hours, counted from the left edge of an activity
// trace (0) to its right edge (24), or null when it falls outside them.
export function hourPosition(iso: string | null, now: Date, hours = 24): number | null {
  if (!iso) return null;
  const hourMs = 3_600_000;
  const left = (Math.floor(now.getTime() / hourMs) - (hours - 1)) * hourMs;
  const position = (Date.parse(iso) - left) / hourMs;
  return position >= 0 && position <= hours ? position : null;
}

// Why a closed channel is closed: archived in Mattermost, or the word CLOSED in its name.
export function closedReason(channel: { archived: boolean }): string {
  return channel.archived ? "Archived" : "Closed by name";
}

// "just now", "4 min ago", "3 h ago", "2 d ago".
export function ago(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

// The message split around each match of the search, in any case, so the matches can be marked.
export function matchParts(text: string, search: string): { text: string; match: boolean }[] {
  const needle = search.trim().toLowerCase();
  if (!needle) return [{ text, match: false }];
  const parts: { text: string; match: boolean }[] = [];
  const lower = text.toLowerCase();
  let from = 0;
  for (let at = lower.indexOf(needle); at !== -1; at = lower.indexOf(needle, from)) {
    if (at > from) parts.push({ text: text.slice(from, at), match: false });
    parts.push({ text: text.slice(at, at + needle.length), match: true });
    from = at + needle.length;
  }
  if (from < text.length) parts.push({ text: text.slice(from), match: false });
  return parts;
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

// What a sweep found, in a sentence.
export function sweepSummary(result: MattermostSweepResult): string {
  const changes = [
    result.new > 0 && `${result.new} new`,
    result.closed > 0 && `${result.closed} closed`,
    result.reopened > 0 && `${result.reopened} reopened`,
    result.lost > 0 && `${result.lost} the bot can no longer read`,
  ].filter(Boolean);
  const found = `Found ${plural(result.found, "channel")}${changes.length ? `: ${changes.join(", ")}` : ""}.`;
  const pulled = `Pulled ${plural(result.inserted, "new message")} from ${plural(result.channels_polled, "channel")}`;
  const failed = result.channels_failed > 0 ? `; ${result.channels_failed} could not be read` : "";
  return `${found} ${pulled}${failed}.`;
}

// What this browser remembers: the layout chosen, and when each user last looked. A blocked or
// full store remembers nothing, and the page works as on a first visit.
export type CommsView = "feed" | "channels";
const VIEW_KEY = "holly.comms.view";
const SEEN_PREFIX = "holly.comms.seen.";

function store(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

export function loadView(): CommsView {
  try {
    return store()?.getItem(VIEW_KEY) === "channels" ? "channels" : "feed";
  } catch {
    return "feed";
  }
}

export function saveView(view: CommsView): void {
  try {
    store()?.setItem(VIEW_KEY, view);
  } catch {
    // Remembered for this page only.
  }
}

export function loadLastSeen(userId: string): string | null {
  try {
    const value = store()?.getItem(SEEN_PREFIX + userId) ?? null;
    return value && !Number.isNaN(Date.parse(value)) ? value : null;
  } catch {
    return null;
  }
}

export function saveLastSeen(userId: string, iso: string): void {
  try {
    store()?.setItem(SEEN_PREFIX + userId, iso);
  } catch {
    // Remembered for this page only.
  }
}
