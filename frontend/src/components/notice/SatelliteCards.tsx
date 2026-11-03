import { Link } from "react-router-dom";
import type { ActivityOverview } from "../../types";
import { RegimeBadge, SourceBadge } from "../ops/Badges";
import { FactList } from "../ops/ManeuverRow";
import { elsetFacts, number } from "./elsetFacts";
import {
  type ManeuverGroup,
  type Satellite,
  deltaVMetresPerSecond,
  foldDuplicates,
  sourceSlots,
  stampUtc,
  maneuverStart,
} from "../../utils/ops";
import SatelliteStrip from "./SatelliteStrip";

function ManeuverList({
  groups,
  slots,
}: Readonly<{ groups: readonly ManeuverGroup[]; slots: ReadonlyMap<string, number> }>) {
  if (groups.length === 0)
    return <p className="muted">No maneuver on this satellite in the window.</p>;
  return (
    <ul className="satellite-maneuvers">
      {groups.map((group) => {
        const m = group.maneuver;
        const start = maneuverStart(m);
        const dv = deltaVMetresPerSecond(m);
        const source = m.source ?? "Unknown";
        return (
          <li key={m.id}>
            <span className="mono">{start === null ? "time unknown" : stampUtc(start)}</span>
            <SourceBadge source={source} slot={slots.get(source) ?? 4} />
            {dv !== null && <span>Δv {number(dv, 3)} m/s</span>}
            {group.copies > 1 && <span className="copies-badge">×{group.copies} records</span>}
          </li>
        );
      })}
    </ul>
  );
}

function SatelliteCard({
  satId,
  noticeId,
  data,
  directory,
  now,
}: Readonly<{
  satId: string;
  noticeId: string;
  data: ActivityOverview;
  directory: ReadonlyMap<string, Satellite>;
  now: number;
}>) {
  const satellite = directory.get(satId);
  const groups = foldDuplicates(data.maneuvers.filter((m) => String(m.sat_no) === satId));
  const notices = data.notices.filter((n) => n.sat_ids.includes(satId));
  const slots = sourceSlots(
    data.maneuvers.map((m) => m.source),
    4,
  );
  const start = Date.parse(data.window_start);
  const end = Math.max(Date.parse(data.generated_at), now);
  return (
    <li className="satellite-card">
      <div className="satellite-card-head">
        <strong>
          {satellite?.name ?? `#${satId}`}
          {satellite?.name && <span className="norad"> #{satId}</span>}
        </strong>
        <RegimeBadge regime={satellite?.regime ?? null} from={satellite?.regimeFrom} />
      </div>
      <FactList facts={elsetFacts(satellite, now)} />
      {!satellite?.elset && (
        <p className="muted">
          No element set for this satellite in the current window&apos;s overview.
        </p>
      )}
      <SatelliteStrip
        satId={satId}
        noticeId={noticeId}
        notices={notices}
        maneuvers={groups}
        start={start}
        end={end}
      />
      <ManeuverList groups={groups} slots={slots} />
      <Link to="/maneuvers" className="back-link">
        Open in Maneuvers
      </Link>
    </li>
  );
}

// Each satellite the notice names: what Holly knows of its orbit, and its activity in the window.
export default function SatelliteCards({
  satIds,
  noticeId,
  data,
  directory,
  loading,
  error,
  now,
}: Readonly<{
  satIds: readonly string[];
  noticeId: string;
  data: ActivityOverview | null;
  directory: ReadonlyMap<string, Satellite>;
  loading: boolean;
  error: string | null;
  now: number;
}>) {
  if (satIds.length === 0) return null;
  if (!data) {
    return (
      <section className="card">
        <h2>Satellites in this notice</h2>
        <p className="mono">{satIds.map((id) => `#${id}`).join(", ")}</p>
        <p className="muted">
          {loading ? "Loading their activity..." : "Their activity could not be loaded."}
        </p>
        {error && !loading && <p className="muted">{error}</p>}
      </section>
    );
  }
  return (
    <section className="card">
      <h2>Satellites in this notice</h2>
      <ul className="satellite-cards">
        {satIds.map((id) => (
          <SatelliteCard
            key={id}
            satId={id}
            noticeId={noticeId}
            data={data}
            directory={directory}
            now={now}
          />
        ))}
      </ul>
    </section>
  );
}
