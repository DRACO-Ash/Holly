import { useEffect, useMemo, useRef, useState } from "react";
import type { ActivityOverview } from "../../types";
import {
  dayHeading,
  groupByDay,
  maneuverStart,
  mostActive,
  type ManeuverGroup,
} from "../../utils/ops";
import ActivityTimeline from "../ops/ActivityTimeline";
import ConsoleHeader from "../ops/ConsoleHeader";
import { type RangeChoice, resolveRange, toggled } from "../ops/consoleFilters";
import FilterChips, { type ActiveFilter } from "../ops/FilterChips";
import { maneuverLanes } from "../ops/lanes";
import ManeuverRow from "../ops/ManeuverRow";
import ObjectBoard from "../ops/ObjectBoard";
import RangeButtons from "../ops/RangeButtons";
import StatTile from "../ops/StatTile";
import Truncation from "../ops/Truncation";
import { useActivity } from "../ops/useActivity";
import { useNow } from "../ops/useNow";
import GeoBelt, { type BeltMark } from "./GeoBelt";
import ManeuverDrawer from "./ManeuverDrawer";
import {
  type LiveFilters,
  type LiveModel,
  applyFilters,
  liveCounts,
  liveModel,
  nameOf,
  noticesFor,
  sourceOf,
} from "./liveModel";

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

function beltMarks(model: LiveModel, groups: readonly ManeuverGroup[]): BeltMark[] {
  const marks: BeltMark[] = [];
  for (const group of groups) {
    const longitude = group.maneuver.facts.post_geo_longitude_deg;
    if (longitude === null) continue;
    marks.push({
      group,
      longitude,
      drift: group.maneuver.facts.post_drift_rate_deg_day,
      slot: model.slots.get(sourceOf(group)) ?? 4,
      source: sourceOf(group),
      label: `${nameOf(model, group.maneuver.sat_no)}, ${sourceOf(group)}, ${longitude.toFixed(2)}°`,
    });
  }
  return marks;
}

interface Choices {
  sources: Set<string>;
  namedOnly: boolean;
  object: string | null;
  text: string;
  range: RangeChoice;
}

const NO_CHOICES: Choices = {
  sources: new Set(),
  namedOnly: false,
  object: null,
  text: "",
  range: null,
};

function activeFilters(
  model: LiveModel,
  choices: Choices,
  set: (next: Partial<Choices>) => void,
): ActiveFilter[] {
  const filters: ActiveFilter[] = [...choices.sources].map((source) => ({
    key: `source-${source}`,
    label: `Source: ${source}`,
    onRemove: () => set({ sources: toggled(choices.sources, source) }),
  }));
  if (choices.namedOnly) {
    filters.push({
      key: "named",
      label: "Named in a notice",
      onRemove: () => set({ namedOnly: false }),
    });
  }
  if (choices.object !== null) {
    filters.push({
      key: "object",
      label: `Satellite: ${nameOf(model, Number(choices.object))}`,
      onRemove: () => set({ object: null }),
    });
  }
  if (choices.range !== null) {
    filters.push({ key: "range", label: "Time range", onRemove: () => set({ range: null }) });
  }
  return filters;
}

function StatBand({
  model,
  choices,
  now,
  set,
}: Readonly<{
  model: LiveModel;
  choices: Choices;
  now: number;
  set: (next: Partial<Choices>) => void;
}>) {
  const counts = liveCounts(model, now);
  return (
    <div className="console-band">
      <StatTile
        count={counts.maneuvers}
        label="Maneuvers"
        tone="accent"
        detail={
          counts.folded > 0 ? `${plural(counts.folded, "duplicate record")} folded` : undefined
        }
      />
      <StatTile count={counts.satellites} label="Satellites" />
      <StatTile count={counts.lastDay} label="Last 24 h" />
      <StatTile
        count={counts.named}
        label="Named in a notice"
        pressed={choices.namedOnly}
        onToggle={() => set({ namedOnly: !choices.namedOnly })}
      />
      {[...model.slots.entries()].map(([source, slot]) => (
        <StatTile
          key={source}
          count={counts.bySource.get(source) ?? 0}
          label={source}
          tone={`source-${slot}`}
          pressed={choices.sources.has(source)}
          onToggle={() => set({ sources: toggled(choices.sources, source) })}
        />
      ))}
    </div>
  );
}

