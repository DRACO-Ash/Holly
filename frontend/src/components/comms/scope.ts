import type { MattermostChannel } from "../../types";

// Which channels the feed shows: the followed ones, every one, or those picked.
export type FeedScope =
  | { kind: "following" }
  | { kind: "all" }
  | { kind: "chosen"; ids: readonly string[] };

// What the feed asks the server for: the channels picked, every channel, or the followed open
// ones by the server's own follow list, so no list of ids grows past the 200 it accepts. Null
// when the scope can hold no message.
export interface ScopeQuery {
  channel_id?: string[];
  followed?: true;
}

export function scopeQuery(
  scope: FeedScope,
  channels: readonly MattermostChannel[],
): ScopeQuery | null {
  if (scope.kind === "all") return {};
  if (scope.kind === "chosen") return { channel_id: [...scope.ids] };
  // Before the first sweep Holly knows no channel and pulls those MATTERMOST_CHANNEL_IDS names:
  // every message it holds is from a channel it follows.
  if (channels.length === 0) return {};
  return channels.some((c) => c.following && c.status === "open") ? { followed: true } : null;
}

// The scope after a channel is picked: added to those chosen, or taken out of them, back to the
// followed channels when none is left.
export function toggled(scope: FeedScope, channelId: string): FeedScope {
  const ids = scope.kind === "chosen" ? scope.ids : [];
  const next = ids.includes(channelId) ? ids.filter((id) => id !== channelId) : [...ids, channelId];
  return next.length ? { kind: "chosen", ids: next } : { kind: "following" };
}
