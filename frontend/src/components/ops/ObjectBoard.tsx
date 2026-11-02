import type { ObjectActivity, Satellite } from "../../utils/ops";
import { RegimeBadge } from "./Badges";
import { Sparkline } from "./Sparkline";

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

// The satellites with the most activity in the window. Choosing one filters the view to it.
export default function ObjectBoard({
  title,
  entries,
  directory,
  start,
  end,
  selected,
  onSelect,
}: Readonly<{
  title: string;
  entries: readonly ObjectActivity[];
  directory: ReadonlyMap<string, Satellite>;
  start: number;
  end: number;
  selected: string | null;
  onSelect: (id: string | null) => void;
}>) {
  return (
    <section className="object-board" aria-labelledby="object-board-title">
      <h2 id="object-board-title">{title}</h2>
      {entries.length === 0 ? (
        <p className="muted">No satellite has activity in the window.</p>
      ) : (
        <ol>
          {entries.map((entry, index) => {
            const satellite = directory.get(entry.id);
            const on = selected === entry.id;
            return (
              <li key={entry.id}>
                <button
                  type="button"
                  className="object-row"
                  aria-pressed={on}
                  onClick={() => onSelect(on ? null : entry.id)}
                >
                  <span className="object-rank">{index + 1}</span>
                  <span className="object-name">
                    <strong>{satellite?.name ?? `#${entry.id}`}</strong>
                    {satellite?.name && <span className="object-id">#{entry.id}</span>}
                  </span>
                  <RegimeBadge regime={satellite?.regime ?? null} from={satellite?.regimeFrom} />
                  <Sparkline times={entry.times} start={start} end={end} />
                  <span className="object-counts">
                    {entry.notices.length > 0 && (
                      <span>{plural(entry.notices.length, "notice")}</span>
                    )}
                    {entry.maneuvers.length > 0 && (
                      <span>{plural(entry.maneuvers.length, "maneuver")}</span>
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
