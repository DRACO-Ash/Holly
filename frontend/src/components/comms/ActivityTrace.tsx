// A channel's last 24 hours at a glance: one bar an hour, oldest on the left and the current hour
// last. Every trace on the page is drawn to one scale, `peak`, so their heights compare. The
// total is read out for anyone who cannot see the bars, unless the trace sits inside a control
// that names it. `seenAt`, the hour of the reader's last visit counted from the left, draws a
// line across the trace.
export const TRACE_HOURS = 24;
const HEIGHT = 16;

// Each hour's count with its hour, the bar's identity: a bar never moves to another hour.
function bars(counts: readonly number[]) {
  return counts.map((count, hour) => ({ count, hour }));
}

export default function ActivityTrace({
  counts,
  hue,
  peak,
  width = 48,
  stretch = false,
  seenAt = null,
  decorative = false,
}: Readonly<{
  counts: readonly number[];
  hue: number;
  peak: number;
  width?: number;
  stretch?: boolean;
  seenAt?: number | null;
  decorative?: boolean;
}>) {
  const total = counts.reduce((sum, count) => sum + count, 0);
  const scale = Math.max(1, peak);
  const step = width / Math.max(1, counts.length);
  const label = `${total} message${total === 1 ? "" : "s"} in the last 24 hours`;
  const named = decorative ? { "aria-hidden": true } : { role: "img", "aria-label": label };
  return (
    <svg
      className={`activity-trace channel-hue-${hue}${stretch ? " stretch" : ""}`}
      viewBox={`0 0 ${width} ${HEIGHT}`}
      width={width}
      height={HEIGHT}
      preserveAspectRatio={stretch ? "none" : undefined}
      {...named}
    >
      {bars(counts).map(({ count, hour }) => {
        const height = count === 0 ? 1 : Math.max(2, Math.round((count / scale) * HEIGHT));
        const current = hour === counts.length - 1 ? " trace-now" : "";
        return (
          <rect
            key={hour}
            x={hour * step}
            y={HEIGHT - height}
            width={step * 0.7}
            height={height}
            className={(count === 0 ? "trace-off" : "trace-on") + current}
          />
        );
      })}
      {seenAt !== null && (
        <line className="trace-seen" x1={seenAt * step} x2={seenAt * step} y1={0} y2={HEIGHT} />
      )}
    </svg>
  );
}
