import NoticeRow from "../ops/NoticeRow";
import type { ActivityManeuver } from "../../types";
import { type Satellite, dayHeading, groupByDay } from "../../utils/ops";
import type { NoticeEntry } from "./noticeFilters";

// The notices shown, grouped by UTC day, newest first; or why there are none.
export default function NoticeList({
  entries,
  filtered,
  directory,
  maneuversBySat,
  now,
  onClear,
}: Readonly<{
  entries: readonly NoticeEntry[];
  filtered: boolean;
  directory: ReadonlyMap<string, Satellite>;
  maneuversBySat: ReadonlyMap<string, readonly ActivityManeuver[]>;
  now: number;
  onClear: () => void;
}>) {
  if (entries.length === 0) {
    return (
      <div className="console-empty">
        {filtered ? (
          <>
            <p>No notice in the window matches these filters.</p>
            <button type="button" onClick={onClear}>
              Clear filters
            </button>
          </>
        ) : (
          <p>No notices in the window. New ones appear here as UDL publishes them.</p>
        )}
      </div>
    );
  }
  return (
    <>
      {groupByDay(entries, (e) => e.time).map((group) => (
        <section key={group.day ?? "unknown"} className="event-day">
          <h2 className="event-day-heading">
            {group.day === null ? "Time unknown" : dayHeading(group.day, now)}
            <span className="event-day-count">{group.items.length}</span>
          </h2>
          <ul className="event-list">
            {group.items.map((entry) => (
              <li key={entry.notice.id}>
                <NoticeRow
                  notice={entry.notice}
                  parsed={entry.parsed}
                  directory={directory}
                  maneuversBySat={maneuversBySat}
                  now={now}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
