import { type PointerEvent, useRef, useState } from "react";
import { dayUtc, histogram, startOfDayUtc } from "../../utils/ops";

export type MarkShape = "dot" | "diamond" | "ring" | "triangle" | "square" | "bar";

export interface TimelineMark {
  id: string;
  time: number;
  // The class suffix for the mark's hue: a kind, a source slot or an urgency.
  tone: string;
  shape: MarkShape;
  // What the mark is, for its tooltip: the list beside the timeline says the same.
  label: string;
  emphasis?: boolean;
}

export interface TimelineLane {
  key: string;
  label: string;
  tone: string;
  marks: TimelineMark[];
}

export type TimeRange = readonly [number, number];

const WIDTH = 1000;
const GUTTER = 200;
const RIGHT = 16;
const AXIS = 26;
const LANE = 30;
const BINS = 60;
const PLOT = WIDTH - GUTTER - RIGHT;
const HOUR = 3_600_000;
const DAY = 24 * HOUR;
// A drag shorter than this many view units is a click, which clears the range.
const MIN_DRAG = 6;

function Mark({
  mark,
  x,
  y,
  onPick,
}: Readonly<{ mark: TimelineMark; x: number; y: number; onPick?: (id: string) => void }>) {
  const size = mark.emphasis ? 7 : 5;
  const common = {
    className: `timeline-mark mark-${mark.shape} tone-${mark.tone}${mark.emphasis ? " mark-emphasis" : ""}${onPick ? " mark-pickable" : ""}`,
    onPointerDown: (event: PointerEvent) => event.stopPropagation(),
    onClick: onPick ? () => onPick(mark.id) : undefined,
  };
  const title = <title>{mark.label}</title>;
  if (mark.shape === "diamond") {
    return (
      <polygon
        {...common}
        points={`${x},${y - size} ${x + size},${y} ${x},${y + size} ${x - size},${y}`}
      >
        {title}
      </polygon>
    );
  }
  if (mark.shape === "triangle") {
    return (
      <polygon
        {...common}
        points={`${x},${y - size} ${x + size},${y + size} ${x - size},${y + size}`}
      >
        {title}
      </polygon>
    );
  }
  if (mark.shape === "bar") {
    return (
      <rect {...common} x={x - size} y={y - size / 2} width={2 * size} height={size}>
        {title}
      </rect>
    );
  }
  if (mark.shape === "square") {
    return (
      <rect
        {...common}
        x={x - size + 1}
        y={y - size + 1}
        width={2 * size - 2}
        height={2 * size - 2}
      >
        {title}
      </rect>
    );
  }
  return (
    <circle {...common} cx={x} cy={y} r={size}>
      {title}
    </circle>
  );
}

function dayTicks(start: number, end: number): number[] {
  const ticks: number[] = [];
  for (let day = startOfDayUtc(start) + DAY; day < end; day += DAY) ticks.push(day);
  return ticks;
}

