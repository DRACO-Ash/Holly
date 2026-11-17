// The prototype's stand-in for Holly's server: every API call the pages make is answered here, in
// the browser, from the synthetic world in data.ts. Nothing leaves the page. Writes (notes,
// timers, thread decisions, shift notes) change the in-memory world until the page is reloaded.
import axios, { AxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, apiClient } from "../api/client";
import type {
  ActivityOverview,
  AssistantFeed,
  EventTimer,
  HandoverObject,
  HandoverStory,
  StoryThread,
  ThreadSuggestion,
} from "../types";
import { H, NOW, SAT_NAMES, USER, buildWorld, iso } from "./data";
import { parseEventClass } from "../utils/ops";

export const world = buildWorld();
const WINDOW_HOURS = 120;
const windowStart = () => iso(Date.now() - WINDOW_HOURS * H);

// There is no server and no credential: the pages only need something stored to count as signed
// in, so one fixed marker stands in for both values.
const SIGNED_IN = "prototype";
localStorage.setItem(ACCESS_TOKEN_KEY, SIGNED_IN);
localStorage.setItem(REFRESH_TOKEN_KEY, SIGNED_IN);

type Params = Record<string, unknown>;
type Answer = [number, unknown];

const page = <T,>(items: T[], params: Params) => {
  const limit = Number(params.limit ?? 50);
  const offset = Number(params.offset ?? 0);
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
};

// A whole number, not part of a longer one: the rule V0.19's server uses for chat.
export const mentionsNumber = (text: string, n: string) => new RegExp(`(^|[^0-9])${n}([^0-9]|$)`).test(text);

function overview(): ActivityOverview {
  return {
    window_hours: WINDOW_HOURS, window_start: windowStart(), generated_at: iso(Date.now()),
    notices: world.notices.map((n) => n.activity), maneuvers: world.maneuvers,
    elsets: world.elsets, truncated: { notices: false, maneuvers: false, elsets: false },
  };
}

function feed(): AssistantFeed {
  return {
    window_hours: WINDOW_HOURS,
    items: world.notices.map((n) => ({
      notification: n.detail, evaluation: n.evaluation, urgency: n.activity.urgency,
      top_action: n.activity.top_action, event_summary: null, event_publication_count: null,
      event_key: n.detail.event_id, assistant_cleared: true,
    })),
  };
}

export function objects(): HandoverObject[] {
  const by = new Map<number, HandoverObject>();
  world.notices.forEach(({ activity: n }) => {
    const parsed = parseEventClass(n.event_class);
    n.sat_ids.forEach((id) => {
      const satNo = Number(id);
      const o = by.get(satNo) ?? {
        sat_no: satNo, name: parsed?.objects.find((x) => x.id === id)?.name ?? SAT_NAMES.get(id) ?? null,
        kinds: [], latest_at: null, events: 0,
        maneuvers: world.maneuvers.filter((m) => m.sat_no === satNo).length,
      };
      o.events += 1;
      if (parsed && !o.kinds.includes(parsed.kindLabel)) o.kinds.push(parsed.kindLabel);
      if (!o.latest_at || Date.parse(n.udl_created_at!) > Date.parse(o.latest_at)) o.latest_at = n.udl_created_at;
      by.set(satNo, o);
    });
  });
  return [...by.values()].sort((a, b) => Date.parse(b.latest_at!) - Date.parse(a.latest_at!));
}

const threadOf = (m: { mm_post_id: string; root_id: string | null }) => m.root_id ?? m.mm_post_id;
const followed = (channelId: string) => world.channels.find((c) => c.mm_channel_id === channelId)?.following !== false;

