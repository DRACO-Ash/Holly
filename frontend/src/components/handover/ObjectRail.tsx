import { useState } from "react";
import type { HandoverObject } from "../../types";
import { eventKind, stampUtc } from "../../utils/ops";
import { KindBadge } from "../ops/Badges";

const matches = (o: HandoverObject, text: string) => {
  const wanted = text.trim().toLowerCase();
  if (!wanted) return true;
  return `${o.sat_no} ${o.name ?? ""} ${o.kinds.join(" ")}`.toLowerCase().includes(wanted);
};

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

// The objects with live events, newest first: pick one to read its story.
export default function ObjectRail({
  objects,
  selected,
  onSelect,
}: Readonly<{
  objects: readonly HandoverObject[];
  selected: number | null;
  onSelect: (satNo: number) => void;
}>) {
  const [text, setText] = useState("");
  const shown = objects.filter((o) => matches(o, text));
  return (
    <nav className="console-panel handover-rail" aria-label="Objects with live events">
      <label className="console-search">
        <span>Find an object</span>
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Name, number or kind"
          maxLength={100}
        />
      </label>
      {shown.length === 0 ? (
        <p className="console-empty">No object matches.</p>
      ) : (
        <ul className="handover-objects">
          {shown.map((o) => (
            <li key={o.sat_no}>
              <button
                type="button"
                className="handover-object"
                aria-pressed={o.sat_no === selected}
                onClick={() => onSelect(o.sat_no)}
              >
                <span className="handover-object-name">
                  {o.name ?? "Unnamed object"} <span className="mono">({o.sat_no})</span>
                </span>
                <span className="handover-object-kinds">
                  {o.kinds.map((k) => (
                    <KindBadge key={k} kind={eventKind(k)} label={k} />
                  ))}
                </span>
                <span className="handover-object-meta">
                  {plural(o.events, "notice")} · {plural(o.maneuvers, "provider record")}
                  {o.latest_at && <> · latest {stampUtc(Date.parse(o.latest_at))}</>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
