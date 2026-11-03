import { useCallback, useEffect, useMemo, useState } from "react";
import { getFeed } from "../api/assistant";
import DashboardBand, { type ActivityCounts } from "../components/dashboard/DashboardBand";
import DashboardTimeline from "../components/dashboard/DashboardTimeline";
import FeedItem from "../components/dashboard/FeedItem";
import { feedBuckets, formatWindow, keepItem } from "../components/dashboard/feed";
import ConsoleHeader from "../components/ops/ConsoleHeader";
import { type RangeChoice, resolveRange, toggled } from "../components/ops/consoleFilters";
import FilterChips, { type ActiveFilter } from "../components/ops/FilterChips";
import ObjectBoard from "../components/ops/ObjectBoard";
import Truncation from "../components/ops/Truncation";
import { useActivity } from "../components/ops/useActivity";
import { useNow } from "../components/ops/useNow";
import type { ActivityOverview, AssistantFeedItem } from "../types";
import { extractErrorMessage } from "../utils/errors";
import {
  type ManeuverGroup,
  URGENCY_LABELS,
  URGENCY_ORDER,
  type Urgency,
  bySatellite,
  foldDuplicates,
  maneuverSatIds,
  maneuverStart,
  mostActive,
  satelliteDirectory,
  timeOf,
} from "../utils/ops";

const REFRESH_INTERVAL_MS = 60_000;
const DAY = 86_400_000;
const BOARD_SIZE = 8;

// The feed's groups, most urgent first, with the notices still awaiting analysis before those
// the assistant found nothing to do about.
const BUCKET_ORDER: readonly Urgency[] = ["high", "medium", "low", "pending", "none"];

const BUCKET_TITLES: Readonly<Record<Urgency, string>> = {
  ...URGENCY_LABELS,
  none: "Informational",
};

function urgencyClass(urgency: Urgency): string {
  return urgency === "none" ? "urgency-pill" : `urgency-pill urgency-${urgency}`;
}

function activityCounts(
  data: ActivityOverview,
  groups: readonly ManeuverGroup[],
  satellites: number,
  now: number,
): ActivityCounts {
  const since = now - DAY;
  const recent = (time: number | null) => time !== null && time >= since;
  return {
    notices24h: data.notices.filter((n) => recent(timeOf(n.udl_created_at))).length,
    maneuvers24h: groups.filter((g) => recent(maneuverStart(g.maneuver))).length,
    satellites,
  };
}

// The filters in force, each with what removes it.
function activeFilters(state: {
  urgencies: ReadonlySet<Urgency>;
  rangeChoice: RangeChoice;
  satellite: string | null;
  satelliteName: string | null;
  setUrgencies: (update: (set: ReadonlySet<Urgency>) => ReadonlySet<Urgency>) => void;
  setRangeChoice: (choice: RangeChoice) => void;
  setSatellite: (id: string | null) => void;
}): ActiveFilter[] {
  const filters: ActiveFilter[] = [...state.urgencies].map((u) => ({
    key: `urgency-${u}`,
    label: URGENCY_LABELS[u],
    onRemove: () => state.setUrgencies((set) => toggled(set, u)),
  }));
  if (state.rangeChoice !== null) {
    filters.push({ key: "range", label: "Time range", onRemove: () => state.setRangeChoice(null) });
  }
  if (state.satellite !== null) {
    filters.push({
      key: "satellite",
      label: state.satelliteName ?? `#${state.satellite}`,
      onRemove: () => state.setSatellite(null),
    });
  }
  return filters;
}

