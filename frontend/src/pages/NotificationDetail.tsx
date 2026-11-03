import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getNotification } from "../api/notifications";
import AssistantPanel from "../components/AssistantPanel";
import NoticeDetails from "../components/notice/NoticeDetails";
import NoticeHero from "../components/notice/NoticeHero";
import SatelliteCards from "../components/notice/SatelliteCards";
import { useActivity } from "../components/ops/useActivity";
import { useNow } from "../components/ops/useNow";
import type { NotificationDetail as NotificationDetailType } from "../types";
import { NEW_TAB_REL } from "../utils/links";
import { parseArtefacts } from "../utils/notso";
import { parseEventClass, satelliteDirectory } from "../utils/ops";

function loadFailure(err: unknown): string {
  const status =
    err && typeof err === "object" && "response" in err
      ? (err as { response?: { status?: number } }).response?.status
      : undefined;
  return status === 404 ? "Notification not found." : "Failed to load notification.";
}

function satIdsOf(item: NotificationDetailType): string[] {
  if (item.sat_ids && item.sat_ids.length > 0) return item.sat_ids;
  return item.sat_no === null ? [] : [String(item.sat_no)];
}

function Artefacts({ item }: Readonly<{ item: NotificationDetailType }>) {
  const images = parseArtefacts(item.raw);
  if (images.length === 0) return null;
  return (
    <section className="card">
      <h2>Source artefacts ({images.length})</h2>
      <ul className="image-list">
        {images.map((img, idx) => (
          <li key={img.id ?? `${img.url ?? "artefact"}-${idx}`}>
            {img.href ? (
              <a href={img.href} target="_blank" rel={NEW_TAB_REL}>
                {img.filename ?? img.url}
              </a>
            ) : (
              <span>{img.filename ?? "(unnamed artefact)"}</span>
            )}
            {img.caption && <span className="image-caption"> &middot; {img.caption}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

// A notice's page: the event first, the assistant's reading, the satellites it names with their
// orbits and activity in the window, then the notice's own text, artefacts and every field.
export default function NotificationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [item, setItem] = useState<NotificationDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activity = useActivity();
  const now = useNow();

  useEffect(() => {
    if (!id) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getNotification(id)
      .then((data) => {
        if (!cancelled) setItem(data);
      })
      .catch((error_: unknown) => {
        if (!cancelled) setError(loadFailure(error_));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const data = activity.data;
  const directory = useMemo(
    () => (data ? satelliteDirectory(data.notices, data.maneuvers, data.elsets) : new Map()),
    [data],
  );

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="form-error">{error}</div>;
  if (!item) return null;

  const parsed = parseEventClass(item.event_class);
  const satIds = satIdsOf(item);
  const first = parsed?.objects.find((o) => o.id)?.id ?? satIds[0];

  return (
    <div>
      <Link to="/notifications" className="back-link">
        &larr; Back to notifications
      </Link>
      <NoticeHero
        item={item}
        parsed={parsed}
        entry={data?.notices.find((n) => n.id === item.id)}
        first={first ? directory.get(first) : undefined}
        now={now}
      />

      <AssistantPanel notificationId={item.id} />

      <SatelliteCards
        satIds={satIds}
        noticeId={item.id}
        data={data}
        directory={directory}
        loading={activity.loading}
        error={activity.error}
        now={now}
      />

      {item.description && (
        <section className="card">
          <h2>Event description</h2>
          <pre className="notso-description">{item.description}</pre>
        </section>
      )}

      <Artefacts item={item} />

      <NoticeDetails item={item} />

      <section className="card">
        <details className="raw-disclosure">
          <summary>Raw UDL payload</summary>
          <pre className="raw-json">{JSON.stringify(item.raw, null, 2)}</pre>
        </details>
      </section>
    </div>
  );
}
