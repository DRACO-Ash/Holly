import { Link } from "react-router-dom";
import type { ActivityManeuver, ActivityNotice } from "../../types";
import { linkedManeuvers } from "./links";
import {
  type ParsedEvent,
  type Satellite,
  clockUtc,
  maneuverStart,
  timeOf,
  urgencyOf,
} from "../../utils/ops";
import { KindBadge, RegimeBadge, StatusBadge, UrgencyBadge } from "./Badges";
import { Stamp } from "./Stamp";

const SHOWN_LINKS = 3;

function Objects({
  notice,
  parsed,
}: Readonly<{ notice: ActivityNotice; parsed: ParsedEvent | null }>) {
  if (!parsed || parsed.objects.length === 0) {
    return <>{notice.event_class ?? notice.notice ?? "Notice"}</>;
  }
  return (
    <>
      {parsed.objects.map((object, index) => (
        <span key={`${object.name}-${object.id ?? index}`} className="event-object">
          {index > 0 && <span className="event-vs">vs </span>}
          {object.name}
          {object.id && object.id !== object.name && <span className="norad"> #{object.id}</span>}
        </span>
      ))}
    </>
  );
}

// One notice in a console list: its kind and urgency, the objects it is about, the other
// satellites it names, the maneuvers on those satellites, and when it arrived.
export default function NoticeRow({
  notice,
  parsed,
  directory,
  maneuversBySat,
  now,
}: Readonly<{
  notice: ActivityNotice;
  parsed: ParsedEvent | null;
  directory: ReadonlyMap<string, Satellite>;
  maneuversBySat: ReadonlyMap<string, readonly ActivityManeuver[]>;
  now: number;
}>) {
  const kind = parsed?.kind ?? "other";
  const urgency = urgencyOf(notice.urgency);
  const named = new Set(parsed?.objects.map((o) => o.id).filter(Boolean));
  const others = notice.sat_ids.filter((id) => !named.has(id));
  const first = parsed?.objects.find((o) => o.id)?.id ?? notice.sat_ids[0];
  const satellite = first ? directory.get(first) : undefined;
  const regime = parsed?.regime ?? satellite?.regime ?? null;
  const regimeFrom = parsed?.regime ? "notice" : satellite?.regimeFrom;
  const maneuvers = linkedManeuvers(notice, maneuversBySat);
  return (
    <Link
      className={`event-row kind-${kind} urgency-${urgency}`}
      to={`/notifications/${notice.id}`}
    >
      <div className="event-main">
        <div className="event-tags">
          <KindBadge kind={kind} label={parsed?.kindLabel} />
          <RegimeBadge regime={regime} from={regimeFrom} />
          <UrgencyBadge urgency={urgency} />
          {notice.status !== "OPEN" && <StatusBadge status={notice.status} />}
        </div>
        <h3 className="event-title">
          <Objects notice={notice} parsed={parsed} />
        </h3>
        {others.length > 0 && (
          <p className="event-links">
            Also names
            {others.slice(0, 4).map((id) => {
              const name = directory.get(id)?.name;
              return (
                <span key={id} className="link-chip">
                  {name ? `${name} #${id}` : `#${id}`}
                </span>
              );
            })}
            {others.length > 4 && <span>and {others.length - 4} more</span>}
          </p>
        )}
        {notice.top_action && (
          <p className="event-action">
            <strong>Next:</strong> {notice.top_action}
          </p>
        )}
        {maneuvers.length > 0 && (
          <p className="event-links">
            <span>
              {maneuvers.length} maneuver{maneuvers.length === 1 ? "" : "s"} on these satellites
            </span>
            {maneuvers.slice(0, SHOWN_LINKS).map((m) => {
              const start = maneuverStart(m);
              return (
                <span key={m.id} className="link-chip">
                  #{m.sat_no} {start === null ? "" : clockUtc(start)} {m.source ?? ""}
                </span>
              );
            })}
            {maneuvers.length > SHOWN_LINKS && (
              <span>and {maneuvers.length - SHOWN_LINKS} more</span>
            )}
          </p>
        )}
      </div>
      <div className="event-side">
        <Stamp time={timeOf(notice.udl_created_at)} now={now} />
        {notice.notice && <span className="event-meta mono">{notice.notice}</span>}
      </div>
    </Link>
  );
}
