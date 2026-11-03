import { Link } from "react-router-dom";
import { KindBadge, RegimeBadge } from "../ops/Badges";
import { linkedManeuvers } from "../ops/links";
import { Stamp } from "../ops/Stamp";
import type { ActivityManeuver, AssistantFeedItem } from "../../types";
import { type Satellite, type Urgency, parseEventClass, timeOf } from "../../utils/ops";
import { asActivityNotice } from "./feed";

function Title({ item }: Readonly<{ item: AssistantFeedItem }>) {
  const n = item.notification;
  const parsed = parseEventClass(n.event_class);
  if (!parsed || parsed.objects.length === 0) return null;
  return (
    <span className="event-title">
      {parsed.objects.map((object, index) => (
        <span key={`${object.name}-${object.id ?? index}`} className="event-object">
          {index > 0 && <span className="event-vs">vs </span>}
          {object.name}
          {object.id && object.id !== object.name && <span className="norad"> #{object.id}</span>}
        </span>
      ))}
    </span>
  );
}

function Pending({ cleared }: Readonly<{ cleared: boolean }>) {
  return (
    <div className="muted">
      {cleared
        ? "Awaiting assistant analysis..."
        : "Not sent to the assistant: its classification marking is not cleared."}
    </div>
  );
}

// One notice in the feed: what it is and about which objects, how it has evolved, the
// assistant's summary and next action, and the maneuvers on the satellites it names.
export default function FeedItem({
  item,
  bucket,
  directory,
  maneuversBySat,
  now,
}: Readonly<{
  item: AssistantFeedItem;
  bucket: Urgency;
  directory: ReadonlyMap<string, Satellite>;
  maneuversBySat: ReadonlyMap<string, readonly ActivityManeuver[]>;
  now: number;
}>) {
  const n = item.notification;
  const parsed = parseEventClass(n.event_class);
  const notice = asActivityNotice(item);
  const first = parsed?.objects.find((o) => o.id)?.id ?? notice.sat_ids[0];
  const satellite = first ? directory.get(first) : undefined;
  const maneuvers = linkedManeuvers(notice, maneuversBySat);
  const summary = item.evaluation?.summary;
  const publications = item.event_publication_count ?? 0;
  return (
    <li>
      <Link
        className={`event-row kind-${parsed?.kind ?? "other"} urgency-${bucket}`}
        to={`/notifications/${n.id}`}
      >
        <div className="event-main">
          <div className="event-tags">
            {parsed && <KindBadge kind={parsed.kind} label={parsed.kindLabel} />}
            <RegimeBadge
              regime={parsed?.regime ?? satellite?.regime ?? null}
              from={parsed?.regime ? "notice" : satellite?.regimeFrom}
            />
            <strong className="event-meta mono">{notice.notice ?? "Notification"}</strong>
          </div>
          <Title item={item} />
          {item.event_summary && (
            <p className="action-feed-evolution">
              <span className="evolution-label">
                Event evolution
                {publications > 1 && <> &middot; {publications} publications</>}
              </span>
              {item.event_summary}
            </p>
          )}
          {summary && <p className="action-feed-summary">{summary}</p>}
          {item.top_action && (
            <p className="event-action action-feed-action">
              <strong>Next:</strong> {item.top_action}
            </p>
          )}
          {maneuvers.length > 0 && (
            <p className="event-links">
              {maneuvers.length} maneuver{maneuvers.length === 1 ? "" : "s"} on these satellites
            </p>
          )}
          {bucket === "pending" && <Pending cleared={item.assistant_cleared} />}
        </div>
        <div className="event-side">
          <Stamp time={timeOf(n.udl_created_at)} now={now} />
        </div>
      </Link>
    </li>
  );
}
