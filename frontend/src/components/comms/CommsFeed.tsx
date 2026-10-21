import { useEffect, useMemo, useRef, useState } from "react";
import { listMattermostMessages } from "../../api/mattermost";
import type { MattermostChannel, MattermostMessage } from "../../types";
import { channelHue, channelHues, channelLabel } from "../../utils/comms";
import { extractErrorMessage } from "../../utils/errors";
import ActivityLanes from "./ActivityLanes";
import MessageList from "./MessageList";
import { type FeedScope, scopeIds, toggled } from "./scope";

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
  const shown = useRef<MattermostMessage[]>([]);
  shown.current = messages;
  const byId = useMemo(() => new Map(channels.map((c) => [c.mm_channel_id, c])), [channels]);
  const hues = useMemo(() => channelHues(channels), [channels]);
  // Keyed by content, so a channel list refreshed with the same channels does not reload.
  const idsKey = scopeIds(scope, channels)?.join("\n");
  const filters = useMemo(
    () => ({
      channel_id: idsKey === undefined ? undefined : idsKey.split("\n").filter(Boolean),
      q: query || undefined,
    }),
    [idsKey, query],
  );
  const none = filters.channel_id !== undefined && filters.channel_id.length === 0;

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), SEARCH_PAUSE_MS);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setWaiting([]);
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
    const timer = window.setInterval(() => {
      const newest = shown.current[0]?.posted_at;
      listMattermostMessages({
        ...filters,
        limit: PAGE,
        offset: 0,
        ...(newest ? { posted_at_gte: newest } : {}),
      })
        .then((page) => {
          const known = new Set(shown.current.map((m) => m.id));
          setWaiting(page.items.filter((m) => !known.has(m.id)));
        })
        .catch(() => undefined);
    }, FEED_POLL_MS);
    return () => window.clearInterval(timer);
  }, [filters, none]);

  function showWaiting() {
    setMessages((current) => [...waiting, ...current]);
    setTotal((count) => count + waiting.length);
    setWaiting([]);
  }

  async function loadOlder() {
    try {
      const page = await listMattermostMessages({
        ...filters,
        limit: PAGE,
        offset: messages.length,
      });
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
        <div className="segmented" role="group" aria-label="Show messages from">
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
        </div>
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
          <button type="button" className="feed-waiting" onClick={showWaiting}>
            Show {waiting.length} new message{waiting.length === 1 ? "" : "s"}
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
