import StatTile from "../ops/StatTile";
import {
  EVENT_KINDS,
  type EventKind,
  KIND_LABELS,
  REGIMES,
  type Regime,
  type Urgency,
} from "../../utils/ops";
import { type NoticeEntry, type NoticeFilters, countBy } from "./noticeFilters";

const DAY = 86_400_000;

// The window in counts, each but the first a filter: urgency, kind and regime.
export default function NoticeBand({
  entries,
  filters,
  now,
  onUrgency,
  onKind,
  onRegime,
}: Readonly<{
  entries: readonly NoticeEntry[];
  filters: NoticeFilters;
  now: number;
  onUrgency: (urgency: Urgency) => void;
  onKind: (kind: EventKind) => void;
  onRegime: (regime: Regime) => void;
}>) {
  const recent = entries.filter((e) => e.time !== null && now - e.time <= DAY).length;
  const urgencies = countBy(entries, (e) => e.urgency);
  const kinds = countBy(entries, (e) => e.kind);
  const regimes = countBy(entries, (e) => e.regime);
  return (
    <div className="console-band">
      <StatTile
        count={entries.length}
        label="In window"
        detail={`+${recent} in last 24 h`}
        tone="accent"
      />
      {(["high", "medium"] as const).map((urgency) => (
        <StatTile
          key={urgency}
          count={urgencies.get(urgency) ?? 0}
          label={urgency === "high" ? "High urgency" : "Medium urgency"}
          tone={urgency}
          pressed={filters.urgencies.has(urgency)}
          onToggle={() => onUrgency(urgency)}
        />
      ))}
      {EVENT_KINDS.filter((kind) => kinds.has(kind)).map((kind) => (
        <StatTile
          key={kind}
          count={kinds.get(kind) ?? 0}
          label={KIND_LABELS[kind]}
          tone={kind}
          pressed={filters.kinds.has(kind)}
          onToggle={() => onKind(kind)}
        />
      ))}
      {REGIMES.filter((regime) => regimes.has(regime)).map((regime) => (
        <StatTile
          key={regime}
          count={regimes.get(regime) ?? 0}
          label={regime}
          detail="regime"
          pressed={filters.regimes.has(regime)}
          onToggle={() => onRegime(regime)}
        />
      ))}
    </div>
  );
}
