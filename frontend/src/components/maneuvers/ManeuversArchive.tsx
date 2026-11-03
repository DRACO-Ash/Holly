import { type FormEvent, useEffect, useState } from "react";
import { listManeuvers } from "../../api/maneuvers";
import type { Maneuver, ManeuverSortColumn, SortDirection } from "../../types";
import { extractErrorMessage } from "../../utils/errors";
import { fullUtc, timeOf } from "../../utils/ops";
import SortableHeader from "../SortableHeader";

const PAGE_SIZE = 50;

function formatTime(value: string | null): string {
  const time = timeOf(value);
  return time === null ? "n/a" : fullUtc(time);
}

// Delta-v in m/s: the UDL km/s figure when the record carries one, else the typed column.
function formatDeltaV(m: Maneuver): string {
  const dv = m.facts.delta_vel_kms === null ? m.delta_v : m.facts.delta_vel_kms * 1000;
  return dv === null ? "n/a" : dv.toFixed(3);
}

// Every stored maneuver, all time, a page at a time, filtered and sorted on the server.
export default function ManeuversArchive() {
  const [items, setItems] = useState<Maneuver[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [satNoFilter, setSatNoFilter] = useState<number | undefined>(undefined);
  const [satNoInput, setSatNoInput] = useState("");
  const [sortColumn, setSortColumn] = useState<ManeuverSortColumn>("event_start_time");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [reloadToken, setReloadToken] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listManeuvers({
      sat_no: satNoFilter,
      limit: PAGE_SIZE,
      offset,
      sort_by: sortColumn,
      sort_dir: sortDirection,
    })
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load maneuvers."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [satNoFilter, offset, sortColumn, sortDirection, reloadToken]);

  function onSortChange(column: ManeuverSortColumn) {
    if (column === sortColumn) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDirection("desc");
    }
    setOffset(0);
  }

  function onFilterSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = satNoInput.trim();
    if (trimmed === "") {
      setSatNoFilter(undefined);
    } else {
      const parsed = Number(trimmed);
      if (!Number.isInteger(parsed)) {
        setError("Satellite number must be a whole number.");
        return;
      }
      setSatNoFilter(parsed);
    }
    setOffset(0);
  }

  const header = (column: ManeuverSortColumn, label: string) => (
    <SortableHeader
      column={column}
      label={label}
      activeColumn={sortColumn}
      activeDirection={sortDirection}
      onChange={onSortChange}
    />
  );
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="card">
      <h2>Full archive</h2>
      <p className="muted-paragraph">
        Every maneuver record Holly holds, all time, as each provider published it: duplicates are
        not folded here.
      </p>
      <form onSubmit={onFilterSubmit} className="filter-form">
        <label>
          Satellite number{" "}
          <input
            type="number"
            value={satNoInput}
            onChange={(e) => setSatNoInput(e.target.value)}
            placeholder="e.g. 25544"
          />
        </label>
        <button type="submit">Apply</button>
        <button
          type="button"
          onClick={() => {
            setSatNoInput("");
            setSatNoFilter(undefined);
            setOffset(0);
          }}
        >
          Clear
        </button>
        <button type="button" onClick={() => setReloadToken((t) => t + 1)}>
          Refresh
        </button>
      </form>

      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {loading && <p className="muted">Loading...</p>}

      <table className="elsets-table">
        <thead>
          <tr>
            {header("sat_no", "Sat No")}
            {header("event_start_time", "Start")}
            {header("event_stop_time", "End")}
            <th>Status</th>
            <th>Δv (m/s)</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.id}>
              <td>{m.sat_no ?? "n/a"}</td>
              <td>{formatTime(m.event_start_time)}</td>
              <td>{formatTime(m.event_stop_time ?? m.facts.event_end_time)}</td>
              <td>{m.facts.status ?? m.maneuver_status ?? "n/a"}</td>
              <td>{formatDeltaV(m)}</td>
              <td>{m.source ?? "n/a"}</td>
            </tr>
          ))}
          {!loading && items.length === 0 && (
            <tr>
              <td colSpan={6}>No maneuvers to show.</td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="pagination">
        <span>
          {total} total &middot; page {currentPage} of {totalPages}
        </span>
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          Previous
        </button>
        <button
          type="button"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
