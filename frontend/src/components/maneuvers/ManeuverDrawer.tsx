import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getManeuver } from "../../api/maneuvers";
import type { ActivityNotice, ManeuverDetail } from "../../types";
import { extractErrorMessage } from "../../utils/errors";
import type { ManeuverGroup } from "../../utils/ops";
import { drawerFacts } from "./drawerFacts";

// A maneuver opened in place: every fact its record carries, the copies folded into it, the
// notices naming its satellite, and the record as UDL published it.
export default function ManeuverDrawer({
  group,
  notices,
}: Readonly<{ group: ManeuverGroup; notices: readonly ActivityNotice[] }>) {
  const [detail, setDetail] = useState<ManeuverDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = group.maneuver.id;

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    getManeuver(id)
      .then((loaded) => {
        if (!cancelled) setDetail(loaded);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load the maneuver record."));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const facts = drawerFacts(detail?.facts ?? group.maneuver.facts);
  return (
    <>
      <h3>The record</h3>
      {facts.length === 0 ? (
        <p className="muted">The record carries none of the fields Holly reads beyond its start.</p>
      ) : (
        <dl className="fact-list">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {group.copies > 1 && (
        <p className="drawer-note">
          Folded from {group.copies} records with the same satellite, start and source:{" "}
          {group.ids.join(", ")}.
        </p>
      )}
      {notices.length > 0 && (
        <>
          <h3>Notices naming this satellite</h3>
          <p className="event-links">
            {notices.map((notice) => (
              <Link key={notice.id} className="link-chip" to={`/notifications/${notice.id}`}>
                {notice.notice ?? "Notice"}
              </Link>
            ))}
          </p>
        </>
      )}
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {!detail && !error && <p className="muted">Loading the record...</p>}
      {detail && (
        <details className="raw-disclosure">
          <summary>Raw UDL record</summary>
          <pre className="raw-json">{JSON.stringify(detail.raw, null, 2)}</pre>
        </details>
      )}
      <p className="drawer-note">
        Field names and units follow the UDL Maneuver schema as Holly reads it (TBC, re-verify
        against this record).
      </p>
    </>
  );
}
