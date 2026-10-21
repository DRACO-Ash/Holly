import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listMattermostMessages } from "../../api/mattermost";
import type { MattermostChannel, MattermostMessage } from "../../types";
import { alsoAsked, channelLabel, closedReason, fullTime, unseen } from "../../utils/comms";
import { extractErrorMessage } from "../../utils/errors";
import { FEED_POLL_MS } from "./CommsFeed";
import FollowSwitch from "./FollowSwitch";
import MessageList from "./MessageList";

const PAGE = 50;
// How near the bottom, in pixels, still counts as reading the latest message.
const NEAR_BOTTOM = 48;

function atBottom(box: HTMLElement): boolean {
  return box.scrollHeight - box.scrollTop - box.clientHeight <= NEAR_BOTTOM;
}

function ClosedNote({ channel }: Readonly<{ channel: MattermostChannel }>) {
  const since = channel.closed_at && (
    <>
      {" "}
      since <time dateTime={channel.closed_at}>{fullTime(channel.closed_at)}</time>
    </>
  );
  return (
    <p className="conversation-note">
      {channel.archived ? (
        <>This channel has been archived in Mattermost{since}.</>
      ) : (
        <>
          This channel has been closed{since}: its name carries the word CLOSED, so Holly treats it
          as closed. Take the word out of its name in Mattermost and the next sweep opens it again.
        </>
      )}{" "}
      Holly keeps the messages it pulled and pulls nothing more.
    </p>
  );
}