// The assistant feed, loaded now and every minute, and on request.
function useFeed() {
  const [items, setItems] = useState<AssistantFeedItem[]>([]);
  const [windowHours, setWindowHours] = useState(120);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  const load = useCallback(async (first: boolean) => {
    if (first) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const data = await getFeed();
      setItems(data.items);
      setWindowHours(data.window_hours);
      setLoadedAt(Date.now());
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load the assistant feed."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => load(false), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  return { items, windowHours, loading, refreshing, error, loadedAt, load };
}

export default function Dashboard() {
  const feed = useFeed();
  const activity = useActivity();
  const now = useNow();
  const [urgencies, setUrgencies] = useState<ReadonlySet<Urgency>>(new Set());
  const [rangeChoice, setRangeChoice] = useState<RangeChoice>(null);
  const [satellite, setSatellite] = useState<string | null>(null);

  const data = activity.data;
  const groups = useMemo(() => foldDuplicates(data?.maneuvers ?? []), [data]);
  const directory = useMemo(
    () => satelliteDirectory(data?.notices ?? [], data?.maneuvers ?? [], data?.elsets ?? []),
    [data],
  );
  const maneuversBySat = useMemo(() => bySatellite(data?.maneuvers ?? [], maneuverSatIds), [data]);
  const board = useMemo(() => mostActive(data?.notices ?? [], groups, BOARD_SIZE), [data, groups]);

  if (feed.loading) {
    return (
      <div>
        <h1>Dashboard</h1>
        <p>Loading assistant feed...</p>
      </div>
    );
  }

  const range = resolveRange(rangeChoice, now);
  const shown = feed.items.filter((item) => keepItem(item, { urgencies, range, satellite }));
  const allBuckets = feedBuckets(feed.items);
  const counts = new Map(URGENCY_ORDER.map((u) => [u, allBuckets.get(u)?.length ?? 0]));
  const buckets = feedBuckets(shown);
  const windowText = formatWindow(feed.windowHours);

  const filters = activeFilters({
    urgencies,
    rangeChoice,
    satellite,
    satelliteName: satellite === null ? null : (directory.get(satellite)?.name ?? null),
    setUrgencies,
    setRangeChoice,
    setSatellite,
  });
  const clearAll = () => {
    setUrgencies(new Set());
    setRangeChoice(null);
    setSatellite(null);
  };
  const refresh = () => {
    feed.load(false);
    activity.reload();
  };

  return (
    <div>
      <ConsoleHeader
        eyebrow="Watch floor"
        title="What needs your attention"
        loadedAt={feed.loadedAt}
        refreshing={feed.refreshing}
        now={now}
        actions={
          <button type="button" onClick={refresh} disabled={feed.refreshing}>
            {feed.refreshing ? "Refreshing..." : "Refresh"}
          </button>
        }
      >
        Last {windowText} of TACREP_NOTSOs, evaluated against your uploaded procedures. Most urgent
        first.
      </ConsoleHeader>

      {feed.error && <div className="form-error">{feed.error}</div>}
      {activity.error && (
        <p className="console-truncated">
          The activity overview could not be loaded, so the timeline and the satellites are missing:{" "}
          {activity.error}
        </p>
      )}
      {data && <Truncation data={data} />}

      <DashboardBand
        counts={counts}
        activity={data ? activityCounts(data, groups, directory.size, now) : null}
        selected={urgencies}
        onToggle={(u) => setUrgencies((set) => toggled(set, u))}
      />

      {data && (
        <div className="console-grid">
          <DashboardTimeline
            data={data}
            groups={groups}
            now={now}
            choice={rangeChoice}
            onChoose={setRangeChoice}
          />
          <div className="console-panel">
            <ObjectBoard
              title="Most active satellites"
              entries={board}
              directory={directory}
              start={Date.parse(data.window_start)}
              end={Math.max(now, Date.parse(data.generated_at))}
              selected={satellite}
              onSelect={setSatellite}
            />
          </div>
        </div>
      )}

      <div className="console-filters">
        <FilterChips filters={filters} onClear={clearAll} />
      </div>

      {feed.items.length === 0 && (
        <section className="card">
          <p>
            No NOTSOs in the last {windowText}. When new ones arrive they'll appear here
            automatically.
          </p>
        </section>
      )}
      {feed.items.length > 0 && shown.length === 0 && (
        <p className="console-empty">No notice in the feed matches these filters.</p>
      )}
      {shown.length > 0 && (
        <section className="card" aria-label="Assistant feed">
          {BUCKET_ORDER.map((bucket) => {
            const rows = buckets.get(bucket) ?? [];
            if (rows.length === 0) return null;
            return (
              <div key={bucket} className="dashboard-bucket">
                <h2>
                  <span className={urgencyClass(bucket)}>{BUCKET_TITLES[bucket]}</span>
                  <span className="bucket-count">{rows.length}</span>
                </h2>
                <ul className="event-list">
                  {rows.map((item) => (
                    <FeedItem
                      key={item.notification.id}
                      item={item}
                      bucket={bucket}
                      directory={directory}
                      maneuversBySat={maneuversBySat}
                      now={now}
                    />
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
