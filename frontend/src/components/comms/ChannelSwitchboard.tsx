import { useMemo } from "react";
import type { MattermostChannel } from "../../types";
import {
  ago,
  channelHue,
  channelHues,
  channelLabel,
  closedReason,
  fullTime,
} from "../../utils/comms";
import ActivityTrace from "./ActivityTrace";
import FollowSwitch from "./FollowSwitch";

const HINT_ID = "switchboard-hint";

// Every channel the bot can read: the open ones with their activity and a follow switch, the
// closed ones folded away below, each kept with what Holly pulled before it closed. In the feed a
// name narrows the feed to that channel (`picking`, pressed while it does); in the conversation
// layout a name opens that channel (current while it is open).
export default function ChannelSwitchboard({
  channels,
  selectedIds,
  picking,
  busyId,
  onSelect,
  onFollow,
  now,
}: Readonly<{
  channels: readonly MattermostChannel[];
  selectedIds: readonly string[];
  picking: boolean;
  busyId: string | null;
  onSelect: (channelId: string) => void;
  onFollow: (channel: MattermostChannel, following: boolean) => void;
  now: Date;
}>) {
  const hues = useMemo(() => channelHues(channels), [channels]);
  const open = channels.filter((c) => c.status === "open");
  const closed = channels.filter((c) => c.status === "closed");
  const followed = open.filter((c) => c.following).length;
  // One scale for every trace, so a quiet channel's bars are short beside a busy one's.
  const peak = Math.max(1, ...open.filter((c) => c.pulled).flatMap((c) => c.activity));

  function name(channel: MattermostChannel) {
    const selected = selectedIds.includes(channel.mm_channel_id);
    return (
      <button
        type="button"
        className="switchboard-name"
        aria-pressed={picking ? selected : undefined}
        aria-current={!picking && selected ? "true" : undefined}
        onClick={() => onSelect(channel.mm_channel_id)}
      >
        <span
          className={`hue-dot channel-hue-${channelHue(channel.mm_channel_id, hues)}`}
          aria-hidden="true"
        />
        {channelLabel(channel)}
      </button>
    );
  }

  function rowClass(channel: MattermostChannel, extra = "") {
    const selected = selectedIds.includes(channel.mm_channel_id) ? " selected" : "";
    return `switchboard-row${extra}${selected}`;
  }

  function activity(channel: MattermostChannel) {
    // A channel Holly does not pull has no activity Holly could know: it says so, rather than
    // drawing a flat line that would read as a quiet channel.
    if (!channel.pulled) return <span className="trace-none">Not pulled</span>;
    const total = channel.activity.reduce((a, b) => a + b, 0);
    return (
      <>
        <ActivityTrace
          counts={channel.activity}
          hue={channelHue(channel.mm_channel_id, hues)}
          peak={peak}
        />
        <span className="trace-total">{total} in 24 h</span>
      </>
    );
  }

  function latest(channel: MattermostChannel) {
    if (!channel.last_message_at) return channel.pulled ? "No messages yet" : null;
    return (
      <span>
        {channel.pulled ? "" : "last pulled "}
        <time dateTime={channel.last_message_at} title={fullTime(channel.last_message_at)}>
          {ago(channel.last_message_at, now)}
        </time>
      </span>
    );
  }

  return (
    <aside className="switchboard" aria-label="Channels">
      <h2 className="switchboard-title">
        Channels{" "}
        <span className="switchboard-count">
          {followed} of {open.length} followed
        </span>
      </h2>
      <p id={HINT_ID} className="switchboard-hint">
        The switches are shared: switching a channel off stops Holly pulling it for everyone.
        {picking && " Select a name to show that channel in the feed."}
      </p>
      {open.length === 0 && (
        <p className="muted">No open channel yet. Add the bot to a channel and it appears here.</p>
      )}
      <ul className="switchboard-list">
        {open.map((channel) => (
          <li key={channel.mm_channel_id} className={rowClass(channel)}>
            <div className="switchboard-line">
              {name(channel)}
              <FollowSwitch
                label={channelLabel(channel)}
                on={channel.following}
                busy={busyId === channel.mm_channel_id}
                describedBy={HINT_ID}
                onChange={(on) => onFollow(channel, on)}
              />
            </div>
            <div className="switchboard-meta">
              {activity(channel)}
              {latest(channel)}
              {(channel.new_since ?? 0) > 0 && (
                <span className="tag tag-count">{channel.new_since} new</span>
              )}
              {channel.is_new && <span className="tag tag-new">New</span>}
              {channel.channel_type === "P" && <span className="tag">Private</span>}
              {!channel.accessible && <span className="tag tag-warn">Bot removed</span>}
            </div>
          </li>
        ))}
      </ul>
      {closed.length > 0 && (
        <details className="switchboard-closed">
          <summary>Closed ({closed.length})</summary>
          <p className="muted">
            Holly keeps what it pulled from these and pulls nothing more. A channel closed by name
            opens again when CLOSED leaves its name.
          </p>
          <ul className="switchboard-list">
            {closed.map((channel) => (
              <li key={channel.mm_channel_id} className={rowClass(channel, " closed")}>
                <div className="switchboard-line">
                  {name(channel)}
                  <span className="tag tag-closed">{closedReason(channel)}</span>
                </div>
                <div className="switchboard-meta">
                  <span>
                    {channel.message_count} message{channel.message_count === 1 ? "" : "s"} kept
                  </span>
                  {channel.closed_at && (
                    <span>
                      closed{" "}
                      <time dateTime={channel.closed_at} title={fullTime(channel.closed_at)}>
                        {ago(channel.closed_at, now)}
                      </time>
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </aside>
  );
}
