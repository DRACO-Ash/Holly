import { Fragment, useMemo } from "react";
import type { MattermostChannel, MattermostMessage } from "../../types";
import {
  channelHue,
  channelHues,
  channelLabel,
  dayLabel,
  fullTime,
  matchParts,
  sameUtcDay,
  timeOfDay,
} from "../../utils/comms";

// Messages under a heading for each day, with a marker where those posted since the last visit
// begin, and any search match marked. The feed lists newest first; a conversation, oldest first.
export default function MessageList({
  messages,
  channels,
  showChannel,
  search = "",
  lastSeen,
  now,
}: Readonly<{
  messages: readonly MattermostMessage[];
  channels: ReadonlyMap<string, MattermostChannel>;
  showChannel: boolean;
  search?: string;
  lastSeen: string | null;
  now: Date;
}>) {
  const seen = lastSeen ? Date.parse(lastSeen) : null;
  const hues = useMemo(() => channelHues(channels.values()), [channels]);
  return (
    <ol className="comms-list">
      {messages.map((m, index) => {
        const previous = index > 0 ? messages[index - 1] : null;
        const fresh = seen !== null && Date.parse(m.posted_at) > seen;
        const wasFresh =
          previous !== null && seen !== null && Date.parse(previous.posted_at) > seen;
        // A marker sits wherever the fresh and the earlier messages meet, whichever way the list
        // runs, and says which follow it.
        const marker = fresh !== wasFresh;
        const channel = channels.get(m.channel_id);
        const label = channel ? channelLabel(channel) : (m.channel_name ?? m.channel_id);
        return (
          <Fragment key={m.id}>
            {(!previous || !sameUtcDay(previous.posted_at, m.posted_at)) && (
              <li className="comms-day">
                <h3>{dayLabel(m.posted_at, now)}</h3>
              </li>
            )}
            {marker && (
              <li className="comms-since">
                <span>{fresh ? "New since your last visit" : "Earlier"}</span>
              </li>
            )}
            <li
              className={`comms-item channel-hue-${channelHue(m.channel_id, hues)}${fresh ? " fresh" : ""}`}
            >
              <div className="comms-head">
                {showChannel && (
                  <span className="comms-channel">
                    <span
                      className={`hue-dot channel-hue-${channelHue(m.channel_id, hues)}`}
                      aria-hidden="true"
                    />
                    #{label}
                  </span>
                )}
                <span className="comms-author">@{m.user_display_name ?? m.user_id}</span>
                <time className="comms-time" dateTime={m.posted_at} title={fullTime(m.posted_at)}>
                  {timeOfDay(m.posted_at)}
                </time>
              </div>
              <p className="comms-body">
                {matchParts(m.message, search).map((part, at) =>
                  part.match ? (
                    // A part's place in the message is its identity: the parts never reorder.
                    <mark key={at}>{part.text}</mark>
                  ) : (
                    <Fragment key={at}>{part.text}</Fragment>
                  ),
                )}
              </p>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
