import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { refreshNotificationsNow } from "../../api/notifications";
import type { ActivityOverview } from "../../types";
import {
  type EventKind,
  KIND_LABELS,
  type Regime,
  type Satellite,
  URGENCY_LABELS,
  type Urgency,
  bySatellite,
  foldDuplicates,
  maneuverSatIds,
  mostActive,
  satelliteDirectory,
  timeOf,
} from "../../utils/ops";
import ActivityTimeline from "../ops/ActivityTimeline";
import ConsoleHeader from "../ops/ConsoleHeader";
import FilterChips, { type ActiveFilter } from "../ops/FilterChips";
import ObjectBoard from "../ops/ObjectBoard";
import RangeButtons from "../ops/RangeButtons";
import Truncation from "../ops/Truncation";
import { type RangeChoice, resolveRange, toggled } from "../ops/consoleFilters";
import { noticeLanesByKind } from "../ops/lanes";
import { useActivity } from "../ops/useActivity";
import { useNow } from "../ops/useNow";
import NoticeBand from "./NoticeBand";
import NoticeList from "./NoticeList";
import { NO_FILTERS, type NoticeFilters, isFiltered, matches, noticeEntry } from "./noticeFilters";

function windowDays(hours: number): string {
  if (hours % 24 !== 0) return `${hours} hours`;
  return hours === 24 ? "day" : `${hours / 24} days`;
}

