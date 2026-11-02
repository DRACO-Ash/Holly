import { histogram } from "../../utils/ops";

const WIDTH = 120;
const HEIGHT = 24;

// Activity over the window as small bars: decoration beside a count that says the same in words.
export function Sparkline({
  times,
  start,
  end,
  bins = 30,
  tone = "accent",
}: Readonly<{
  times: readonly number[];
  start: number;
  end: number;
  bins?: number;
  tone?: string;
}>) {
  const counts = histogram(times, start, end, bins);
  const peak = Math.max(1, ...counts);
  const step = WIDTH / bins;
  return (
    <svg
      className={`sparkline tone-${tone}`}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width={WIDTH}
      height={HEIGHT}
      aria-hidden="true"
      focusable="false"
    >
      <line className="sparkline-base" x1="0" x2={WIDTH} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} />
      {counts.map((count, index) =>
        count === 0 ? null : (
          <rect
            // The bins are fixed slices of the window, so a bin's place is its identity.
            key={`bin-${index * step}`}
            className="sparkline-bar"
            x={index * step + 0.5}
            width={Math.max(1, step - 1)}
            y={HEIGHT - 1 - (count / peak) * (HEIGHT - 2)}
            height={(count / peak) * (HEIGHT - 2)}
          />
        ),
      )}
    </svg>
  );
}
