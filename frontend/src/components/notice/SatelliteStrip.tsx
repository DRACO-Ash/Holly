import type { ActivityNotice } from "../../types";
import {
  type ManeuverGroup,
  dayUtc,
  maneuverStart,
  parseEventClass,
  stampUtc,
  startOfDayUtc,
  timeOf,
} from "../../utils/ops";
import { Mark } from "../ops/ActivityTimeline";
import { KIND_SHAPES } from "../ops/lanes";

const WIDTH = 300;
const HEIGHT = 56;
// Room on the left for the two lanes' names.
const LEFT = 76;
const RIGHT = 8;
const AXIS = 14;
const ROW = 20;
const DAY = 86_400_000;

// One satellite's activity across the window: its maneuvers on the upper row, the notices that
// name it on the lower, this notice marked out. Decoration beside a list that says the same.
export default function SatelliteStrip({
  satId,
  noticeId,
  notices,
  maneuvers,
  start,
  end,
}: Readonly<{
  satId: string;
  noticeId: string;
  notices: readonly ActivityNotice[];
  maneuvers: readonly ManeuverGroup[];
  start: number;
  end: number;
}>) {
  const span = Math.max(1, end - start);
  const plot = WIDTH - LEFT - RIGHT;
  const xOf = (time: number) =>
    LEFT + ((Math.min(end, Math.max(start, time)) - start) / span) * plot;
  const days: number[] = [];
  for (let day = startOfDayUtc(start) + DAY; day < end; day += DAY) days.push(day);
  const upper = AXIS + ROW / 2;
  const lower = AXIS + ROW + ROW / 2;
  return (
    <svg
      className="activity-timeline satellite-strip"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`#${satId}: ${maneuvers.length} maneuvers and ${notices.length} notices in the window`}
      focusable="false"
    >
      {days.map((day) => (
        <g key={day} className="timeline-day">
          <line x1={xOf(day)} x2={xOf(day)} y1={AXIS - 2} y2={HEIGHT - 2} />
          <text x={xOf(day) + 2} y={AXIS - 4}>
            {dayUtc(day)}
          </text>
        </g>
      ))}
      <rect className="timeline-lane-bg" x={LEFT} y={AXIS + 2} width={plot} height={ROW - 4} />
      <rect
        className="timeline-lane-bg"
        x={LEFT}
        y={AXIS + ROW + 2}
        width={plot}
        height={ROW - 4}
      />
      <text className="timeline-lane-label" x={4} y={upper + 4}>
        Maneuvers
      </text>
      <text className="timeline-lane-label" x={4} y={lower + 4}>
        Notices
      </text>
      {maneuvers.map((group) => {
        const time = maneuverStart(group.maneuver);
        if (time === null) return null;
        return (
          <circle
            key={group.maneuver.id}
            className="timeline-mark tone-maneuver"
            cx={xOf(time)}
            cy={upper}
            r={4}
          >
            <title>{`Maneuver, ${group.maneuver.source ?? "unknown source"}, ${stampUtc(time)}`}</title>
          </circle>
        );
      })}
      {notices.map((notice) => {
        const time = timeOf(notice.udl_created_at);
        if (time === null) return null;
        const kind = parseEventClass(notice.event_class)?.kind ?? "other";
        const self = notice.id === noticeId;
        const label = `${self ? "This notice" : (notice.notice ?? "A notice")}, ${stampUtc(time)}`;
        return (
          <Mark
            key={notice.id}
            mark={{
              id: notice.id,
              time,
              tone: kind,
              shape: KIND_SHAPES[kind],
              label,
              emphasis: self,
            }}
            x={xOf(time)}
            y={lower}
          />
        );
      })}
    </svg>
  );
}