// Swimlanes across the window: one lane per kind or source, a mark per event at its time, a
// faint density of the lane's events behind its marks, the UTC days, and now. Dragging across
// the plot picks a time range, which the view applies as a filter; a click clears it. The view
// offers the same range as buttons, so nothing here is reachable by pointer alone.
export default function ActivityTimeline({
  lanes,
  start,
  end,
  now,
  title,
  range,
  onRange,
  onPick,
}: Readonly<{
  lanes: readonly TimelineLane[];
  start: number;
  end: number;
  now: number;
  title: string;
  range: TimeRange | null;
  onRange: (range: TimeRange | null) => void;
  onPick?: (id: string) => void;
}>) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<readonly [number, number] | null>(null);
  const height = AXIS + lanes.length * LANE + 8;
  const span = Math.max(1, end - start);
  const xOf = (time: number) =>
    GUTTER + ((Math.min(end, Math.max(start, time)) - start) / span) * PLOT;
  const timeOf = (x: number) =>
    start + ((Math.min(GUTTER + PLOT, Math.max(GUTTER, x)) - GUTTER) / PLOT) * span;

  const viewX = (event: PointerEvent) => {
    const box = svgRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return GUTTER;
    return ((event.clientX - box.left) / box.width) * WIDTH;
  };
  const onDown = (event: PointerEvent<SVGRectElement>) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const x = viewX(event);
    setDrag([x, x]);
  };
  const onMove = (event: PointerEvent<SVGRectElement>) => {
    if (drag) setDrag([drag[0], viewX(event)]);
  };
  const onUp = () => {
    if (!drag) return;
    const [a, b] = drag;
    setDrag(null);
    if (Math.abs(b - a) < MIN_DRAG) onRange(null);
    else onRange([timeOf(Math.min(a, b)), timeOf(Math.max(a, b))]);
  };

  const shown: TimeRange | null = drag
    ? [timeOf(Math.min(...drag)), timeOf(Math.max(...drag))]
    : range;
  const total = lanes.reduce((n, lane) => n + lane.marks.length, 0);
  const summary = `${title}: ${total} events in ${lanes.length} lanes, ${lanes
    .map((lane) => `${lane.label} ${lane.marks.length}`)
    .join(", ")}.`;

  return (
    <svg
      ref={svgRef}
      className="activity-timeline"
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label={summary}
      focusable="false"
    >
      {dayTicks(start, end).map((tick) => (
        <g key={tick} className="timeline-day">
          <line x1={xOf(tick)} x2={xOf(tick)} y1={AXIS - 6} y2={height - 4} />
          <text x={xOf(tick) + 4} y={AXIS - 10}>
            {dayUtc(tick)}
          </text>
        </g>
      ))}
      {lanes.map((lane, index) => {
        const top = AXIS + index * LANE;
        const counts = histogram(
          lane.marks.map((m) => m.time),
          start,
          end,
          BINS,
        );
        const peak = Math.max(1, ...counts);
        return (
          <g key={lane.key} className={`timeline-lane tone-${lane.tone}`}>
            <rect
              className="timeline-lane-bg"
              x={GUTTER}
              y={top + 2}
              width={PLOT}
              height={LANE - 4}
            />
            {counts.map((count, bin) =>
              count === 0 ? null : (
                <rect
                  key={`${lane.key}-${bin * (PLOT / BINS)}`}
                  className="timeline-density"
                  x={GUTTER + (bin * PLOT) / BINS}
                  width={PLOT / BINS}
                  y={top + 2 + (LANE - 4) * (1 - count / peak)}
                  height={(LANE - 4) * (count / peak)}
                />
              ),
            )}
            <text className="timeline-lane-label" x={8} y={top + LANE / 2 + 4}>
              {lane.label}
            </text>
            <text className="timeline-lane-count" x={GUTTER - 10} y={top + LANE / 2 + 4}>
              {lane.marks.length}
            </text>
          </g>
        );
      })}
      {shown && (
        <rect
          className="timeline-range"
          x={xOf(shown[0])}
          y={AXIS - 4}
          width={Math.max(1, xOf(shown[1]) - xOf(shown[0]))}
          height={height - AXIS}
        />
      )}
      <rect
        className="timeline-brush"
        x={GUTTER}
        y={AXIS - 4}
        width={PLOT}
        height={height - AXIS}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={() => setDrag(null)}
      />
      {lanes.map((lane, index) => {
        const y = AXIS + index * LANE + LANE / 2;
        return (
          <g key={`${lane.key}-marks`}>
            {lane.marks.map((mark) => (
              <Mark key={mark.id} mark={mark} x={xOf(mark.time)} y={y} onPick={onPick} />
            ))}
          </g>
        );
      })}
      {now >= start && now <= end + HOUR && (
        <g className="timeline-now">
          <line x1={xOf(now)} x2={xOf(now)} y1={AXIS - 8} y2={height - 4} />
          <text x={xOf(now) - 4} y={AXIS - 10}>
            now
          </text>
        </g>
      )}
    </svg>
  );
}
