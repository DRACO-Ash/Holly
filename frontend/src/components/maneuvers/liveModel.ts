// The live Maneuvers view's reading of the activity overview: the maneuvers folded, each
// satellite's name and notices, the providers' hue slots, and the filters applied.
import type { ActivityNotice, ActivityOverview } from "../../types";
import {
  type ManeuverGroup,
  type Satellite,
  bySatellite,
  foldDuplicates,
  maneuverStart,
  noticeSatIds,
  satelliteDirectory,
  searchText,
  sourceSlots,
  timeOf,
} from "../../utils/ops";
import type { TimeRange } from "../ops/ActivityTimeline";
import { inRange } from "../ops/consoleFilters";

export const SLOTS = 4;
const DAY = 86_400_000;

export interface LiveModel {
  groups: ManeuverGroup[];
  directory: Map<string, Satellite>;
  noticesBySat: Map<string, ActivityNotice[]>;
  slots: Map<string, number>;
  start: number;
  end: number;
}

export function liveModel(data: ActivityOverview, now: number): LiveModel {
  const start = timeOf(data.window_start) ?? now - data.window_hours * 3_600_000;
  return {
    groups: foldDuplicates(data.maneuvers),
    directory: satelliteDirectory(data.notices, data.maneuvers, data.elsets),
    noticesBySat: bySatellite(data.notices, noticeSatIds),
    slots: sourceSlots(
      data.maneuvers.map((m) => m.source),
      SLOTS,
    ),
    start,
    end: Math.max(now, timeOf(data.generated_at) ?? now),
  };
}

export const sourceOf = (group: ManeuverGroup) => group.maneuver.source ?? "Unknown";
export const satIdOf = (group: ManeuverGroup) =>
  group.maneuver.sat_no === null ? null : String(group.maneuver.sat_no);

export function noticesFor(model: LiveModel, group: ManeuverGroup): ActivityNotice[] {
  const id = satIdOf(group);
  return id === null ? [] : (model.noticesBySat.get(id) ?? []);
}

export function nameOf(model: LiveModel, satNo: number | null): string {
  if (satNo === null) return "Unidentified object";
  return model.directory.get(String(satNo))?.name ?? `#${satNo}`;
}

export interface LiveFilters {
  sources: ReadonlySet<string>;
  namedOnly: boolean;
  object: string | null;
  text: string;
  range: TimeRange | null;
}

function matchesText(model: LiveModel, group: ManeuverGroup, needle: string): boolean {
  if (needle === "") return true;
  const m = group.maneuver;
  const id = satIdOf(group);
  const name = id === null ? null : model.directory.get(id)?.name;
  return searchText([
    m.sat_no,
    name,
    m.source,
    m.facts.status,
    m.maneuver_status,
    m.facts.characterization,
    m.mnvr_type,
  ]).includes(needle);
}

export function applyFilters(
  model: LiveModel,
  groups: readonly ManeuverGroup[],
  filters: LiveFilters,
): ManeuverGroup[] {
  const needle = filters.text.trim().toLowerCase();
  return groups.filter(
    (group) =>
      (filters.sources.size === 0 || filters.sources.has(sourceOf(group))) &&
      (!filters.namedOnly || noticesFor(model, group).length > 0) &&
      (filters.object === null || satIdOf(group) === filters.object) &&
      inRange(maneuverStart(group.maneuver), filters.range) &&
      matchesText(model, group, needle),
  );
}

export interface LiveCounts {
  maneuvers: number;
  folded: number;
  satellites: number;
  lastDay: number;
  named: number;
  bySource: Map<string, number>;
}

export function liveCounts(model: LiveModel, now: number): LiveCounts {
  const bySource = new Map<string, number>();
  const satellites = new Set<string>();
  let folded = 0;
  let lastDay = 0;
  let named = 0;
  for (const group of model.groups) {
    folded += group.copies - 1;
    const id = satIdOf(group);
    if (id !== null) satellites.add(id);
    const start = maneuverStart(group.maneuver);
    if (start !== null && start >= now - DAY) lastDay += 1;
    if (noticesFor(model, group).length > 0) named += 1;
    bySource.set(sourceOf(group), (bySource.get(sourceOf(group)) ?? 0) + 1);
  }
  return {
    maneuvers: model.groups.length,
    folded,
    satellites: satellites.size,
    lastDay,
    named,
    bySource,
  };
}
