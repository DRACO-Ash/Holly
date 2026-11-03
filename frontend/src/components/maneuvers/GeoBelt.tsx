import type { ManeuverGroup } from "../../utils/ops";
import { SourceBadge } from "../ops/Badges";

const WIDTH = 1000;
const HEIGHT = 100;
const LEFT = 20;
const RIGHT = 20;
const AXIS_Y = 64;
// Marks closer than this share a longitude's column and are stacked into rows above the axis.
const CLOSE = 12;
const ROWS = 3;
const ROW_STEP = 14;
const PLOT = WIDTH - LEFT - RIGHT;
const TICKS = [-180, -120, -60, 0, 60, 120, 180] as const;
// The drift line's length per degree a day: long enough to see, short enough to stay near.
const DRIFT_SCALE = 300;
const DRIFT_CAP = 60;

// Any longitude, east of Greenwich up to 360 too, as -180 to 180.
const normalised = (longitude: number) => ((((longitude + 180) % 360) + 360) % 360) - 180;
const xOf = (longitude: number) => LEFT + ((normalised(longitude) + 180) / 360) * PLOT;

// The row each mark sits on: the lowest whose last mark is far enough to its left.
function stackRows(xs: readonly number[]): number[] {
  const order = xs.map((x, index) => ({ x, index })).sort((a, b) => a.x - b.x);
  const last = new Array<number>(ROWS).fill(-Infinity);
  const rows = new Array<number>(xs.length).fill(0);
  for (const { x, index } of order) {
    const free = last.findIndex((edge) => x - edge >= CLOSE);
    const row = free === -1 ? 0 : free;
    rows[index] = row;
    last[row] = x;
  }
  return rows;
}

function tickLabel(longitude: number): string {
  if (longitude === 0) return "0°";
  return `${Math.abs(longitude)}°${longitude < 0 ? "W" : "E"}`;
}

export interface BeltMark {
  group: ManeuverGroup;
  longitude: number;
  drift: number | null;
  slot: number;
  source: string;
  label: string;
}

// The geostationary maneuvers at the longitude each record gives after the burn, coloured by
// provider, each with a short line in the direction and rough size of its drift.
export default function GeoBelt({ marks }: Readonly<{ marks: readonly BeltMark[] }>) {
  const summary = `GEO belt: ${marks.length} maneuver${marks.length === 1 ? "" : "s"} by longitude after the burn.`;
  const xs = marks.map((mark) => xOf(mark.longitude));
  const rows = stackRows(xs);
  const sources = [...new Map(marks.map((mark) => [mark.source, mark.slot])).entries()].sort(
    ([a], [b]) => a.localeCompare(b),
  );
  return (
    <>
      <ul className="belt-legend" aria-label="Providers">
        {sources.map(([source, slot]) => (
          <li key={source}>
            <SourceBadge source={source} slot={slot} />
          </li>
        ))}
      </ul>
      <svg
        className="geo-belt"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={summary}
        focusable="false"
      >
        <line className="geo-belt-axis" x1={LEFT} x2={WIDTH - RIGHT} y1={AXIS_Y} y2={AXIS_Y} />
        {TICKS.map((tick) => (
          <g key={tick} className="geo-belt-tick">
            <line x1={xOf(tick)} x2={xOf(tick)} y1={AXIS_Y - 6} y2={AXIS_Y + 6} />
            <text x={xOf(tick)} y={AXIS_Y + 26}>
              {tickLabel(tick)}
            </text>
          </g>
        ))}
        {marks.map((mark, index) => {
          const x = xs[index];
          const y = AXIS_Y - 14 - rows[index] * ROW_STEP;
          const reach =
            mark.drift === null
              ? 0
              : Math.max(-DRIFT_CAP, Math.min(DRIFT_CAP, mark.drift * DRIFT_SCALE));
          return (
            <g key={mark.group.maneuver.id}>
              {reach !== 0 && (
                <line className="geo-belt-drift" x1={x} x2={x + reach} y1={y} y2={y} />
              )}
              <circle
                className={`timeline-mark mark-dot tone-source-${mark.slot}`}
                cx={x}
                cy={y}
                r={5}
              >
                <title>{mark.label}</title>
              </circle>
            </g>
          );
        })}
      </svg>
    </>
  );
}
