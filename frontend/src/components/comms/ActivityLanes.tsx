import type { MattermostChannel } from "../../types";
import { channelHue, channelLabel, hourPosition, plural } from "../../utils/comms";
import ActivityTrace, { TRACE_HOURS } from "./ActivityTrace";

// The last 24 hours of every channel Holly pulls, one lane each in its own hue and all on one
// scale, with a line where the reader's last visit falls and the current hour on the right. Only
// pulled channels have a lane: Holly cannot know how busy a channel it does not read has been.
// A lane is a button that narrows the feed to its channel, or widens it again.
export default function ActivityLanes({
  channels,
  hues,
  chosen,
  onToggle,
  lastSeen,
  now,
}: Readonly<{
  channels: readonly MattermostChannel[];
  hues: ReadonlyMap<string, number>;
  chosen: readonly string[];
  onToggle: (channelId: string) => void;
  lastSeen: string | null;
  now: Date;
}>) {
  const lanes = channels.filter((c) => c.pulled);
  if (lanes.length === 0) return null;
  const peak = Math.max(1, ...lanes.flatMap((c) => c.activity));
  const total = lanes.reduce((sum, c) => sum + c.activity.reduce((a, b) => a + b, 0), 0);
  const seenAt = hourPosition(lastSeen, now, TRACE_HOURS);
  return (
    <section className="lanes" aria-labelledby="lanes-title">
      <div className="lanes-head">
        <h2 id="lanes-title" className="lanes-title">
          Last 24 hours
        </h2>
        <p className="lanes-key">
          {plural(total, "message")} across {plural(lanes.length, "channel")}, the busiest hour{" "}
          {peak}.{seenAt !== null && " The line marks your last visit."}
        </p>
      </div>
      <ul className="lanes-list">
        {lanes.map((channel) => {
          const sum = channel.activity.reduce((a, b) => a + b, 0);
          const pressed = chosen.includes(channel.mm_channel_id);
          const hue = channelHue(channel.mm_channel_id, hues);
          return (
            <li key={channel.mm_channel_id}>
              <button
                type="button"
                className="lane"
                aria-pressed={pressed}
                aria-label={`${channelLabel(channel)}, ${plural(sum, "message")} in the last 24 hours`}
                onClick={() => onToggle(channel.mm_channel_id)}
              >
                <span className="lane-name">
                  <span className={`hue-dot channel-hue-${hue}`} aria-hidden="true" />
                  {channelLabel(channel)}
                </span>
                <ActivityTrace
                  counts={channel.activity}
                  hue={hue}
                  peak={peak}
                  width={240}
                  stretch
                  seenAt={seenAt}
                  decorative
                />
                <span className="lane-total">{sum}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="lanes-axis" aria-hidden="true">
        <span>24 h ago</span>
        <span>12 h ago</span>
        <span>now</span>
      </div>
    </section>
  );
}