export function story(satNo: number): HandoverStory {
  const id = String(satNo);
  const notices = world.notices.filter((n) => n.activity.sat_ids.includes(id));
  const keys = new Set(notices.map((n) => n.detail.event_id!));
  const notsos = notices.map((n) => n.activity.notice).filter((x): x is string => !!x);
  const links = world.links.filter((l) => keys.has(l.event_key));
  const decided = new Set(links.map((l) => l.thread_id));
  const posts = world.messages.filter((m) => followed(m.channel_id));
  const threads: StoryThread[] = links
    .filter((l) => l.decision === "confirmed")
    .map((l) => {
      const own = posts
        .filter((m) => threadOf(m) === l.thread_id)
        .sort((a, b) => Date.parse(a.posted_at) - Date.parse(b.posted_at));
      return {
        thread_id: l.thread_id, event_keys: [l.event_key], channel_name: own[0]?.channel_name ?? null,
        confirmed_at: iso(NOW - 20 * H), truncated: false,
        posts: own.map((m) => ({ post_id: m.mm_post_id, posted_at: m.posted_at, author: m.user_display_name, message: m.message })),
      };
    });
  const byThread = new Map<string, typeof posts>();
  posts
    .filter((m) => Date.parse(m.posted_at) >= Date.now() - WINDOW_HOURS * H)
    .filter((m) => mentionsNumber(m.message, id) || notsos.some((n) => m.message.includes(n)))
    .forEach((m) => byThread.set(threadOf(m), [...(byThread.get(threadOf(m)) ?? []), m]));
  const suggestions: ThreadSuggestion[] = [];
  byThread.forEach((list, threadId) => {
    if (decided.has(threadId)) return;
    const first = [...list].sort((a, b) => Date.parse(a.posted_at) - Date.parse(b.posted_at))[0];
    suggestions.push({
      thread_id: threadId, event_key: notices[0]?.detail.event_id ?? "", channel_name: first.channel_name,
      reason: `names ${id}`, matching_posts: list.length,
      first_post: { post_id: first.mm_post_id, posted_at: first.posted_at, author: first.user_display_name, message: first.message },
    });
  });
  return {
    sat_no: satNo, name: objects().find((o) => o.sat_no === satNo)?.name ?? SAT_NAMES.get(id) ?? null,
    window_hours: WINDOW_HOURS, window_start: windowStart(), generated_at: iso(Date.now()),
    notices: notices.map(({ activity: n, detail }) => ({
      id: n.id, event_key: detail.event_id!, notice: n.notice, event_class: n.event_class,
      kind: parseEventClass(n.event_class)?.kindLabel ?? null, status: n.status,
      udl_created_at: n.udl_created_at, source: detail.source, udl_id: detail.udl_id,
    })),
    maneuvers: world.maneuvers
      .filter((m) => m.sat_no === satNo)
      .map((m) => ({ id: m.id, source: m.source, event_start_time: m.event_start_time, maneuver_status: m.facts.status, udl_id: m.udl_id, facts: m.facts })),
    threads,
    suggestions: suggestions.slice(0, 20),
    timers: world.timers
      .filter((t) => !t.dismissed_at && t.event_key && keys.has(t.event_key))
      .sort((a, b) => Date.parse(a.target_time) - Date.parse(b.target_time))
      .map((t) => ({ id: t.id, label: t.label, target_time: t.target_time, event_key: t.event_key })),
    notes: world.notes
      .filter((n) => n.sat_no === satNo)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .map((n) => ({ id: n.id, author_id: n.author_id, author: n.author, text: n.text, created_at: n.created_at })),
    truncated: false,
  };
}

const NOT_FOUND: Answer = [404, { detail: "Not found." }];

