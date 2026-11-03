import type { ManeuverGroup } from "../../utils/ops";

const WIDTH = 1000;
const HEIGHT = 90;
const LEFT = 20;
const RIGHT = 20;
const AXIS_Y = 50;
const PLOT = WIDTH - LEFT - RIGHT;
const TICKS = [-180, -120, -60, 0, 60, 120, 180] as const;
// The drift line's length per degree a day: long enough to see, short enough to stay near.
const DRIFT_SCALE = 300;
const DRIFT_CAP = 60;

const xOf = (longitude: number) => LEFT + ((longitude + 180) / 360) * PLOT;

function tickLabel(longitude: number): string {
  if (longitude === 0) return "0°";
  return `${Math.abs(longitude)}°${longitude < 0 ? "W" : "E"}`;
}

export interface BeltMark {
  group: ManeuverGroup;
  longitude: number;
  drift: number | null;
  slot: number;
  label: string;
}

// The geostationary maneuvers at the longitude each record gives after the burn, coloured by
// provider, each with a short line in the direction and rough size of its drift.
export default function GeoBelt({ marks }: Readonly<{ marks: readonly BeltMark[] }>) {
  const summary = `GEO belt: ${marks.length} maneuver${marks.length === 1 ? "" : "s"} by longitude after the burn.`;
  return (
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
      {marks.map((mark) => {
        const x = xOf(Math.max(-180, Math.min(180, mark.longitude)));
        const reach =
          mark.drift === null
            ? 0
            : Math.max(-DRIFT_CAP, Math.min(DRIFT_CAP, mark.drift * DRIFT_SCALE));
        return (
          <g key={mark.group.maneuver.id}>
            {reach !== 0 && (
              <line
                className="geo-belt-drift"
                x1={x}
                x2={x + reach}
                y1={AXIS_Y - 14}
                y2={AXIS_Y - 14}
              />
            )}
            <circle
              className={`timeline-mark mark-dot tone-source-${mark.slot}`}
              cx={x}
              cy={AXIS_Y - 14}
              r={5}
            >
              <title>{mark.label}</title>
            </circle>
          </g>
        );
      })}
    </svg>
  );
}
