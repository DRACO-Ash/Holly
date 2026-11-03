import { useState } from "react";
import ManeuversArchive from "../components/maneuvers/ManeuversArchive";
import ManeuversLive from "../components/maneuvers/ManeuversLive";

type View = "live" | "archive";

// Maneuvers: the live window as a console by default, and every stored record in the archive.
export default function ManeuversPage() {
  const [view, setView] = useState<View>("live");
  return (
    <div className="console-page">
      <fieldset className="segmented view-tabs">
        <legend className="visually-hidden">View</legend>
        <button type="button" aria-pressed={view === "live"} onClick={() => setView("live")}>
          Live window
        </button>
        <button type="button" aria-pressed={view === "archive"} onClick={() => setView("archive")}>
          Full archive
        </button>
      </fieldset>
      {view === "live" ? <ManeuversLive /> : <ManeuversArchive />}
    </div>
  );
}
