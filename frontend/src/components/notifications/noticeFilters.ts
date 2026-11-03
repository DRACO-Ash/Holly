// The live Notifications view's reading of the window: each notice with what the filters test,
// and the filters themselves.
import type { ActivityNotice } from "../../types";
import { type RangeChoice, inRange, resolveRange } from "../ops/consoleFilters";
import {
  type EventKind,
  type ParsedEvent,
  type Regime,
  type Satellite,
  type Urgency,
  parseEventClass,
  searchText,
  timeOf,
  urgencyOf,
} from "../../utils/ops";

export interface NoticeEntry {
  notice: ActivityNotice;
  parsed: ParsedEvent | null;
  kind: EventKind;
  urgency: Urgency;
  regime: Regime | null;
  time: number | null;
  text: string;
}

export interface NoticeFilters {
  urgencies: ReadonlySet<Urgency>;
  kinds: ReadonlySet<EventKind>;
  regimes: ReadonlySet<Regime>;
  satellite: string | null;
  text: string;
  range: RangeChoice;
}

export const NO_FILTERS: NoticeFilters = {
  urgencies: new Set(),
  kinds: new Set(),
  regimes: new Set(),
  satellite: null,
  text: "",
  range: null,
};

export function isFiltered(filters: NoticeFilters): boolean {
  return (
    filters.urgencies.size > 0 ||
    filters.kinds.size > 0 ||
    filters.regimes.size > 0 ||
    filters.satellite !== null ||
    filters.text.trim() !== "" ||
    filters.range !== null
  );
}

export function noticeEntry(
  notice: ActivityNotice,
  directory: ReadonlyMap<string, Satellite>,
): NoticeEntry {
  const parsed = parseEventClass(notice.event_class);
  const first = parsed?.objects.find((o) => o.id)?.id ?? notice.sat_ids[0];
  const names = notice.sat_ids.map((id) => directory.get(id)?.name);
  return {
    notice,
    parsed,
    kind: parsed?.kind ?? "other",
    urgency: urgencyOf(notice.urgency),
    regime: parsed?.regime ?? (first ? (directory.get(first)?.regime ?? null) : null),
    time: timeOf(notice.udl_created_at),
    text: searchText([notice.notice, notice.event_class, ...notice.sat_ids, ...names]),
  };
}

const passes = <T>(set: ReadonlySet<T>, value: T | null) =>
  set.size === 0 || (value !== null && set.has(value));

export function matches(entry: NoticeEntry, filters: NoticeFilters, now: number): boolean {
  const needle = filters.text.trim().toLowerCase();
  return (
    passes(filters.urgencies, entry.urgency) &&
    passes(filters.kinds, entry.kind) &&
    passes(filters.regimes, entry.regime) &&
    (filters.satellite === null || entry.notice.sat_ids.includes(filters.satellite)) &&
    (needle === "" || entry.text.includes(needle)) &&
    inRange(entry.time, resolveRange(filters.range, now))
  );
}

// How many entries have each value of `key`, in the order the values first appear.
export function countBy<K>(entries: readonly NoticeEntry[], key: (e: NoticeEntry) => K | null) {
  const counts = new Map<K, number>();
  for (const entry of entries) {
    const value = key(entry);
    if (value !== null) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}
