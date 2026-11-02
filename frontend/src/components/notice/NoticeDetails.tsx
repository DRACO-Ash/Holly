import { Fragment } from "react";
import type { NotificationDetail } from "../../types";
import { NEW_TAB_REL, safeHttpUrl } from "../../utils/links";
import { StatusBadge } from "../ops/Badges";

function formatField(value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  return new Date(value).toISOString().replace("T", " ").slice(0, 19);
}

function satelliteNumbers(item: NotificationDetail): string {
  if (item.sat_ids && item.sat_ids.length > 0) return item.sat_ids.join(", ");
  return item.sat_no === null ? "n/a" : String(item.sat_no);
}

function SourceLink({ link }: Readonly<{ link: string }>) {
  const safe = safeHttpUrl(link);
  if (!safe) return <span>{link}</span>;
  return (
    <a href={safe} target="_blank" rel={NEW_TAB_REL}>
      {link}
    </a>
  );
}

// Every field of the notice in one list: status, identification and timing.
export default function NoticeDetails({ item }: Readonly<{ item: NotificationDetail }>) {
  const rows: [string, string][] = [
    ["Event type", formatField(item.event_type)],
    ["Message type", formatField(item.msg_type)],
    ["Classification", formatField(item.classification_marking)],
    ["Data mode", formatField(item.data_mode)],
    ["Notice", formatField(item.notso_identifier ?? item.notice_id)],
    ["Event ID", formatField(item.event_id)],
    ["UDL ID", formatField(item.udl_id)],
    ["Source", formatField(item.source)],
    ["Origin network", formatField(item.orig_network)],
    ["Created by", formatField(item.created_by)],
    ["Author", formatField(item.company_name)],
    ["UDL created", formatDateTime(item.udl_created_at)],
    ["Published", formatDateTime(item.publish_date)],
    ["Effective from", formatDateTime(item.effective_from)],
    ["Effective until", formatDateTime(item.effective_until)],
    ["Satellite numbers", satelliteNumbers(item)],
    ["Region", formatField(item.region)],
  ];
  return (
    <section className="card">
      <h2>Details</h2>
      <dl className="detail-grid">
        <dt>Status</dt>
        <dd>{item.status ? <StatusBadge status={item.status} /> : "n/a"}</dd>
        {rows.map(([term, value]) => (
          <Fragment key={term}>
            <dt>{term}</dt>
            <dd>{value}</dd>
          </Fragment>
        ))}
        {item.notso_link && (
          <>
            <dt>Source link</dt>
            <dd>
              <SourceLink link={item.notso_link} />
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}
