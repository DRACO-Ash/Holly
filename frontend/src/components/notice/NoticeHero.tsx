import type { ActivityNotice, NotificationDetail } from "../../types";
import { KindBadge, RegimeBadge, StatusBadge, UrgencyBadge } from "../ops/Badges";
import { Stamp } from "../ops/Stamp";
import { type ParsedEvent, type Satellite, stampUtc, timeOf, urgencyOf } from "../../utils/ops";

function Title({
  item,
  parsed,
}: Readonly<{ item: NotificationDetail; parsed: ParsedEvent | null }>) {
  if (!parsed || parsed.objects.length === 0) {
    return <>{item.notso_identifier ?? item.notice_id ?? "Notification"}</>;
  }
  return (
    <>
      {parsed.objects.map((object, index) => (
        <span key={`${object.name}-${object.id ?? "none"}`}>
          {index > 0 && <span className="event-vs">vs </span>}
          {object.name}
          {object.id && object.id !== object.name && <span className="norad"> #{object.id}</span>}
        </span>
      ))}
    </>
  );
}

function Moment({ label, value }: Readonly<{ label: string; value: string | null }>) {
  const time = timeOf(value);
  if (time === null) return null;
  return (
    <span>
      {label} {stampUtc(time)}
    </span>
  );
}

// The notice's event first: its kind, urgency and regime, the objects it is about, and when.
export default function NoticeHero({
  item,
  parsed,
  entry,
  first,
  now,
}: Readonly<{
  item: NotificationDetail;
  parsed: ParsedEvent | null;
  entry: ActivityNotice | undefined;
  first: Satellite | undefined;
  now: number;
}>) {
  const kind = parsed?.kind ?? "other";
  const regime = parsed?.regime ?? first?.regime ?? null;
  const regimeFrom = parsed?.regime ? "notice" : first?.regimeFrom;
  const notice = item.notso_identifier ?? item.notice_id;
  return (
    <section className={`notice-hero kind-${kind}`}>
      <div className="event-tags">
        {parsed && <KindBadge kind={kind} label={parsed.kindLabel} />}
        <RegimeBadge regime={regime} from={regimeFrom} />
        {entry && <UrgencyBadge urgency={urgencyOf(entry.urgency)} />}
        <StatusBadge status={item.status} />
      </div>
      <h1>
        <Title item={item} parsed={parsed} />
      </h1>
      <p className="notice-hero-meta">
        {notice && <span className="mono">{notice}</span>}
        <span>
          UDL created <Stamp time={timeOf(item.udl_created_at)} now={now} withClock={false} />
        </span>
        <Moment label="Published" value={item.publish_date} />
        <Moment label="Effective from" value={item.effective_from} />
        <Moment label="Effective until" value={item.effective_until} />
        {item.company_name && <span>By {item.company_name}</span>}
      </p>
    </section>
  );
}
