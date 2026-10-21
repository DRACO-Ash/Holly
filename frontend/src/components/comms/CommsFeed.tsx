import { useEffect, useMemo, useRef, useState } from "react";
import { listMattermostMessages } from "../../api/mattermost";
import type { MattermostChannel, MattermostMessage } from "../../types";
import { alsoAsked, channelHue, channelHues, channelLabel, unseen } from "../../utils/comms";
import { extractErrorMessage } from "../../utils/errors";
import ActivityLanes from "./ActivityLanes";
import MessageList from "./MessageList";
import { type FeedScope, type ScopeQuery, scopeQuery, toggled } from "./scope";

const PAGE = 50;
// The feed looks for newer messages this often, and offers them rather than moving the list.
export const FEED_POLL_MS = 30_000;
const SEARCH_PAUSE_MS = 300;

// Every followed channel in one stream, newest first, under the last 24 hours of each: searchable,
// narrowed to the channels picked, with newer messages offered at the top as they arrive.
export default function CommsFeed({
  channels,
  scope,
  onScope,
  lastSeen,
  now,
}: Readonly<{
  channels: readonly MattermostChannel[];
  scope: FeedScope;
  onScope: (scope: FeedScope) => void;
  lastSeen: string | null;
  now: Date;
}>) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<MattermostMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState<MattermostMessage[]>([]);
  // How many arrived, and whether more than one poll's page did: showing those reloads the
  // latest page, so the list never skips the ones the poll could not hold.
  const [arrived, setArrived] = useState({ count: 0, more: false });
  const shown = useRef<MattermostMessage[]>([]);
  shown.current = messages;
  const asked = useRef<object | null>(null);
  const byId = useMemo(() => new Map(channels.map((c) => [c.mm_channel_id, c])), [channels]);
  const hues = useMemo(() => channelHues(channels), [channels]);
  // Keyed by content, so a channel list refreshed with the same channels does not reload.
  const scopeKey = JSON.stringify(scopeQuery(scope, channels));
  const none = scopeKey === "null";
  const filters = useMemo(
    () => ({ ...(JSON.parse(scopeKey) as ScopeQuery | null), q: query || undefined }),
    [scopeKey, query],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), SEARCH_PAUSE_MS);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    asked.current = filters;
    setWaiting([]);
    setArrived({ count: 0, more: false });
    if (none) {
      setMessages([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    listMattermostMessages({ ...filters, limit: PAGE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setMessages(page.items);
        setTotal(page.total);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load messages."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, none]);

  useEffect(() => {
    if (none) return undefined;
    // A poll answered after the scope changed, or after the feed closed, changes nothing.
    let cancelled = false;
    const timer = window.setInterval(() => {
      const newest = shown.current[0]?.posted_at;
      listMattermostMessages({
        ...filters,
        limit: PAGE,
        offset: 0,
        ...(newest ? { posted_at_gte: newest } : {}),
      })
        .then((page) => {
          if (cancelled) return;
          setWaiting(unseen(page.items, shown.current));
          setArrived({
            count: page.total - alsoAsked(shown.current, newest),
            more: page.total > page.items.length,
          });
        })
        .catch(() => undefined);
    }, FEED_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [filters, none]);

  async function showWaiting() {
    const { more } = arrived;
    setWaiting([]);
    setArrived({ count: 0, more: false });
    if (!more) {
      setMessages((current) => [...waiting, ...current]);
      setTotal((count) => count + waiting.length);
      return;
    }
    const scoped = filters;
    try {
      const page = await listMattermostMessages({ ...scoped, limit: PAGE, offset: 0 });
      if (asked.current !== scoped) return;
      setMessages(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load messages."));
    }
  }

  async function loadOlder() {
    const scoped = filters;
    try {
      const page = await listMattermostMessages({
        ...scoped,
        limit: PAGE,
        offset: messages.length,
      });
      // An answer for a scope or search since changed is dropped.
      if (asked.current !== scoped) return;
      const known = new Set(messages.map((m) => m.id));
      setMessages([...messages, ...page.items.filter((m) => !known.has(m.id))]);
      setTotal(page.total);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load older messages."));
    }
  }

  const chosen = scope.kind === "chosen" ? scope.ids : [];
  const nameOf = (id: string) => {
    const channel = byId.get(id);
    return channel ? channelLabel(channel) : id;
  };

  return (
    <div className="comms-feed">
      <ActivityLanes
        channels={channels.filter((c) => c.following && c.status === "open")}
        hues={hues}
        chosen={chosen}
        onToggle={(id) => onScope(toggled(scope, id))}
        lastSeen={lastSeen}
        now={now}
      />
      <div className="feed-controls">
        <fieldset className="segmented">
          <legend className="visually-hidden">Show messages from</legend>
          <button
            type="button"
            aria-pressed={scope.kind === "following"}
            onClick={() => onScope({ kind: "following" })}
          >
            Followed channels
          </button>
          <button
            type="button"
            aria-pressed={scope.kind === "all"}
            onClick={() => onScope({ kind: "all" })}
          >
            All channels
          </button>
        </fieldset>
        <label className="feed-search">
          Search messages{" "}
          <input
            type="search"
            value={search}
            maxLength={200}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {chosen.length > 0 && (
        <div className="feed-chosen">
          <span>Showing only</span>
          <ul className="chips">
            {chosen.map((id) => (
              <li key={id}>
                <button
                  type="button"
                  className="chip"
                  aria-label={`Stop showing #${nameOf(id)}`}
                  onClick={() => onScope(toggled(scope, id))}
                >
                  <span
                    className={`hue-dot channel-hue-${channelHue(id, hues)}`}
                    aria-hidden="true"
                  />
                  #{nameOf(id)}
                  <span className="chip-x" aria-hidden="true">
                    x
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => onScope({ kind: "following" })}>
            Show every followed channel
          </button>
        </div>
      )}
      <output className="feed-status">
        {waiting.length > 0 && (
          <button type="button" className="feed-waiting" onClick={() => void showWaiting()}>
            Show {arrived.count} new message{arrived.count === 1 ? "" : "s"}
          </button>
        )}
      </output>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {loading && <p className="muted">Loading messages...</p>}
      {!loading && none && (
        <p className="muted">No channel is followed. Switch one on in the channel list.</p>
      )}
      {!loading && !none && messages.length === 0 && !error && (
        <p className="muted">
          {query ? `No message contains "${query}".` : "No messages from these channels yet."}
        </p>
      )}
      <h2 className="visually-hidden">Messages</h2>
      <MessageList
        messages={messages}
        channels={byId}
        showChannel
        search={query}
        lastSeen={lastSeen}
        now={now}
      />
      {messages.length > 0 && (
        <div className="pagination">
          <span>
            {messages.length} of {total} messages
          </span>
          <button
            type="button"
            disabled={messages.length >= total}
            onClick={() => void loadOlder()}
          >
            Load older
          </button>
        </div>
      )}
    </div>
  );
}
