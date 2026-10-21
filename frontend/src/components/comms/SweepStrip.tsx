import type { MattermostSweep } from "../../types";
import { ago, everyLabel, fullTime } from "../../utils/comms";

// When Holly last looked for the bot's channels, as whom, whether it worked, and a way to look
// again now. The words say what the lamp shows, so the lamp is never the only sign.
export default function SweepStrip({
  sweep,
  sweeping,
  onSweep,
  now,
}: Readonly<{ sweep: MattermostSweep; sweeping: boolean; onSweep: () => void; now: Date }>) {
  let lamp = "sweep-lamp";
  if (sweeping) lamp += " busy";
  else if (sweep.ok === true) lamp += " ok";
  else if (sweep.ok === false) lamp += " failed";
  const when = sweep.last_at && (
    <time dateTime={sweep.last_at} title={fullTime(sweep.last_at)}>
      {ago(sweep.last_at, now)}
    </time>
  );
  let text;
  if (!sweep.last_at) text = <>No channel sweep has run since Holly last started.</>;
  else if (sweep.ok === false) text = <>The last channel sweep, {when}, failed.</>;
  else
    text = (
      <>
        Channels swept {when}
        {sweep.bot && <> as @{sweep.bot}</>}, {everyLabel(sweep.interval_seconds)}.
      </>
    );
  return (
    <div className="sweep-strip">
      <span className={lamp} aria-hidden="true" />
      <p className="sweep-text">{text}</p>
      <button
        type="button"
        aria-disabled={sweeping || undefined}
        onClick={() => {
          if (!sweeping) onSweep();
        }}
      >
        {sweeping ? "Finding channels..." : "Find channels now"}
      </button>
    </div>
  );
}