function get(path: string, params: Params): Answer {
  const tail = path.split("/").pop() ?? "";
  if (path === "/auth/me") return [200, USER];
  if (path === "/activity") return [200, overview()];
  if (path === "/assistant/feed") return [200, feed()];
  if (path.startsWith("/assistant/evaluation/")) {
    const n = world.notices.find((x) => x.activity.id === tail);
    return n?.evaluation ? [200, n.evaluation] : NOT_FOUND;
  }
  if (path === "/notifications") {
    const sat = params.sat_no === undefined ? null : String(params.sat_no);
    return [200, page(world.notices.map((n) => n.detail).filter((n) => !sat || n.sat_ids?.includes(sat)), params)];
  }
  if (path.startsWith("/notifications/")) {
    const n = world.notices.find((x) => x.activity.id === tail);
    return n ? [200, n.detail] : NOT_FOUND;
  }
  if (path === "/maneuvers") {
    const sat = params.sat_no === undefined ? null : Number(params.sat_no);
    return [200, page(world.maneuvers.filter((m) => sat === null || m.sat_no === sat), params)];
  }
  if (path.startsWith("/maneuvers/")) {
    const m = world.maneuvers.find((x) => x.id === tail);
    return m ? [200, { ...m, raw: { satNo: m.sat_no, source: m.source, eventStartTime: m.event_start_time } }] : NOT_FOUND;
  }
  if (path === "/event-timers") {
    const all = params.include_dismissed === true || params.include_dismissed === "true";
    return [200, { items: world.timers.filter((t) => all || !t.dismissed_at) }];
  }
  if (path === "/mattermost/channels") {
    const sweep = { configured: true, last_at: iso(Date.now() - 4 * 60_000), ok: true, problem: null, bot: "sample-bot", interval_seconds: 300 };
    return [200, { channels: world.channels, sweep }];
  }
  if (path === "/mattermost/messages") {
    const wanted = ([] as unknown[]).concat(params.channel_id ?? []).map(String);
    const q = typeof params.q === "string" ? params.q.toLowerCase() : "";
    const only = params.followed === true || params.followed === "true";
    const items = world.messages.filter(
      (m) =>
        (wanted.length === 0 || wanted.includes(m.channel_id)) &&
        (!only || followed(m.channel_id)) &&
        (!q || m.message.toLowerCase().includes(q)),
    );
    return [200, page(items.map(({ root_id: _r, ...m }) => m), params)];
  }
  if (path === "/handover/objects") {
    return [200, { window_hours: WINDOW_HOURS, window_start: windowStart(), generated_at: iso(Date.now()), objects: objects(), truncated: false }];
  }
  if (path.startsWith("/handover/objects/")) return [200, story(Number(tail))];
  const today = iso(NOW).slice(0, 10);
  if (path === "/shift-log/notes") return [200, { items: world.shiftNotes, shift_date: today }];
  if (path === "/shift-log/dates") {
    return [200, { items: [{ shift_date: today, note_count: world.shiftNotes.length, has_summary: false }] }];
  }
  if (path === "/shift-log/summary") return [200, null];
  if (path === "/procedures") return [200, { items: [], total: 0 }];
  if (path === "/manuals" || path === "/users") return [200, []];
  return [200, { items: [], total: 0, limit: 50, offset: 0 }];
}

function newTimer(body: Record<string, unknown>): EventTimer {
  const now = iso(Date.now());
  return {
    id: `t-new-${world.timers.length}`, event_key: typeof body.event_key === "string" ? body.event_key : null,
    label: String(body.label), target_time: String(body.target_time),
    pre_alert_minutes: Number(body.pre_alert_minutes ?? 5), recurrence: String(body.recurrence ?? "none"),
    pre_alert_fired_at: null, dismissed_at: null, dismissed_by: null, created_by: USER.id, shift_date: null,
    created_at: now, updated_at: now,
  };
}

