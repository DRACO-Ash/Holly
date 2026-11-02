import { fullUtc, relativeTime, stampUtc } from "../../utils/ops";

// A time as "3 h ago", with the UTC stamp beside it and the full time on hover.
export function Stamp({
  time,
  now,
  withClock = true,
}: Readonly<{ time: number | null; now: number; withClock?: boolean }>) {
  if (time === null) return <span className="stamp stamp-unknown">time unknown</span>;
  const iso = new Date(time).toISOString();
  return (
    <time className="stamp" dateTime={iso} title={fullUtc(time)}>
      <span className="stamp-relative">{relativeTime(time, now)}</span>
      {withClock && <span className="stamp-clock">{stampUtc(time)}</span>}
    </time>
  );
}
