import type { MattermostChannel } from "../../types";

// Which channels the feed shows: the followed ones, every one, or those picked.
export type FeedScope =
  | { kind: "following" }
  | { kind: "all" }
  | { kind: "chosen"; ids: readonly string[] };

// The channel ids to ask for, or undefined for every channel. An empty list asks for none.
export function scopeIds(
  scope: FeedScope,
  channels: readonly MattermostChannel[],
): string[] | undefined {
  if (scope.kind === "all") return undefined;
  if (scope.kind === "chosen") return [...scope.ids];
  // Before the first sweep Holly knows no channel and pulls those MATTERMOST_CHANNEL_IDS names:
  // every message it holds is from a channel it follows.
  if (channels.length === 0) return undefined;
  return channels.filter((c) => c.following && c.status === "open").map((c) => c.mm_channel_id);
}

// The scope after a channel is picked: added to those chosen, or taken out of them, back to the
// followed channels when none is left.
export function toggled(scope: FeedScope, channelId: string): FeedScope {
  const ids = scope.kind === "chosen" ? scope.ids : [];
  const next = ids.includes(channelId) ? ids.filter((id) => id !== channelId) : [...ids, channelId];
  return next.length ? { kind: "chosen", ids: next } : { kind: "following" };
}
