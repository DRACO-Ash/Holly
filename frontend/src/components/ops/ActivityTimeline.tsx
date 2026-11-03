import {
  type PointerEvent,
  type ReactNode,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";
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

// The view is drawn at the width it is shown, so its text and marks keep their size on a phone;
// before it is measured, and where it cannot be, it is 1000 units wide.
const WIDTH = 1000;
const NARROW = 600;
const RIGHT = 16;
const AXIS = 26;
const LANE = 30;
const BINS = 60;
const HOUR = 3_600_000;
const DAY = 24 * HOUR;
// A drag shorter than this many view units is a click, which clears the range.
const MIN_DRAG = 6;

// A lane with more marks than this draws them smaller, so its density shows between them.
const DENSE = 80;

function markClass(mark: TimelineMark, pickable: boolean): string {
  const classes = ["timeline-mark", `mark-${mark.shape}`, `tone-${mark.tone}`];
  if (mark.emphasis) classes.push("mark-emphasis");
  if (pickable) classes.push("mark-pickable");
  return classes.join(" ");
}

// The glyph for each shape at (x, y), `size` from its centre to its edge.
function Glyph({
  shape,
  x,
  y,
  size,
  children,
  ...handlers
}: Readonly<
  {
    shape: MarkShape;
    x: number;
    y: number;
    size: number;
    children: ReactNode;
    className: string;
    onClick?: () => void;
  } & Partial<BrushHandlers>
>) {
  switch (shape) {
    case "diamond":
      return (
        <polygon
          {...handlers}
          points={`${x},${y - size} ${x + size},${y} ${x},${y + size} ${x - size},${y}`}
        >
          {children}
        </polygon>
      );
    case "triangle":
      return (
        <polygon
          {...handlers}
          points={`${x},${y - size} ${x + size},${y + size} ${x - size},${y + size}`}
        >
          {children}
        </polygon>
      );
    case "bar":
      return (
        <rect {...handlers} x={x - size} y={y - size / 2} width={2 * size} height={size}>
          {children}
        </rect>
      );
    case "square":
      return (
        <rect
          {...handlers}
          x={x - size + 1}
          y={y - size + 1}
          width={2 * size - 2}
          height={2 * size - 2}
        >
          {children}
        </rect>
      );
    default:
      return (
        <circle {...handlers} cx={x} cy={y} r={size}>
          {children}
        </circle>
      );
  }
}

// The plot's drag handlers. A mark that is not picked carries them too, so a drag can start on it.
export interface BrushHandlers {
  onPointerDown: (event: PointerEvent) => void;
  onPointerMove: (event: PointerEvent) => void;
  onPointerUp: () => void;
  onPointerCancel: () => void;
}

export function Mark({
  mark,
  x,
  y,
  onPick,
  brush,
  dense = false,
}: Readonly<{
  mark: TimelineMark;
  x: number;
  y: number;
  onPick?: (id: string) => void;
  brush?: BrushHandlers;
  dense?: boolean;
}>) {
  const base = dense ? 3 : 5;
  const pointer = onPick
    ? { onPointerDown: (event: PointerEvent) => event.stopPropagation() }
    : brush;
  return (
    <Glyph
      shape={mark.shape}
      x={x}
      y={y}
      size={mark.emphasis ? base + 2 : base}
      className={markClass(mark, onPick !== undefined)}
      // A pickable mark takes its own pointer; any other starts a drag as the plot does.
      {...pointer}
      onClick={onPick ? () => onPick(mark.id) : undefined}
    >
      <title>{mark.label}</title>
    </Glyph>
  );
}

function useViewWidth(ref: RefObject<SVGSVGElement | null>): number {
  const [width, setWidth] = useState(WIDTH);
  useEffect(() => {
    const element = ref.current?.parentElement;
    if (!element || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.round(entry.contentRect.width);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

// A lane's label cut to fit the gutter, its whole text kept for the tooltip.
function fitted(label: string, gutter: number): string {
  const room = Math.max(4, Math.floor((gutter - 44) / 7.6));
  return label.length <= room ? label : `${label.slice(0, room - 1)}…`;
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
  const width = useViewWidth(svgRef);
  const gutter = width < NARROW ? 110 : 200;
  const plot = Math.max(1, width - gutter - RIGHT);
  const height = AXIS + lanes.length * LANE + 8;
  const span = Math.max(1, end - start);
  const xOf = (time: number) =>
    gutter + ((Math.min(end, Math.max(start, time)) - start) / span) * plot;
  const timeOf = (x: number) =>
    start + ((Math.min(gutter + plot, Math.max(gutter, x)) - gutter) / plot) * span;

  const viewX = (event: PointerEvent) => {
    const box = svgRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return gutter;
    return ((event.clientX - box.left) / box.width) * width;
  };
  const onDown = (event: PointerEvent) => {
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Without pointer capture the drag still works while the pointer stays on the plot.
    }
    const x = viewX(event);
    setDrag([x, x]);
  };
  const onMove = (event: PointerEvent) => {
    if (drag) setDrag([drag[0], viewX(event)]);
  };
  const onUp = () => {
    if (!drag) return;
    const [a, b] = drag;
    setDrag(null);
    if (Math.abs(b - a) < MIN_DRAG) onRange(null);
    else onRange([timeOf(Math.min(a, b)), timeOf(Math.max(a, b))]);
  };

  const brush: BrushHandlers = {
    onPointerDown: onDown,
    onPointerMove: onMove,
    onPointerUp: onUp,
    onPointerCancel: () => setDrag(null),
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
      viewBox={`0 0 ${width} ${height}`}
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
              x={gutter}
              y={top + 2}
              width={plot}
              height={LANE - 4}
            />
            {counts.map((count, bin) =>
              count === 0 ? null : (
                <rect
                  key={`${lane.key}-${bin * (plot / BINS)}`}
                  className="timeline-density"
                  x={gutter + (bin * plot) / BINS}
                  width={plot / BINS}
                  y={top + 2 + (LANE - 4) * (1 - count / peak)}
                  height={(LANE - 4) * (count / peak)}
                />
              ),
            )}
            <g>
              {fitted(lane.label, gutter) !== lane.label && <title>{lane.label}</title>}
              <text className="timeline-lane-label" x={8} y={top + LANE / 2 + 4}>
                {fitted(lane.label, gutter)}
              </text>
            </g>
            <text className="timeline-lane-count" x={gutter - 10} y={top + LANE / 2 + 4}>
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
        x={gutter}
        y={AXIS - 4}
        width={plot}
        height={height - AXIS}
        {...brush}
      />
      {lanes.map((lane, index) => {
        const y = AXIS + index * LANE + LANE / 2;
        return (
          <g key={`${lane.key}-marks`}>
            {lane.marks.map((mark) => (
              <Mark
                key={mark.id}
                mark={mark}
                x={xOf(mark.time)}
                y={y}
                onPick={onPick}
                brush={brush}
                dense={lane.marks.length > DENSE}
              />
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
