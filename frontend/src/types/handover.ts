// The Handover tab: objects with live events, and one object's story with where each item came
// from (src/app/schemas/handover.py).
import type { ManeuverFacts } from "./maneuver";

export interface HandoverObject {
  sat_no: number;
  name: string | null;
  kinds: string[];
  latest_at: string | null;
  events: number;
  maneuvers: number;
}

export interface HandoverObjectList {
  window_hours: number;
  window_start: string;
  generated_at: string;
  objects: HandoverObject[];
  truncated: boolean;
}

export interface StoryNotice {
  id: string;
  event_key: string;
  notice: string | null;
  event_class: string | null;
  kind: string | null;
  status: string | null;
  udl_created_at: string | null;
  source: string | null;
  udl_id: string | null;
}

export interface StoryManeuver {
  id: string;
  source: string | null;
  event_start_time: string | null;
  maneuver_status: string | null;
  udl_id: string | null;
  facts: ManeuverFacts;
}

export interface StoryPost {
  post_id: string;
  posted_at: string;
  author: string | null;
  message: string;
}

export interface StoryThread {
  thread_id: string;
  // Every notice of the object the thread was confirmed against.
  event_keys: string[];
  channel_name: string | null;
  confirmed_at: string;
  posts: StoryPost[];
  truncated: boolean;
}

export interface ThreadSuggestion {
  thread_id: string;
  event_key: string;
  channel_name: string | null;
  reason: string;
  first_post: StoryPost;
  matching_posts: number;
}

export interface StoryTimer {
  id: string;
  label: string;
  target_time: string;
  event_key: string | null;
}

export interface StoryNote {
  id: string;
  author_id: string | null;
  author: string | null;
  text: string;
  created_at: string;
}

export interface HandoverStory {
  sat_no: number;
  name: string | null;
  window_hours: number;
  window_start: string;
  generated_at: string;
  notices: StoryNotice[];
  maneuvers: StoryManeuver[];
  threads: StoryThread[];
  suggestions: ThreadSuggestion[];
  timers: StoryTimer[];
  notes: StoryNote[];
  truncated: boolean;
}

export type LinkDecision = "confirmed" | "rejected" | "clear";

export interface ThreadLinkDecision {
  thread_id: string;
  event_key: string;
  decision: LinkDecision;
}