function ManeuverList({
  model,
  groups,
  now,
  openId,
  onToggle,
}: Readonly<{
  model: LiveModel;
  groups: readonly ManeuverGroup[];
  now: number;
  openId: string | null;
  onToggle: (id: string) => void;
}>) {
  if (groups.length === 0) {
    return <p className="console-empty">No maneuvers match. Clear a filter to see more.</p>;
  }
  return (
    <>
      {groupByDay(groups, (g) => maneuverStart(g.maneuver)).map(({ day, items }) => (
        <section key={day ?? "unknown"} className="event-day">
          <h2 className="event-day-heading">
            {day === null ? "Time unknown" : dayHeading(day, now)}
            <span className="event-day-count">{items.length}</span>
          </h2>
          <ul className="event-list">
            {items.map((group) => (
              <ManeuverRow
                key={group.maneuver.id}
                group={group}
                satellite={
                  group.maneuver.sat_no === null
                    ? undefined
                    : model.directory.get(String(group.maneuver.sat_no))
                }
                slot={model.slots.get(sourceOf(group)) ?? 4}
                notices={noticesFor(model, group)}
                now={now}
                open={openId === group.maneuver.id}
                onToggle={() => onToggle(group.maneuver.id)}
              >
                <ManeuverDrawer group={group} notices={noticesFor(model, group)} />
              </ManeuverRow>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

function Console({
  data,
  now,
  choices,
  set,
  openId,
  onOpen,
}: Readonly<{
  data: ActivityOverview;
  now: number;
  choices: Choices;
  set: (next: Partial<Choices>) => void;
  openId: string | null;
  onOpen: (id: string | null) => void;
}>) {
  const model = useMemo(() => liveModel(data, now), [data, now]);
  const range = resolveRange(choices.range, now);
  const filters: LiveFilters = { ...choices, range };
  const shown = applyFilters(model, model.groups, filters);
  const belt = beltMarks(model, shown);
  const scrollTo = useRef<string | null>(null);
  useEffect(() => {
    if (openId === null || scrollTo.current !== openId) return;
    scrollTo.current = null;
    const target = document.getElementById(`maneuver-${openId}`);
    // jsdom and some older browsers have no scrollIntoView: the row still opens.
    if (target && "scrollIntoView" in target) target.scrollIntoView({ block: "center" });
  }, [openId]);
  const pick = (id: string) => {
    scrollTo.current = id;
    onOpen(id);
  };

  return (
    <>
      <Truncation data={data} />
      <StatBand model={model} choices={choices} now={now} set={set} />
      <div className="console-grid">
        <section className="console-panel" aria-labelledby="maneuver-timeline-title">
          <div className="console-panel-head">
            <h2 id="maneuver-timeline-title">Timeline</h2>
            <RangeButtons choice={choices.range} onChoose={(next) => set({ range: next })} />
          </div>
          <ActivityTimeline
            lanes={maneuverLanes(shown, model.slots, (satNo) => nameOf(model, satNo))}
            start={model.start}
            end={model.end}
            now={now}
            title="Maneuvers by provider"
            range={range}
            onRange={(next) => set({ range: next ? { from: next[0], to: next[1] } : null })}
            onPick={pick}
          />
          <p className="console-hint">
            Drag across the timeline to choose a time range; click a mark to open that maneuver.
          </p>
        </section>
        <div className="console-panel">
          <ObjectBoard
            title="Most manoeuvring satellites"
            entries={mostActive([], model.groups, 8)}
            directory={model.directory}
            start={model.start}
            end={model.end}
            selected={choices.object}
            onSelect={(id) => set({ object: id })}
          />
        </div>
      </div>
      {belt.length > 0 && (
        <section className="console-panel console-belt" aria-labelledby="geo-belt-title">
          <h2 id="geo-belt-title">GEO belt</h2>
          <GeoBelt marks={belt} />
          <p className="console-hint">
            Longitude after the burn, from each record&apos;s postGeoLongitude (UDL field, TBC). The
            line shows the direction of the drift and its rough size; drifts above 0.2° a day are
            drawn at the same length. Marks close together are stacked.
          </p>
        </section>
      )}
      <div className="console-filters">
        <label className="console-search">
          Search maneuvers
          <input
            type="search"
            value={choices.text}
            onChange={(e) => set({ text: e.target.value })}
            placeholder="Satellite, name, source or status"
            maxLength={100}
          />
        </label>
        <FilterChips
          filters={activeFilters(model, choices, set)}
          onClear={() => set({ ...NO_CHOICES, text: choices.text })}
        />
      </div>
      <p className="console-count">
        Showing {shown.length} of {plural(model.groups.length, "maneuver")}
      </p>
      <ManeuverList
        model={model}
        groups={shown}
        now={now}
        openId={openId}
        onToggle={(id) => onOpen(openId === id ? null : id)}
      />
    </>
  );
}

// The live window: the maneuvers that started in it, folded, counted, on a timeline by
// provider, the busiest satellites, the GEO belt when records give longitudes, and the list.
export default function ManeuversLive() {
  const { data, error, loading, refreshing, loadedAt, reload } = useActivity();
  const now = useNow();
  const [choices, setChoices] = useState<Choices>(NO_CHOICES);
  const [openId, setOpenId] = useState<string | null>(null);
  const set = (next: Partial<Choices>) => setChoices((current) => ({ ...current, ...next }));

  return (
    <>
      <ConsoleHeader
        eyebrow="Fusion provider detections"
        title="Maneuvers"
        loadedAt={loadedAt}
        refreshing={refreshing}
        now={now}
        actions={
          <button type="button" onClick={reload} disabled={refreshing}>
            Refresh
          </button>
        }
      >
        UDL maneuver records from the fusion providers, for the window. The assistant uses them to
        put NOTSOs for the same satellites in context. Holly folds a provider&apos;s duplicate
        records into one maneuver.
      </ConsoleHeader>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {loading && <p className="muted">Loading the window...</p>}
      {data && (
        <Console
          data={data}
          now={now}
          choices={choices}
          set={set}
          openId={openId}
          onOpen={setOpenId}
        />
      )}
    </>
  );
}