// One channel at a time, as a conversation reads: oldest at the top and the latest at the
// bottom, opening where the messages new since the last visit begin, with earlier messages a
// click away. Newer messages join at the bottom as they arrive, or wait below a reader who has
// scrolled up.
export default function ChannelConversation({
  channel,
  channels,
  busy,
  onFollow,
  lastSeen,
  now,
}: Readonly<{
  channel: MattermostChannel;
  channels: readonly MattermostChannel[];
  busy: boolean;
  onFollow: (channel: MattermostChannel, following: boolean) => void;
  lastSeen: string | null;
  now: Date;
}>) {
  const [messages, setMessages] = useState<MattermostMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [below, setBelow] = useState<MattermostMessage[]>([]);
  // More arrived than one poll's page holds: showing them reloads the latest page instead, so
  // none is skipped.
  const [belowMore, setBelowMore] = useState(false);
  const [belowCount, setBelowCount] = useState(0);
  const scroller = useRef<HTMLDivElement | null>(null);
  const shown = useRef<MattermostMessage[]>([]);
  shown.current = messages;
  const stick = useRef(false);
  const byId = useMemo(() => new Map(channels.map((c) => [c.mm_channel_id, c])), [channels]);
  const channelId = channel.mm_channel_id;
  const label = channelLabel(channel);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setBelow([]);
    listMattermostMessages({ channel_id: channelId, limit: PAGE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setMessages([...page.items].reverse());
        setTotal(page.total);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load this channel."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [channelId]);

  // Once the channel has loaded: open where the new messages begin, else at the latest.
  useEffect(() => {
    const box = scroller.current;
    if (loading || !box) return;
    const marker = box.querySelector<HTMLElement>(".comms-since");
    box.scrollTop = marker ? marker.offsetTop - box.offsetTop : box.scrollHeight;
  }, [loading, channelId]);

  // A message that joined at the bottom keeps the reader at the bottom.
  useEffect(() => {
    const box = scroller.current;
    if (stick.current && box) box.scrollTop = box.scrollHeight;
    stick.current = false;
  }, [messages]);

  const latest = useCallback(async () => {
    const page = await listMattermostMessages({ channel_id: channelId, limit: PAGE, offset: 0 });
    stick.current = true;
    setMessages([...page.items].reverse());
    setTotal(page.total);
  }, [channelId]);

  // A poll's answer: messages that joined at the bottom are shown if the reader is there,
  // else held below with their count.
  const arrive = useCallback(
    async (
      items: MattermostMessage[],
      pageTotal: number,
      more: boolean,
      newest: string | undefined,
    ) => {
      const arrived = unseen(items, shown.current);
      if (arrived.length === 0) return;
      const box = scroller.current;
      if (box && atBottom(box)) {
        if (more) return await latest();
        stick.current = true;
        setMessages((current) => [...current, ...arrived]);
        setTotal((count) => count + arrived.length);
      } else {
        setBelow(arrived);
        setBelowMore(more);
        setBelowCount(pageTotal - alsoAsked(shown.current, newest));
      }
    },
    [latest],
  );

  useEffect(() => {
    // A poll answered after the channel changed, or after it closed, changes nothing.
    let cancelled = false;
    const timer = window.setInterval(() => {
      const newest = shown.current[shown.current.length - 1]?.posted_at;
      listMattermostMessages({
        channel_id: channelId,
        limit: PAGE,
        offset: 0,
        ...(newest ? { posted_at_gte: newest } : {}),
      })
        .then(async (page) => {
          if (cancelled) return;
          const more = page.total > page.items.length;
          await arrive([...page.items].reverse(), page.total, more, newest);
        })
        .catch(() => undefined);
    }, FEED_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [channelId, arrive]);

  async function showBelow() {
    const more = belowMore;
    setBelow([]);
    setBelowMore(false);
    if (more) {
      try {
        await latest();
      } catch (err) {
        setError(extractErrorMessage(err, "Failed to load this channel."));
      }
      return;
    }
    stick.current = true;
    setMessages((current) => {
      const known = new Set(current.map((m) => m.id));
      return [...current, ...below.filter((m) => !known.has(m.id))];
    });
    setTotal((count) => count + below.length);
  }

  async function loadEarlier() {
    try {
      const page = await listMattermostMessages({
        channel_id: channelId,
        limit: PAGE,
        offset: messages.length,
      });
      const known = new Set(messages.map((m) => m.id));
      const earlier = [...page.items].reverse().filter((m) => !known.has(m.id));
      setMessages([...earlier, ...messages]);
      setTotal(page.total);
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load earlier messages."));
    }
  }

  return (
    <div className="conversation">
      <div className="conversation-head">
        <div>
          <h2 className="record-value">#{label}</h2>
          <p className="muted">
            {channel.team_name && <>{channel.team_name} · </>}
            {channel.channel_type === "P" ? "Private channel" : "Public channel"} ·{" "}
            {channel.message_count} message{channel.message_count === 1 ? "" : "s"} held
          </p>
        </div>
        {channel.status === "open" ? (
          <FollowSwitch
            label={label}
            on={channel.following}
            busy={busy}
            onChange={(on) => onFollow(channel, on)}
          />
        ) : (
          <span className="tag tag-closed">{closedReason(channel)}</span>
        )}
      </div>
      {channel.status === "closed" && <ClosedNote channel={channel} />}
      {channel.status === "open" && !channel.accessible && (
        <p className="conversation-note">
          The bot can no longer read this channel, so Holly pulls nothing from it until the bot is
          added back.
        </p>
      )}
      {channel.status === "open" && channel.accessible && !channel.following && (
        <p className="conversation-note">
          Not followed: Holly pulls nothing from this channel until it is followed again.
        </p>
      )}
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      <div className="conversation-scroll" ref={scroller}>
        {messages.length < total && (
          <button type="button" className="conversation-earlier" onClick={() => void loadEarlier()}>
            Load earlier messages
          </button>
        )}
        {loading && <p className="muted">Loading the channel...</p>}
        {!loading && messages.length === 0 && !error && (
          <p className="muted">Holly holds no message from this channel yet.</p>
        )}
        <MessageList
          messages={messages}
          channels={byId}
          showChannel={false}
          lastSeen={lastSeen}
          now={now}
        />
        <output className="conversation-status">
          {below.length > 0 && (
            <button type="button" className="feed-waiting" onClick={() => void showBelow()}>
              {belowCount} new message{belowCount === 1 ? "" : "s"} below
            </button>
          )}
        </output>
      </div>
    </div>
  );
}
