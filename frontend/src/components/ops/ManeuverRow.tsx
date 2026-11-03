import type { ReactNode } from "react";
import type { ActivityNotice } from "../../types";
import {
  type ManeuverGroup,
  type Satellite,
  clockSecondsUtc,
  maneuverStart,
} from "../../utils/ops";
import { type Fact, maneuverFacts } from "./maneuverFacts";
import { RegimeBadge, SourceBadge } from "./Badges";
import { Stamp } from "./Stamp";

// The facts as a description list, or, inside a button, where a list may not go, as text.
export function FactList({
  facts,
  inline = false,
}: Readonly<{ facts: readonly Fact[]; inline?: boolean }>) {
  if (facts.length === 0) return null;
  if (inline) {
    return (
      <span className="fact-list">
        {facts.map((fact, index) => (
          <span key={fact.label} className="fact" title={fact.title}>
            {index > 0 && <span className="visually-hidden">, </span>}
            <span className="fact-label">{fact.label}</span>{" "}
            <span className="fact-value">{fact.value}</span>
          </span>
        ))}
      </span>
    );
  }
  return (
    <dl className="fact-list">
      {facts.map((fact) => (
        <div key={fact.label} title={fact.title}>
          <dt>{fact.label}</dt>
          <dd>{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// One maneuver (its copies folded) in a console list. It opens in place to show the record.
export default function ManeuverRow({
  group,
  satellite,
  slot,
  notices,
  now,
  open,
  onToggle,
  children,
}: Readonly<{
  group: ManeuverGroup;
  satellite: Satellite | undefined;
  slot: number;
  notices: readonly ActivityNotice[];
  now: number;
  open: boolean;
  onToggle: () => void;
  children?: ReactNode;
}>) {
  const m = group.maneuver;
  const start = maneuverStart(m);
  const status = m.facts.status ?? m.maneuver_status;
  const label = m.facts.characterization ?? m.mnvr_type;
  const drawer = `maneuver-${m.id}`;
  return (
    <li>
      <button
        type="button"
        className={`event-row source-${slot}`}
        aria-expanded={open}
        aria-controls={drawer}
        onClick={onToggle}
      >
        <span className="event-main">
          <span className="event-tags">
            <SourceBadge source={m.source ?? "Unknown"} slot={slot} />
            <RegimeBadge regime={satellite?.regime ?? null} from={satellite?.regimeFrom} />
            {status && <span className="status-pill">{status}</span>}
            {m.facts.uct && <span className="status-pill">UCT</span>}
            {group.copies > 1 && (
              <span
                className="copies-badge"
                title="The provider published this maneuver more than once"
              >
                ×{group.copies} records
              </span>
            )}
          </span>
          <span className="event-title">
            {satellite?.name ?? (m.sat_no === null ? "Unidentified object" : `#${m.sat_no}`)}
            {satellite?.name && <span className="norad">#{m.sat_no}</span>}
            {label && <span className="event-vs">{label}</span>}
          </span>
          <FactList facts={maneuverFacts(group)} inline />
          {notices.length > 0 && (
            <span className="event-links">
              Named in
              {notices.slice(0, 3).map((n) => (
                <span key={n.id} className="link-chip">
                  {n.notice ?? "a notice"}
                </span>
              ))}
              {notices.length > 3 && <span>and {notices.length - 3} more</span>}
            </span>
          )}
        </span>
        <span className="event-side">
          <Stamp time={start} now={now} withClock={false} />
          {start !== null && <span className="stamp-clock">{clockSecondsUtc(start)}</span>}
        </span>
      </button>
      {open && (
        <div id={drawer} className="maneuver-drawer">
          {children}
        </div>
      )}
    </li>
  );
}
