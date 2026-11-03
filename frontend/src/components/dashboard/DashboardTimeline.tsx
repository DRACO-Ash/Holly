import { useNavigate } from "react-router-dom";
import ActivityTimeline, { type TimelineLane } from "../ops/ActivityTimeline";
import { type RangeChoice, resolveRange } from "../ops/consoleFilters";
import { noticeLanesByUrgency } from "../ops/lanes";
import RangeButtons from "../ops/RangeButtons";
import type { ActivityOverview } from "../../types";
import { type ManeuverGroup, maneuverStart, parseEventClass, stampUtc } from "../../utils/ops";
import { formatWindow } from "./feed";

function maneuverLane(groups: readonly ManeuverGroup[]): TimelineLane {
  const marks = [];
  for (const group of groups) {
    const time = maneuverStart(group.maneuver);
    if (time === null) continue;
    const sat =
      group.maneuver.sat_no === null ? "Unidentified object" : `#${group.maneuver.sat_no}`;
    marks.push({
      id: group.maneuver.id,
      time,
      tone: "maneuver",
      shape: "dot" as const,
      label: `Maneuver: ${sat}, ${group.maneuver.source ?? "Unknown"}, ${stampUtc(time)}`,
    });
  }
  return { key: "maneuvers", label: "Maneuvers", tone: "maneuver", marks };
}

// The window on one timeline: the notices by urgency, then every maneuver, with the range that
// filters the feed below. A notice's mark opens it.
export default function DashboardTimeline({
  data,
  groups,
  now,
  choice,
  onChoose,
}: Readonly<{
  data: ActivityOverview;
  groups: readonly ManeuverGroup[];
  now: number;
  choice: RangeChoice;
  onChoose: (choice: RangeChoice) => void;
}>) {
  const navigate = useNavigate();
  const notices = new Set(data.notices.map((n) => n.id));
  const lanes = [
    ...noticeLanesByUrgency(data.notices, (n) => parseEventClass(n.event_class)),
    maneuverLane(groups),
  ];
  const start = Date.parse(data.window_start);
  const end = Math.max(now, Date.parse(data.generated_at));
  const title = `Last ${formatWindow(data.window_hours)}`;
  return (
    <section className="console-panel" aria-labelledby="dashboard-timeline-title">
      <div className="console-panel-head">
        <h2 id="dashboard-timeline-title">{title}</h2>
        <RangeButtons choice={choice} onChoose={onChoose} />
      </div>
      <ActivityTimeline
        lanes={lanes}
        start={start}
        end={end}
        now={now}
        title={title}
        range={resolveRange(choice, now)}
        onRange={(range) => onChoose(range ? { from: range[0], to: range[1] } : null)}
        onPick={(id) => {
          if (notices.has(id)) navigate(`/notifications/${id}`);
          else navigate("/maneuvers");
        }}
      />
      <p className="console-hint">
        Drag across the timeline to show only that stretch of the feed; click it to clear.
      </p>
    </section>
  );
}
