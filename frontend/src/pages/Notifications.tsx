import { useState } from "react";
import NotificationsArchive from "../components/notifications/NotificationsArchive";
import NotificationsLive from "../components/notifications/NotificationsLive";

type View = "live" | "archive";

// Notifications: the live window as a console by default, and every notice Holly holds, a page
// at a time, as the archive.
export default function NotificationsPage() {
  const [view, setView] = useState<View>("live");
  return (
    <div className="console">
      <fieldset className="segmented view-tabs">
        <legend className="visually-hidden">View</legend>
        <button type="button" aria-pressed={view === "live"} onClick={() => setView("live")}>
          Live window
        </button>
        <button type="button" aria-pressed={view === "archive"} onClick={() => setView("archive")}>
          Full archive
        </button>
      </fieldset>
      {view === "live" && <NotificationsLive />}
      {view === "archive" && <NotificationsArchive />}
    </div>
  );
}