function post(path: string, body: Record<string, unknown>): Answer {
  const parts = path.split("/");
  if (path === "/auth/refresh") return [200, { access_token: SIGNED_IN, refresh_token: SIGNED_IN, token_type: "bearer" }];
  if (path === "/auth/logout") return [204, null];
  if (path === "/event-timers") {
    const t = newTimer(body);
    world.timers.push(t);
    return [201, t];
  }
  if (path.startsWith("/event-timers/")) {
    const t = world.timers.find((x) => x.id === parts[2]);
    if (!t) return NOT_FOUND;
    if (parts[3] === "dismiss") t.dismissed_at = iso(Date.now());
    if (parts[3] === "acknowledge-pre-alert") t.pre_alert_fired_at = iso(Date.now());
    return [200, t];
  }
  if (path === "/handover/thread-links") {
    const threadId = String(body.thread_id);
    const eventKey = String(body.event_key);
    const decision = String(body.decision);
    world.links = world.links.filter((l) => !(l.thread_id === threadId && l.event_key === eventKey));
    if (decision === "confirmed" || decision === "rejected") world.links.push({ thread_id: threadId, event_key: eventKey, decision });
    return [200, { thread_id: threadId, event_key: eventKey, decision }];
  }
  if (path.startsWith("/handover/objects/") && parts[4] === "notes") {
    const note = {
      id: `note-${world.notes.length}-${Date.now()}`, author_id: USER.id, author: USER.username,
      text: String(body.text).trim(), created_at: iso(Date.now()), sat_no: Number(parts[3]),
    };
    world.notes.push(note);
    return [201, { id: note.id, author_id: note.author_id, author: note.author, text: note.text, created_at: note.created_at }];
  }
  if (path === "/shift-log/notes") {
    const n = {
      id: `s-${world.shiftNotes.length}`, author_id: USER.id, shift_date: iso(NOW).slice(0, 10),
      raw_text: String(body.raw_text ?? body.text ?? ""), polished_text: null, polish_error: null, model: null,
      created_at: iso(Date.now()), updated_at: iso(Date.now()),
    };
    world.shiftNotes.push(n);
    return [201, n];
  }
  if (path === "/mattermost/channels/reviewed") return [200, { reviewed: 0 }];
  if (path === "/mattermost/sweep") {
    return [200, { ok: true, problem: null, found: 0, new: 0, closed: 0, reopened: 0, lost: 0, channels_polled: 5, channels_failed: 0, inserted: 0 }];
  }
  return [400, { detail: "The prototype does not do that." }];
}

function remove(path: string): Answer {
  const parts = path.split("/");
  if (path.startsWith("/handover/notes/")) {
    world.notes = world.notes.filter((n) => n.id !== parts[3]);
    return [204, null];
  }
  if (path.startsWith("/event-timers/")) {
    world.timers = world.timers.filter((t) => t.id !== parts[2]);
    return [204, null];
  }
  return NOT_FOUND;
}

function change(path: string, body: Record<string, unknown>): Answer {
  if (path.startsWith("/mattermost/channels/")) {
    const c = world.channels.find((x) => x.mm_channel_id === decodeURIComponent(path.split("/")[3]));
    if (!c) return NOT_FOUND;
    if (typeof body.following === "boolean") c.following = body.following;
    return [200, c];
  }
  return NOT_FOUND;
}

function parseBody(data: unknown): Record<string, unknown> {
  if (typeof data !== "string" || !data) return {};
  try {
    return JSON.parse(data) as Record<string, unknown>;
  } catch {
    return {};
  }
}

const adapter: AxiosAdapter = (config: InternalAxiosRequestConfig) =>
  new Promise((resolve, reject) => {
    const path = (config.url ?? "").replace(/^\/api\/v1/, "").split("?")[0];
    const params = (config.params ?? {}) as Params;
    const body = parseBody(config.data);
    const method = (config.method ?? "get").toLowerCase();
    const route: Record<string, () => Answer> = {
      get: () => get(path, params),
      post: () => post(path, body),
      delete: () => remove(path),
      patch: () => change(path, body),
      put: () => change(path, body),
    };
    const [status, data] = (route[method] ?? (() => NOT_FOUND))();
    const response: AxiosResponse = { data, status, statusText: String(status), headers: {}, config, request: {} };
    // A short, varied delay, so the pages load as they do against a server.
    globalThis.setTimeout(
      () =>
        status < 400
          ? resolve(response)
          : reject(new AxiosError(`Request failed with status ${status}`, "ERR_BAD_REQUEST", config, {}, response)),
      80 + Math.round(Math.random() * 120),
    );
  });

apiClient.defaults.adapter = adapter;
axios.defaults.adapter = adapter;