function pullError(err: unknown): string {
  const detail =
    err && typeof err === "object" && "response" in err
      ? ((err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail ?? null)
      : null;
  return typeof detail === "string" ? detail : "UDL pull failed.";
}

function rangeLabel(range: RangeChoice): string {
  if (range === null) return "";
  return "hours" in range ? `Last ${range.hours} h` : "Dragged time range";
}

function satelliteLabel(id: string, directory: ReadonlyMap<string, Satellite>): string {
  const name = directory.get(id)?.name;
  return name ? `${name} #${id}` : `#${id}`;
}

// The chips for the filters in force, each removing its own filter.
function activeFilters(
  filters: NoticeFilters,
  directory: ReadonlyMap<string, Satellite>,
  set: (change: Partial<NoticeFilters>) => void,
): ActiveFilter[] {
  const chips: ActiveFilter[] = [];
  for (const urgency of filters.urgencies) {
    chips.push({
      key: `u-${urgency}`,
      label: `${URGENCY_LABELS[urgency]} urgency`,
      onRemove: () => set({ urgencies: toggled(filters.urgencies, urgency) }),
    });
  }
  for (const kind of filters.kinds) {
    chips.push({
      key: `k-${kind}`,
      label: KIND_LABELS[kind],
      onRemove: () => set({ kinds: toggled(filters.kinds, kind) }),
    });
  }
  for (const regime of filters.regimes) {
    chips.push({
      key: `r-${regime}`,
      label: regime,
      onRemove: () => set({ regimes: toggled(filters.regimes, regime) }),
    });
  }
  if (filters.satellite !== null) {
    chips.push({
      key: "sat",
      label: satelliteLabel(filters.satellite, directory),
      onRemove: () => set({ satellite: null }),
    });
  }
  if (filters.text.trim() !== "") {
    chips.push({
      key: "text",
      label: `“${filters.text.trim()}”`,
      onRemove: () => set({ text: "" }),
    });
  }
  if (filters.range !== null) {
    chips.push({
      key: "range",
      label: rangeLabel(filters.range),
      onRemove: () => set({ range: null }),
    });
  }
  return chips;
}

function LiveConsole({ data, now }: Readonly<{ data: ActivityOverview; now: number }>) {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<NoticeFilters>(NO_FILTERS);
  const set = (change: Partial<NoticeFilters>) => setFilters((f) => ({ ...f, ...change }));

  const directory = useMemo(
    () => satelliteDirectory(data.notices, data.maneuvers, data.elsets),
    [data],
  );
  const entries = useMemo(
    () => data.notices.map((notice) => noticeEntry(notice, directory)),
    [data, directory],
  );
  const maneuversBySat = useMemo(() => bySatellite(data.maneuvers, maneuverSatIds), [data]);
  const board = useMemo(() => mostActive(data.notices, foldDuplicates(data.maneuvers), 8), [data]);
  const parsedById = useMemo(() => new Map(entries.map((e) => [e.notice.id, e.parsed])), [entries]);

  const shown = entries.filter((entry) => matches(entry, filters, now));
  const start = timeOf(data.window_start) ?? now;
  const end = Math.max(timeOf(data.generated_at) ?? now, now);
  const lanes = noticeLanesByKind(
    shown.map((e) => e.notice),
    (notice) => parsedById.get(notice.id) ?? null,
  );
  const filtered = isFiltered(filters);

  return (
    <>
      <Truncation data={data} />
      <NoticeBand
        entries={entries}
        filters={filters}
        now={now}
        onUrgency={(u: Urgency) => set({ urgencies: toggled(filters.urgencies, u) })}
        onKind={(k: EventKind) => set({ kinds: toggled(filters.kinds, k) })}
        onRegime={(r: Regime) => set({ regimes: toggled(filters.regimes, r) })}
      />
      <div className="console-grid">
        <section className="console-panel" aria-labelledby="notice-timeline-title">
          <div className="console-panel-head">
            <h2 id="notice-timeline-title">Timeline</h2>
            <RangeButtons choice={filters.range} onChoose={(range) => set({ range })} />
          </div>
          <ActivityTimeline
            lanes={lanes}
            start={start}
            end={end}
            now={now}
            title="Notices in the window by kind"
            range={resolveRange(filters.range, now)}
            onRange={(range) => set({ range: range ? { from: range[0], to: range[1] } : null })}
            onPick={(id) => {
              void navigate(`/notifications/${id}`);
            }}
          />
          <p className="console-hint">Drag across the timeline to filter to a time range.</p>
        </section>
        <div className="console-panel">
          <ObjectBoard
            title="Most active satellites"
            entries={board}
            directory={directory}
            start={start}
            end={end}
            selected={filters.satellite}
            onSelect={(satellite) => set({ satellite })}
          />
        </div>
      </div>
      <div className="console-filters">
        <label className="console-search">
          Search notices
          <input
            type="search"
            value={filters.text}
            maxLength={100}
            placeholder="Name, number or notice"
            onChange={(e) => set({ text: e.target.value })}
          />
        </label>
        <FilterChips
          filters={activeFilters(filters, directory, set)}
          onClear={() => setFilters(NO_FILTERS)}
        />
      </div>
      <p className="console-count">
        Showing {shown.length} of {entries.length} notices
      </p>
      <NoticeList
        entries={shown}
        filtered={filtered}
        directory={directory}
        maneuversBySat={maneuversBySat}
        now={now}
        onClear={() => setFilters(NO_FILTERS)}
      />
    </>
  );
}

// The live window: every notice of the last days in counts, on a timeline, by satellite and as a
// list, with the maneuvers on the satellites each names.
export default function NotificationsLive() {
  const activity = useActivity();
  const now = useNow();
  const [pulling, setPulling] = useState(false);
  const [pullFailure, setPullFailure] = useState<string | null>(null);

  async function onPull() {
    setPulling(true);
    setPullFailure(null);
    try {
      await refreshNotificationsNow();
      activity.reload();
    } catch (error) {
      setPullFailure(pullError(error));
    } finally {
      setPulling(false);
    }
  }

  const hours = activity.data?.window_hours ?? 120;
  return (
    <>
      <ConsoleHeader
        eyebrow="Notices to space operators"
        title="Notifications"
        loadedAt={activity.loadedAt}
        refreshing={activity.refreshing}
        now={now}
        actions={
          <>
            <button type="button" onClick={activity.reload} disabled={activity.refreshing}>
              Refresh
            </button>
            <button type="button" onClick={() => void onPull()} disabled={pulling}>
              {pulling ? "Pulling..." : "Pull from UDL"}
            </button>
          </>
        }
      >
        The last {windowDays(hours)} of TACREP_NOTSOs from UDL, refreshed hourly in the background.
        The assistant analyses each new notice against your procedures as it arrives.
      </ConsoleHeader>
      {pullFailure && (
        <div className="form-error" role="alert">
          {pullFailure}
        </div>
      )}
      {activity.error && (
        <div className="form-error" role="alert">
          {activity.error}
        </div>
      )}
      {activity.loading && <p className="muted">Loading the window...</p>}
      {activity.data && <LiveConsole data={activity.data} now={now} />}
    </>
  );
}
