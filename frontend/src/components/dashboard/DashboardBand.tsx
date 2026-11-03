import StatTile from "../ops/StatTile";
import { URGENCY_LABELS, type Urgency } from "../../utils/ops";

const TILES: readonly { urgency: Urgency; tone: string }[] = [
  { urgency: "high", tone: "high" },
  { urgency: "medium", tone: "medium" },
  { urgency: "low", tone: "low" },
  { urgency: "pending", tone: "pending" },
  { urgency: "none", tone: "neutral" },
];

export interface ActivityCounts {
  notices24h: number;
  maneuvers24h: number;
  satellites: number;
}

// The counts across the top: the feed by urgency, each a filter, then the last day's activity.
export default function DashboardBand({
  counts,
  activity,
  selected,
  onToggle,
}: Readonly<{
  counts: ReadonlyMap<Urgency, number>;
  activity: ActivityCounts | null;
  selected: ReadonlySet<Urgency>;
  onToggle: (urgency: Urgency) => void;
}>) {
  return (
    <div className="console-band">
      {TILES.map(({ urgency, tone }) => (
        <StatTile
          key={urgency}
          count={counts.get(urgency) ?? 0}
          label={URGENCY_LABELS[urgency]}
          tone={tone}
          pressed={selected.has(urgency)}
          onToggle={() => onToggle(urgency)}
        />
      ))}
      {activity && (
        <>
          <StatTile count={activity.notices24h} label="Notices in 24 h" tone="accent" />
          <StatTile count={activity.maneuvers24h} label="Maneuvers in 24 h" tone="maneuver" />
          <StatTile count={activity.satellites} label="Satellites active" />
        </>
      )}
    </div>
  );
}
