export interface MattermostMessage {
  id: string;
  mm_post_id: string;
  channel_id: string;
  channel_name: string | null;
  user_id: string;
  user_display_name: string | null;
  posted_at: string;
  message: string;
  post_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface MattermostMessagePage {
  items: MattermostMessage[];
  total: number;
  limit: number;
  offset: number;
}

export interface MattermostListQuery {
  // One channel or several; none means every channel.
  channel_id?: string | string[];
  user_id?: string;
  posted_at_gte?: string;
  // Text the message holds, in any case.
  q?: string;
  limit?: number;
  offset?: number;
}

// A channel the bot can read, as Holly's latest sweep found it.
export interface MattermostChannel {
  mm_channel_id: string;
  name: string;
  display_name: string | null;
  team_name: string | null;
  channel_type: string;
  status: "open" | "closed";
  archived: boolean;
  accessible: boolean;
  following: boolean;
  is_new: boolean;
  // Followed, open and readable: Holly pulls its messages.
  pulled: boolean;
  first_seen_at: string;
  last_seen_at: string;
  closed_at: string | null;
  message_count: number;
  last_message_at: string | null;
  // Messages in each of the last 24 hours, oldest first.
  activity: number[];
  // Messages Holly holds posted after the user's last visit, when the page asked about one.
  new_since: number | null;
}

export interface MattermostSweep {
  last_at: string | null;
  ok: boolean | null;
  problem: string | null;
  bot: string | null;
  interval_seconds: number;
}

export interface MattermostChannels {
  channels: MattermostChannel[];
  sweep: MattermostSweep;
}

export interface MattermostSweepResult {
  ok: boolean | null;
  problem: string | null;
  found: number;
  new: number;
  closed: number;
  reopened: number;
  lost: number;
  channels_polled: number;
  channels_failed: number;
  inserted: number;
}
